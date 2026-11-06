"""Miniaturas / portadas con la línea gráfica MacroWise.
Principios (de las 3 referencias de David + reglas de marca):
 - La persona es REAL y del propio video: se elige el fotograma más nítido, de cara grande y bien centrada; nunca se deforma.
 - Recorte limpio (BiRefNet-portrait, MIT) sobre fondo SÓLIDO de marca; sin degradados, sin glow.
 - Titular corto (máx. 2 líneas, ≤ 5 palabras): línea 1 blanca, línea 2 en caja de color opaca (lima por defecto; oro/teal/púrpura/terracota
   si el tema es valor/técnico/geo/coste). Etiqueta mono arriba con la taxonomía + logo MW.
 - Zona segura Instagram: el grid recorta 3:4 al centro (y 240–1680 sobre 1920): nada importante fuera. La cara nunca la tapa el texto.
Variantes: A impacto (recorte + fondo sólido), B cajas (foto completa + cajas apiladas), C cinético (foto + texto con palabra clave).
Horizontal 16:9 (YouTube): A y B."""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .common import BRAND, FFMPEG, FONTS_DIR, LOGO_BLANCO, ROOT, color_marca, hex_rgb, log

S = 2  # supermuestreo: se compone al doble y se reduce (bordes suaves)
F_TIT = str(FONTS_DIR / "Geist-Bold.ttf")
F_MONO = str(FONTS_DIR / "GeistMono-Bold.ttf")
_sesion = None


# ---------- elegir el mejor fotograma ----------
def _frame(video, t, ancho=1280):
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={ancho}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)


def elegir_frame(video, dur, n=36, ini=0.0, fin=None, carpeta=None):
    """Puntúa n fotogramas: cara grande y centrada, nitidez en la cara, exposición razonable. Devuelve (t, imagen_BGR_1920, ranking)."""
    fin = fin or dur
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (1280, 720), 0.8, 0.3, 5000)
    res = []
    for i in range(n):
        t = ini + (fin - ini) * (i + 0.5) / n
        img = _frame(video, t)
        if img is None:
            continue
        h, w = img.shape[:2]
        det.setInputSize((w, h))
        _, caras = det.detect(img)
        if caras is None or not len(caras):
            continue
        x, y, fw, fh = [int(v) for v in max(caras, key=lambda c: c[2] * c[3])[:4]]
        conf = float(max(caras, key=lambda c: c[2] * c[3])[-1])
        x, y = max(x, 0), max(y, 0)
        cara = cv2.cvtColor(img[y:y + fh, x:x + fw], cv2.COLOR_BGR2GRAY)
        if cara.size == 0:
            continue
        nit = float(cv2.Laplacian(cara, cv2.CV_64F).var())
        lum = float(cara.mean())
        tam = fh / h
        centro = 1 - abs((x + fw / 2) / w - 0.5) * 1.2
        exp_ok = 1.0 if 85 <= lum <= 185 else 0.6
        score = conf * np.sqrt(tam) * np.log1p(nit) * max(centro, 0.2) * exp_ok * (1.0 if tam > 0.12 else 0.5)
        res.append({"t": round(t, 2), "score": round(score, 3), "nitidez": round(nit, 1), "cara_pct": round(tam * 100, 1), "lum": round(lum, 1)})
    res.sort(key=lambda r: -r["score"])
    if not res:
        raise RuntimeError("No encontré ninguna cara clara en el video; pasa --t o --imagen")
    mejor = res[0]
    # fotograma a resolución completa
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-ss", f"{mejor['t']:.2f}", "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    full = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)
    if carpeta:
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        hoja = []
        for r in res[:6]:
            im = _frame(video, r["t"], 480)
            if im is not None:
                cv2.putText(im, f"{r['t']}s  score {r['score']}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                hoja.append(im)
        if hoja:
            hh = min(i.shape[0] for i in hoja)
            hoja = [i[:hh] for i in hoja]
            filas = [np.hstack(hoja[k:k + 3] + [np.zeros_like(hoja[0])] * (3 - len(hoja[k:k + 3]))) for k in range(0, len(hoja), 3)]
            cv2.imwrite(str(Path(carpeta) / "miniatura_candidatos.jpg"), np.vstack(filas))
        (Path(carpeta) / "miniatura_ranking.json").write_text(json.dumps(res[:10], indent=1), encoding="utf-8")
    return mejor["t"], full, res


# ---------- recorte de la persona ----------
def recortar(img_bgr):
    """RGBA de la persona (BiRefNet-portrait). Alfa limpiado: sin halo (erosión 1 px + suavizado)."""
    global _sesion
    from rembg import new_session, remove
    if _sesion is None:
        _sesion = new_session("birefnet-portrait")
    rgb = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    out = remove(rgb, session=_sesion).convert("RGBA")
    a = out.getchannel("A")
    from scipy import ndimage
    arr = np.array(a)
    lab, n = ndimage.label(arr > 40)
    if n > 1:
        areas = ndimage.sum(arr > 40, lab, range(1, n + 1))
        keep = int(np.argmax(areas)) + 1
        arr = np.where(lab == keep, arr, 0).astype(np.uint8)       # solo la persona principal: sin manos/restos flotantes
    a = Image.fromarray(arr).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.9))
    out.putalpha(a)
    return out


def _cara(img_bgr):
    h, w = img_bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (w, h), 0.7, 0.3, 5000)
    _, caras = det.detect(img_bgr)
    if caras is None or not len(caras):
        return (w * 0.5, h * 0.35, h * 0.25)
    x, y, fw, fh = max(caras, key=lambda c: c[2] * c[3])[:4]
    return (x + fw / 2, y + fh / 2, fh)


# ---------- utilidades de dibujo ----------
def _font(path, px):
    return ImageFont.truetype(path, int(px))


def _ajustar(txt, path, px, ancho_max):
    while px > 40 and _font(path, px).getlength(txt) > ancho_max:
        px -= 4
    return px


def _caja(d, xy, r, fill):
    d.rounded_rectangle(xy, r, fill=fill)


def _chip(d, x, y, texto, color, px=34):
    f = _font(F_MONO, px)
    w = f.getlength(texto.upper()) + px * 1.4
    _caja(d, (x, y, x + w, y + px * 1.9), px * 0.4, hex_rgb(BRAND["colores"]["fondo"]) + (255,))
    d.rounded_rectangle((x, y, x + w, y + px * 1.9), px * 0.4, outline=hex_rgb(color), width=max(3, px // 10))
    d.text((x + px * 0.7, y + px * 0.28), texto.upper(), font=f, fill=hex_rgb(color))
    return w


def _logo(canvas, x, y, ancho):
    if not Path(LOGO_BLANCO).exists():
        return
    lg = Image.open(LOGO_BLANCO).convert("RGBA")
    lg = lg.resize((int(ancho), int(ancho * lg.height / lg.width)), Image.LANCZOS)
    canvas.alpha_composite(lg, (int(x), int(y)))


def _texto_titular(canvas, d, cx, y, l1, l2, ancho_max, px, col_caja, centro=True, x_izq=None):
    """Línea 1 blanca + línea 2 en caja de color opaca. Devuelve y final."""
    px1 = _ajustar(l1, F_TIT, px, ancho_max)
    f1 = _font(F_TIT, px1)
    w1 = f1.getlength(l1)
    x1 = cx - w1 / 2 if centro else x_izq
    d.text((x1 + 4, y + 6), l1, font=f1, fill=(0, 0, 0, 90))            # sombra suave
    d.text((x1, y), l1, font=f1, fill=(255, 255, 255, 255))
    y2 = y + px1 * 1.18
    if not l2:
        return y2
    px2 = _ajustar(l2, F_TIT, px, ancho_max - px * 0.6)
    f2 = _font(F_TIT, px2)
    w2 = f2.getlength(l2)
    pad = px2 * 0.28
    bx = cx - (w2 + pad * 2) / 2 if centro else x_izq
    _caja(d, (bx, y2, bx + w2 + pad * 2, y2 + px2 * 1.22), px2 * 0.14, hex_rgb(col_caja) + (255,))
    texto_col = (26, 26, 23, 255) if col_caja in (BRAND["colores"]["lima"], BRAND["colores"]["oro"], BRAND["colores"]["teal"]) else (255, 255, 255, 255)
    d.text((bx + pad, y2 + px2 * 0.04), l2, font=f2, fill=texto_col)
    return y2 + px2 * 1.22


# ---------- variantes ----------
def variante_A_vertical(persona, base_bgr, titulo, tema, fondo, etiqueta, ruta):
    W, H = 1080 * S, 1920 * S
    bg = hex_rgb(color_marca(fondo)) + (255,)
    lienzo = Image.new("RGBA", (W, H), bg)
    cx, cy, fh = _cara(base_bgr)
    esc = max(0.20 * H / fh, 0.50 * H / (base_bgr.shape[0] - cy))   # cara ~20 % del alto, y el torso llega al borde inferior
    esc = min(esc, 1.7 * S)
    p = persona.resize((int(persona.width * esc), int(persona.height * esc)), Image.LANCZOS)
    ox, oy = int(W * 0.5 - cx * esc), int(H * 0.635 - cy * esc)
    lienzo.paste(p, (ox, oy), p)
    d = ImageDraw.Draw(lienzo)
    acento = color_marca(tema)
    _chip(d, W * 0.075, 270 * S, etiqueta, acento, 30 * S)
    _logo(lienzo, W - 330 * S, 262 * S, 250 * S)
    l1, l2 = titulo
    _texto_titular(lienzo, d, W / 2, 380 * S, l1, l2, W * 0.86, 132 * S, color_marca("lima") if tema == "lima" else acento if tema in ("valor", "tecnico", "geo", "coste") else color_marca("lima"))
    lienzo.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(ruta, quality=95)


def variante_B_vertical(base_bgr, titulo, tema, etiqueta, ruta):
    W, H = 1080 * S, 1920 * S
    cx, cy, fh = _cara(base_bgr)
    h0, w0 = base_bgr.shape[:2]
    ancho_rec = min(w0, h0 * 9 / 16 / 1.0)
    alto_rec = ancho_rec * 16 / 9
    if alto_rec > h0:
        alto_rec = h0
        ancho_rec = h0 * 9 / 16
    x0 = int(min(max(cx - ancho_rec / 2, 0), w0 - ancho_rec))
    y0 = int(min(max(cy - 0.30 * alto_rec, 0), h0 - alto_rec))
    rec = base_bgr[y0:y0 + int(alto_rec), x0:x0 + int(ancho_rec)]
    img = Image.fromarray(cv2.cvtColor(rec, cv2.COLOR_BGR2RGB)).resize((W, H), Image.LANCZOS).convert("RGBA")
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.4).convert("RGBA")
    img = Image.blend(img, Image.new("RGBA", (W, H), (26, 26, 23, 255)), 0.10)     # baja luz pareja: sin degradado
    d = ImageDraw.Draw(img)
    acento = color_marca(tema)
    _chip(d, W * 0.075, 270 * S, etiqueta, acento, 30 * S)
    _logo(img, W - 330 * S, 262 * S, 250 * S)
    l1, l2 = titulo
    col = acento if tema in ("valor", "tecnico", "geo", "coste") else color_marca("lima")
    # cajas apiladas sobre el torso (como la referencia 1), por debajo de la cara
    f_px = 104 * S
    px1 = _ajustar(l1, F_TIT, f_px, W * 0.84)
    f1 = _font(F_TIT, px1)
    y = H * 0.745
    pad = px1 * 0.26
    w1 = f1.getlength(l1)
    bx = W / 2 - (w1 + pad * 2) / 2
    _caja(d, (bx, y, bx + w1 + pad * 2, y + px1 * 1.22), px1 * 0.14, hex_rgb(BRAND["colores"]["fondo"]) + (255,))
    d.text((bx + pad, y + px1 * 0.04), l1, font=f1, fill=(255, 255, 255, 255))
    if l2:
        y2 = y + px1 * 1.28
        px2 = _ajustar(l2, F_TIT, f_px, W * 0.84)
        f2 = _font(F_TIT, px2)
        w2 = f2.getlength(l2)
        pad2 = px2 * 0.26
        bx2 = W / 2 - (w2 + pad2 * 2) / 2
        _caja(d, (bx2, y2, bx2 + w2 + pad2 * 2, y2 + px2 * 1.22), px2 * 0.14, hex_rgb(col) + (255,))
        tc = (26, 26, 23, 255) if col in (BRAND["colores"]["lima"], BRAND["colores"]["oro"], BRAND["colores"]["teal"]) else (255, 255, 255, 255)
        d.text((bx2 + pad2, y2 + px2 * 0.04), l2, font=f2, fill=tc)
    img.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(ruta, quality=95)


def variante_C_vertical(base_bgr, titulo, tema, etiqueta, ruta):
    """Foto completa + texto cinético inclinado (como 'Valor VS Ruido'): línea 1 blanca, línea 2 clave en lima/acento."""
    W, H = 1080 * S, 1920 * S
    cx, cy, fh = _cara(base_bgr)
    h0, w0 = base_bgr.shape[:2]
    alto_rec = h0
    ancho_rec = h0 * 9 / 16
    x0 = int(min(max(cx - ancho_rec / 2, 0), w0 - ancho_rec))
    rec = base_bgr[:, x0:x0 + int(ancho_rec)]
    img = Image.fromarray(cv2.cvtColor(rec, cv2.COLOR_BGR2RGB)).resize((W, H), Image.LANCZOS).convert("RGBA")
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.4).convert("RGBA")
    img = Image.blend(img, Image.new("RGBA", (W, H), (26, 26, 23, 255)), 0.30)
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    l1, l2 = titulo
    col = color_marca(tema) if tema in ("valor", "tecnico", "geo", "coste") else color_marca("lima")
    px = _ajustar(max([l1, l2], key=len), F_TIT, 150 * S, W * 0.80)
    f = _font(F_TIT, px)
    y = H * 0.705
    for linea, c in ((l1, (255, 255, 255, 255)), (l2, hex_rgb(col) + (255,))):
        if not linea:
            continue
        d.text((W * 0.09 + 6, y + 8), linea, font=f, fill=(0, 0, 0, 110))
        d.text((W * 0.09, y), linea, font=f, fill=c)
        y += px * 1.12
    sombra = capa.filter(ImageFilter.GaussianBlur(10 * S))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", (W, H), (0, 0, 0, 120)), (0, 0), sombra.getchannel("A"))
    capa = capa.transform(capa.size, Image.AFFINE, (1, 0.16, -0.16 * H * 0.76, 0, 1, 0), Image.BICUBIC)   # inclinación tipo cursiva
    img.alpha_composite(sh)
    img.alpha_composite(capa)
    d2 = ImageDraw.Draw(img)
    _chip(d2, W * 0.075, 270 * S, etiqueta, color_marca(tema) if tema in ("valor", "tecnico", "geo", "coste") else color_marca("lima"), 30 * S)
    _logo(img, W - 330 * S, 262 * S, 250 * S)
    img.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(ruta, quality=95)


def variante_A_horizontal(persona, base_bgr, titulo, tema, fondo, etiqueta, ruta):
    W, H = 1920 * S, 1080 * S
    lienzo = Image.new("RGBA", (W, H), hex_rgb(color_marca(fondo)) + (255,))
    cx, cy, fh = _cara(base_bgr)
    esc = max(0.34 * H / fh, 0.62 * H / (base_bgr.shape[0] - cy))
    esc = min(esc, 1.7 * S)
    p = persona.resize((int(persona.width * esc), int(persona.height * esc)), Image.LANCZOS)
    ox, oy = int(W * 0.70 - cx * esc), int(H * 0.44 - cy * esc)
    lienzo.paste(p, (ox, oy), p)
    d = ImageDraw.Draw(lienzo)
    acento = color_marca(tema)
    _chip(d, W * 0.05, H * 0.10, etiqueta, acento, 30 * S)
    _logo(lienzo, W * 0.05, H - 150 * S, 280 * S)
    l1, l2 = titulo
    col = acento if tema in ("valor", "tecnico", "geo", "coste") else color_marca("lima")
    _texto_titular(lienzo, d, 0, H * 0.28, l1, l2, W * 0.50, 150 * S, col, centro=False, x_izq=W * 0.05)
    lienzo.convert("RGB").resize((1920, 1080), Image.LANCZOS).save(ruta, quality=95)


# ---------- orquestador ----------
def generar(video=None, imagen=None, t=None, titulo=("", ""), tema="lima", etiqueta="MACROWISE", fondo="fondo", carpeta=".", dur=None, ventana=None):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if imagen:
        base = cv2.imread(str(imagen))
        t_sel = None
    elif t is not None:
        base = _frame(video, t, 1920)
        t_sel = t
    else:
        ini, fin = (ventana or (0.0, dur))
        t_sel, base, ranking = elegir_frame(video, dur, ini=ini, fin=fin, carpeta=carpeta)
        log(f"mejor fotograma: {t_sel}s (ranking en miniatura_ranking.json)")
    persona = recortar(base)
    persona.save(carpeta / "persona_recorte_ALFA.png")
    # el recorte y la cara están en coordenadas del original; el lienzo trabaja a escala S
    base_s = base
    persona_s = persona
    out = {}
    out["A_impacto_vertical"] = carpeta / "thumb_A_impacto_vertical.jpg"
    variante_A_vertical(persona_s, base_s, titulo, tema, fondo, etiqueta, out["A_impacto_vertical"])
    out["B_cajas_vertical"] = carpeta / "thumb_B_cajas_vertical.jpg"
    variante_B_vertical(base_s, titulo, tema, etiqueta, out["B_cajas_vertical"])
    out["C_cinetico_vertical"] = carpeta / "thumb_C_cinetico_vertical.jpg"
    variante_C_vertical(base_s, titulo, tema, etiqueta, out["C_cinetico_vertical"])
    out["A_impacto_horizontal"] = carpeta / "thumb_A_impacto_horizontal.jpg"
    variante_A_horizontal(persona_s, base_s, titulo, tema, fondo, etiqueta, out["A_impacto_horizontal"])
    (carpeta / "miniatura_info.json").write_text(json.dumps({"t": t_sel, "titulo": titulo, "tema": tema, "etiqueta": etiqueta, "fondo": fondo,
                                                              "salidas": {k: str(v) for k, v in out.items()}}, indent=1, ensure_ascii=False), encoding="utf-8")
    return out
