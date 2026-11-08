"""Planos: divide el vídeo en tomas de ~3-4 s (cortes entre palabras) con encuadre por cara y punch-in alterno.
Los cortes visuales NO quitan tiempo: suben la densidad (~25 cambios/min) sin tocar el audio.
Cada toma lleva un recorte estático (x,y,w,h) -> sin movimiento de cámara falso, solo jump-cuts de oficio.

Encuadre vertical (9:16, 1:1, 4:5): los subtítulos ocupan el borde inferior de la zona segura, así que la cara se coloca en la
parte ALTA de esa zona (ojos al 30-38 % del alto), la barbilla queda por encima del bloque de subtítulos y la cabeza nunca se corta."""
import os
import subprocess

import cv2
import numpy as np

from .common import FFMPEG, log


def detectar_cajas(src, dur=None, ancho_muestra=640, fps=2.0, ss=0.0, t=None):
    """Caras con caja completa y ojos, normalizadas 0-1 sobre el fotograma ORIGINAL (respeta su relación de aspecto,
    también en vertical). Devuelve lista de dicts {t, x, y, w, h, cx, cy, ojos_y} (x,y = esquina sup. izq. de la caja).
    Detector: YuNet (OpenCV Zoo, MIT) — el Haar clásico ya no viene en OpenCV 5. ojos_y sale de los puntos de referencia."""
    from .common import ROOT, probe
    info = probe(src)
    ar = info["alto"] / info["ancho"] if info.get("ancho") else 9 / 16
    alto = int(round(ancho_muestra * ar / 2) * 2)
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (ancho_muestra, alto), 0.7, 0.3, 5000)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-ss", str(ss)]
    if t:
        cmd += ["-t", str(t)]
    cmd += ["-i", src, "-vf", f"fps={fps},scale={ancho_muestra}:{alto}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    tam_frame = ancho_muestra * alto * 3
    out, i = [], 0
    while True:
        buf = p.stdout.read(tam_frame)
        if len(buf) < tam_frame:
            break
        img = np.frombuffer(buf, np.uint8).reshape(alto, ancho_muestra, 3)
        _, caras = det.detect(np.ascontiguousarray(img))
        if caras is not None and len(caras):
            c = max(caras, key=lambda c: c[2] * c[3])
            x, y, w, h = [float(v) for v in c[:4]]
            ojos = (float(c[5]) + float(c[7])) / 2 if len(c) >= 8 else y + h * 0.38
            out.append({"t": ss + i / fps, "x": x / ancho_muestra, "y": y / alto, "w": w / ancho_muestra, "h": h / alto,
                        "cx": (x + w / 2) / ancho_muestra, "cy": (y + h / 2) / alto, "ojos_y": ojos / alto})
        i += 1
    p.wait()
    log(f"caras detectadas en {len(out)}/{i} muestras")
    return out


def detectar_caras(src, dur=None, ancho_muestra=640, fps=2.0, ss=0.0, t=None):
    """Lista de (t, cx, cy, tam, arriba, abajo, ojos_y), todo normalizado 0-1 (tam = alto de la cara / alto de imagen;
    arriba/abajo = bordes de la caja; ojos_y = altura media de los ojos). Los 4 primeros campos son el formato histórico."""
    return [(c["t"], c["cx"], c["cy"], c["h"], c["y"], c["y"] + c["h"], c["ojos_y"]) for c in detectar_cajas(src, dur, ancho_muestra, fps, ss, t)]


def _snap_a_palabra(t, palabras_nuevo, ventana=0.6):
    """Mueve t al hueco entre palabras más cercano (para no cortar a mitad de palabra)."""
    mejor, dmin = t, ventana
    for a, b in zip(palabras_nuevo, palabras_nuevo[1:]):
        c = (a["e"] + b["s"]) / 2
        if abs(c - t) < dmin and a["e"] <= c <= b["s"] + 1e-6:
            mejor, dmin = c, abs(c - t)
    return mejor


def tomas(keep, palabras_orig, objetivo=3.6, minimo=2.0):
    """Sobre los tramos a conservar (tiempos ORIGINALES), crea tomas. Corta en huecos entre palabras u onsets."""
    ws = sorted(palabras_orig, key=lambda w: w["s"])
    res = []
    for a, b in keep:
        d = b - a
        n = max(1, int(round(d / objetivo)))
        if d < minimo * 1.5:
            n = 1
        cortes = [a]
        for k in range(1, n):
            t = a + d * k / n
            # buscar hueco entre palabras (en tiempo original)
            mej, dmin = t, 0.7
            for w0, w1 in zip(ws, ws[1:]):
                c = (w0["e"] + w1["s"]) / 2
                if a < c < b and abs(c - t) < dmin:
                    mej, dmin = c, abs(c - t)
            cortes.append(mej)
        cortes.append(b)
        cortes = sorted(set(round(c, 3) for c in cortes))
        for x, y in zip(cortes, cortes[1:]):
            if y - x > 0.2:
                res.append((x, y))
    return res


# ---------------------------------------------------------------------------------------------------------
# Encuadre vertical con la cara en la parte alta de la zona segura (los subtítulos van bajo la cara).
# Objetivo: ojos entre el 30 y el 38 % del alto; la barbilla siempre por encima del bloque de subtítulos; NUNCA cortar la cabeza.
# Orden de preferencia (de menos a más intrusivo): 1) zoom base (1.0 / punch-in) con el recorte desplazado, 2) punch-in algo mayor
# (suave, +0.02 por paso), 3) recorte desplazado hacia abajo con el hueco inferior relleno con el propio video desenfocado y
# oscurecido (como el modo 'pilar').
# ---------------------------------------------------------------------------------------------------------
OJOS_OBJ = (0.30, 0.38)         # banda objetivo de los ojos (fracción del alto de salida)
OJOS_MAX_SIN_RELLENO = 0.42     # si sin relleno solo se llega a ojos más abajo que esto, se usa relleno
ZOOM_MAX = 1.30
RELLENO_MAX = 0.30              # fracción máxima del recorte que puede ser relleno desenfocado
HUECO_SUBS = 0.03               # holgura (fracción del alto) entre la barbilla y el bloque de subtítulos (absorbe el ruido de YuNet, ~2 %)
K_MIN = 0.70                    # escala mínima del video cuando la cara es enorme (por debajo, el fondo desenfocado domina)
PELO = 0.35                     # la cabeza real sobresale ~35 % del alto de la caja de YuNet por encima de ella


def _formato_de(out_w, out_h):
    from .common import BRAND
    for k, f in BRAND["formatos"].items():
        if f["w"] == out_w and f["h"] == out_h:
            return k
    return None


def tope_subtitulos(formato, out_w, out_h, lineas=None):
    """Fracción del alto donde EMPIEZA el bloque de subtítulos, según zonas.py y los tamaños de subs.py.
    Los estilos 'visual'/'clasico'/'karaoke-cajas' son UNA línea que termina en el borde inferior de la zona segura (alto de la caja
    ≈ 1.16·fs); 'minimo' puede usar 2. Si subs.py cambia sus tamaños (_FS), esto los lee; si no existen, usa brand.json (78 px, 2 líneas)."""
    from .common import BRAND
    from . import zonas
    seg = zonas.seg(formato)
    bajo = out_h * (1 - seg["abajo"])
    try:
        from . import subs
        fs = subs._FS[formato]["base"]
        n = lineas or 1
        alto = n * 1.16 * fs + 0.25 * fs                  # + holgura del 'pop' de entrada (escala 108 %) y la sombra
    except (ImportError, AttributeError, KeyError):
        tam = BRAND["subtitulos"]["tam_vertical"]
        n = lineas or 2
        alto = n * tam * 1.30 + tam * 0.12
    return (bajo - alto) / out_h


def _punto_en(lo, hi, ideal):
    """Punto de [lo, hi] más cercano a `ideal` (None si el intervalo está vacío)."""
    if lo > hi + 1e-9:
        return None
    return min(max(ideal, lo), hi)


def _stats_cara(caras, a, b, src_w, src_h):
    """(cx, arriba, abajo, ojos) en píxeles del origen: mediana de las muestras de la toma (o la más cercana en el tiempo)."""
    pts = [c for c in caras if a <= c[0] <= b]
    if not pts and caras:
        t0 = (a + b) / 2
        pts = [min(caras, key=lambda c: abs(c[0] - t0))]
    if not pts:
        return None
    med = lambda k: float(np.median([p[k] for p in pts]))
    cx = med(1) * src_w
    if len(pts[0]) >= 7:
        # extremos prudentes: la barbilla baja al abrir la boca y la cabeza sube al gesticular -> percentiles, no mediana
        top = float(np.percentile([p[4] for p in pts], 15)) * src_h
        bot = float(np.percentile([p[5] for p in pts], 85)) * src_h
        eye = med(6) * src_h
    else:  # tuplas históricas de 4 campos: cara = 'tam' alrededor de cy
        cy, tam = med(2) * src_h, med(3) * src_h
        top, bot, eye = cy - tam / 2, cy + tam / 2, cy - tam * 0.12
    return cx, top, bot, eye


def _encuadre_cara(stats, src_h, cw0, ch0, z0, zoom_alt, sub_top):
    """Elige (z, y0, relleno_px, e, encogido) para una toma (encogido = None o {k, yf}). y0 puede pasar del borde inferior del origen (entonces hay relleno).
    e = posición final de los ojos como fracción del alto de salida."""
    cx, top, bot, eye = stats
    hf = bot - top
    zmax = min(ZOOM_MAX, max(z0, zoom_alt) + 0.10)
    ideal = sum(OJOS_OBJ) / 2
    best_t2 = None
    z = z0
    while z <= zmax + 1e-9:
        ch = ch0 / z
        e_min = (eye - top + PELO * hf) / ch + 0.01             # cabeza entera (con pelo) dentro del encuadre
        e_max = sub_top - HUECO_SUBS - (bot - eye) / ch         # barbilla por encima de los subtítulos
        f_lo = (eye - max(0.0, src_h - ch)) / ch                # ojos si el recorte baja lo más posible dentro del origen
        f_hi = eye / ch                                         # ojos si el recorte va arriba del todo (y0 = 0)
        if ch >= src_h - 1:
            f_lo = f_hi = eye / ch
        # nivel 1: ojos en la banda objetivo y sin salirse del origen
        p = _punto_en(max(OJOS_OBJ[0], e_min, f_lo), min(OJOS_OBJ[1], e_max, f_hi), ideal)
        if p is not None:
            return z, eye - p * ch, 0.0, p, None
        # nivel 2 (se recuerda el de menor zoom): sin solape y ojos no demasiado bajos, dentro del origen
        if best_t2 is None:
            p2 = _punto_en(max(e_min, f_lo), min(e_max, f_hi, OJOS_MAX_SIN_RELLENO), ideal)
            if p2 is not None:
                best_t2 = (z, eye - p2 * ch, 0.0, p2, None)
        z = round(z + 0.02, 4)
    if best_t2 is not None:
        return best_t2
    # nivel 3: relleno inferior (el recorte baja más allá del origen) o, si la cara es tan grande que no cabe, reducir el video
    ch = ch0 / z0
    e_min = (eye - top + PELO * hf) / ch + 0.01
    e_max = sub_top - HUECO_SUBS - (bot - eye) / ch
    if e_max >= e_min:
        p = _punto_en(max(OJOS_OBJ[0], e_min), min(OJOS_OBJ[1], e_max), ideal)
        if p is None:
            p = _punto_en(e_min, e_max, ideal)
        y0 = eye - p * ch
        pad = max(0.0, y0 + ch - src_h)
        if pad > RELLENO_MAX * ch:      # limita el relleno; la cara queda algo más baja pero la cabeza intacta
            y0 = src_h - ch + RELLENO_MAX * ch
            pad = RELLENO_MAX * ch
        return z0, y0, pad, (eye - y0) / ch, None
    # cara demasiado grande para tener cabeza entera Y barbilla sobre los subtítulos: se reduce el video (escala k) sobre su propio
    # fondo desenfocado y oscurecido (como el modo 'pilar'). Recorte arriba lo justo para que entre la cabeza con pelo.
    limite = sub_top - HUECO_SUBS
    y0 = min(max(top - PELO * hf - 0.02 * ch, 0.0), max(0.0, src_h - ch))
    k = min(1.0, limite * ch / max(bot - y0, 1.0))
    k = max(k, K_MIN)
    e0, c0 = k * (eye - y0) / ch, k * (bot - y0) / ch
    yf = min(max(ideal - e0, 0.0), max(0.0, limite - c0))
    return z0, y0, 0.0, e0 + yf, {"k": k, "yf": yf}


def recortes(tomas_lista, caras, src_w, src_h, out_w, out_h, zoom_alt=1.12, titular_zoom=True, formato=None):
    """Para cada toma: (a, b, x, y, w, h[, vis]) del recorte en píxeles del origen. Zoom alterno 1.0 / zoom_alt.
    7º elemento (solo si hace falta, dict): {'vis': alto visible del origen desde y} -> el resto del recorte (h - vis) se rellena en
    render con el propio borde inferior reflejado y desenfocado; o {'k', 'yf'} -> video a escala k (cara enorme) sobre su propio
    fondo desenfocado y oscurecido, desplazado yf (fracción del alto) desde arriba.
    Formatos con subtítulo bajo la cara (9:16, 1:1, 4:5): ojos en 30-38 % del alto, barbilla sobre los subtítulos, cabeza intacta."""
    from . import zonas
    ta = out_w / out_h
    cw0 = min(src_w, src_h * ta)
    ch0 = cw0 / ta
    formato = formato or _formato_de(out_w, out_h)
    con_subs = formato is not None and zonas.es_vertical(formato) and os.environ.get("MW_ENCUADRE") != "clasico"   # clasico = encuadre antiguo (A/B)
    sub_top = tope_subtitulos(formato, out_w, out_h) if con_subs else None
    res = []
    for i, (a, b) in enumerate(tomas_lista):
        z = 1.0 if i % 2 == 0 else zoom_alt
        st = _stats_cara(caras, a, b, src_w, src_h) if caras else None
        cx = st[0] if st else src_w / 2
        pad, encogido = 0.0, None
        if st and con_subs:
            z, y, pad, _, encogido = _encuadre_cara(st, src_h, cw0, ch0, z, zoom_alt, sub_top)
            cw, ch = cw0 / z, ch0 / z
            x = min(max(cx - cw / 2, 0), src_w - cw)
        else:
            cy = ((st[1] + st[2]) / 2) if st else src_h * 0.4
            cw, ch = cw0 / z, ch0 / z
            x = min(max(cx - cw / 2, 0), src_w - cw)
            if z == 1.0 and ch >= src_h - 1:
                y = 0.0
            else:
                y = min(max(cy - 0.42 * ch, 0), src_h - ch)  # la cara a ~42% de altura (ojos ~36 %): aire sobre la cabeza
        item = [a, b, int(x) // 2 * 2, int(max(y, 0)) // 2 * 2, int(cw) // 2 * 2, int(ch) // 2 * 2]
        if encogido:
            item.append(dict(encogido))                      # {'k', 'yf'}: video a escala k con y desplazada yf (fracción del alto)
        elif pad > 2:
            item.append({"vis": max(2, int(src_h - item[3]) // 2 * 2)})
        res.append(tuple(item))
    return res
