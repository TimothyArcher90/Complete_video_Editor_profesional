# -*- coding: utf-8 -*-
"""PROPUESTA (NO integrada en mw_editor): corrección y etalonaje de color para presentadores a cámara.

Todo son funciones PURAS: devuelven listas de filtros FFmpeg (strings) o números. Solo `medir_*` / `perfil_clip`
tocan disco (leen fotogramas vía ffmpeg) y `mascara_persona` usa OpenCV (GrabCut). Dependencias: numpy, opencv (cv2.FaceDetectorYN/YuNet).

Principios (validados en docs/investigacion/color.md):
  * UNA sola conversión de entrada (YUV tv BT.709 -> RGB 16 bit) y UNA de salida (RGB -> YUV tv). Nada de `eq` ni
    `huesaturation`: fuerzan 8 bit / yuv444p por dentro (verificado con -v verbose: auto_scale a yuv444p y rgb24).
  * Orden: superblancos -> exposición -> balance de blancos -> tono de piel -> curva -> saturación -> look -> legal range.
  * Los parámetros se calculan UNA vez por clip/cámara con la mediana de N fotogramas (nunca por fotograma: parpadea).
  * Los gains se predicen sobre el RGB de la piel medida (se simula la cadena) antes de ejecutar ffmpeg.
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------------------------- marca / constantes
BRAND_HEX = {"warm_black": "#1A1A17", "warm_dark": "#232320", "stone_light": "#D6D1C8",
             "oro": "#C9A84C", "teal": "#50B5A2", "purpura": "#73247D"}
PIEL_LINEA_DEG = 123.0          # línea de piel (I-line) del vectorscopio: ángulo de atan2(Cr-128, Cb-128), Cb en x, Cr en y
PIEL_TOL_DEG = 6.0              # aceptación: 123 ± 6 (fallo duro a ± 10)
Y_PIEL_OBJETIVO = 150.0         # luma tv (16-235) de la mediana de piel para piel clara/media (~61 IRE). Oscura: 100-125.
BIN_YUNET = Path(r"C:\Users\tante\Projects\macrowise-video-editor\brand\models\face_detection_yunet_2023mar.onnx")

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


def fotogramas_rgb(ruta, n=12, ffmpeg="ffmpeg", filtros_previos=None):
    """n fotogramas repartidos (5 %-95 %) en UNA sola pasada de ffmpeg (rawvideo rgb24, matriz/rango tv BT.709 explícitos). Rápido:
    10x más que un `-ss` por fotograma. `filtros_previos`: lista de filtros a medir (p. ej. la cadena candidata) antes de la lectura."""
    d = duracion(ruta)
    w, h = (int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(ruta)],
                                           capture_output=True, text=True, check=True).stdout.strip().split("x"))
    ini, span = 0.05 * d, 0.90 * d
    vf = ",".join((filtros_previos or []) + [f"fps={n / span:.6f}", "scale=in_range=tv:in_color_matrix=bt709:out_range=full:flags=accurate_rnd+full_chroma_int", "format=rgb24"])
    p = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{span:.3f}", "-i", str(ruta), "-vf", vf, "-frames:v", str(n), "-f", "rawvideo", "-"],
                       capture_output=True, check=True)
    a = np.frombuffer(p.stdout, np.uint8)
    k = a.size // (w * h * 3)
    return a[: k * w * h * 3].reshape(k, h, w, 3)


def perfil_clip(ruta, n=12, ffmpeg="ffmpeg", filtros_previos=None):
    """Perfil estable de un clip: mediana sobre n fotogramas repartidos. Devuelve dict con piel (mediana), neutros (mediana),
    dispersión de la piel entre fotogramas (ΔE00 al valor mediano, p90) y fotogramas usados. Éste es el ÚNICO input de las cadenas.
    Para medir DESPUÉS de una cadena: pasa `filtros_previos`=cadena SIN filtros_entrada/salida, o mide el fichero ya renderizado."""
    pieles, neut = [], []
    for fr in fotogramas_rgb(ruta, n, ffmpeg, filtros_previos):
        p = medir_piel(fr)
        if p is None:
            continue
        pieles.append(p)
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
              "dispersion_de00_p90": float(np.percentile(disp, 90)), "n_frames": len(pieles)}
    if neut:
        perfil["neutros"] = {"rgb": np.median(np.array([x["rgb"] for x in neut]), axis=0).tolist(), "n_frames": len(neut)}
    return perfil


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
def filtros_entrada(recuperar_superblancos=True):
    """YUV tv BT.709 -> RGB 16 bit lineal-a-gamma (codificado). Si el origen trae Y>235 (superblancos, frecuente en iPhone/streams),
    se comprimen ANTES de convertir: si no, el recorte del RGB los destruye (verificado: YMAX 255 en los dos clips de prueba)."""
    f = []
    if recuperar_superblancos:
        f.append("lutyuv=y='if(gt(val,220),220+(val-220)*15/34,val)'")
    f.append("scale=in_range=tv:in_color_matrix=bt709:out_range=full:flags=accurate_rnd+full_chroma_int")
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


def cadena_completa(perfil, look="warm_black", fuerza_look=1.0, y_objetivo=Y_PIEL_OBJETIVO, mascara_exposicion=False, **kw):
    """Cadena ORDENADA lista para `-vf` (lista de filtros). Devuelve (filtros, parametros).
    Si mascara_exposicion=True se omite la exposición global: úsala en `grafo_exposicion_enmascarada`."""
    prm = parametros_correccion(perfil, y_objetivo=y_objetivo, **kw)
    f = filtros_entrada()
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
