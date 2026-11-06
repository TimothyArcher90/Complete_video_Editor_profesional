# -*- coding: utf-8 -*-
"""Etalonaje profesional de MacroWise (integrado desde docs/investigacion/color_propuesta.py).

Pipeline de 8 pasos con el orden medido en la investigacion (docs/investigacion/color.md): superblancos -> exposicion ->
balance de blancos -> tono de piel -> curva -> saturacion -> look de marca -> salida legal. Parametros por camara calculados UNA
vez (mediana de 12 fotogramas) y guardados en 00_DOCS/color.json. Dos niveles: 'calidad' (16 bit, cadena viva) y 'rapido'
(la cadena estatica horneada en una LUT 3D 33^3 propia, aplicada con lut3d tetraedrico). Ver docs/investigacion/color_implementacion.md.
Punto de entrada para el motor: plan_color(...) -> imagen.cadena(). Todo lo demas son funciones puras o de medicion.
"""
from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------------------------- marca / constantes
BRAND_HEX = {"warm_black": "#1A1A17", "warm_dark": "#232320", "stone_light": "#D6D1C8",
             "oro": "#C9A84C", "teal": "#50B5A2", "purpura": "#73247D"}
PIEL_LINEA_DEG = 123.0          # línea de piel (I-line) del vectorscopio: ángulo de atan2(Cr-128, Cb-128), Cb en x, Cr en y
PIEL_TOL_DEG = 6.0              # aceptación: 123 ± 6 (fallo duro a ± 10)
Y_PIEL_OBJETIVO = 150.0         # luma tv (16-235) de la mediana de piel para piel clara/media (~61 IRE). Oscura: 100-125.
RAIZ = Path(__file__).resolve().parent.parent
BIN_YUNET = RAIZ / "brand" / "models" / "face_detection_yunet_2023mar.onnx"

# BT.709: RGB (0-1, codificado) <-> Y'CbCr (Y 0-1, Cb/Cr -0.5..0.5)
_T = np.array([[0.2126, 0.7152, 0.0722],
               [-0.2126 / 1.8556, -0.7152 / 1.8556, 0.9278 / 1.8556],
               [0.7874 / 1.5748, -0.7152 / 1.5748, -0.0722 / 1.5748]])
_TINV = np.linalg.inv(_T)


# --------------------------------------------------------------------------------------------- medición (puro)
def ycc_tv(rgb):
    """rgb float 0-1 (...,3) -> (Y, Cb, Cr) en unidades de vídeo 8 bit rango tv (Y 16-235, Cb/Cr 16-240, neutro 128)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    y = rgb @ _T[0]
    cb = rgb @ _T[1]
    cr = rgb @ _T[2]
    return 16 + 219 * y, 128 + 224 * cb, 128 + 224 * cr


def angulo_croma(cb, cr):
    """Ángulo de vectorscopio en grados [0,360) y radio (unidades tv). La piel debe caer en ~123°."""
    return (math.degrees(math.atan2(cr - 128.0, cb - 128.0)) % 360.0), math.hypot(cb - 128.0, cr - 128.0)


def rgb_a_lab(rgb):
    """rgb 0-1 (...,3) -> Lab (D65, sRGB~BT.709). Solo para ΔE RELATIVOS (no es calibración absoluta)."""
    import cv2
    a = np.asarray(rgb, dtype=np.float32).reshape(-1, 1, 3)
    return cv2.cvtColor(a, cv2.COLOR_RGB2Lab).reshape(np.shape(rgb)).astype(np.float64)


def delta_e2000(lab1, lab2):
    """CIEDE2000 en numpy (validado contra skimage.color.deltaE_ciede2000 en el laboratorio). ΔE00<=1: imperceptible; <=2.5: cortes
    aceptables; >4: se nota entre planos."""
    l1, a1, b1 = (np.asarray(lab1, float)[..., i] for i in range(3))
    l2, a2, b2 = (np.asarray(lab2, float)[..., i] for i in range(3))
    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    cm = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(cm ** 7 / (cm ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dlp, dcp = l2 - l1, c2p - c1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where((c1p * c2p) == 0, 0, dh)
    dhp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))
    lpm, cpm = (l1 + l2) / 2, (c1p + c2p) / 2
    hs = h1p + h2p
    hm = np.where(np.abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2))
    hm = np.where((c1p * c2p) == 0, hs, hm)
    t = (1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm)) +
         0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63)))
    dth = 30 * np.exp(-(((hm - 275) / 25) ** 2))
    rc = 2 * np.sqrt(cpm ** 7 / (cpm ** 7 + 25.0 ** 7))
    sl = 1 + 0.015 * (lpm - 50) ** 2 / np.sqrt(20 + (lpm - 50) ** 2)
    sc, sh = 1 + 0.045 * cpm, 1 + 0.015 * cpm * t
    rt = -np.sin(np.radians(2 * dth)) * rc
    return np.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp / sh) ** 2 + rt * (dcp / sc) * (dhp / sh))


_DET = None


def _detector(ancho, alto):
    global _DET
    import cv2
    if _DET is None:
        _DET = cv2.FaceDetectorYN.create(str(BIN_YUNET), "", (ancho, alto), 0.7)
    _DET.setInputSize((ancho, alto))
    return _DET


def detectar_cara(rgb8):
    """YuNet sobre un fotograma rgb uint8 (H,W,3). Devuelve (x,y,w,h) de la cara más grande o None."""
    import cv2
    h, w = rgb8.shape[:2]
    _, caras = _detector(w, h).detect(cv2.cvtColor(rgb8, cv2.COLOR_RGB2BGR))
    if caras is None or not len(caras):
        return None
    c = max(caras, key=lambda f: f[2] * f[3])
    return tuple(int(v) for v in c[:4])


def mascara_piel(rgb, caja):
    """Máscara booleana de píxeles de piel DENTRO de la caja de la cara: puerta Cb/Cr clásica + luma sin quemar/sin barba oscura.
    Evita gafas, pelo, barba y brillos especulares (Y>225)."""
    x, y, w, h = caja
    H, W = rgb.shape[:2]
    x0, x1 = max(0, int(x + 0.12 * w)), min(W, int(x + 0.88 * w))
    y0, y1 = max(0, int(y + 0.15 * h)), min(H, int(y + 0.95 * h))
    sub = rgb[y0:y1, x0:x1].astype(np.float64) / 255.0
    yy, cb, cr = ycc_tv(sub)
    ang = (np.degrees(np.arctan2(cr - 128, cb - 128)) % 360)
    rad = np.hypot(cb - 128, cr - 128)
    ok = (cb > 77) & (cb < 127) & (cr > 133) & (cr < 173) & (yy > 55) & (yy < 225) & (rad > 8) & (ang > 95) & (ang < 150)
    m = np.zeros(rgb.shape[:2], bool)
    m[y0:y1, x0:x1] = ok
    return m


def medir_piel(rgb8, caja=None):
    """Mide la piel de un fotograma rgb uint8 (decodificado con matriz BT.709 y rango tv->full correctos).
    Devuelve dict con y (tv), cb, cr, angulo, croma, rgb (mediana 0-1), lab, n (píxeles) o None si no hay cara/piel suficiente."""
    caja = caja or detectar_cara(rgb8)
    if caja is None:
        return None
    m = mascara_piel(rgb8, caja)
    n = int(m.sum())
    if n < 150:
        return None
    px = rgb8[m].astype(np.float64) / 255.0
    med = np.median(px, axis=0)
    y, cb, cr = ycc_tv(med)
    ang, rad = angulo_croma(float(cb), float(cr))
    return {"y": float(y), "cb": float(cb), "cr": float(cr), "angulo": ang, "croma": rad,
            "rgb": med.tolist(), "lab": rgb_a_lab(med).tolist(), "n": n, "caja": caja}


def medir_neutros(rgb8, caja):
    """Estima el reparto de color de la luz sobre superficies casi neutras (camiseta blanca, pared gris) CERCA de la cara,
    sin piel, sin quemados. Devuelve {'rgb': media, 'gan': (gr,gg,gb) con g=1, 'n': px} o None si hay <0.4 % de píxeles."""
    import cv2
    H, W = rgb8.shape[:2]
    f = rgb8.astype(np.float32) / 255.0
    hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
    s, v = hsv[..., 1], hsv[..., 2]
    x, y, w, h = caja
    cerca = np.zeros((H, W), bool)
    cerca[max(0, y - h): min(H, y + 3 * h), max(0, x - 2 * w): min(W, x + 3 * w)] = True
    cara = np.zeros((H, W), bool)
    cara[max(0, y - h // 3): y + h + h // 3, max(0, x - w // 3): x + w + w // 3] = True
    piel = mascara_piel(rgb8, (max(0, x - w), max(0, y - h), 3 * w, 3 * h))
    m = cerca & ~cara & ~piel & (s < 0.18) & (v > 0.32) & (v < 0.90)
    if m.mean() < 0.004:
        return None
    px = f[m].reshape(-1, 3)
    med = px.mean(axis=0).astype(np.float64)
    return {"rgb": med.tolist(), "gan": (float(med[1] / med[0]), 1.0, float(med[1] / med[2])), "n": int(m.sum())}


def _ffmpeg_fotograma_rgb(ruta, t, ffmpeg="ffmpeg"):
    """Un fotograma como rgb uint8 (H,W,3) decodificado POR FFMPEG con matriz/rango del fichero (cv2.VideoCapture usa la matriz
    equivocada en algunos builds: comprobado en el laboratorio)."""
    p = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{t:.3f}", "-i", str(ruta), "-frames:v", "1", "-vf", "setparams=colorspace=bt709:range=tv",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True)
    import cv2
    im = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def duracion(ruta, ffprobe="ffprobe"):
    return float(subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                                capture_output=True, text=True, check=True).stdout.strip())


def fotogramas_rgb(ruta, n=12, ffmpeg="ffmpeg", filtros_previos=None, matriz="bt709", rango="tv"):
    """n fotogramas repartidos (5 %-95 %) como rgb uint8, decodificados POR FFMPEG con matriz/rango explicitos (cv2.VideoCapture usa otra matriz).
    UN SOLO proceso de ffmpeg (arrancar ffmpeg cuesta ~3 s en esta maquina): clips <= 120 s en una pasada con `fps`; largos con n entradas
    `-ss` (busqueda, coste independiente de la duracion: un largo de 40 min no se decodifica entero). Salida a PNG en un directorio temporal."""
    import cv2
    d = duracion(ruta)
    conv = ",".join((filtros_previos or []) + [f"scale=in_range={'pc' if rango == 'pc' else 'tv'}:in_color_matrix={matriz}:out_range=full:flags=accurate_rnd+full_chroma_int", "format=rgb24"])
    with tempfile.TemporaryDirectory(prefix="mw_fr_") as td:
        if d <= 120:
            span = 0.90 * d
            cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{0.05 * d:.3f}", "-t", f"{span:.3f}", "-i", str(ruta), "-vf", f"fps={n / span:.6f},{conv}",
                   "-frames:v", str(n), str(Path(td) / "f%02d.png")]
        else:
            cmd = [ffmpeg, "-v", "error", "-y"]
            for k in range(n):
                cmd += ["-ss", f"{0.05 * d + 0.90 * d * (k + 0.5) / n:.3f}", "-i", str(ruta)]
            for k in range(n):
                cmd += ["-map", f"{k}:v:0", "-frames:v", "1", "-vf", conv, str(Path(td) / f"f{k + 1:02d}.png")]
        subprocess.run(cmd, capture_output=True)
        out = []
        for f in sorted(Path(td).glob("f*.png")):
            im = cv2.imread(str(f), cv2.IMREAD_COLOR)
            if im is not None:
                out.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    return out


def fondo_y(rgb8, caja):
    """Luma tv (p75) del fondo: columnas fuera de la banda de la persona (caja x +-1.5 anchos). Detecta la ventana brillante detras."""
    x, y, w, h = caja
    small = rgb8[::4, ::4].astype(np.float64) / 255.0
    yy = ycc_tv(small)[0]
    xs = np.arange(small.shape[1]) * 4
    fuera = (xs < x - 1.5 * w) | (xs > x + 2.5 * w)
    reg = yy[:, fuera] if fuera.any() else yy[: max(1, yy.shape[0] // 5)]
    return float(np.percentile(reg, 75))


def perfil_de_fotogramas(frames):
    """Perfil estable: mediana sobre los fotogramas. piel (mediana), neutros (mediana), dispersion de la piel (dE00 p90), fondo_y, cajas."""
    pieles, neut, fondos, cajas = [], [], [], []
    for fr in frames:
        p = medir_piel(fr)
        if p is None:
            continue
        pieles.append(p)
        cajas.append(p["caja"])
        fondos.append(fondo_y(fr, p["caja"]))
        nt = medir_neutros(fr, p["caja"])
        if nt:
            neut.append(nt)
    if not pieles:
        return None
    med = lambda k: float(np.median([p[k] for p in pieles]))
    rgbm = np.median(np.array([p["rgb"] for p in pieles]), axis=0)
    labm = rgb_a_lab(rgbm)
    disp = [float(delta_e2000(np.array(p["lab"]), labm)) for p in pieles]
    perfil = {"piel": {"y": med("y"), "cb": med("cb"), "cr": med("cr"), "angulo": med("angulo"), "croma": med("croma"),
                       "rgb": rgbm.tolist(), "lab": labm.tolist()},
              "dispersion_de00_p90": float(np.percentile(disp, 90)), "n_frames": len(pieles), "n_leidos": len(frames),
              "fondo_y_p75": float(np.median(fondos)), "cajas": [[int(v) for v in c] for c in cajas]}
    if neut:
        perfil["neutros"] = {"rgb": np.median(np.array([x["rgb"] for x in neut]), axis=0).tolist(), "n_frames": len(neut)}
    return perfil


def perfil_clip(ruta, n=12, ffmpeg="ffmpeg", filtros_previos=None, matriz="bt709", rango="tv"):
    """Perfil estable de un clip (mediana de n fotogramas repartidos). Es el UNICO input de las cadenas."""
    return perfil_de_fotogramas(fotogramas_rgb(ruta, n, ffmpeg, filtros_previos, matriz, rango))


# --------------------------------------------------------------------------------------------- matrices de color (puro)
def matriz_croma(rot_deg=0.0, sat=1.0):
    """3x3 en RGB codificado que rota el vector de croma `rot_deg` grados (+ = sube el ángulo del vectorscopio) y lo escala `sat`.
    Exacta en el plano Cb/Cr de BT.709, conserva el luma."""
    a = math.radians(rot_deg)
    c, s = sat * math.cos(a), sat * math.sin(a)
    r = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    return _TINV @ r @ _T


def matriz_ganancias(gr=1.0, gg=1.0, gb=1.0):
    return np.diag([gr, gg, gb])


def _ccm(m):
    """colorchannelmixer a partir de una 3x3 (filas = canal de salida)."""
    n = ["rr", "rg", "rb", "gr", "gg", "gb", "br", "bg", "bb"]
    return "colorchannelmixer=" + ":".join(f"{k}={v:.5f}" for k, v in zip(n, np.asarray(m).reshape(-1)))


def _simular_rgb(rgb, gamma=1.0, m=None):
    v = np.clip(np.asarray(rgb, float), 1e-6, 1) ** gamma
    if m is not None:
        v = np.clip(m @ v, 0, 1)
    return v


# --------------------------------------------------------------------------------------------- parámetros de corrección (puro)
def objetivo_desde_referencia(perfil_ref):
    """Para igualar UNA cámara/persona a otra (misma persona en dos cámaras, o entrevistado y entrevistador): usa la piel medida de la
    referencia como objetivo en vez de la línea absoluta de 123°. Devuelve kwargs para parametros_correccion/cadena_completa."""
    p = perfil_ref["piel"]
    return {"y_objetivo": p["y"], "angulo_objetivo": p["angulo"], "croma_objetivo": p["croma"]}


def hue_signalstats_a_angulo(hue):
    """signalstats.HUE* = atan2(U-128, V-128)+180° (NO es el ángulo de vectorscopio). Conversión: angulo = (270 - HUE) mod 360.
    La línea de piel 123° equivale a HUEMED de signalstats ≈ 147°."""
    return (270.0 - float(hue)) % 360.0


def parametros_correccion(perfil, y_objetivo=Y_PIEL_OBJETIVO, fuerza_wb=0.7, fuerza_piel=0.6, max_wb=0.05, max_rot=8.0,
                          croma_objetivo=None, angulo_objetivo=PIEL_LINEA_DEG):
    """Decide la corrección PRIMARIA a partir del perfil medido. Devuelve dict con:
       gamma (exposición), wb (gr,gg,gb), rot_deg (a la línea de piel), sat_piel, avisos (lo que NO se puede/debe arreglar)."""
    avisos = []
    p = perfil["piel"]
    yn = max(0.02, (p["y"] - 16) / 219.0)
    yt = (y_objetivo - 16) / 219.0
    gamma = float(np.clip(math.log(yt) / math.log(yn), 0.72, 1.25))
    if abs(math.log(yt) / math.log(yn) - gamma) > 1e-6:
        avisos.append(f"exposición fuera de rango seguro (piel Y={p['y']:.0f}): se limita el gamma a {gamma:.2f}; más sube el ruido")
    # balance de blancos por referencia neutra (limitado ±max_wb; sin neutros fiables no se toca)
    wb = (1.0, 1.0, 1.0)
    nt = perfil.get("neutros")
    if nt:
        r, g, b = nt["rgb"]
        gr, gb = float(np.clip(g / r, 1 - max_wb, 1 + max_wb)), float(np.clip(g / b, 1 - max_wb, 1 + max_wb))
        wb = (1 + (gr - 1) * fuerza_wb, 1.0, 1 + (gb - 1) * fuerza_wb)
    else:
        avisos.append("sin superficie neutra fiable cerca de la cara: balance de blancos se deja a la línea de piel")
    # línea de piel: se SIMULA la cadena sobre el RGB de la piel y se rota el residuo (parcial, ±max_rot)
    v = _simular_rgb(p["rgb"], gamma, matriz_ganancias(*wb))
    _, cb, cr = ycc_tv(v)
    ang, rad = angulo_croma(float(cb), float(cr))
    resid = ((angulo_objetivo - ang + 180) % 360) - 180
    rot = float(np.clip(resid * fuerza_piel, -max_rot, max_rot))
    if abs(resid) > 2 * max_rot:
        avisos.append(f"la piel queda a {resid:+.0f}° de la línea de piel: luz mixta o máscara de color, revisar a mano")
    sat_piel = 1.0
    if croma_objetivo:
        sat_piel = float(np.clip(croma_objetivo / max(rad, 1e-6), 0.85, 1.15))
    return {"gamma": gamma, "wb": wb, "rot_deg": rot, "sat_piel": sat_piel, "avisos": avisos,
            "piel_pre_giro": {"angulo": ang, "croma": rad}}


# --------------------------------------------------------------------------------------------- bloques de cadena (puro)
def filtros_entrada(recuperar_superblancos=True, matriz="bt709", rango="tv"):
    """YUV -> RGB 16 bit (codificado). Si el origen trae Y>235 (superblancos, frecuente en iPhone/streams), se comprimen ANTES
    de convertir: si no, el recorte del RGB los destruye (verificado: YMAX 255 en los dos clips de prueba). `matriz` y `rango`
    se leen del fichero (clips etiquetados bt470bg/601 NO se decodifican como 709); sin superblancos si el origen es full range."""
    f = []
    if recuperar_superblancos and rango == "tv":
        f.append("lutyuv=y='if(gt(val,220),220+(val-220)*15/34,val)'")
    f.append(f"scale=in_range={'pc' if rango == 'pc' else 'tv'}:in_color_matrix={matriz}:out_range=full:flags=accurate_rnd+full_chroma_int")
    f.append("format=gbrp16le")
    return f


def filtros_salida(limitar=True):
    """RGB -> YUV 4:2:0 tv BT.709 con dither Floyd-Steinberg + limitadores + etiquetas explícitas."""
    f = ["scale=in_range=full:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int:sws_dither=ed", "format=yuv420p"]
    if limitar:
        f += ["limiter=min=16:max=235:planes=1", "limiter=min=16:max=240:planes=6"]
    f.append("setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv")
    return f


def f_exposicion(gamma):
    """Gamma por canal (conserva negro 0 y blanco 1: no quema): <1 aclara."""
    if abs(gamma - 1) < 0.008:
        return []
    g = f"gammaval({gamma:.4f})"
    return [f"lutrgb=r={g}:g={g}:b={g}"]


def f_primaria(wb=(1, 1, 1), rot_deg=0.0, sat=1.0):
    """Balance de blancos + giro hacia la línea de piel en UNA sola matriz (menos redondeos)."""
    m = matriz_croma(rot_deg, sat) @ matriz_ganancias(*wb)
    if np.allclose(m, np.eye(3), atol=2e-4):
        return []
    return [_ccm(m)]


def f_piel_selectivo(rojos=(0, 0, 0, 0), amarillos=(0, 0, 0, 0)):
    """Ajuste CMYK relativo solo sobre rojos/amarillos (donde vive la piel). Cada tupla = (cian, magenta, amarillo, negro) en -1..1.
    Ej.: rojos=(0.05,0,0,0) apaga ~4 % de rojo (piel acalorada); amarillos=(0,0,0.04,0) calienta."""
    if not any(rojos) and not any(amarillos):
        return []
    s = lambda t: " ".join(f"{v:.3f}" for v in t)
    return [f"selectivecolor=correction_method=relative:reds='{s(rojos)}':yellows='{s(amarillos)}'"]


def _pts(puntos):
    return " ".join(f"{x:.4f}/{y:.4f}" for x, y in puntos)


def f_curva(puntos, suelo_rgb=None, techo_rgb=None):
    """Curva tonal PCHIP (monótona: sin inversiones). `puntos` = [(x,y),...] sobre el maestro, de 0 a 1.
    suelo_rgb/techo_rgb: negro y blanco por canal (tinte del suelo/techo, p. ej. negro cálido) -> curvas R/G/B."""
    pts = sorted(puntos)
    if suelo_rgb is None and techo_rgb is None:
        return [f"curves=master='{_pts(pts)}':interp=pchip"]
    sm, tm = pts[0][1], pts[-1][1]
    suelo = suelo_rgb or (sm,) * 3
    techo = techo_rgb or (tm,) * 3
    cs = []
    for c in range(3):
        cs.append([(x, float(np.clip(y + (suelo[c] - sm) * (1 - x) + (techo[c] - tm) * x, 0, 1))) for x, y in pts])
    return [f"curves=red='{_pts(cs[0])}':green='{_pts(cs[1])}':blue='{_pts(cs[2])}':interp=pchip"]


def f_saturacion(sat=1.0, vibrance=0.0):
    """Saturación global (matriz, conserva luma) + vibrance (protege lo ya saturado; piel intacta con valores <=0.15)."""
    f = []
    if abs(sat - 1) > 0.003:
        f.append(_ccm(matriz_croma(0.0, sat)))
    if abs(vibrance) > 0.003:
        f.append(f"vibrance=intensity={vibrance:.3f}")
    return f


def f_balance(sombras=(0, 0, 0), medios=(0, 0, 0), luces=(0, 0, 0), conservar_luma=True):
    """colorbalance: cada tupla (r,g,b) en -1..1. Valores útiles: 0.005-0.03. >0.05 ya es un tinte evidente."""
    if not any(sombras) and not any(medios) and not any(luces):
        return []
    k = {}
    for pre, t in (("s", sombras), ("m", medios), ("h", luces)):
        for c, v in zip("rgb", t):
            if v:
                k[f"{c}{pre}"] = v
    return ["colorbalance=" + ":".join(f"{a}={b:.4f}" for a, b in k.items()) + (":pl=1" if conservar_luma else "")]


# --------------------------------------------------------------------------------------------- looks de marca MacroWise
# Todos: luz cálida, contraste suave, altas luces rodadas (techo < 1), suelo de negro > 0 (negro cálido tipo #1A1A17 atenuado),
# SIN glow/degradado/viñeta/neón. Los números salen de las iteraciones del laboratorio (ver color.md §5).
LOOKS = {
    "warm_black": {  # por defecto: estudio cálido, negros suaves, contraste de editorial
        "curva": [(0, 0.030), (0.10, 0.094), (0.30, 0.282), (0.50, 0.500), (0.72, 0.738), (0.90, 0.893), (1, 0.952)],
        "suelo": (0.036, 0.034, 0.027), "techo": (0.956, 0.950, 0.932),
        "sombras": (0.012, 0.004, -0.016), "medios": (0.012, 0.004, -0.012), "luces": (0.012, 0.004, -0.016),
        "sat": 0.95, "vibrance": 0.10},
    "stone_light": {  # alta clave, piedra clara: sensación aire/papel, contraste mínimo
        "curva": [(0, 0.050), (0.12, 0.150), (0.35, 0.370), (0.55, 0.570), (0.78, 0.790), (0.92, 0.900), (1, 0.935)],
        "suelo": (0.054, 0.052, 0.046), "techo": (0.945, 0.935, 0.915),
        "sombras": (0.006, 0.003, -0.008), "medios": (0.010, 0.006, -0.010), "luces": (0.014, 0.008, -0.014),
        "sat": 0.90, "vibrance": 0.06},
    "oro_editorial": {  # acento oro #C9A84C en luces; piel cálida; sombras neutras (sin verdear)
        "curva": [(0, 0.032), (0.10, 0.092), (0.30, 0.278), (0.50, 0.500), (0.72, 0.742), (0.90, 0.897), (1, 0.950)],
        "suelo": (0.034, 0.032, 0.028), "techo": (0.958, 0.944, 0.905),
        "sombras": (0.006, 0.002, -0.006), "medios": (0.016, 0.008, -0.016), "luces": (0.028, 0.012, -0.034),
        "sat": 0.94, "vibrance": 0.08},
    "teal_sutil": {  # sombras hacia teal #50B5A2 (≈1 %) con luces cálidas: separación de planos sin neón
        "curva": [(0, 0.030), (0.10, 0.092), (0.30, 0.280), (0.50, 0.500), (0.72, 0.740), (0.90, 0.895), (1, 0.950)],
        "suelo": (0.026, 0.036, 0.036), "techo": (0.958, 0.948, 0.925),
        "sombras": (-0.014, 0.004, 0.010), "medios": (0.006, 0.0, -0.006), "luces": (0.014, 0.006, -0.018),
        "sat": 0.96, "vibrance": 0.08},
}


def f_look(nombre, fuerza=1.0):
    """Bloque de look (curva + tintes + saturación). fuerza 0..1 escala todo hacia el neutro (0 = sin look)."""
    L = LOOKS[nombre]
    k = float(fuerza)
    ident = [(x, x) for x, _ in L["curva"]]
    curva = [(x, x + (y - x) * k) for (x, y), (_, _) in zip(L["curva"], ident)]
    suelo = tuple(c * k for c in L["suelo"])
    techo = tuple(1 + (c - 1) * k for c in L["techo"])
    esc = lambda t: tuple(v * k for v in t)
    f = f_curva(curva, suelo, techo)
    f += f_balance(esc(L["sombras"]), esc(L["medios"]), esc(L["luces"]))
    f += f_saturacion(1 + (L["sat"] - 1) * k, L["vibrance"] * k)
    return f


def cadena_completa(perfil, look="warm_black", fuerza_look=1.0, y_objetivo=Y_PIEL_OBJETIVO, mascara_exposicion=False, matriz="bt709", rango="tv", **kw):
    """Cadena ORDENADA lista para `-vf` (lista de filtros). Devuelve (filtros, parametros).
    Si mascara_exposicion=True se omite la exposición global: úsala en `grafo_exposicion_enmascarada`."""
    prm = parametros_correccion(perfil, y_objetivo=y_objetivo, **kw)
    f = filtros_entrada(True, matriz, rango)
    if not mascara_exposicion:
        f += f_exposicion(prm["gamma"])             # 1 exposición
    f += f_primaria(prm["wb"], prm["rot_deg"], prm["sat_piel"])   # 2 balance de blancos + 3 línea de piel
    if look:
        f += f_look(look, fuerza_look)              # 4 curva + 5 saturación + 6 look
    f += filtros_salida()                           # 7 legal range / BT.709
    return f, prm


def a_vf(filtros):
    return ",".join(filtros)


# --------------------------------------------------------------------------------------------- caras subexpuestas (máscara)
def mascara_persona(rgb8, caja=None, escala=0.35, pluma_px=None):
    """Silueta de la persona (cabeza+cuello+hombros) con GrabCut inicializado por la caja de YuNet. Devuelve float32 0-1 del tamaño del
    fotograma con pluma gaussiana. Sin degradado radial: el borde sigue la silueta, que es lo que evita los halos."""
    import cv2
    H, W = rgb8.shape[:2]
    caja = caja or detectar_cara(rgb8)
    if caja is None:
        return None
    x, y, w, h = caja
    s = escala
    small = cv2.resize(cv2.cvtColor(rgb8, cv2.COLOR_RGB2BGR), (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    sx, sy, sw, sh = (int(v * s) for v in (x, y, w, h))
    m = np.full(small.shape[:2], cv2.GC_BGD, np.uint8)
    x0, x1 = max(0, sx - sw), min(small.shape[1], sx + 2 * sw)
    y0, y1 = max(0, sy - int(0.5 * sh)), small.shape[0]
    m[y0:y1, x0:x1] = cv2.GC_PR_BGD
    xa, xb = max(0, sx - int(0.8 * sw)), min(small.shape[1], sx + int(1.8 * sw))
    m[max(0, sy - int(0.25 * sh)): y1, xa:xb] = cv2.GC_PR_FGD
    m[sy + int(0.2 * sh): sy + int(0.85 * sh), sx + int(0.2 * sw): sx + int(0.8 * sw)] = cv2.GC_FGD
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(small, m, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
    fg = ((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    full = cv2.resize(fg.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    sig = pluma_px or max(4.0, 0.012 * W)
    return np.clip(cv2.GaussianBlur(full, (0, 0), sig), 0, 1)


def halo_anillo(luma_antes, luma_despues, mascara, ancho_px=40):
    """Prueba objetiva anti-halo: diferencia media de luma (0-255) en un ANILLO de `ancho_px` por FUERA de la máscara (>0.5).
    Si |Δ| > 2 hay halo visible. Entradas: arrays 2-D de luma tv antes/después, máscara float 0-1."""
    import cv2
    m = (mascara > 0.5).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ancho_px + 1, 2 * ancho_px + 1))
    anillo = (cv2.dilate(m, k) - cv2.dilate(m, np.ones((9, 9), np.uint8))) > 0
    return float((luma_despues[anillo].mean() - luma_antes[anillo].mean())) if anillo.any() else 0.0


def grafo_exposicion_enmascarada(filtros_cara, filtros_resto, entrada_mascara="[1:v]"):
    """filter_complex que aplica `filtros_cara` solo bajo la máscara y `filtros_resto` fuera (misma cadena sin exposición).
    La máscara (gris) llega como 2º input (vídeo de máscaras o PNG en bucle). Ambas ramas se mezclan en RGB 16 bit y se convierten UNA vez.
    `filtros_*` deben ir SIN filtros_entrada()/filtros_salida() (se añaden aquí)."""
    ent, sal = ",".join(filtros_entrada()), ",".join(filtros_salida())
    a = ",".join(filtros_resto) or "null"
    b = ",".join(filtros_cara) or "null"
    return (f"[0:v]{ent},split[ra][rb];[ra]{a}[g0];[rb]{b}[g1];"
            f"{entrada_mascara}format=gray16le,scale=iw:ih[mk];[g0][g1][mk]maskedmerge,{sal}[vout]")


# --------------------------------------------------------------------------------------------- LUT y HDR
def filtro_lut(ruta_cube, intensidad=1.0):
    """lut3d tetraédrico con intensidad (mezcla). Aplicar SOLO sobre rec709 display-referred (una LUT creativa 'a 709')
    y siempre DESPUÉS de la corrección primaria. Devuelve un fragmento de filter_complex entre etiquetas [in] -> [out]."""
    p = str(ruta_cube).replace("\\", "/").replace(":", r"\:")
    if intensidad >= 0.999:
        return f"[in]lut3d=file='{p}':interp=tetrahedral[out]"
    return (f"[in]split[a][b];[b]lut3d=file='{p}':interp=tetrahedral[l];"
            f"[a][l]blend=all_expr='A*(1-{intensidad:.3f})+B*{intensidad:.3f}'[out]")


def cadena_hdr_a_sdr(npl=100):
    """HLG/PQ (iPhone 'HDR', Dolby Vision perfil 8.4) -> SDR BT.709. Necesario ANTES de todo lo demás: IG/TikTok/Shorts solo conservan
    bien SDR 8 bit BT.709. Mobius conserva detalle de luces sin los recortes de 'clip'."""
    return [f"zscale=t=linear:npl={npl}", "format=gbrpf32le", "tonemap=mobius:desat=0",
            "zscale=p=bt709:t=bt709:m=bt709:r=tv", "format=yuv420p"]


# --------------------------------------------------------------------------------------------- medición con ffmpeg
def comando_signalstats(ruta, crop=None, ffmpeg="ffmpeg", salida="-"):
    """Comando que escribe YMIN/YLOW/YAVG/YHIGH/YMAX, U/V, SAT*, HUE*, TOUT/VREP/BRNG por fotograma.
    `crop`=(w,h,x,y) para medir solo el parche de piel. BRNG = % de píxeles fuera de rango legal."""
    vf = (f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else "") + "signalstats=stat=tout+vrep+brng,metadata=print:file=" + salida
    return [ffmpeg, "-hide_banner", "-v", "error", "-i", str(ruta), "-vf", vf, "-f", "null", "-"]


def parsear_signalstats(texto):
    """texto de metadata=print -> dict clave -> lista de valores por fotograma."""
    out = {}
    for k, v in re.findall(r"lavfi\.signalstats\.(\w+)=([-\d.]+)", texto):
        out.setdefault(k, []).append(float(v))
    return out


def comando_vectorscope(ruta, salida_png, t=10.0, ffmpeg="ffmpeg"):
    """Vectorscopio de ffmpeg (graticule en color, matriz 709) de un fotograma. La línea de piel NO la dibuja ffmpeg: ver `angulo_croma`."""
    return [ffmpeg, "-hide_banner", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(ruta), "-vf",
            "vectorscope=mode=color2:colorspace=709:graticule=color:opacity=0.8:envelope=instant", "-frames:v", "1", str(salida_png)]


# --------------------------------------------------------------------------------------------- criterios de aceptación
def evaluar(perfil_despues, y_objetivo=Y_PIEL_OBJETIVO, tol_y=15.0, stats=None):
    """Lista de (criterio, valor, ok). `stats` = parsear_signalstats() del clip final (opcional)."""
    p = perfil_despues["piel"]
    r = [("piel Y (tv)", round(p["y"], 1), abs(p["y"] - y_objetivo) <= tol_y),
         ("piel ángulo (°)", round(p["angulo"], 1), abs(p["angulo"] - PIEL_LINEA_DEG) <= PIEL_TOL_DEG),
         ("piel croma (radio tv)", round(p["croma"], 1), 14.0 <= p["croma"] <= 40.0),
         ("dispersión piel ΔE00 p90 entre fotogramas", round(perfil_despues["dispersion_de00_p90"], 2), perfil_despues["dispersion_de00_p90"] <= 2.5)]
    if stats:
        r += [("YMAX <= 235", max(stats["YMAX"]), max(stats["YMAX"]) <= 235), ("YMIN >= 16", min(stats["YMIN"]), min(stats["YMIN"]) >= 16),
              ("BRNG medio % <= 0.1", round(float(np.mean(stats.get("BRNG", [0]))), 3), float(np.mean(stats.get("BRNG", [0]))) <= 0.1)]
    return r


# ==================================================================================================== INTEGRACION AL MOTOR
# Lo de arriba son piezas puras / de medicion (investigacion). Lo de abajo es lo que usa imagen.cadena():
#   sonda -> perfil por camara (una vez, color.json) -> parametros -> [mascara] -> cadena 'calidad' (16 bit) o 'rapido' (LUT 3D horneada).
import hashlib
import json
import os
import sys
import tempfile
import time

VERSION_COLOR = 3
LOOK_DEFECTO = "warm_black"
UMBRAL_RAPIDO_S = 180.0      # origen > 3 min -> 'rapido' (LUT); <= 3 min -> 'calidad' (16 bit vivo). Override: modo= / MW_COLOR_MODO
LUT_N = 33
IOU_MINIMO_MASCARA = 0.85    # estabilidad temporal minima de la silueta para usar la mascara estatica
LICENCIA_LUT = ("LUTs generadas por MacroWise Editor a partir de curvas, matrices y balances propios (sin material de terceros).\n"
                "Licencia: propiedad de David Arango / MacroWise; uso comercial libre; no derivan de ninguna LUT ni preset de terceros.\n")


def _fq(ruta):
    """Ruta para dentro de un filtro (Windows), entre comillas simples: dentro de las comillas solo hay que escapar ':' (nivel de opciones).
    Valido en -vf y en -/filter_complex. Una ruta con ' no es representable: se rechaza en vez de romper el grafo en silencio."""
    s = str(ruta).replace("\\", "/")
    if "'" in s:
        raise ValueError(f"ruta con apostrofe no usable en un filtro: {s}")
    return "'" + s.replace(":", r"\:") + "'"


def sonda(ruta, ffprobe="ffprobe"):
    """Matriz/rango/HDR/duracion del fichero (la matriz se HONRA desde la etiqueta: bt470bg -> bt601; sin etiqueta: <720 px -> 601, resto 709)."""
    p = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,pix_fmt,color_space,color_transfer,color_range:format=duration", "-of", "json", str(ruta)],
                       capture_output=True, text=True, check=True)
    j = json.loads(p.stdout)
    st = (j.get("streams") or [{}])[0]
    cs, tr, cr, pf = st.get("color_space"), st.get("color_transfer"), st.get("color_range"), st.get("pix_fmt", "")
    h = int(st.get("height") or 0)
    if cs in ("bt470bg", "smpte170m", "bt601"):
        matriz = "bt601"
    elif cs == "bt709":
        matriz = "bt709"
    elif cs in ("bt2020nc", "bt2020c"):
        matriz = "bt2020"
    else:
        matriz = "bt601" if 0 < h < 720 else "bt709"
    hdr = tr in ("arib-std-b67", "smpte2084")
    if hdr:
        matriz = "bt709"        # tras cadena_hdr_a_sdr ya sale en 709 tv
    return {"matriz": matriz, "rango": "pc" if (cr == "pc" or pf.startswith("yuvj")) else "tv", "hdr": hdr,
            "duracion": float((j.get("format") or {}).get("duration") or 0), "ancho": int(st.get("width") or 0), "alto": h}


def objetivo_y_piel(y_medida):
    """Piel clara/media (Y >= 130): 150. Por debajo, la piel oscura y la cara subexpuesta no se distinguen con una sola cara: NO se fuerza 150, el
    objetivo sube 20 niveles sobre lo medido (continuo: 100..150) y se avisa del tipo. Una piel oscura queda en ~110+-15, no se aclara a 150."""
    obj = float(np.clip(y_medida + 20.0, 100.0, Y_PIEL_OBJETIVO))
    return obj, ("clara/media" if y_medida >= 130 else "oscura o subexpuesta")


def piel_fiable(perfil):
    """(ok, motivo). Una 'piel' sin croma (<14: barba, sombra, camiseta gris) o muy oscura (Y<60) NO es piel: no se corrige con ella."""
    p = perfil["piel"]
    if p["croma"] < 14.0:
        return False, f"croma de 'piel' {p['croma']:.0f} < 14: lo medido no es piel (barba/sombra/gris; p. ej. varias personas en cuadricula)"
    if p["y"] < 60.0:
        return False, f"piel Y={p['y']:.0f} < 60: medicion no fiable"
    return True, ""


def nucleo(prm, look, fuerza=1.0, con_expo=True):
    """Pasos 1-6 (RGB 16 bit puntuales): exposicion -> balance de blancos + linea de piel -> curva/saturacion/look."""
    f = f_exposicion(prm["gamma"]) if con_expo else []
    f += f_primaria(tuple(prm["wb"]), prm["rot_deg"], prm["sat_piel"])
    if look:
        f += f_look(look, fuerza)
    return f


# -------------------------------------------------------------------------------------------------------------- LUT 3D horneada
def hornear_lut(filtros_nucleo, destino, titulo, n=LUT_N, ffmpeg="ffmpeg"):
    """Pasa una imagen identidad 33x1089 (16 bit, r varia mas rapido) por la cadena estatica y la guarda como .cube. Equivale a la cadena viva
    salvo la interpolacion del cubo. Devuelve la ruta."""
    import cv2
    idx = np.arange(n)
    B, G, R = np.meshgrid(idx, idx, idx, indexing="ij")
    img = (np.stack([R, G, B], -1).reshape(n * n, n, 3) / (n - 1))
    u16 = np.round(img * 65535).astype(np.uint16)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    png = destino.with_suffix(".identidad.png")
    cv2.imwrite(str(png), u16[..., ::-1])
    vf = ",".join(["format=gbrp16le"] + list(filtros_nucleo) + ["format=gbrp16le"])
    p = subprocess.run([ffmpeg, "-v", "error", "-i", str(png), "-vf", vf, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"],
                       capture_output=True)
    png.unlink(missing_ok=True)
    if p.returncode or len(p.stdout) != n * n * n * 6:
        raise RuntimeError("no se pudo hornear la LUT: " + p.stderr.decode("utf-8", "replace")[-400:])
    out = np.frombuffer(p.stdout, np.uint16).reshape(n * n * n, 3).astype(np.float64) / 65535.0
    head = ("# MacroWise Editor - LUT propia (generada por nosotros desde curvas/matrices/balances propios, sin terceros).\n"
            "# Licencia: propiedad de MacroWise; uso comercial libre. Espacio: RGB codificado Rec.709 full-range (16 bit) -> igual.\n"
            f"TITLE \"{titulo}\"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
    destino.write_text(head + "\n".join(f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in out) + "\n", encoding="ascii")
    (destino.parent / "LICENCIA_LUTS.txt").write_text(LICENCIA_LUT, encoding="utf-8")
    return destino


def filtro_lut_horneada(cube):
    return f"lut3d=file={_fq(cube)}:interp=tetrahedral"


# -------------------------------------------------------------------------------------------------------------- mascara estatica por camara
def mascara_estatica(frames, perfil):
    """Silueta de persona por camara: GrabCut (caja YuNet) en cada fotograma -> mediana. Mide la estabilidad temporal (IoU de cada
    fotograma contra la mediana): si baja de IOU_MINIMO_MASCARA la persona se mueve demasiado para una mascara fija y NO se usa."""
    ms = []
    for fr in frames:
        caja = detectar_cara(fr)
        if caja is None:
            continue
        m = mascara_persona(fr, caja)
        if m is not None:
            ms.append(m)
    if len(ms) < 4:
        return None
    med = np.median(np.stack(ms), axis=0).astype(np.float32)
    b = med > 0.5
    ious = [float((b & (m > 0.5)).sum() / max(1, (b | (m > 0.5)).sum())) for m in ms]
    return {"mascara": med, "iou_medio": float(np.mean(ious)), "iou_min": float(np.min(ious)), "n": len(ms)}


# -------------------------------------------------------------------------------------------------------------- color.json
def _clave_camara(ruta):
    p = Path(ruta)
    st = p.stat()
    return hashlib.sha1(f"{p.name}|{st.st_size}|{st.st_mtime_ns}|v{VERSION_COLOR}".encode()).hexdigest()[:10]


def _cargar(docs):
    f = Path(docs) / "color.json"
    if f.exists():
        try:
            j = json.loads(f.read_text(encoding="utf-8-sig"))
            if j.get("version") == VERSION_COLOR:
                return j
        except Exception:
            pass
    return {"version": VERSION_COLOR, "camaras": {}}


def _guardar(docs, j):
    f = Path(docs) / "color.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(j, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    os.replace(tmp, f)


def contexto_del_llamador():
    """(ruta_origen, carpeta_00_DOCS) buscados en las variables locales de quien llama (cmd_editar tiene `src` y `docs`). Para no tocar
    __main__.py; si __main__ pasa ruta=/proyecto= explicitos, esto no se usa."""
    try:
        for n in range(2, 9):
            loc = sys._getframe(n).f_locals
            if isinstance(loc.get("src"), (str, Path)) and loc.get("docs") is not None and Path(str(loc["src"])).exists():
                return str(loc["src"]), Path(loc["docs"])
    except ValueError:
        pass
    return None, None


# -------------------------------------------------------------------------------------------------------------- orquestador
def plan_color(ruta, docs=None, proyecto=None, duracion=None, look=None, modo=None, fuerza_look=1.0, referencia=None, forzar=False, ffmpeg="ffmpeg"):
    """Decide y construye el etalonaje de UNA camara/toma. Devuelve dict:
       filtros (lista lista para chain_pre, termina en yuv420p tv BT.709), decisiones (texto), modo, look, params, lut, mascara, avisos."""
    look = look or os.environ.get("MW_COLOR_LOOK") or LOOK_DEFECTO
    if look != "ninguno" and look not in LOOKS:
        raise ValueError(f"look desconocido {look!r}; opciones: {', '.join(LOOKS)}")
    look = None if look == "ninguno" else look
    s = sonda(ruta)
    dur = duracion or s["duracion"]
    env_modo = os.environ.get("MW_COLOR_MODO")
    modo = modo if modo in ("calidad", "rapido") else (env_modo if env_modo in ("calidad", "rapido") else None)
    modo_auto = modo is None
    modo = modo or ("rapido" if dur > UMBRAL_RAPIDO_S else "calidad")
    docs = Path(docs) if docs else None
    proyecto = Path(proyecto) if proyecto else (docs.parent if docs else None)
    dec, avisos = [], []
    clave = _clave_camara(ruta)
    cj = _cargar(docs) if docs else {"version": VERSION_COLOR, "camaras": {}}
    ent = cj["camaras"].get(clave) if not forzar else None
    ref_perfil = None
    if referencia:
        sr = sonda(referencia)
        ref_perfil = perfil_clip(referencia, 12, ffmpeg, None, sr["matriz"], sr["rango"])

    prev = cadena_hdr_a_sdr() if s["hdr"] else None
    if s["hdr"]:
        dec.append("origen HDR (HLG/PQ): tone-mapping a SDR BT.709 antes de todo (mobius)")
    if ent and ent.get("params") is not None and not referencia:
        perfil, prm, masc_meta = ent.get("perfil"), ent["params"], ent.get("mascara")
        dec.append(f"color: parametros de camara leidos de color.json (clave {clave}), no recalculados")
    else:
        frames = fotogramas_rgb(ruta, 12, ffmpeg, prev, s["matriz"], s["rango"])
        perfil = perfil_de_fotogramas(frames)
        masc_meta = None
        motivo_no_fiable = ""
        if perfil is not None:
            ok_piel, motivo_no_fiable = piel_fiable(perfil)
            if not ok_piel:
                perfil_no_fiable, perfil = perfil, None
        if perfil is None:
            prm = {"gamma": 1.0, "wb": [1.0, 1.0, 1.0], "rot_deg": 0.0, "sat_piel": 1.0, "objetivo_y": None, "tipo_piel": None,
                   "avisos": [("piel no fiable: " + motivo_no_fiable if motivo_no_fiable else "no se detecta cara/piel en los 12 fotogramas") + ": sin correccion primaria, solo look"]}
        else:
            if ref_perfil:
                kw = objetivo_desde_referencia(ref_perfil)
                y_obj, tipo_piel = kw["y_objetivo"], "por referencia"
                prm = parametros_correccion(perfil, fuerza_wb=1.0, fuerza_piel=1.0, max_rot=16.0, **kw)
            else:
                y_obj, tipo_piel = objetivo_y_piel(perfil["piel"]["y"])
                if perfil["piel"]["y"] < 125 and perfil["fondo_y_p75"] - perfil["piel"]["y"] >= 45:
                    # contraluz (ventana mucho mas clara que la cara): la cara esta subexpuesta, no es piel oscura -> objetivo 135 (el gamma
                    # tope 0.72 limita lo que se puede subir sin comer ruido)
                    y_obj, tipo_piel = max(y_obj, 135.0), "subexpuesta por contraluz"
                prm = parametros_correccion(perfil, y_objetivo=y_obj)
            prm["wb"] = [float(v) for v in prm["wb"]]
            prm["objetivo_y"], prm["tipo_piel"] = y_obj, tipo_piel
            dec.append(f"piel medida Y={perfil['piel']['y']:.0f} angulo={perfil['piel']['angulo']:.0f} (mediana de {perfil['n_frames']} fotogramas): "
                       f"piel {tipo_piel}, objetivo Y={y_obj:.0f}")
            # cara subexpuesta con ventana detras -> mascara de silueta estatica
            if perfil["piel"]["y"] < 125 and perfil["fondo_y_p75"] - perfil["piel"]["y"] >= 45 and perfil["n_frames"] >= 4:
                r = mascara_estatica(frames, perfil)
                if r and r["iou_medio"] >= IOU_MINIMO_MASCARA:
                    mp = (proyecto / "04_GRAPHICS" if proyecto else Path(tempfile.gettempdir())) / f"color_mascara_{clave}.png"
                    mp.parent.mkdir(parents=True, exist_ok=True)
                    import cv2
                    cv2.imwrite(str(mp), np.round(np.clip(r["mascara"], 0, 1) * 255).astype(np.uint8))
                    masc_meta = {"archivo": str(mp), "iou_medio": r["iou_medio"], "iou_min": r["iou_min"], "n": r["n"], "tipo": "estatica por camara"}
                else:
                    avisos.append("cara subexpuesta con ventana detras pero la silueta es inestable (persona en movimiento): exposicion GLOBAL "
                                  "(el fondo sube con la cara); limite documentado de la mascara estatica")
                    if r:
                        masc_meta = {"descartada": True, "iou_medio": r["iou_medio"], "iou_min": r["iou_min"]}
        avisos += prm.get("avisos", [])
    usa_mascara = bool(masc_meta and masc_meta.get("archivo") and Path(masc_meta["archivo"]).exists())
    # ---- construccion
    entrada = (prev or []) + filtros_entrada(True, s["matriz"], s["rango"])
    salida = filtros_salida()
    ent_s, sal_s = ",".join(entrada), ",".join(salida)
    fA = nucleo(prm, look, fuerza_look, con_expo=not usa_mascara)       # fuera de la silueta
    fB = nucleo(prm, look, fuerza_look, con_expo=True)                  # dentro (cara) con exposicion
    lut = None
    if modo == "rapido":
        lutdir = (proyecto / "04_GRAPHICS" / "luts") if proyecto else Path(tempfile.gettempdir()) / "mw_luts"
        h = hashlib.sha1(("|".join(fA) + "##" + "|".join(fB)).encode()).hexdigest()[:8]
        base = f"{look or 'sin_look'}_{clave}_{h}"
        pa = lutdir / f"{base}{'_fondo' if usa_mascara else ''}.cube"
        if not pa.exists():
            hornear_lut(fA, pa, f"MacroWise {look or 'sin_look'} {clave}")
        lut = [str(pa)]
        if usa_mascara:
            pb = lutdir / f"{base}_cara.cube"
            if not pb.exists():
                hornear_lut(fB, pb, f"MacroWise {look or 'sin_look'} {clave} cara")
            lut.append(str(pb))
        cA, cB = filtro_lut_horneada(lut[0]), (filtro_lut_horneada(lut[1]) if usa_mascara else None)
    else:
        cA, cB = ",".join(fA) or "null", ",".join(fB) or "null"
    if usa_mascara:
        mk = f"movie=filename={_fq(masc_meta['archivo'])},format=gray16le[cmk]"
        filtros = [f"{ent_s},split[cm1][cm2];[cm1]{cA}[cm3];[cm2]{cB}[cm4];{mk};[cm3][cm4][cmk]maskedmerge,{sal_s}"]
    else:
        filtros = entrada + ([cA] if modo == "rapido" else fA) + salida
    dec.append(f"etalonaje 8 pasos (superblancos > exposicion > balance > piel > curva > saturacion > look > salida legal): look {look or 'ninguno'}, "
               f"gamma {prm['gamma']:.3f}, giro de piel {prm['rot_deg']:+.1f} grados, matriz de entrada {s['matriz']}/{s['rango']}")
    dec.append(f"modo {modo}{' (auto por duracion ' + format(dur, '.0f') + ' s)' if modo_auto else ' (forzado)'}: " +
               ("cadena 16 bit viva" if modo == "calidad" else f"LUT 3D {LUT_N}^3 horneada ({', '.join(Path(x).name for x in lut)}), lut3d tetraedrico"))
    if usa_mascara:
        dec.append(f"cara subexpuesta con ventana detras: exposicion solo bajo mascara de silueta estatica (IoU temporal {masc_meta['iou_medio']:.2f}), "
                   "sin cambio de color distinto dentro/fuera")
    for a in avisos:
        dec.append("AVISO: " + a)
    res = {"filtros": filtros, "decisiones": dec, "modo": modo, "look": look, "params": prm, "lut": lut,
           "mascara": masc_meta, "avisos": avisos, "perfil": perfil, "clave": clave, "sonda": s}
    if docs:
        cj["camaras"][clave] = {"fuente": str(ruta), "creado": time.strftime("%Y-%m-%d %H:%M:%S"), "perfil": perfil, "params": prm, "mascara": masc_meta,
                                "look": look, "fuerza_look": fuerza_look, "modo": modo, "sonda": s, "luts": lut, "avisos": avisos}
        _guardar(docs, cj)
    return res
