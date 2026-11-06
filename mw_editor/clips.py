"""Selección de reels/shorts a partir de un master largo (sin APIs de pago; solo transcripción local + señales medidas).

Ventanas de min..max segundos que empiezan en inicio de frase y terminan en fin de frase (no se corta a mitad de frase).
Puntuación 0-100 = 0.35 gancho + 0.25 densidad + 0.20 claridad de audio + 0.15 presencia de cara + 0.05 ajuste de duración.
  gancho   : primeros 3 s -> pregunta, cifra, contraste, afirmación fuerte, frase corta; penaliza saludos/muletillas.
  densidad : ritmo de palabras (2.3-3.3 pal/s ideal), conceptos únicos por segundo, cifras y nombres propios; penaliza silencios.
  claridad : relación señal/ruido local (percentil 90 vs 10 del nivel), nivel de voz, recortes y confianza media de Whisper.
  cara     : fracción de muestras (1 cada 2 s) con cara detectada (YuNet, MIT).
El master NUNCA se modifica: extraer() hace una copia recortada con ffmpeg -ss/-t."""
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .common import FFMPEG, ROOT, log
from .capitulos import STOP, _limpia, frases

INTERROG = re.compile(r"^(¿|qu[eé]\b|c[oó]mo\b|por qu[eé]\b|cu[aá]ndo\b|cu[aá]nt[oa]s?\b|qui[eé]n(es)?\b|d[oó]nde\b|cu[aá]l(es)?\b|sab[ií]as\b|y si\b|what\b|why\b|how\b|who\b)", re.I)
CIFRA = re.compile(r"\d|%|\$|\b(mill[oó]n|millones|mil|cien|ciento|billones?|miles|por ciento|porcentaje|doble|triple|mitad)\b", re.I)
CONTRASTE = re.compile(r"\b(pero|sin embargo|aunque|en cambio|al rev[eé]s|contrario|sino|mito|mentira|en realidad|paradoja|no es|ya no|dej[oó] de)\b", re.I)
FUERTE = re.compile(r"\b(nunca|jam[aá]s|siempre|nadie|todos|ninguno|secreto|verdad|clave|error|peor|mejor|incre[ií]ble|ojo|cuidado|imposible|evita|deja de|no hagas|ganar|perder|riesgo|quiebra|burbuja|crisis|nobody|never|always|secret|mistake|truth)\b", re.I)
RELLENO_INICIO = {"hola", "bueno", "pues", "eh", "este", "entonces", "ok", "gracias", "vale", "mira", "y", "o", "osea", "a", "bienvenidos"}


# ---------- señales de audio y cara ----------
def audio_features(video, paso=0.5):
    """Nivel RMS en dBFS y fracción de muestras recortadas por tramo de `paso` s (una sola pasada de ffmpeg, en streaming)."""
    sr = 16000
    n = int(sr * paso)
    p = subprocess.Popen([FFMPEG, "-hide_banner", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    db, clip, resto = [], [], b""
    while True:
        buf = p.stdout.read(n * 4 * 400)
        if not buf:
            break
        buf = resto + buf
        k = len(buf) // (n * 4)
        resto = buf[k * n * 4:]
        if k:
            x = np.frombuffer(buf[:k * n * 4], dtype=np.float32).reshape(k, n)
            db.extend((20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-9)).tolist())
            clip.extend((np.abs(x) > 0.985).mean(axis=1).tolist())
    p.wait()
    return {"paso": paso, "db": np.array(db), "clip": np.array(clip)}


def face_features(video, paso=2.0, ancho=480):
    """1 fotograma cada `paso` s -> [presencia 0/1, área relativa de la cara más grande]. Una sola pasada de ffmpeg."""
    modelo = ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(video)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.search(r"(\d{2,5})x(\d{2,5})", info.split("Video:")[-1]) if "Video:" in info else None
    if not m or not modelo.exists():
        return None
    w0, h0 = int(m.group(1)), int(m.group(2))
    rot = re.search(r"rotate\s*:\s*(\d+)", info)
    if rot and int(rot.group(1)) in (90, 270):
        w0, h0 = h0, w0
    h = int(round(ancho * h0 / w0 / 2) * 2)
    det = cv2.FaceDetectorYN.create(str(modelo), "", (ancho, h), 0.8, 0.3, 5000)
    p = subprocess.Popen([FFMPEG, "-hide_banner", "-v", "error", "-i", str(video), "-an", "-vf", f"fps=1/{paso},scale={ancho}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    fs = ancho * h * 3
    pres, area = [], []
    while True:
        buf = p.stdout.read(fs)
        if len(buf) < fs:
            break
        img = np.frombuffer(buf, np.uint8).reshape(h, ancho, 3)
        _, caras = det.detect(img)
        if caras is None or not len(caras):
            pres.append(0)
            area.append(0.0)
        else:
            c = max(caras, key=lambda c: c[2] * c[3])
            a_rel = float(c[2] * c[3]) / (ancho * h)
            # Una cara pequeña (< 3 % del cuadro) es un recuadro de pantalla compartida/PiP, no un plano de presentador:
            # no cuenta como 'presencia' para elegir reels (si no, salen reels con la cara en una esquina y un gráfico al lado).
            pres.append(1 if a_rel >= 0.03 else 0)
            area.append(a_rel)
    p.wait()
    return {"paso": paso, "presencia": np.array(pres), "area": np.array(area)}


# ---------- puntuación ----------
def _gancho(palabras, i0, ini):
    """Puntúa los primeros 3 s del tramo. Devuelve (0-100, [motivos])."""
    txt_w = [w for w in palabras[i0:i0 + 40] if w["s"] < ini + 3.0]
    if not txt_w:
        return 0.0, []
    txt = " ".join(w["w"] for w in txt_w)
    bajo = txt.lower()
    pts, mot = 0.0, []
    if "?" in txt or INTERROG.search(bajo):
        pts += 35
        mot.append("pregunta")
    if CIFRA.search(bajo):
        pts += 40
        mot.append("cifra")
    if CONTRASTE.search(bajo):
        pts += 30
        mot.append("contraste")
    if FUERTE.search(bajo):
        pts += 30
        mot.append("afirmación fuerte")
    if len(txt_w) <= 9:
        pts += 10
        mot.append("frase corta")
    primera = _limpia(txt_w[0]["w"])
    if primera in RELLENO_INICIO:
        pts -= 25
        mot.append("(arranca con muletilla/saludo)")
    cont = [_limpia(w["w"]) for w in txt_w]
    if sum(1 for c in cont if c in STOP) > 0.7 * len(cont):
        pts -= 10
    return max(0.0, min(100.0, pts)), mot


def _tri(x, a, b, c, d):
    """Trapecio: 0 en a, 1 entre b y c, 0 en d."""
    if x <= a or x >= d:
        return 0.0
    if x < b:
        return (x - a) / (b - a)
    if x <= c:
        return 1.0
    return (d - x) / (d - c)


def puntuar(palabras, video=None, dur=None, n=5, min_s=20.0, max_s=90.0, solape_min=2.0, audio=None, cara=None, verbose=True):
    """Devuelve el top-n de ventanas [{ini, fin, dur, puntuacion, componentes, motivo, texto}] sin solaparse."""
    if not palabras:
        return []
    dur = dur or palabras[-1]["e"]
    fr = frases(palabras, pausa=0.6)
    if audio is None and video:
        log("clips: midiendo audio ...")
        audio = audio_features(video)
    if cara is None and video:
        log("clips: detectando caras ...")
        cara = face_features(video)
    db = audio["db"] if audio is not None else None
    cand = []
    for a in range(len(fr)):
        i0 = fr[a]["i0"]
        t0 = palabras[i0]["s"]
        g, mg = _gancho(palabras, i0, t0)
        for b in range(a, len(fr)):
            t1 = fr[b]["e"]
            d = t1 - t0
            if d > max_s:
                break
            if d < min_s:
                continue
            i1 = fr[b]["i1"]
            ws = palabras[i0:i1 + 1]
            # densidad
            ritmo = len(ws) / d
            cont = [c for c in (_limpia(w["w"]) for w in ws) if len(c) >= 4 and c not in STOP]
            unicos = len(set(c[:6] for c in cont)) / d
            ent = sum(1 for w in ws if re.search(r"\d", w["w"])) + sum(1 for k, w in enumerate(ws[1:], 1) if w["w"][:1].isupper() and not re.search(r"[.?!]$", ws[k - 1]["w"]))
            ent_s = min(1.0, (ent / d) / 0.25)
            huecos = sum(max(0.0, ws[k + 1]["s"] - ws[k]["e"]) for k in range(len(ws) - 1) if ws[k + 1]["s"] - ws[k]["e"] > 0.7)
            dens = 100 * (0.40 * _tri(ritmo, 1.2, 2.3, 3.3, 4.6) + 0.45 * min(1.0, unicos / 1.4) + 0.15 * ent_s) - 60 * min(1.0, huecos / d)
            dens = max(0.0, dens)
            # claridad
            conf = float(np.mean([w.get("p", 0.8) for w in ws]))
            conf_s = min(1.0, max(0.0, (conf - 0.6) / 0.35))
            snr_txt = ""
            if db is not None and len(db):
                k0, k1 = int(t0 / audio["paso"]), max(int(t0 / audio["paso"]) + 2, int(t1 / audio["paso"]))
                seg = db[k0:k1]
                if len(seg) >= 4:
                    p90, p10 = np.percentile(seg, 90), np.percentile(seg, 10)
                    snr = float(p90 - p10)
                    lvl = float(p90)
                    clipf = float(audio["clip"][k0:k1].mean())
                    sn_s = min(1.0, max(0.0, (snr - 10) / 20))
                    lv_s = _tri(lvl, -48, -30, -12, -3)
                    clar = 100 * (0.40 * sn_s + 0.20 * lv_s + 0.40 * conf_s) - 400 * clipf
                    snr_txt = f"SNR {snr:.0f} dB"
                else:
                    clar = 100 * conf_s
            else:
                clar = 100 * conf_s
            clar = max(0.0, min(100.0, clar))
            # cara
            if cara is not None and len(cara["presencia"]) and cara["presencia"].sum() > 0:
                k0, k1 = int(t0 / cara["paso"]), max(int(t0 / cara["paso"]) + 1, int(t1 / cara["paso"]))
                s = cara["presencia"][k0:k1]
                fc = float(s.mean()) if len(s) else 0.0
            elif cara is not None:
                fc = 0.0
            else:
                fc = 0.5
            fcs = 100 * fc
            # duración
            fit = 100 * (0.5 + 0.5 * _tri(d, 12, 25, 60, 100))
            total = 0.35 * g + 0.25 * dens + 0.20 * clar + 0.15 * fcs + 0.05 * fit
            cand.append({"a": a, "b": b, "ini": t0, "fin": t1, "i0": i0, "i1": i1, "puntuacion": round(total, 1),
                         "componentes": {"gancho": round(g, 1), "densidad": round(dens, 1), "claridad": round(clar, 1), "cara": round(fcs, 1), "duracion": round(fit, 1)},
                         "_mg": mg, "_ritmo": ritmo, "_unicos": unicos * d, "_snr": snr_txt, "_conf": conf})
    cand.sort(key=lambda c: -c["puntuacion"])
    elegidos = []
    for c in cand:
        if len(elegidos) >= n:
            break
        if any(c["ini"] < e["fin"] + solape_min and c["fin"] > e["ini"] - solape_min for e in elegidos):
            continue
        elegidos.append(c)
    out = []
    for r, c in enumerate(sorted(elegidos, key=lambda c: -c["puntuacion"]), 1):
        i0, i1 = c["i0"], c["i1"]
        ant = palabras[i0 - 1]["e"] if i0 > 0 else 0.0
        sig = palabras[i1 + 1]["s"] if i1 + 1 < len(palabras) else dur
        ini = max(0.0, c["ini"] - min(0.25, max(0.0, (c["ini"] - ant) / 2)))
        fin = min(dur, c["fin"] + min(0.35, max(0.0, (sig - c["fin"]) / 2)))
        texto = " ".join(w["w"] for w in palabras[i0:i1 + 1])
        gancho_txt = " ".join(w["w"] for w in palabras[i0:i0 + 40] if w["s"] < c["ini"] + 3.0)
        motivo = []
        motivo.append("gancho: " + (" + ".join(c["_mg"]) if c["_mg"] else "débil") + f" («{gancho_txt[:70]}»)")
        motivo.append(f"densidad: {c['_ritmo']:.1f} pal/s, {c['_unicos']:.0f} conceptos únicos")
        motivo.append(f"audio: {c['_snr'] or 's/d'}, confianza Whisper {c['_conf']:.2f}")
        motivo.append(f"cara en {c['componentes']['cara']:.0f}% de las muestras" if cara is not None else "cara: no medida")
        out.append({"rank": r, "ini": round(ini, 2), "fin": round(fin, 2), "dur": round(fin - ini, 2), "puntuacion": c["puntuacion"],
                    "componentes": c["componentes"], "motivo": "; ".join(motivo), "gancho": gancho_txt, "texto": texto})
    if verbose:
        log(f"clips: {len(cand)} ventanas puntuadas -> top {len(out)}")
    return out


def extraer(master, ini, fin, salida):
    """Copia recortada del master (re-codificada con calidad alta para corte exacto). El master no se toca."""
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    if salida.exists():
        return salida
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-ss", f"{ini:.3f}", "-i", str(master), "-t", f"{fin - ini:.3f}",
           "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
           "-movflags", "+faststart", str(salida)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("falló la extracción: " + r.stderr[-600:])
    return salida


def palabras_de_clip(palabras, ini, fin):
    """Palabras del tramo desplazadas a t=0 (para reusar la transcripción del master sin volver a transcribir)."""
    out = []
    for w in palabras:
        if w["s"] >= ini - 0.01 and w["e"] <= fin + 0.01:
            out.append({**w, "s": round(w["s"] - ini, 3), "e": round(w["e"] - ini, 3)})
    return out


def guardar(clips, ruta):
    Path(ruta).write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
