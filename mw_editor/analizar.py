"""F1 Medición: mide vídeo y audio y deja las decisiones en números, no en adjetivos."""
import json
import re
import statistics
from pathlib import Path

import cv2

from .common import FFMPEG, log, probe, run


def _loudnorm_medir(src, ss=None, t=None):
    pre = []
    if ss is not None:
        pre += ["-ss", str(ss)]
    if t is not None:
        pre += ["-t", str(t)]
    p = run([FFMPEG, "-hide_banner", "-v", "info", *pre, "-i", src, "-vn", "-af",
             "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    return json.loads(m.group(0)) if m else {}


def medir_audio(src, dur):
    """LUFS, LRA, pico verdadero, suelo de ruido y silencios. Mide sobre un máximo de 10 min para ir rápido."""
    t = min(dur, 600)
    ln = _loudnorm_medir(src, t=t)
    # suelo de ruido: astats por ventanas de 0,5 s; el suelo = percentil 10 del RMS por ventana
    p = run([FFMPEG, "-hide_banner", "-v", "error", "-t", str(t), "-i", src, "-vn", "-af",
             "aresample=16000,astats=metadata=1:reset=1:length=0.5,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"], check=False)
    niveles = [float(x) for x in re.findall(r"RMS_level=(-?\d+\.?\d*|-inf)", p.stdout) if x != "-inf"]
    niveles.sort()
    suelo = niveles[int(len(niveles) * 0.10)] if niveles else None
    voz = niveles[int(len(niveles) * 0.90)] if niveles else None
    s = run([FFMPEG, "-hide_banner", "-v", "info", "-t", str(t), "-i", src, "-vn", "-af",
             "silencedetect=n=-38dB:d=0.5", "-f", "null", "-"], check=False)
    sil = len(re.findall(r"silence_start", s.stderr))
    return {
        "lufs": float(ln.get("input_i", "nan")) if ln else None,
        "lra": float(ln.get("input_lra", "nan")) if ln else None,
        "pico_verdadero_dbtp": float(ln.get("input_tp", "nan")) if ln else None,
        "suelo_ruido_db": suelo,
        "nivel_voz_db": voz,
        "snr_aprox_db": (voz - suelo) if (voz is not None and suelo is not None) else None,
        "silencios_mayores_0_5s": sil,
        "muestra_s": t,
    }


def medir_video(src, dur, carpeta_frames):
    """Exposición global y de la zona de la cara (centro), saturación, nitidez (varianza del Laplaciano)."""
    carpeta_frames = Path(carpeta_frames)
    carpeta_frames.mkdir(parents=True, exist_ok=True)
    n = 12
    ys, yc, yminc, ymaxc, sat, lap, blown = [], [], [], [], [], [], []
    for i in range(n):
        t = dur * (i + 0.5) / n
        out = carpeta_frames / f"ref_{i:02d}_{int(t):05d}s.jpg"
        run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-q:v", "2", out], check=False)
        img = cv2.imread(str(out))
        if img is None:
            continue
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        cx = gray[int(h * 0.1):int(h * 0.6), int(w * 0.30):int(w * 0.70)]
        ys.append(float(gray.mean()))
        yc.append(float(cx.mean()))
        yminc.append(float(cx.min()))
        ymaxc.append(float(cx.max()))
        sat.append(float(hsv[:, :, 1].mean()))
        lap.append(float(cv2.Laplacian(cx, cv2.CV_64F).var()))
        blown.append(float((gray >= 250).mean()))
    if not ys:
        return {}
    med = statistics.median
    return {
        "exposicion_global_0_255": round(med(ys), 1),
        "exposicion_zona_cara_0_255": round(med(yc), 1),
        "negro_zona_cara": round(med(yminc), 1),
        "blanco_zona_cara": round(med(ymaxc), 1),
        "saturacion_media": round(med(sat), 1),
        "nitidez_laplaciano_cara": round(med(lap), 1),
        "altas_luces_quemadas_pct": round(100 * med(blown), 2),
        "frames_ref": str(carpeta_frames),
    }


def analizar(src, carpeta_docs):
    """Devuelve y guarda analisis.json. Incluye 'diagnostico': lo que se puede y no se puede arreglar."""
    carpeta_docs = Path(carpeta_docs)
    carpeta_docs.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    log("medición de audio ...")
    aud = medir_audio(src, info["duracion"]) if info.get("tiene_audio") else {}
    log("medición de imagen ...")
    vid = medir_video(src, info["duracion"], carpeta_docs / "frames_ref")
    diag, no_arreglable = [], []
    if aud:
        if aud.get("suelo_ruido_db") is not None and aud["suelo_ruido_db"] > -50:
            diag.append(f"ruido de fondo alto (suelo {aud['suelo_ruido_db']:.0f} dB): reducir ruido")
        if aud.get("pico_verdadero_dbtp") is not None and aud["pico_verdadero_dbtp"] > -0.5:
            no_arreglable.append("posible clipping en origen: se limita pero no se reconstruye la onda")
        if aud.get("lufs") is not None and abs(aud["lufs"] + 14) > 3:
            diag.append(f"nivel {aud['lufs']:.1f} LUFS: normalizar a -14")
    if vid:
        if vid["exposicion_zona_cara_0_255"] < 95:
            diag.append(f"cara subexpuesta ({vid['exposicion_zona_cara_0_255']}/255): levantar medios")
        if vid["altas_luces_quemadas_pct"] > 2.0:
            no_arreglable.append(f"{vid['altas_luces_quemadas_pct']}% de píxeles quemados: lo quemado no se recupera en post")
        if vid["nitidez_laplaciano_cara"] < 40:
            diag.append("imagen blanda: candidato a upscaling (Real-ESRGAN, BSD-3)")
    if info.get("bitrate", 0) and info["bitrate"] < 1_500_000:
        no_arreglable.append(f"bitrate de origen bajo ({info['bitrate']/1000:.0f} kbps): los bloques de compresión no se arreglan")
    res = {"origen": str(src), "info": info, "audio": aud, "video": vid, "diagnostico": diag, "no_se_puede_arreglar": no_arreglable}
    (carpeta_docs / "analisis.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log("analisis.json listo")
    return res
