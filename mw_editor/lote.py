"""Procesa una carpeta de clips (tests o entrada diaria): editar -> QC -> hoja de contacto -> RESUMEN.md.
Un fallo en un clip no detiene el lote: se registra el error y se sigue.
Cada corrida guarda su puntuación en un historial JSON y el RESUMEN trae un cuadro comparativo contra la corrida anterior."""
import shutil
import subprocess
import time
import traceback
from argparse import Namespace
from pathlib import Path

from PIL import Image, ImageDraw

from . import metricas as M
from .common import FFMPEG, log
from .qc import qc_proyecto_completo, resumen_estado

EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}
ULTIMO = {}  # resultado de la última corrida (puntuaciones, comparación con la anterior) para quien llame a lote()


def _hoja(proj, fm, salida, n=5, ancho=220):
    pv = next(iter(sorted((Path(proj) / "06_EXPORT").glob(f"*_{fm}_v*_PREVIEW_*.mp4"))), None)
    if not pv:
        return None
    subprocess.run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(pv), "-vf", f"fps={n}/10,scale={ancho}:-2,tile={n}x1", "-frames:v", "1", str(salida)])
    return Image.open(salida) if Path(salida).exists() else None


def _cuadro_md(items, comp, corrida_prev):
    """Cuadro comparativo: una fila por clip con puntuación, delta contra la corrida anterior y qué métricas se movieron."""
    cab = ["| clip | estado | puntuación | vs anterior | por formato | mejoran | empeoran |", "|---|---|---|---|---|---|---|"]
    filas = []
    for clip, it in items.items():
        c = comp.get(clip, {})
        fm = " · ".join(f"{k} {v['puntuacion']:.0f}" for k, v in it.get("formatos", {}).items() if v.get("puntuacion") is not None and k != "miniaturas")
        pun = "—" if it.get("puntuacion") is None else f"{it['puntuacion']:.1f}"
        filas.append(f"| {clip} | {it.get('estado', '?')} | {pun} | {M.flecha(c.get('delta'))} | {fm} | {', '.join(c.get('mejoran', [])[:6]) or '—'} | {', '.join(c.get('empeoran', [])[:6]) or '—'} |")
    punt = [it["puntuacion"] for it in items.values() if it.get("puntuacion") is not None]
    prev = [it["puntuacion"] for it in (corrida_prev or {}).get("items", {}).values() if it.get("puntuacion") is not None]
    media = sum(punt) / len(punt) if punt else None
    media_prev = sum(prev) / len(prev) if prev else None
    pie = f"**Media: {media:.1f}**" if media is not None else "Media: —"
    if media is not None and media_prev is not None:
        pie += f" (corrida anterior {corrida_prev['id']}: {media_prev:.1f} -> {M.flecha(media - media_prev, 0.5)})"
    elif corrida_prev is None:
        pie += " (primera corrida guardada: sin comparación)"
    return "\n".join(cab + filas) + "\n\n" + pie


def _un_proyecto(proj, perfil):
    res, resumen = qc_proyecto_completo(proj, perfil)
    return res, resumen, resumen_estado(res)


def _item(resumen, estado):
    return {"puntuacion": resumen["puntuacion"], "estado": estado, "metricas": resumen["metricas"], "formatos": resumen["formatos"]}


def lote(carpeta_in, out_root, formato="ambos", idioma="auto", rapido=True, estilo="visual", plan_por_clip=None, plan=None, historial=None, etiqueta="",
         perfil=None, solo_qc=False):
    """plan: ruta de un plan.json de gráficos para todos los clips; plan_por_clip: {stem: ruta}. Se copia a 00_DOCS/plan_grafico.json (lo lee el QC de cifras).
    solo_qc=True no re-edita: vuelve a medir los proyectos ya existentes en out_root (para iterar sobre el propio QC)."""
    from .__main__ import cmd_editar
    entradas = sorted(p for p in Path(carpeta_in).iterdir() if p.suffix.lower() in EXT)
    filas, hojas, items = [], [], {}
    for p in entradas:
        proj = Path(out_root) / p.stem
        t0 = time.time()
        plan_p = (plan_por_clip or {}).get(p.stem) or plan
        a = Namespace(video=str(p), out=str(proj), nombre=p.stem, formato=formato, idioma=idioma, modelo="medium", plan=plan_p, sin_cortes=False,
                      pausa_max=0.45, toma=3.6, zoom=1.12, luz=1.0, sin_luz=False, estilo=estilo, rehacer=False, preview=True, progreso=False, rapido=rapido)
        err = None
        try:
            if not (solo_qc and (proj / "06_EXPORT").exists()):
                cmd_editar(a)
            if plan_p and Path(plan_p).exists():
                (proj / "00_DOCS").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(plan_p, proj / "00_DOCS" / "plan_grafico.json")
            res, resumen, estado = _un_proyecto(proj, perfil)
            items[p.stem] = _item(resumen, estado)
        except Exception:  # noqa: BLE001
            err = traceback.format_exc(limit=3)
            res, estado = {}, "FAIL"
            items[p.stem] = {"puntuacion": None, "estado": "FAIL", "metricas": {}, "formatos": {}}
            log(f"ERROR en {p.name}: {err.splitlines()[-1]}")
        filas.append((p.stem, estado, time.time() - t0, res, err))
        for fm in ("vertical", "horizontal"):
            h = _hoja(proj, fm, proj / "00_DOCS" / f"hoja_{fm}.jpg") if not err else None
            if h:
                hojas.append((p.stem, fm, h))
    # historial + comparación contra la corrida anterior
    ruta_h = M.ruta_historial(out_root) if historial is None else Path(historial)
    prev = (M.cargar_historial(ruta_h).get("corridas") or [None])[-1]
    corrida = M.guardar_corrida(ruta_h, items, etiqueta)
    comp = M.comparar(corrida, prev)
    ULTIMO.clear()
    ULTIMO.update({"items": items, "comparacion": comp, "corrida": corrida["id"], "anterior": (prev or {}).get("id"), "historial": str(ruta_h)})
    # RESUMEN_TESTS.md
    md = ["# RESUMEN DE TESTS", "", f"{len(filas)} clips · {sum(1 for f in filas if f[1] == 'PASS')} PASS · {sum(1 for f in filas if f[1] == 'WARN')} WARN · {sum(1 for f in filas if f[1] == 'FAIL')} FAIL",
          "", f"Corrida `{corrida['id']}`{(' · ' + etiqueta) if etiqueta else ''} · historial: `{ruta_h}`", "", "## Cuadro comparativo (puntuación 0-100)", "", _cuadro_md(items, comp, prev), ""]
    for nombre, estado, seg, res, err in filas:
        pun = items[nombre]["puntuacion"]
        md.append(f"## {nombre} — {estado} · {('%.1f' % pun) if pun is not None else '—'}/100 ({seg:.0f}s)")
        if err:
            md.append("```\n" + err + "\n```")
        for fm, cks in res.items():
            for c in cks:
                if c["estado"] not in ("PASS", "N/A"):
                    md.append(f"- {fm}: **{c['estado']}**{' (info)' if c.get('informativo') and c['estado'] == 'WARN' else ''} {c['check']} — {c['detalle']}")
        md.append("")
    (Path(out_root) / "RESUMEN_TESTS.md").write_text("\n".join(md), encoding="utf-8")
    # hoja global
    if hojas:
        ancho = max(h.width for _, _, h in hojas) + 200
        alto = sum(h.height + 6 for _, _, h in hojas)
        g = Image.new("RGB", (ancho, alto), (26, 26, 23))
        d = ImageDraw.Draw(g)
        y = 0
        for nombre, fm, h in hojas:
            d.text((6, y + h.height // 2 - 8), f"{nombre[:22]}\n{fm}", fill=(214, 209, 200))
            g.paste(h, (200, y))
            y += h.height + 6
        g.save(Path(out_root) / "HOJA_TESTS.jpg", quality=90)
    return filas


def qc_proyectos(proyectos, historial=None, perfil=None, etiqueta="", salida=None):
    """Mide proyectos YA editados (sin re-renderizar), guarda la corrida en el historial y escribe el cuadro comparativo.
    proyectos: lista de carpetas de proyecto, o una carpeta que contiene proyectos. Devuelve {clip: item}."""
    rutas = []
    for q in proyectos:
        q = Path(q)
        if (q / "06_EXPORT").exists():
            rutas.append(q)
        else:
            rutas += sorted(d for d in q.iterdir() if d.is_dir() and (d / "06_EXPORT").exists())
    items = {}
    for proj in rutas:
        try:
            res, resumen, estado = _un_proyecto(proj, perfil)
            items[proj.name] = _item(resumen, estado)
        except Exception:  # noqa: BLE001
            log(f"ERROR QC {proj.name}: {traceback.format_exc(limit=2).splitlines()[-1]}")
            items[proj.name] = {"puntuacion": None, "estado": "FAIL", "metricas": {}, "formatos": {}}
    base = rutas[0].parent if rutas else Path(".")
    ruta_h = M.ruta_historial(base) if historial is None else Path(historial)
    prev = (M.cargar_historial(ruta_h).get("corridas") or [None])[-1]
    corrida = M.guardar_corrida(ruta_h, items, etiqueta)
    comp = M.comparar(corrida, prev)
    cuadro = _cuadro_md(items, comp, prev)
    (Path(salida) if salida else base / "CUADRO_METRICAS.md").write_text(f"# Cuadro de métricas - corrida {corrida['id']}\n\n{cuadro}\n", encoding="utf-8")
    ULTIMO.clear()
    ULTIMO.update({"items": items, "comparacion": comp, "corrida": corrida["id"], "anterior": (prev or {}).get("id"), "historial": str(ruta_h), "cuadro": cuadro})
    log("\n" + cuadro)
    return items
