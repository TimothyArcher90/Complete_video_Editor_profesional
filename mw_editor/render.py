"""Render del vídeo base en UNA sola codificación (sin pérdida generacional):
origen -> denoise -> exposición/color -> tomas (recorte + escala) -> concat -> nitidez suave -> x264 crf17 slow + audio limpio."""
from pathlib import Path

from .common import BRAND, FFMPEG, log, run


def render_base(src, recortes, wav, salida, formato, chain_pre, chain_post, fps=None, mostrar_progreso=False, luz=1.0, pilar=False):
    from .common import dims
    W, H = dims(formato)
    n = len(recortes)
    g = [f"[0:v]{','.join(chain_pre)}[vs]" if chain_pre else "[0:v]null[vs]"]
    g.append(f"[vs]split={n}{''.join(f'[s{i}]' for i in range(n))}" if n > 1 else "[vs]null[s0]")
    for i, (a, b, x, y, w, h, *extra) in enumerate(recortes):
        if pilar:  # origen vertical -> salida horizontal: video centrado a altura completa sobre su propio fondo desenfocado y oscurecido
            g.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,split=2[pa{i}][pb{i}]")
            g.append(f"[pa{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.14[pbg{i}]")
            g.append(f"[pb{i}]scale=-2:{H}:flags=lanczos[pfg{i}]")
            g.append(f"[pbg{i}][pfg{i}]overlay=(W-w)/2:0,setsar=1[v{i}]")
        elif extra and isinstance(extra[0], dict) and "k" in extra[0]:
            # Cara enorme: video reducido a escala k, centrado, sobre su propio fondo desenfocado y oscurecido (como el modo 'pilar').
            k, yf = float(extra[0]["k"]), float(extra[0]["yf"])
            fw, fh = int(round(W * k / 2) * 2), int(round(H * k / 2) * 2)
            g.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},split=2[pa{i}][pb{i}]")
            # fondo SÓLIDO Warm Black (un fondo desenfocado del propio video se veía como una mancha clara con camisas blancas)
            g.append(f"[pa{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},drawbox=x=0:y=0:w=iw:h=ih:color=0x1A1A17:t=fill[pbg{i}]")
            g.append(f"[pb{i}]scale={fw}:{fh}:flags=lanczos[pfg{i}]")
            g.append(f"[pbg{i}][pfg{i}]overlay=(W-w)/2:{int(round(H * yf / 2) * 2)},setsar=1[v{i}]")
        elif extra and isinstance(extra[0], dict) and "vis" in extra[0] and extra[0]["vis"] < h - 2:
            # Encuadre con relleno inferior: el recorte ideal baja más allá del borde del origen (para subir la cara sobre los subtítulos).
            # Arriba va la parte real (vis) a escala completa; debajo, su propio borde inferior reflejado, desenfocado y algo oscurecido,
            # fundido en una franja corta para que no se vea la costura (sin degradados de color ni neón). Ese hueco cae bajo los
            # subtítulos y la interfaz de la app.
            vis = int(extra[0]["vis"])
            hv = min(H - 2, int(round(H * vis / h / 2) * 2))
            ph = H - hv
            tr = max(4, min(90, int(ph * 1.5) // 2 * 2))
            g.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,crop={w}:{vis}:{x}:{y},scale={W}:{hv}:flags=lanczos,setsar=1,split=3[pa{i}][pb{i}][pc{i}]")
            g.append(f"[pa{i}]crop={W}:{hv - tr}:0:0[fa{i}]")                                          # parte real sin tocar
            g.append(f"[pb{i}]crop={W}:{tr}:0:{hv - tr}[fb{i}]")                                       # franja de fundido (real)
            g.append(f"[pc{i}]crop={W}:{ph + tr}:0:{hv - ph - tr},drawbox=x=0:y=0:w=iw:h=ih:color=0x1A1A17:t=fill,split=2[sa{i}][sb{i}]")
            g.append(f"[sa{i}]crop={W}:{tr}:0:0[sfa{i}]")                                              # franja de fundido (reflejo)
            g.append(f"[sb{i}]crop={W}:{ph}:0:{tr}[sfb{i}]")                                           # resto del relleno
            g.append(f"[fb{i}][sfa{i}]blend=all_expr='A*(1-Y/{tr})+B*(Y/{tr})'[tf{i}]")
            g.append(f"[fa{i}][tf{i}][sfb{i}]vstack=inputs=3,setsar=1[v{i}]")
        else:
            g.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1[v{i}]")
    cat = "".join(f"[v{i}]" for i in range(n))
    post = ("," + ",".join(chain_post)) if chain_post else ""
    fpsf = f",fps={fps}" if fps else ""
    if luz and luz > 0:
        k = float(luz)
        # Luz de estudio suave: la cara (elipse fija, porque el encuadre ya la centra) sube de gamma y se calienta apenas;
        # el fondo baja un punto. Sin glow, sin degradado de color: solo exposición y balance, altas luces rodadas.
        g.append(f"{cat}concat=n={n}:v=1:a=0{post}{fpsf},split=2[la][lb]")
        g.append(f"[la]eq=gamma={1 + 0.07 * k:.3f}:brightness={0.012 * k:.3f},colorbalance=rm={0.025 * k:.3f}:gm={0.008 * k:.3f}:bm={-0.025 * k:.3f}:rs={0.02 * k:.3f}:bs={-0.015 * k:.3f}[lit]")
        g.append(f"[lb]eq=brightness={-0.03 * k:.3f}:contrast={1 + 0.03 * k:.3f}[dim]")
        g.append(f"[2:v]format=gray,scale={W}:{H}[mk]")
        g.append("[dim][lit][mk]maskedmerge,format=yuv420p[vout]")
    else:
        g.append(f"{cat}concat=n={n}:v=1:a=0{post}{fpsf},format=yuv420p[vout]")
    script = Path(salida).with_suffix(".graph.txt")
    script.write_text(";\n".join(g), encoding="utf-8")
    enc = BRAND["encode"]
    dur_total = sum(b - a for a, b, *_ in recortes)
    entrada_mask = []
    if luz and luz > 0:
        mp = Path(salida).with_suffix(".luz.png")
        _mascara_luz(W, H, mp)
        entrada_mask = ["-loop", "1", "-framerate", str(fps or 30), "-i", str(mp)]
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-stats", "-i", src, "-i", wav, *entrada_mask,
           "-/filter_complex", script, "-map", "[vout]", "-map", "1:a", "-t", f"{dur_total:.3f}",
           *enc["x264"], "-c:a", "aac", "-b:a", "256k", "-ac", "2", "-ar", "48000", "-movflags", "+faststart", salida]
    log(f"render base {formato} {W}x{H}: {n} tomas -> {Path(salida).name}")
    run(cmd, capture=not mostrar_progreso)
    script.unlink(missing_ok=True)
    Path(salida).with_suffix(".luz.png").unlink(missing_ok=True)
    return salida


def _mascara_luz(W, H, ruta):
    """Elipse suave centrada donde el encuadre deja la cara (x 50 %, y 37 %: ojos al 30-38 %, la cara baja hasta ~46 %). 8 bit, gris."""
    import numpy as np
    from PIL import Image
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx - 0.50 * W) / (0.40 * W)) ** 2 + ((yy - 0.37 * H) / (0.27 * H)) ** 2
    m = np.exp(-d * 1.6)
    Image.fromarray((m * 255).astype("uint8"), "L").save(ruta)
