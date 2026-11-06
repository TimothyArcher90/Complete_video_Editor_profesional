"""Verificación del encuadre: ¿tapan los subtítulos la cara?  (mide sobre el vídeo YA renderizado, con YuNet)

Uso:
  python -m mw_editor.verificar_encuadre BASE.mp4 SUBTITULOS.ass [--formato vertical] [--fps 4] [--json salida.json]

Mide, en fotogramas muestreados del MP4 base:
  - bbox de la cara (YuNet) y posición de los ojos,
  - bbox de los subtítulos activos en ese instante (se reconstruye del propio ASS: posición de cada palabra + su ancho medido
    con la fuente de marca; en estilo 'clásico' se usa el bloque centrado sobre el margen inferior),
  - solape cara/subtítulos, cabeza cortada (caja de la cara + 35 % de pelo fuera del encuadre), ojos fuera de la banda 30-38 %.
Criterio de aceptación: >= 95 % de los fotogramas muestreados con cara SIN solape (métrica A, bbox de unión de los subtítulos).
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .common import BRAND, FFMPEG, ROOT, dims, log, probe

OJOS_OBJ = (0.30, 0.38)
PELO = 0.35


def _t(s):
    h, m, r = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


def _ancho(texto, fs):
    """Ancho renderizado de una palabra: subs.ancho_real (calibrado con libass) si existe; si no, PIL × 0.84."""
    from . import subs
    f = getattr(subs, "ancho_real", None)
    return f(texto, fs) if f else subs.medir(texto, fs, "titular", -0.03 * fs) * 0.84


def cajas_subtitulos(ass, formato):
    """Lista de eventos {t0, t1, cajas:[(x0,y0,x1,y1)]} reconstruidos de un ASS de subtítulos (visual o clásico)."""
    from .subs import medir
    w, h = dims(formato)
    tam = BRAND["subtitulos"]["tam_vertical"] if formato in ("vertical", "cuadrado", "4x5") else BRAND["subtitulos"]["tam_horizontal"]
    txt = Path(ass).read_text(encoding="utf-8")
    mv = re.search(r"^Style: Sub,[^,]*,[^,]*,.*?,(\d+),(\d+),(\d+),\d+\s*$", txt, re.M)   # MarginL, MarginR, MarginV, Encoding
    eventos = []
    for m in re.finditer(r"^Dialogue: (\d+),([\d:.]+),([\d:.]+),(\w+),[^,]*,\d+,\d+,\d+,[^,]*,(.*)$", txt, re.M):
        capa, t0, t1, estilo, cuerpo = m.groups()
        if estilo == "Pal":
            mo = re.search(r"\\move\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", cuerpo) or re.search(r"\\pos\(([-\d.]+),([-\d.]+)", cuerpo)
            palabra = re.sub(r"\{[^}]*\}", "", cuerpo).replace("\\N", " ").strip()
            if not mo or not palabra:
                continue
            g = [float(v) for v in mo.groups()]
            xc, yc = (g[2], g[3]) if len(g) == 4 else (g[0], g[1])
            mf = re.search(r"\\fs(\d+)", cuerpo)
            fs = int(mf.group(1)) if mf else tam
            a = _ancho(palabra, fs)
            pad = fs * 0.22
            eventos.append({"t0": _t(t0), "t1": _t(t1), "cajas": [(xc - a / 2 - pad, yc - fs * 0.58, xc + a / 2 + pad, yc + fs * 0.58)]})
        elif estilo == "Sub" and mv:
            palabra = re.sub(r"\{[^}]*\}", "", cuerpo).strip()
            mV = int(mv.group(3))
            a = medir(palabra, tam, "titular", -0.03 * tam)
            xc, yb = w / 2, h - mV
            eventos.append({"t0": _t(t0), "t1": _t(t1), "cajas": [(xc - a / 2, yb - tam * 1.2, xc + a / 2, yb)]})
    return eventos


def _union(cajas):
    return (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))


def _cruza(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def caras_en(video, fps=4.0, ancho_muestra=640):
    """[(t, x0, y0, x1, y1, ojos_y)] normalizado 0-1 sobre el fotograma del video."""
    info = probe(video)
    alto = int(round(ancho_muestra * info["alto"] / info["ancho"] / 2) * 2)
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (ancho_muestra, alto), 0.7, 0.3, 5000)
    p = subprocess.Popen([FFMPEG, "-hide_banner", "-v", "error", "-i", video, "-vf", f"fps={fps},scale={ancho_muestra}:{alto}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = ancho_muestra * alto * 3
    out, i, total = [], 0, 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        total += 1
        _, caras = det.detect(np.ascontiguousarray(np.frombuffer(buf, np.uint8).reshape(alto, ancho_muestra, 3)))
        if caras is not None and len(caras):
            c = max(caras, key=lambda c: c[2] * c[3])
            x, y, w, h = [float(v) for v in c[:4]]
            ojos = (float(c[5]) + float(c[7])) / 2
            out.append((i / fps, x / ancho_muestra, y / alto, (x + w) / ancho_muestra, (y + h) / alto, ojos / alto))
        i += 1
    p.wait()
    return out, total


def medir(base, ass, formato="vertical", fps=4.0):
    """Devuelve dict con las métricas. `ass` puede ser None (solo mide posición de la cara)."""
    from .zonas import seg
    w, h = dims(formato)
    caras, total = caras_en(str(base), fps)
    ev = cajas_subtitulos(ass, formato) if ass else []
    sg = seg(formato)
    tam = BRAND["subtitulos"]["tam_vertical"]
    from .planos import tope_subtitulos
    sub_top_res = tope_subtitulos(formato, w, h) * h                           # bloque reservado, igual que planos.recortes
    filas = []
    for t, x0, y0, x1, y1, ojos in caras:
        cara = (x0 * w, y0 * h, x1 * w, y1 * h)
        activos = [e for e in ev if e["t0"] <= t <= e["t1"]]
        cajas = [c for e in activos for c in e["cajas"]]
        sol_union = bool(cajas) and _cruza(cara, _union(cajas))
        sol_pal = any(_cruza(cara, c) for c in cajas)
        sol_res = cara[3] > sub_top_res
        hf = y1 - y0
        cabeza_cortada = (y0 - PELO * hf) < -0.005 or x0 < 0 or x1 > 1
        filas.append({"t": round(t, 2), "ojos": round(ojos, 3), "cara_arriba": round(y0, 3), "cara_abajo": round(y1, 3),
                      "subs_activos": bool(cajas), "solape_union": sol_union, "solape_palabras": sol_pal,
                      "pisa_banda_reservada": sol_res, "cabeza_cortada": cabeza_cortada})
    n = len(filas)
    con_subs = [f for f in filas if f["subs_activos"]]
    pct = lambda k, lst=filas: (100.0 * sum(1 for f in lst if f[k]) / len(lst)) if lst else 0.0
    ojos = [f["ojos"] for f in filas]
    return {
        "video": str(base), "formato": formato, "fps_muestreo": fps, "muestras": total, "con_cara": n,
        "sin_solape_pct": round(100 - pct("solape_union"), 1),                       # METRICA A (criterio >= 95)
        "sin_solape_palabras_pct": round(100 - pct("solape_palabras"), 1),
        "sin_solape_con_subs_pct": round(100 - pct("solape_union", con_subs), 1) if con_subs else None,
        "frames_con_subs": len(con_subs),
        "sin_pisar_banda_reservada_pct": round(100 - pct("pisa_banda_reservada"), 1),
        "cabeza_cortada_pct": round(pct("cabeza_cortada"), 1),
        "ojos_media": round(float(np.mean(ojos)), 3) if ojos else None,
        "ojos_min": round(min(ojos), 3) if ojos else None, "ojos_max": round(max(ojos), 3) if ojos else None,
        "ojos_en_30_38_pct": round(100.0 * sum(1 for o in ojos if OJOS_OBJ[0] <= o <= OJOS_OBJ[1]) / n, 1) if n else None,
        "filas": filas,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mw_editor.verificar_encuadre")
    ap.add_argument("base")
    ap.add_argument("ass", nargs="?")
    ap.add_argument("--formato", default="vertical", choices=["vertical", "cuadrado", "4x5", "horizontal"])
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    r = medir(a.base, a.ass, a.formato, a.fps)
    res = {k: v for k, v in r.items() if k != "filas"}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
