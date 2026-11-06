"""Guías visuales de zonas seguras: dibuja sobre un fotograma (o un video corto) los rectángulos PROHIBIDOS de cada plataforma.

Uso (todo sale en docs/guias_zonas/ por defecto):
  python -m mw_editor.guias_zonas                         # 4 guías: 9:16, 1:1, 4:5 y 16:9 sobre fondo de marca
  python -m mw_editor.guias_zonas --frame captura.png     # la misma guía sobre una imagen (p. ej. captura del móvil)
  python -m mw_editor.guias_zonas --video clip.mp4 --t 3  # sobre un fotograma del video (formato = el del video)
  python -m mw_editor.guias_zonas --video clip.mp4 --clip # además, un MP4 corto con la guía superpuesta a todo el video

Cada guía se escribe dos veces:
  guia_<fmt>.png          opaca: fondo Warm Black + rejilla + zonas + leyenda con la confianza de cada cifra
  guia_<fmt>_overlay.png  RGBA transparente: solo las líneas, para superponer a una captura real de la app y comparar

Colores (paleta de marca, sin neón ni degradados): un color por plataforma; la UNIÓN conservadora en lima.
TODAS las cifras de interfaz son terceros o estimadas (ver zonas.py): la guía existe para contrastarlas con capturas reales."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import zonas as zn
from .common import BRAND, FFMPEG, FONTS_DIR, ROOT, dims, hex_rgb, log, run

SALIDA = ROOT / "docs" / "guias_zonas"
# formato interno -> (nombre de archivo, etiqueta)
FORMATOS = {"vertical": ("9x16", "9:16 · 1080x1920"), "cuadrado": ("1x1", "1:1 · 1080x1080"),
            "4x5": ("4x5", "4:5 · 1080x1350"), "horizontal": ("16x9", "16:9 · 1920x1080")}
CODIGOS = {"tiktok": "TT", "instagram-reels": "IR", "youtube-shorts": "YS", "linkedin-vertical": "LI",
           "linkedin-cuadrado": "LI", "linkedin-4x5": "LI", "instagram-feed-4x5": "IF", "youtube-16x9": "YT", "linkedin-16x9": "LI"}
COLOR_PERFIL = {"tiktok": "oro", "instagram-reels": "teal", "youtube-shorts": "purpura", "linkedin-vertical": "terracota",
                "linkedin-cuadrado": "terracota", "linkedin-4x5": "terracota", "instagram-feed-4x5": "teal",
                "youtube-16x9": "oro", "linkedin-16x9": "teal"}
# Posición de los ojos que busca el encuadre (fracción del alto) -> banda de referencia en la guía
OJOS_OBJETIVO = (0.30, 0.38)


def _fuente(mono, tam, peso="Bold"):
    nombre = f"GeistMono-{peso}.ttf" if mono else f"Geist-{peso}.ttf"
    try:
        return ImageFont.truetype(str(FONTS_DIR / nombre), tam)
    except OSError:
        return ImageFont.load_default()


def _rgb(nombre):
    c = BRAND["colores"]
    return hex_rgb(c.get(nombre, nombre))


def _perfiles_del_formato(formato):
    return zn.perfiles_de_formato(formato)


def _linea_discont(d, p0, p1, color, ancho, trazo=18, hueco=12):
    """Línea discontinua (los perfiles se distinguen de la unión, que va continua)."""
    (x0, y0), (x1, y1) = p0, p1
    largo = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if largo == 0:
        return
    ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
    t = 0.0
    while t < largo:
        a = (x0 + ux * t, y0 + uy * t)
        b = (x0 + ux * min(t + trazo, largo), y0 + uy * min(t + trazo, largo))
        d.line([a, b], fill=color, width=ancho)
        t += trazo + hueco


def dibujar_capa(formato, con_etiquetas=True):
    """RGBA transparente (tamaño del lienzo) con las zonas prohibidas de cada perfil + la unión + banda de ojos."""
    W, H = dims(formato)
    esc = W / 1080 if formato != "horizontal" else W / 1920 * 1.15
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa, "RGBA")
    f_et = _fuente(True, max(15, int(19 * esc)))
    f_peq = _fuente(True, max(13, int(16 * esc)), "Regular")
    perfiles = _perfiles_del_formato(formato)
    ancho_l = max(2, int(3 * esc))

    # 1) bandas prohibidas de cada perfil (relleno muy suave + línea de borde discontinua)
    etiquetas = {}      # (lado, valor) -> [codigos]
    for n in perfiles:
        px = zn.perfil_px(n)
        col = _rgb(COLOR_PERFIL[n])
        relleno = col + (20,)
        d.rectangle((0, 0, W, px["arriba"]), fill=relleno)
        d.rectangle((0, H - px["abajo"], W, H), fill=relleno)
        d.rectangle((0, px["arriba"], px["izquierda"], H - px["abajo"]), fill=relleno)
        d.rectangle((W - px["derecha"], px["arriba"], W, H - px["abajo"]), fill=relleno)
        _linea_discont(d, (0, px["arriba"]), (W, px["arriba"]), col + (235,), ancho_l)
        _linea_discont(d, (0, H - px["abajo"]), (W, H - px["abajo"]), col + (235,), ancho_l)
        _linea_discont(d, (px["izquierda"], 0), (px["izquierda"], H), col + (235,), ancho_l)
        _linea_discont(d, (W - px["derecha"], 0), (W - px["derecha"], H), col + (235,), ancho_l)
        for lado, v in (("arriba", px["arriba"]), ("abajo", px["abajo"]), ("izquierda", px["izquierda"]), ("derecha", px["derecha"])):
            etiquetas.setdefault((lado, v), []).append((CODIGOS[n], col))

    # 2) unión conservadora (lima, continua)
    u = zn.union_px("+".join(perfiles), formato)
    lima = _rgb("lima")
    x0, y0, x1, y1 = u["izquierda"], u["arriba"], W - u["derecha"], H - u["abajo"]
    d.rectangle((x0, y0, x1, y1), outline=lima + (255,), width=max(3, int(5 * esc)))

    # 2b) preset 'universal' de Electric Eye (defecto del motor en 9:16): más ancho a la derecha que la unión de plataformas
    if formato == "vertical":
        pu = zn.PRESETS_VERTICAL_PX["universal"]
        _linea_discont(d, (pu["izquierda"], pu["arriba"]), (W - pu["derecha"], pu["arriba"]), lima + (200,), ancho_l, 6, 8)
        _linea_discont(d, (W - pu["derecha"], pu["arriba"]), (W - pu["derecha"], H - pu["abajo"]), lima + (200,), ancho_l, 6, 8)
        _linea_discont(d, (pu["izquierda"], pu["arriba"]), (pu["izquierda"], H - pu["abajo"]), lima + (200,), ancho_l, 6, 8)
        if con_etiquetas:
            d.text((W - pu["derecha"] - 330, y0 + 40), "universal (defecto motor): der 242", font=f_peq, fill=lima + (255,))

    # 3) columna de botones (solo 9:16): x <= 780 desde y >= 840 (criterio propio)
    if formato == "vertical":
        cb = zn.COLUMNA_BOTONES_PX
        d.rectangle((cb["x_max"], cb["desde_y"], W, H - u["abajo"]), outline=_rgb("texto") + (200,), width=max(2, int(3 * esc)))
        if con_etiquetas:
            d.text((cb["x_max"] + 8, cb["desde_y"] + 8), "COLUMNA DE BOTONES\n(criterio propio)", font=f_peq, fill=_rgb("texto") + (235,))

    # 4) banda de ojos objetivo (30-38 %) y caja de subtítulos aproximada
    if zn.es_vertical(formato):
        ya, yb = H * OJOS_OBJETIVO[0], H * OJOS_OBJETIVO[1]
        d.rectangle((x0, ya, x1, yb), outline=_rgb("texto") + (190,), width=max(2, int(3 * esc)))
        if con_etiquetas:
            d.text((x0 + 10, ya + 6), "OJOS OBJETIVO 30-38 %", font=f_peq, fill=_rgb("texto") + (255,))
        sub_bajo = y1
        sub_alto = sub_bajo - 2 * BRAND["subtitulos"]["tam_vertical"] * 1.30 * (W / 1080)
        d.rectangle((x0, sub_alto, x1, sub_bajo), outline=_rgb("blanco") + (190,), width=max(2, int(2 * esc)))
        if con_etiquetas:
            d.text((x0 + 10, sub_alto + 6), "SUBTÍTULOS (2 líneas)", font=f_peq, fill=_rgb("blanco") + (255,))

    # 5) cuadrícula de perfil de Instagram (solo 9:16): recortes 3:4 / 4:5
    if formato == "vertical":
        for k, v in zn.CUADRICULA_INSTAGRAM.items():
            if k == "1:1":
                continue
            ya, yb = v["y_visible"]
            for y in (ya, yb):
                _linea_discont(d, (W - 150, y), (W, y), _rgb("texto") + (200,), max(2, int(3 * esc)), 8, 8)
            if con_etiquetas:
                d.text((W - 150, ya + 4), f"perfil {k}", font=f_peq, fill=_rgb("texto") + (235,))

    # 6) etiquetas de márgenes (código de plataforma + px), apiladas para que no choquen
    if con_etiquetas:
        pila = {}
        y_lat = int(H * 0.045) if formato == "vertical" else int(H * 0.5) - 40
        for (lado, v), items in sorted(etiquetas.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            texto = "/".join(sorted({c for c, _ in items})) + f" {v}"
            col = items[0][1]
            if lado == "arriba":
                k = pila.setdefault("arriba", 0)
                pila["arriba"] += 1
                d.text((12 + k * int(190 * esc), max(2, v - int(24 * esc))), texto, font=f_et, fill=col + (255,))
            elif lado == "abajo":
                k = pila.setdefault("abajo", 0)
                pila["abajo"] += 1
                d.text((12 + k * int(190 * esc), H - v + 5), texto, font=f_et, fill=col + (255,))
            elif lado == "izquierda":
                k = pila.setdefault("izq", 0)
                pila["izq"] += 1
                d.text((8, y_lat + k * int(26 * esc)), "IZQ " + texto, font=f_peq, fill=col + (255,))
            else:
                k = pila.setdefault("der", 0)
                pila["der"] += 1
                t = "DER " + texto
                ancho = d.textlength(t, font=f_peq)
                d.text((W - ancho - 8, y_lat + k * int(26 * esc)), t, font=f_peq, fill=col + (255,))
        d.text((x0 + 10, y0 + 8), "UNIÓN conservadora (rect. seguro)", font=f_et, fill=lima + (255,))
    return capa


def _leyenda(formato):
    """Líneas de texto para el pie de la guía opaca: perfiles, confianza y aviso."""
    perfiles = _perfiles_del_formato(formato)
    ls = []
    for n in perfiles:
        p = zn.PERFILES[n]
        px = p["px"]
        ls.append((COLOR_PERFIL[n], f"{CODIGOS[n]}  {p['nombre']}: arriba {px['arriba']} · abajo {px['abajo']} · izq {px['izquierda']} · der {px['derecha']}  [{p['confianza'].upper()}]"))
    u = zn.union_px("+".join(perfiles), formato)
    ls.append(("lima", f"UNIÓN: arriba {u['arriba']} · abajo {u['abajo']} · izq {u['izquierda']} · der {u['derecha']}  [{zn.confianza_union('+'.join(perfiles), formato).upper()}]"))
    if formato == "vertical":
        pu = zn.PRESETS_VERTICAL_PX["universal"]
        ls.append(("lima", f"universal (defecto del motor, Electric Eye): arriba {pu['arriba']} · abajo {pu['abajo']} · izq {pu['izquierda']} · der {pu['derecha']}  [TERCEROS]"))
    ls.append(("texto", "NINGUNA cifra es oficial: contrastar con capturas reales de cada app."))
    return ls


def guia_opaca(formato, fondo=None):
    """Guía con fondo (imagen dada o Warm Black + rejilla del 10 %) y leyenda."""
    W, H = dims(formato)
    esc = W / 1080 if formato != "horizontal" else W / 1920 * 1.15
    if fondo is not None:
        base = Image.open(fondo).convert("RGB").resize((W, H), Image.LANCZOS)
        base = Image.blend(base, Image.new("RGB", (W, H), _rgb("fondo")), 0.35)
    else:
        base = Image.new("RGB", (W, H), _rgb("fondo"))
        d0 = ImageDraw.Draw(base)
        for i in range(1, 10):
            d0.line([(W * i / 10, 0), (W * i / 10, H)], fill=_rgb("tarjeta"), width=1)
            d0.line([(0, H * i / 10), (W, H * i / 10)], fill=_rgb("tarjeta"), width=1)
    capa = dibujar_capa(formato)
    img = base.convert("RGBA")
    img.alpha_composite(capa)
    d = ImageDraw.Draw(img, "RGBA")
    esc_l = esc * (0.72 if formato == "horizontal" else 1.0)
    f_l = _fuente(True, max(13, int(17 * esc_l)), "Regular")
    nombre, etiqueta = FORMATOS[formato]
    # tarjeta de leyenda OPACA en el centro del área inferior prohibida (no hay video ahí que tapar)
    ls = _leyenda(formato)
    alto_l = int(len(ls) * 24 * esc_l + 60 * esc_l)
    ancho_l = int(W * (0.62 if formato == "horizontal" else 0.92))
    yb = H - 8 * esc
    xl, yl = (W - ancho_l) // 2, int(yb - alto_l)
    d.rounded_rectangle((xl, yl, xl + ancho_l, yl + alto_l), 14, fill=_rgb("tarjeta") + (255,), outline=_rgb("borde") + (255,), width=2)
    d.text((xl + 16, yl + 10), f"ZONAS PROHIBIDAS · {etiqueta}", font=_fuente(True, max(16, int(20 * esc_l)), "Bold"), fill=_rgb("blanco") + (255,))
    for i, (c, t) in enumerate(ls):
        d.text((xl + 16, yl + int(40 * esc_l) + i * int(24 * esc_l)), t, font=f_l, fill=_rgb(c) + (255,))
    return img.convert("RGB")


def fotograma(video, t, salida):
    run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1", salida])
    return salida


def formato_de(w, h):
    r = w / h
    if r > 1.3:
        return "horizontal"
    if r > 0.9:
        return "cuadrado"
    if r > 0.7:
        return "4x5"
    return "vertical"


def clip_con_guia(video, formato, salida):
    """MP4 corto con el overlay de la guía encima de todo el video (para mirar el encuadre en movimiento)."""
    W, H = dims(formato)
    ov = Path(salida).with_suffix(".overlay.png")
    dibujar_capa(formato).save(ov)
    run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", video, "-i", str(ov), "-filter_complex",
         f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[b];[b][1:v]overlay=0:0,format=yuv420p[o]",
         "-map", "[o]", "-map", "0:a?", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", str(salida)])
    ov.unlink(missing_ok=True)
    return salida


_JSON_CLAVE = {"tiktok": "tiktok", "instagram-reels": "instagram_reels", "youtube-shorts": "youtube_shorts", "linkedin-vertical": "linkedin_9x16",
               "linkedin-cuadrado": "linkedin_1x1", "linkedin-4x5": "linkedin_4x5", "youtube-16x9": "youtube_horizontal", "linkedin-16x9": "linkedin_16x9"}


def comprobar_json():
    """Compara PERFILES de zonas.py con docs/investigacion/zonas_seguras.json. Devuelve lista de discrepancias (vacía = coherente).
    instagram-feed-4x5 no está en el JSON (estimación propia) y se salta."""
    import json
    j = json.loads((ROOT / "docs" / "investigacion" / "zonas_seguras.json").read_text(encoding="utf-8"))["plataformas"]
    malas = []
    for n, k in _JSON_CLAVE.items():
        a, b = zn.PERFILES[n]["px"], j[k]["zonas_ui_px"]
        if a != b:
            malas.append(f"{n}: zonas.py {a} != json[{k}] {b}")
        if zn.PERFILES[n]["confianza"] == "oficial":
            malas.append(f"{n}: marcado oficial; ninguna zona de interfaz lo es")
    return malas


def generar(carpeta=SALIDA, formatos=None, frame=None):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    out = []
    for fm in formatos or list(FORMATOS):
        nombre, _ = FORMATOS[fm]
        p1 = carpeta / f"guia_{nombre}.png"
        p2 = carpeta / f"guia_{nombre}_overlay.png"
        guia_opaca(fm, frame).save(p1)
        dibujar_capa(fm, con_etiquetas=True).save(p2)
        out += [p1, p2]
        log("guía", fm, "->", p1.name, "+", p2.name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mw_editor.guias_zonas", description="Guías de zonas seguras por plataforma")
    ap.add_argument("--out", default=str(SALIDA))
    ap.add_argument("--formato", choices=list(FORMATOS) + ["todos"], default="todos")
    ap.add_argument("--frame", help="imagen de fondo (captura o fotograma)")
    ap.add_argument("--video", help="video del que sacar un fotograma (y, con --clip, un MP4 con la guía encima)")
    ap.add_argument("--t", type=float, default=1.0, help="segundo del fotograma (con --video)")
    ap.add_argument("--clip", action="store_true", help="con --video: MP4 corto con la guía superpuesta")
    ap.add_argument("--comprobar", action="store_true", help="solo comprueba que zonas.py coincide con docs/investigacion/zonas_seguras.json")
    a = ap.parse_args(argv)
    if a.comprobar:
        malas = comprobar_json()
        print(chr(10).join(malas) if malas else "OK: los 8 perfiles con JSON coinciden con docs/investigacion/zonas_seguras.json")
        for fm in FORMATOS:
            print(zn.resumen_union(zn.PERFILES_POR_DEFECTO[fm], fm))
        raise SystemExit(1 if malas else 0)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.video:
        from .common import probe
        i = probe(a.video)
        fm = formato_de(i["ancho"], i["alto"])
        nombre = Path(a.video).stem[:30]
        fr = fotograma(a.video, a.t, str(out / f"{nombre}_frame.png"))
        p = out / f"{nombre}_guia_{FORMATOS[fm][0]}.png"
        guia_opaca(fm, fr).save(p)
        log("guía sobre fotograma:", p)
        if a.clip:
            log("clip con guía:", clip_con_guia(a.video, fm, out / f"{nombre}_guia_{FORMATOS[fm][0]}.mp4"))
        return
    generar(out, None if a.formato == "todos" else [a.formato], a.frame)


if __name__ == "__main__":
    main()
