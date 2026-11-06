"""plan.json inicial AUTOMÁTICO: lower third (si el brief trae nombre) + énfasis hablados + CTA (si el brief lo trae).

Es un BORRADOR para que David / Claude revisen: no se publica nada sin esa revisión.
  * Toda cifra detectada va como candidata con "verificada": false y "fuente": "" -> el motor la RECHAZA al componer
    (aviso "CIFRA RECHAZADA") hasta que alguien la verifique contra fuente oficial y ponga fuente + verificada:true.
  * Los textos grandes nunca contienen una cifra que no esté en el audio (enfasis.verificar_cifras_en_audio).
  * Las claves con prefijo "_" (_auto, _revisar, _descartados, _tipo...) las ignora el motor: son notas para quien revisa.

Uso:
  python -m mw_editor.plan_auto --words <03_TRANSCRIPT/words_final.json> [--brief brief.json] [--formato vertical] [--out plan.json]
  python -m mw_editor.plan_auto --proyecto <carpeta del proyecto> [--brief brief.json]     (lee words_final.json, escribe 05_PROJECT/plan_auto.json)

brief.json (todas las claves son opcionales):
  {"nombre": "Guillermo Valencia", "rol": "MacroWise", "idioma": "es",
   "cta": {"verbo": "Comenta", "palabra": "Link", "extra": "y te lo envío por mensaje directo"},
   "max_por_min": 5, "sep_min": 4.0}"""
import argparse
import json
from pathlib import Path

from . import enfasis as en


def _cta_brief(brief):
    c = brief.get("cta")
    if not c:
        return None
    if isinstance(c, str):
        return {"verbo": "Comenta", "palabra": c, "extra": ""}
    if not c.get("palabra"):
        return None
    return {"verbo": c.get("verbo", "Comenta"), "palabra": c["palabra"], "extra": c.get("extra", "")}


def componer_plan(pal, formato="vertical", brief=None, dur_total=None):
    brief = brief or {}
    fin = dur_total or (pal[-1]["e"] + 0.3 if pal else 0.0)
    plan = {"_auto": {"formato": formato, "duracion_s": round(fin, 2), "generado_por": "mw_editor.plan_auto"},
            "_revisar": [], "lower_thirds": [], "titulos_grandes": [], "impacto": [], "cifras": [], "cta": []}
    evitar = []
    nombre = brief.get("nombre") or brief.get("presentador")
    if nombre and fin >= 3.0:
        dur = round(min(4.0, max(2.0, fin - 1.5)), 2)
        plan["lower_thirds"].append({"t": 0.6, "dur": dur, "nombre": nombre, "rol": brief.get("rol", "")})
        evitar.append((0.6, 0.6 + dur))
    elif not nombre:
        plan["_revisar"].append("el brief no trae nombre: no se puso lower third")
    cta = _cta_brief(brief)
    if cta:
        if fin >= 8.0:
            dur = 4.0
            t = round(max(evitar[-1][1] + 0.5 if evitar else 0.0, fin - dur - 0.3), 2)
            plan["cta"].append({"t": t, "dur": dur, **cta, "_tipo": "cta", "_motivo": "pedido en el brief"})
            evitar.append((t, t + dur))
        else:
            plan["_revisar"].append("el brief trae CTA pero el vídeo dura menos de 8 s: no cabe")
    cfg = {k: brief[k] for k in ("max_por_min", "sep_min", "cifras_por_min", "max_solape") if k in brief}
    e = en.proponer(pal, formato=formato, idioma=brief.get("idioma"), evitar=evitar, cfg=cfg, dur_total=fin)
    plan["titulos_grandes"] = e["titulos_grandes"]
    if formato != "vertical":                       # largo: caja opaca Warm Black detrás (sobre pantallas claras el lima no se lee)
        for tg in plan["titulos_grandes"]:
            tg.setdefault("caja", True)
    plan["impacto"] = e["impacto"]
    plan["cifras"] = e["cifras"]
    if not cta:
        plan["cta"] = e["cta"]
    plan["_descartados"] = e["descartados"]
    plan["_auto"]["resumen_enfasis"] = e["resumen"]
    if plan["cifras"]:
        plan["_revisar"].append(f"{len(plan['cifras'])} cifra(s) candidata(s) con verificada:false. El motor las rechaza hasta que alguien verifique cada una "
                                "contra fuente oficial y rellene 'fuente' y 'verificada': true (o las borre). Las etiquetas son una sugerencia: afínalas.")
    if plan["impacto"]:
        plan["_revisar"].append("el modo 'impacto' pone una palabra gigante en lima ≤ 1,2 s: confirma que el momento lo merece; si lo usas, pasa ocultar=ocultar_desde_plan(plan) a los subtítulos.")
    plan["_revisar"].append("todo texto grande se propone para reforzar lo que se acaba de decir (no duplica el subtítulo): revisa tono y ortografía antes de entregar.")
    return plan


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mw_editor.plan_auto")
    ap.add_argument("--words")
    ap.add_argument("--proyecto")
    ap.add_argument("--brief")
    ap.add_argument("--formato", default="vertical")
    ap.add_argument("--out")
    ap.add_argument("--dur", type=float)
    a = ap.parse_args(argv)
    if a.proyecto:
        words = Path(a.proyecto) / "03_TRANSCRIPT" / "words_final.json"
        out = Path(a.out) if a.out else Path(a.proyecto) / "05_PROJECT" / "plan_auto.json"
    elif a.words:
        words, out = Path(a.words), Path(a.out) if a.out else Path("plan_auto.json")
    else:
        ap.error("indica --words o --proyecto")
    pal = json.loads(words.read_text(encoding="utf-8-sig"))
    brief = json.loads(Path(a.brief).read_text(encoding="utf-8-sig")) if a.brief else {}
    plan = componer_plan(pal, a.formato, brief, a.dur)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[plan_auto] {out}: {len(plan['titulos_grandes'])} títulos grandes, {len(plan['impacto'])} impactos, {len(plan['cifras'])} cifras candidatas, "
          f"{len(plan['cta'])} CTA, {len(plan['lower_thirds'])} lower third")
    for r in plan["_revisar"]:
        print("  REVISAR:", r)
    return plan


if __name__ == "__main__":
    main()
