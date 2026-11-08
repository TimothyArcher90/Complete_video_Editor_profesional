"""Composición de capas: ASS -> ProRes 4444 con alfa (subtítulos y gráficos por separado) +
MP4 de referencia con clips (mapas Electric Eye, gráficas Ride the Lightning, infografías HyperFrames) y paneles en cápsula."""
from pathlib import Path

from PIL import Image, ImageDraw

from .zonas import es_vertical
from .common import BRAND, FFMPEG, FONTS_DIR, ffq, hex_rgb, log, probe, run, dims


def _ass_matte(ass, salida):
    """Copia del ASS con TODO en blanco (conserva los alfas): sirve de matte para el canal alfa."""
    import re
    txt = Path(ass).read_text(encoding="utf-8")
    txt = re.sub(r"&H([0-9A-Fa-f]{2})[0-9A-Fa-f]{6}(?=[,\n])", r"&H\1FFFFFF", txt)      # estilos (8 dígitos)
    txt = re.sub(r"(\\[1-4]c)&H[0-9A-Fa-f]{6}&", r"\1&HFFFFFF&", txt)                     # colores inline
    Path(salida).write_text(txt, encoding="utf-8")
    return salida


def ass_a_alfa(ass, dur, formato, salida, fps=30):
    """ASS -> ProRes 4444 con alfa REAL. El filtro ass de ffmpeg no escribe el canal alfa, así que:
    color = ASS sobre negro (premultiplicado) ; alfa = mismo ASS todo en blanco ; alphamerge + unpremultiply."""
    W, H = dims(formato)
    matte = _ass_matte(ass, str(ass) + ".matte.ass")
    fd = ffq(FONTS_DIR)
    src = f"color=c=black:s={W}x{H}:r={fps}:d={dur:.3f}"
    g = (f"[0:v]format=yuv444p,ass=filename='{ffq(ass)}':fontsdir='{fd}'[c];"
         f"[1:v]format=yuv444p,ass=filename='{ffq(matte)}':fontsdir='{fd}',format=gray[m];"
         f"[c][m]alphamerge,format=yuva444p,unpremultiply=inplace=1,format=yuva444p10le[o]")
    run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-f", "lavfi", "-i", src, "-f", "lavfi", "-i", src,
         "-filter_complex", g, "-map", "[o]", *BRAND["encode"]["prores_alfa"], "-an", salida])
    Path(matte).unlink(missing_ok=True)
    return salida


def _png_capsula(w, h, radio, carpeta, nombre):
    """Máscara (gris) y marco (RGBA, borde lima 6 px) de la cápsula. Todo opaco."""
    s = 2
    m = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radio * s, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    mp = Path(carpeta) / f"{nombre}_mask.png"
    m.save(mp)
    fr = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radio * s, outline=hex_rgb(BRAND["colores"]["lima"]) + (255,), width=6 * s)
    fr = fr.resize((w, h), Image.LANCZOS)
    fp = Path(carpeta) / f"{nombre}_marco.png"
    fr.save(fp)
    return mp, fp


def _caja(nombre, formato):
    W, H = dims(formato)
    if es_vertical(formato):
        cajas = {"full": (0, 0, W, H), "panel": (int(W * 0.06), int(H * 0.25), int(W * 0.80), int(H * 0.50)),
                 "arriba": (int(W * 0.06), int(H * 0.15), int(W * 0.80), int(H * 0.36))}
    else:
        cajas = {"full": (0, 0, W, H), "panel": (int(W * 0.27), int(H * 0.10), int(W * 0.68), int(H * 0.80)),
                 "arriba": (int(W * 0.27), int(H * 0.10), int(W * 0.68), int(H * 0.80))}
    return cajas.get(nombre, cajas["panel"])


def referencia(base, plan, formato, srt, graficos_mov, subs_mov, salida, carpeta_tmp, preview_burned_ass=None, graficos_ass=None):
    """MP4 de referencia: base + paneles en cápsula + clips + gráficos + (subs opcionales quemados SOLO en el preview)."""
    W, H = dims(formato)
    info = probe(base)
    dur = info["duracion"]
    if srt and (not Path(srt).exists() or Path(srt).stat().st_size < 5):
        srt = None  # video sin voz: SRT vacío -> ffmpeg no puede abrirlo como pista
    entradas = ["-i", str(base)]
    f = []
    cur = "[0:v]"
    idx = 1

    # --- paneles en cápsula (estilo Aztec Lab con paleta MacroWise) ---
    cap = BRAND["capsula"][formato]
    cx, cy, cw, ch = int(W * cap["x"]), int(H * cap["y"]), int(W * cap["w"]), int(H * cap["h"])
    for pi, pn in enumerate(plan.get("paneles", [])):
        t0, t1 = pn["t"], pn["t"] + pn["dur"]
        en = f"enable='between(t,{t0:.3f},{t1:.3f})'"
        mp, fp = _png_capsula(cw, ch, cap["radio"], carpeta_tmp, f"cap{pi}")
        entradas += ["-f", "lavfi", "-i", f"color=c={BRAND['colores']['fondo']}:s={W}x{H}:r={info.get('fps', 30)}:d={dur:.3f}"]
        bg = idx
        idx += 1
        entradas += ["-loop", "1", "-i", str(mp)]
        mk = idx
        idx += 1
        entradas += ["-loop", "1", "-i", str(fp)]
        fr = idx
        idx += 1
        f.append(f"{cur}[{bg}:v]overlay=0:0:{en}[pb{pi}]")
        # recorte de la cápsula: parte superior-centro del vídeo base (donde está la cara)
        bw = int(cw * 1.0)
        if es_vertical(formato):
            alto_src = int(W * ch / cw)
            f.append(f"[0:v]crop={W}:{alto_src}:0:{int(H * 0.12)},scale={cw}:{ch}:flags=lanczos,format=yuva420p[cp{pi}a]")
        else:
            ancho_src = int(H * cw / ch)
            f.append(f"[0:v]crop={ancho_src}:{H}:{(W - ancho_src) // 2}:0,scale={cw}:{ch}:flags=lanczos,format=yuva420p[cp{pi}a]")
        f.append(f"[{mk}:v]format=gray[mk{pi}]")
        f.append(f"[cp{pi}a][mk{pi}]alphamerge[cp{pi}]")
        f.append(f"[pb{pi}][cp{pi}]overlay={cx}:{cy}:{en}:format=auto[pc{pi}]")
        f.append(f"[pc{pi}][{fr}:v]overlay={cx}:{cy}:{en}:format=auto[pm{pi}]")
        cur = f"[pm{pi}]"
        if pn.get("clip"):
            plan.setdefault("clips", []).append({"t": pn["t"], "dur": pn["dur"], "archivo": pn["clip"], "caja": pn.get("caja", "panel")})

    # --- clips (mapas / gráficas / infografías) ---
    for ci, c in enumerate(plan.get("clips", [])):
        t0, t1 = c["t"], c["t"] + c["dur"]
        archivo = Path(c["archivo"])
        if not archivo.exists():
            log(f"AVISO: clip no existe: {archivo}")
            continue
        es_img = archivo.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        if es_img:
            entradas += ["-loop", "1", "-t", f"{c['dur']:.3f}", "-i", str(archivo)]
        else:
            entradas += ["-i", str(archivo)]
        k = idx
        idx += 1
        x, y, w, h = _caja(c.get("caja", "panel"), formato)
        en = f"enable='between(t,{t0:.3f},{t1:.3f})'"
        f.append(f"[{k}:v]setpts=PTS-STARTPTS+{t0:.3f}/TB,scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,format=yuva420p[cl{ci}]")
        f.append(f"{cur}[cl{ci}]overlay=x={x}+({w}-w)/2:y={y}+({h}-h)/2:{en}:eof_action=pass:format=auto[cm{ci}]")
        cur = f"[cm{ci}]"

    # --- gráficos de marca (tarjetas) ---
    if graficos_mov and Path(graficos_mov).exists():
        entradas += ["-i", str(graficos_mov)]
        g = idx
        idx += 1
        f.append(f"{cur}[{g}:v]overlay=0:0:format=auto[gm]")
        cur = "[gm]"
    if graficos_ass and Path(graficos_ass).exists():      # largos (>10 min) no generan ProRes alfa: las tarjetas se queman desde el ASS en la versión de entrega
        f.append(f"{cur}ass=filename='{ffq(graficos_ass)}':fontsdir='{ffq(FONTS_DIR)}'[gass]")
        cur = "[gass]"
    if preview_burned_ass:
        f.append(f"{cur}ass=filename='{ffq(preview_burned_ass)}':fontsdir='{ffq(FONTS_DIR)}'[vf]")
        cur = "[vf]"
    f.append(f"{cur}format=yuv420p[vout]")
    script = Path(carpeta_tmp) / "ref.graph.txt"
    script.write_text(";\n".join(f), encoding="utf-8")
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", *entradas]
    if srt and not preview_burned_ass:
        cmd += ["-i", str(srt)]
    cmd += ["-/filter_complex", script, "-map", "[vout]", "-map", "0:a"]
    if srt and not preview_burned_ass:
        cmd += ["-map", f"{idx}:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa"]
    cmd += ["-shortest", *BRAND["encode"]["x264"], "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", salida]
    run(cmd)
    return salida
