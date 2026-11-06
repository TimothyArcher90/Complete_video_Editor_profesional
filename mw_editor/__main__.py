"""CLI: python -m mw_editor <comando>
  proyecto NOMBRE            crea 00_DOCS..06_EXPORT
  editar VIDEO --out DIR     análisis -> transcripción -> cortes -> audio -> imagen -> planos -> base + subtítulos (+ capas si hay plan)
  componer --out DIR --plan plan.json   (re)genera tarjetas, ProRes con alfa y MP4 de referencia sin repetir el trabajo pesado
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import analizar as an, audio as au, componer as co, cortes as cu, detectar as de, imagen as im, planos as pl, render as rn, subs as su, transcribir as tr
from .common import BRAND, FFMPEG, crear_proyecto, dims, log, probe, siguiente_version, SUBCARPETAS


def _carpetas(out):
    out = Path(out)
    for s in SUBCARPETAS:
        (out / s).mkdir(parents=True, exist_ok=True)
    return {k: out / k for k in SUBCARPETAS}


def cmd_editar(a):
    from .zonas import set_preset
    set_preset(getattr(a, "zona", "universal") or "universal")
    if getattr(a, "rapido", False):
        BRAND["encode"]["x264"] = ["-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        a.modelo = "small" if a.modelo == "medium" else a.modelo
    src = str(Path(a.video).resolve())
    nombre = a.nombre or Path(src).stem[:40].replace(" ", "_")
    C = _carpetas(a.out)
    exp, docs, trn = C["06_EXPORT"], C["00_DOCS"], C["03_TRANSCRIPT"]
    info = probe(src)
    # F1 medición
    analisis_p = docs / "analisis.json"
    analisis = json.loads(analisis_p.read_text(encoding="utf-8-sig")) if analisis_p.exists() and not a.rehacer else an.analizar(src, docs)
    for d in analisis.get("diagnostico", []):
        log("diagnóstico:", d)
    for d in analisis.get("no_se_puede_arreglar", []):
        log("NO SE PUEDE ARREGLAR EN POST:", d)
    # F4 transcripción
    wp = trn / "words.json"
    if not info.get("tiene_audio"):
        log("el video NO tiene audio: sin transcripción ni subtítulos; se genera pista silenciosa")
        palabras = []
        wp.write_text("[]", encoding="utf-8")
    elif wp.exists() and not a.rehacer:
        palabras = json.loads(wp.read_text(encoding="utf-8-sig"))
    else:
        palabras = tr.transcribir(src, wp, idioma=a.idioma, modelo=a.modelo)
    dur = info["duracion"]
    # F5 cortes técnicos
    if a.sin_cortes:
        keep = [(0.0, round(dur, 3))]
        plan_c = {"keep": keep, "quitados": [], "duracion_original": dur, "duracion_final": dur}
    else:
        plan_c = cu.plan_cortes(palabras, dur, pausa_max=a.pausa_max)
        keep = [tuple(k) for k in plan_c["keep"]]
    cu.guardar(plan_c, C["05_PROJECT"] / "cut_plan.json")
    log(f"cortes: {len(plan_c['quitados'])} · {dur:.1f}s -> {plan_c['duracion_final']:.1f}s")
    pf = cu.remapear_palabras(palabras, keep)
    (trn / "words_final.json").write_text(json.dumps(pf, ensure_ascii=False, indent=1), encoding="utf-8")
    de.transcript_legible(pf, trn / "transcript_final.txt")
    cand = de.candidatos(pf, trn / "candidatos.json")
    log(f"candidatos de capas: {len(cand)} (ver 03_TRANSCRIPT/candidatos.json)")
    # F3 audio (una vez; es común a ambos formatos)
    n = 1
    while any(exp.glob(f"{nombre}_*_v{n}_base.mp4")):  # nunca sobrescribir: v1, v2, v3 ...
        n += 1
    wav = C["02_AUDIO"] / f"{nombre}_v{n}_voz_limpia.wav"
    if not info.get("tiene_audio"):
        import subprocess as _sp
        _sp.run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{sum(b - a_ for a_, b in keep):.3f}", "-c:a", "pcm_s24le", str(wav)], check=True)
        ra = {"decisiones": ["sin audio de origen"], "lufs_final": float("nan"), "pico_final_dbtp": float("nan"), "ok": True, "revertido": False}
    else:
        ra = au.procesar(src, str(wav), analisis, keep=keep)
    _cad = im.cadena(analisis.get("video"), info, look=getattr(a, "look", None), modo=getattr(a, "color_modo", None), ruta=src, proyecto=a.out)
    (docs / "reparacion.json").write_text(json.dumps({"audio": ra, "imagen": list(_cad[1])}, indent=2, ensure_ascii=False), encoding="utf-8")
    log("audio:", "; ".join(ra["decisiones"]), f"-> {ra['lufs_final']:.1f} LUFS, pico {ra['pico_final_dbtp']:.1f} dBTP", "(REVERTIDO)" if ra["revertido"] else "")
    # F3 imagen: cadenas
    pre, dec_i = list(_cad[0]), list(_cad[1])
    for d_ in dec_i:
        log("imagen:", d_)
    post = [pre.pop()] if pre and pre[-1].startswith("unsharp") else []
    # caras
    caras = pl.detectar_caras(src, dur)
    formatos = {"ambos": ["vertical", "horizontal"], "todos": ["vertical", "cuadrado", "horizontal"]}.get(a.formato, [a.formato])
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8-sig")) if a.plan else {}
    salidas = {}
    if a.plan:
        import shutil as _sh
        _sh.copyfile(a.plan, docs / "plan_grafico.json")
    for fm in formatos:
        W, H = dims(fm)
        tomas = pl.tomas(keep, palabras, objetivo=(6.0 if (W > H and a.toma == 3.6) else a.toma))   # largo horizontal: plano mediano 4,5-6 s (preset_largo)
        rec = pl.recortes(tomas, caras, info["ancho"], info["alto"], W, H, zoom_alt=a.zoom)
        base = exp / f"{nombre}_{fm}_v{n}_base.mp4"
        rn.render_base(src, rec, str(wav), str(base), fm, pre, post, fps=round(info["fps"]) if info.get("fps") else None, mostrar_progreso=a.progreso, luz=0.0 if a.sin_luz else a.luz, pilar=(W > H and info["ancho"] < info["alto"]))
        salidas[fm] = base
        _capas(base, pf, plan, fm, nombre, n, exp, C, a.preview, a.estilo)
    log("LISTO:", ", ".join(str(v) for v in salidas.values()))


def _capas(base, pf, plan, fm, nombre, n, exp, C, preview=False, estilo="visual"):
    """Subtítulos, tarjetas, ProRes alfa y referencia para un formato."""
    dur = probe(str(base))["duracion"]
    ass_s = exp / f"{nombre}_{fm}_v{n}_subtitulos.ass"
    gs = su.ass_subtitulos_estilo(pf, fm, ass_s, estilo, ocultar=su.ocultar_desde_plan(plan))
    srt = exp / f"{nombre}_v{n}_subtitulos.srt"
    su.srt_frases(pf, srt)
    log(f"{fm}: {gs} grupos de subtítulo dinámico + SRT editable")
    if dur > 600 and not os.environ.get("MW_FORZAR_ALFA"):
        # Largo (>10 min): un ProRes 4444 de todo el video tardaria horas y pesaria varios GB. El master editable es SRT + ASS
        # (pista de subtitulos); el *_base.mp4 ya es el entregable. MW_FORZAR_ALFA=1 fuerza el ProRes completo.
        log(f"{fm}: video largo ({dur / 60:.0f} min): sin ProRes alfa ni REFERENCIA (SRT + ASS editables; el *_base.mp4 es el entregable)")
        if any(plan.get(k) for k in ("lower_thirds", "titulos", "cifras", "titulos_grandes", "cta")):
            ass_g = exp / f"{nombre}_{fm}_v{n}_graficos.ass"
            for av in su.ass_graficos(plan, fm, ass_g):
                log("AVISO:", av)
        return
    subs_mov = co.ass_a_alfa(str(ass_s), dur, fm, str(exp / f"{nombre}_{fm}_v{n}_subtitulos_ALFA.mov"))
    graf_mov = None
    if any(plan.get(k) for k in ("lower_thirds", "titulos", "cifras", "titulos_grandes", "cta")):
        ass_g = exp / f"{nombre}_{fm}_v{n}_graficos.ass"
        for av in su.ass_graficos(plan, fm, ass_g):
            log("AVISO:", av)
        graf_mov = co.ass_a_alfa(str(ass_g), dur, fm, str(exp / f"{nombre}_{fm}_v{n}_graficos_ALFA.mov"))
    tmp = C["04_GRAPHICS"] / "_tmp"
    tmp.mkdir(exist_ok=True)
    ref = exp / f"{nombre}_{fm}_v{n}_REFERENCIA.mp4"
    co.referencia(str(base), dict(plan), fm, srt, graf_mov, subs_mov, str(ref), tmp)
    if preview:
        pv = exp / f"{nombre}_{fm}_v{n}_PREVIEW_subs_quemados_NO_ENTREGAR.mp4"
        co.referencia(str(base), dict(plan), fm, None, graf_mov, subs_mov, str(pv), tmp, preview_burned_ass=str(ass_s))
    log("referencia:", ref)


def cmd_componer(a):
    C = _carpetas(a.out)
    exp, trn = C["06_EXPORT"], C["03_TRANSCRIPT"]
    pf = json.loads((trn / "words_final.json").read_text(encoding="utf-8-sig"))
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8-sig"))
    (C["00_DOCS"] / "plan_grafico.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    bases = sorted(exp.glob("*_base.mp4"))
    if a.formato != "ambos":
        bases = [b for b in bases if f"_{a.formato}_" in b.name]
    if a.version:
        bases = [b for b in bases if f"_v{a.version}_" in b.name]
    for b in bases:
        fm = next(f for f in ("vertical", "cuadrado", "4x5", "horizontal") if f"_{f}_" in b.name)
        nombre = b.name.split(f"_{fm}_v")[0]
        n = int(b.name.split(f"_{fm}_v")[1].split("_")[0])
        _capas(b, pf, plan, fm, nombre, n, exp, C, a.preview, a.estilo)


def cmd_miniatura(a):
    from . import miniatura as mi
    out = Path(a.out)
    l = (a.titulo.split("|") + [""])[:2]
    dur = probe(a.video)["duracion"] if a.video else None
    res = mi.generar(video=a.video, imagen=a.imagen, t=a.t, titulo=(l[0].strip(), l[1].strip()), tema=a.tema, etiqueta=a.etiqueta, fondo=a.fondo, carpeta=out, dur=dur)
    for k, v in res.items():
        log("miniatura", k, v)


def cmd_lote(a):
    from .lote import lote
    filas = lote(a.carpeta, a.out, formato=a.formato, idioma=a.idioma, rapido=not a.lento, estilo=a.estilo)
    for nombre, estado, seg, res, err in filas:
        log(f"{estado}  {nombre}  ({seg:.0f}s)")


def cmd_entrada(a):
    from .entrada import entrada
    entrada(inbox=a.inbox, formato=a.formato)


def cmd_qc(a):
    from .qc import qc_proyecto_completo, resumen_estado
    for proj in a.proyectos:
        res, resumen = qc_proyecto_completo(proj, a.perfil)
        log(f"{Path(proj).name}: {resumen_estado(res)} · puntuación {resumen.get('puntuacion')}")
        for fm, cks in res.items():
            for c in cks:
                if c["estado"] not in ("PASS", "N/A"):
                    log(f"  {fm}: {c['estado']} {c['check']} — {c['detalle']}")


def main():
    ap = argparse.ArgumentParser(prog="mw_editor")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("proyecto")
    p.add_argument("nombre")
    p.add_argument("--raiz")
    e = sp.add_parser("editar")
    e.add_argument("video")
    e.add_argument("--out", required=True)
    e.add_argument("--nombre")
    e.add_argument("--formato", choices=["vertical", "horizontal", "cuadrado", "4x5", "ambos", "todos"], default="vertical")
    e.add_argument("--idioma", default="es")
    e.add_argument("--modelo", default="medium")
    e.add_argument("--plan")
    e.add_argument("--sin-cortes", action="store_true")
    e.add_argument("--pausa-max", type=float, default=0.45)
    e.add_argument("--toma", type=float, default=3.6, help="duración objetivo de cada toma (s)")
    e.add_argument("--zoom", type=float, default=1.12, help="punch-in alterno")
    e.add_argument("--luz", type=float, default=1.0, help="intensidad de la luz de estudio sobre la cara (0 = apagada)")
    e.add_argument("--sin-luz", action="store_true")
    e.add_argument("--estilo", choices=["visual", "clasico", "karaoke-cajas", "minimo", "pildora"], default="visual", help="subtítulos: visual (palabra clave en caja de color) o clasico")
    e.add_argument("--zona", choices=["estandar", "meta-reels", "universal"], default="universal", help="perfil de zona segura 9:16 (universal = sirve en todas las redes)")
    e.add_argument("--look", choices=["warm_black", "stone_light", "oro_editorial", "teal_sutil", "ninguno"], default=None, help="look de color de marca (defecto warm_black)")
    e.add_argument("--color-modo", dest="color_modo", choices=["calidad", "rapido"], default=None, help="calidad = 16 bit; rapido = LUT 3D horneada (auto por duracion)")
    e.add_argument("--rapido", action="store_true", help="pruebas: x264 veryfast + Whisper small")
    e.add_argument("--rehacer", action="store_true")
    e.add_argument("--preview", action="store_true", help="además, MP4 con subtítulos quemados SOLO para mirar en el móvil")
    e.add_argument("--progreso", action="store_true")
    en = sp.add_parser("entrada", help="procesa los videos nuevos de INPUT_AQUI")
    en.add_argument("--inbox")
    en.add_argument("--formato", choices=["vertical", "horizontal", "cuadrado", "4x5", "ambos", "todos"], default="ambos")
    q = sp.add_parser("qc", help="mide proyectos ya editados (sin re-renderizar)")
    q.add_argument("proyectos", nargs="+")
    q.add_argument("--perfil")
    lo = sp.add_parser("lote")
    lo.add_argument("carpeta")
    lo.add_argument("--out", required=True)
    lo.add_argument("--formato", choices=["vertical", "horizontal", "cuadrado", "4x5", "ambos", "todos"], default="ambos")
    lo.add_argument("--idioma", default="auto")
    lo.add_argument("--estilo", choices=["visual", "clasico", "karaoke-cajas", "minimo", "pildora"], default="visual")
    lo.add_argument("--lento", action="store_true", help="calidad final (preset slow, Whisper medium) en vez del modo rápido de pruebas")
    m = sp.add_parser("miniatura")
    m.add_argument("--video")
    m.add_argument("--imagen")
    m.add_argument("--t", type=float, help="segundo exacto del fotograma (si no, lo elige solo)")
    m.add_argument("--titulo", required=True, help="'Línea 1|Línea 2' (máx. 5 palabras en total)")
    m.add_argument("--tema", default="lima", choices=["lima", "valor", "tecnico", "geo", "coste"])
    m.add_argument("--etiqueta", default="MACROWISE")
    m.add_argument("--fondo", default="fondo", help="color de marca del fondo sólido: fondo|tarjeta|teal|purpura|oro|lima")
    m.add_argument("--out", required=True)
    c = sp.add_parser("componer")
    c.add_argument("--out", required=True)
    c.add_argument("--plan", required=True)
    c.add_argument("--formato", choices=["vertical", "horizontal", "cuadrado", "4x5", "ambos", "todos"], default="ambos")
    c.add_argument("--preview", action="store_true")
    c.add_argument("--estilo", choices=["visual", "clasico", "karaoke-cajas", "minimo", "pildora"], default="visual")
    c.add_argument("--version", type=int, help="solo esta versión (v1, v2 ...)")
    rf = sp.add_parser("referencia", help="copia una referencia a REFERENCIAS, la mide y escribe el brand sheet borrador")
    rf.add_argument("video")
    rf.add_argument("--tipo", choices=["largo_horizontal", "reels_vertical", "miniaturas"], default="largo_horizontal")
    rf.add_argument("--nombre")
    sb = sp.add_parser("storyboard", help="hoja de contacto de los momentos con gráfico/rótulo antes de la entrega")
    sb.add_argument("proyecto")
    sb.add_argument("--formato", default="horizontal")
    from .produce import registrar, despachar  # subcomandos de producción masiva: produce | clips | exportar | sync
    registrar(sp)
    a = ap.parse_args()
    if despachar(a):
        return
    if a.cmd == "referencia":
        from .referencia import cmd_referencia
        cmd_referencia(a.video, a.tipo, a.nombre)
        return
    if a.cmd == "storyboard":
        from .referencia import cmd_storyboard
        cmd_storyboard(a.proyecto, a.formato)
        return
    if a.cmd == "proyecto":
        print(crear_proyecto(a.nombre, raiz=a.raiz))
    elif a.cmd == "editar":
        cmd_editar(a)
    elif a.cmd == "entrada":
        cmd_entrada(a)
    elif a.cmd == "qc":
        cmd_qc(a)
    elif a.cmd == "lote":
        cmd_lote(a)
    elif a.cmd == "miniatura":
        cmd_miniatura(a)
    elif a.cmd == "componer":
        cmd_componer(a)


if __name__ == "__main__":
    main()
