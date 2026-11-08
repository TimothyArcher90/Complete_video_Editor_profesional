"""Reels del Arca #39 con capas gráficas completas (infografía / ecuación). Uso: python _pruebas/reels_arca.py"""
import json
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, r"C:\Users\tante\Projects\macrowise-video-editor")
from mw_editor import clips as cl, exportar as ex
from mw_editor.__main__ import cmd_componer, cmd_editar
from mw_editor.common import crear_proyecto, probe
RAIZ_DIR = None

LARGO = Path(r"E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados\06-11-2026\Arca_14ene2026_editado")
GR = Path(r"C:\Users\tante\Videos\Arca_reels\_graficos")
RAIZ = Path(r"C:\Users\tante\Videos\Arca_reels")
raw_master = LARGO / "01_RAW" / "arca_14ene.mp4"
palabras = json.loads((LARGO / "03_TRANSCRIPT" / "words.json").read_text(encoding="utf-8-sig"))
FUENTE = "Ejemplo del autor · El Arca Digital #39"

REELS = [
    dict(k=3, nombre="Arca_14ene2026_tiempo_libre", ini=214.3, fin=285.46, titulo="Invertir para qué|Ganar tiempo libre", cta_txt="Súmate al Arca"),
    dict(k=4, nombre="Arca_14ene2026_anos_libertad", ini=287.41, fin=375.69, titulo="Cuánto tardas|en ser libre", cta_txt="Súmate al Arca"),
]


def primera(pf, pred, desde=0.0):
    for w in pf:
        if w["s"] >= desde and pred(w["w"].lower().strip(".,;:¿?¡!%")):
            return w["s"]
    return None


def plan_a(pf, dur):
    t200 = primera(pf, lambda t: t == "200")
    # vertical: sin títulos ni CTA superpuestos (la cara ocupa el cuadro); solo el panel de la ecuación
    return {
        "paneles": [{"t": max(1.0, t200 - 1.0), "dur": min(25.0, dur - max(1.0, t200 - 1.0) - 1.0), "clip": str(GR / "ecuacion_vertical.mp4"), "caja": "panel"}],
    }


def plan_b(pf, dur):
    t38 = primera(pf, lambda t: t == "38")
    t0 = max(0.3, t38 - 3.9)
    return {
        "paneles": [{"t": t0, "dur": min(87.0, dur - t0 - 1.0), "clip": str(GR / "infografia_vertical.mp4"), "caja": "panel"}],
    }


for r in REELS:
    nom = r["nombre"]
    rp = crear_proyecto(nom, raiz=str(RAIZ))
    raw = rp / "01_RAW" / f"{nom}.mp4"
    cl.extraer(raw_master, r["ini"], r["fin"], raw)
    trn = rp / "03_TRANSCRIPT"
    trn.mkdir(exist_ok=True)
    pc = cl.palabras_de_clip(palabras, r["ini"], r["fin"])
    (trn / "words.json").write_text(json.dumps(pc, ensure_ascii=False, indent=1), encoding="utf-8")
    cmd_editar(ex.ns_editar(raw, rp, nom, "vertical", idioma="es", rapido=False, estilo="visual"))
    pf = json.loads((trn / "words_final.json").read_text(encoding="utf-8-sig"))
    base, n = ex._mejor_base(rp / "06_EXPORT", "vertical")
    dur = probe(str(base))["duracion"]
    plan = plan_a(pf, dur) if r["k"] == 3 else plan_b(pf, dur)
    pp = rp / "05_PROJECT" / "plan.json"
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    cmd_componer(Namespace(out=str(rp), plan=str(pp), formato="vertical", version=str(n), preview=False, estilo="visual"))
    ex.exportar(rp, ["instagram-reels", "tiktok", "youtube-shorts"], rapido=False, titulo=r["titulo"], tema="lima", etiqueta="EL ARCA DIGITAL #39", cta=r["cta_txt"], idioma="es", tipo="corto")
    print("REEL LISTO:", rp)
