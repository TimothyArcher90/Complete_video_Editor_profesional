"""Bandeja de entrada: David deja el video en INPUT_AQUI (y, si quiere, un brief.txt); esto crea el proyecto del día,
copia el original a 01_RAW (intocable), edita vertical + horizontal, pasa el QC y deja el siguiente paso escrito.
El original de INPUT_AQUI no se toca ni se mueve."""
import json
import shutil
import time
from argparse import Namespace
from pathlib import Path

from .common import PROYECTOS_RAIZ, RAIZ_E, crear_proyecto, log

EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}


def inbox_por_defecto():
    base = RAIZ_E.parent if RAIZ_E.parent.exists() else PROYECTOS_RAIZ.parent
    return base / "INPUT_AQUI"


def _brief(inbox, stem):
    """brief.txt (o <nombre>.txt): líneas 'clave: valor'. Claves: titulo (Línea 1|Línea 2), tema, etiqueta, idioma, cta, cifras."""
    for cand in (Path(inbox) / f"{stem}.txt", Path(inbox) / "brief.txt"):
        if cand.exists():
            d = {}
            for ln in cand.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    d[k.strip().lower()] = v.strip()
            return d
    return {}


def entrada(inbox=None, raiz=None, formato="ambos"):
    from .__main__ import cmd_editar
    from .miniatura import generar
    from .qc import qc_proyecto, resumen_estado
    from .common import probe

    inbox = Path(inbox) if inbox else inbox_por_defecto()
    inbox.mkdir(parents=True, exist_ok=True)
    reg_p = inbox / ".procesados.json"
    reg = json.loads(reg_p.read_text(encoding="utf-8")) if reg_p.exists() else {}
    nuevos = [p for p in sorted(inbox.iterdir()) if p.suffix.lower() in EXT and f"{p.name}|{p.stat().st_size}" not in reg]
    if not nuevos:
        log(f"No hay videos nuevos en {inbox}")
        return []
    hechos = []
    for p in nuevos:
        brief = _brief(inbox, p.stem)
        proj = crear_proyecto(p.stem, raiz=raiz)
        raw = proj / "01_RAW" / p.name
        if not raw.exists():
            shutil.copy2(p, raw)          # el original queda intacto en INPUT_AQUI; 01_RAW tiene su copia
        a = Namespace(video=str(raw), out=str(proj), nombre=p.stem, formato=formato, idioma=brief.get("idioma", "auto"), modelo="medium", plan=None,
                      sin_cortes=False, pausa_max=0.45, toma=3.6, zoom=1.12, luz=1.0, sin_luz=False, estilo="visual", rehacer=False, preview=True,
                      progreso=False, rapido=False)
        t0 = time.time()
        cmd_editar(a)
        res = qc_proyecto(proj)
        estado = resumen_estado(res)
        thumbs = ""
        if brief.get("titulo"):
            l = (brief["titulo"].split("|") + [""])[:2]
            generar(video=str(raw), titulo=(l[0].strip(), l[1].strip()), tema=brief.get("tema", "lima"), etiqueta=brief.get("etiqueta", "MACROWISE"),
                    carpeta=proj / "06_EXPORT" / "THUMBNAILS", dur=probe(str(raw))["duracion"])
            thumbs = "Miniaturas generadas con el título del brief."
        (proj / "00_DOCS" / "SIGUIENTE_PASO.md").write_text(
            f"# {p.stem}\n\nQC automático: **{estado}** (detalle en `00_DOCS\\qc.json`). Tiempo: {(time.time() - t0) / 60:.1f} min.\n\n"
            "Pendiente (lo hace Claude con la skill `macrowise-editor`):\n"
            "1. Leer `03_TRANSCRIPT\\transcript_final.txt` y `candidatos.json` y escribir `05_PROJECT\\plan.json` (nombre, títulos, cifras con fuente, mapas, gráficas, cierre).\n"
            "2. Mapas (Electric Eye) y gráficas (Ride the Lightning) si hacen falta; luego `componer`.\n"
            f"3. Miniaturas: {thumbs or 'falta el titular; salen del propio video'}.\n"
            "4. Copy en Google Doc y URL en `00_DOCS\\COPY_URL_Drive.txt`.\n", encoding="utf-8")
        reg[f"{p.name}|{p.stat().st_size}"] = {"proyecto": str(proj), "estado": estado, "fecha": time.strftime("%Y-%m-%d %H:%M")}
        reg_p.write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding="utf-8")
        hechos.append((p.name, estado, str(proj)))
        log(f"LISTO {p.name}: {estado} -> {proj}")
    return hechos
