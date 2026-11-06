"""Flujo «referencias → brand sheet → storyboard» (inspirado en el Free AI Video Editor Starter Kit, adaptado a MacroWise).

  python -m mw_editor referencia VIDEO [--tipo largo_horizontal|reels_vertical] [--nombre X]
      copia el video a REFERENCIAS/<tipo>/, mide cortes/transiciones/audio (ref_video), saca hojas de contacto
      y escribe REFERENCIAS/brand_sheet_aprobado/BORRADOR_<nombre>.md para que David lo lea y apruebe.
  python -m mw_editor storyboard PROYECTO [--formato horizontal]
      hoja de contacto de los momentos con gráfico/píldora/rótulo del plan, ANTES de la entrega final (REFERENCIAS/storyboards).
Regla: la referencia inspira, no se copia (marcas, colores y logos ajenos no se usan)."""
import json
import shutil
import subprocess
from pathlib import Path

from .common import RAIZ_E, probe

REFS = Path(RAIZ_E).parent / "REFERENCIAS"


def _hojas(video, dest, dur, n=3, por_hoja=24):
    out = []
    paso = max(10, int(dur / (n * por_hoja)))
    for k in range(n):
        ss = k * por_hoja * paso
        if ss >= dur:
            break
        f = dest / f"hoja_{k + 1}.jpg"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", str(ss), "-t", str(por_hoja * paso), "-i", str(video),
                        "-vf", f"fps=1/{paso},scale=480:-2,tile=4x6:padding=4:color=black", "-frames:v", "1", str(f)], stdin=subprocess.DEVNULL)
        if f.exists():
            out.append(f)
    return out


def cmd_referencia(video, tipo="largo_horizontal", nombre=None):
    from . import ref_video as rv
    video = Path(video)
    nombre = nombre or video.stem[:40]
    dest = REFS / tipo / nombre
    dest.mkdir(parents=True, exist_ok=True)
    dst = dest / video.name
    if not dst.exists():
        shutil.copy2(video, dst)
    info = probe(str(dst))
    res = rv.analizar(dst, dest / "medidas.json")
    hojas = _hojas(dst, dest, info["duracion"])
    bs = REFS / "brand_sheet_aprobado" / f"BORRADOR_{nombre}.md"
    a = res.get("audio", {})
    bs.write_text(
        f"# Brand sheet (BORRADOR) — {nombre}\n\n> Léelo antes de aprobar. Inspirado en la referencia, no una copia.\n\n"
        f"- Duración: {res['duracion_s']} s · cambios/min: {res['cambios_por_min']} · plano mediano: {res['plano_mediano_s']} s · máx: {res['plano_max_s']} s\n"
        f"- Cortes secos: {res['cortes_secos']} · transiciones graduales: {res['transiciones_graduales']}\n"
        f"- Audio: {a.get('lufs')} LUFS · pico {a.get('true_peak')} dBTP (nuestro objetivo −14 / −1)\n"
        f"- Hojas de contacto: {', '.join(h.name for h in hojas)} (en {dest})\n\n"
        "## A completar tras mirar las hojas (fuentes, colores, subtítulos, zooms, gráficos, música)\n"
        "Traducir SIEMPRE a la paleta MacroWise (Warm Black, Geist; sin neón ni degradados; tarjetas opacas).\n"
        "\nEstado: PENDIENTE DE APROBACIÓN DE DAVID\n", encoding="utf-8")
    print("referencia:", dest, "\nbrand sheet borrador:", bs)
    return dest


def cmd_storyboard(proyecto, formato="horizontal"):
    proyecto = Path(proyecto)
    exp = proyecto / "06_EXPORT"
    bases = sorted(exp.glob(f"*_{formato}_v*_REFERENCIA.mp4")) or sorted(exp.glob(f"*_{formato}_v*_base.mp4"))
    if not bases:
        raise SystemExit("no hay video para el storyboard")
    v = bases[-1]
    plan_f = proyecto / "00_DOCS" / "plan_grafico.json"
    plan = json.loads(plan_f.read_text(encoding="utf-8-sig")) if plan_f.exists() else {}
    ts = sorted({round(float(x.get("t", 0)) + 0.8, 1) for k in ("titulos_grandes", "cifras", "lower_thirds", "cta", "impacto") for x in plan.get(k, []) if isinstance(x, dict)})
    dur = probe(str(v))["duracion"]
    if not ts:
        ts = [round(dur * k / 12, 1) for k in range(12)]
    dest = REFS / "storyboards"
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / f"_{proyecto.name}"
    tmp.mkdir(exist_ok=True)
    for i, t in enumerate(ts[:24]):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", str(t), "-i", str(v), "-frames:v", "1", "-vf", "scale=480:-2", str(tmp / f"{i:02d}.jpg")], stdin=subprocess.DEVNULL)
    out = dest / f"STORYBOARD_{proyecto.name}_{formato}.jpg"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostdin", "-framerate", "1", "-i", str(tmp / "%02d.jpg"), "-vf", "tile=4x6:padding=4:color=black", "-frames:v", "1", str(out)], stdin=subprocess.DEVNULL)
    shutil.rmtree(tmp, ignore_errors=True)
    print("storyboard:", out, "| momentos:", len(ts[:24]))
    return out
