"""Análisis de TEXTO de una referencia (subtítulos automáticos json3 de YouTube): ritmo del habla, estructura, ganchos, patrocinios, CTA.
No necesita el video. Mide lo que se puede medir del guion: palabras/s, pausas largas, preguntas retóricas, 'bucles abiertos', menciones de
suscripción/patrocinio y su posición en el tiempo."""
import json
import re
import statistics
from pathlib import Path

RE_PREG = re.compile(r"\?|\b(qu[eé]|c[oó]mo|por qu[eé]|cu[aá]ndo|cu[aá]nto)\b", re.I)
RE_BUCLE = re.compile(r"\b(m[aá]s adelante|en un momento|ahora (te|os) cuento|al final|despu[eé]s (te|os)|luego (te|os)|no te vayas|quédate|sigue viendo|ver[aá]s|veremos|el tercer|la raz[oó]n)\b", re.I)
RE_CTA = re.compile(r"\b(suscr[ií]b|suscribas|campanita|dale (like|me gusta)|me gusta|comenta|comentarios|comparte|newsletter|enlace|descripci[oó]n|canal)\b", re.I)
RE_SPONSOR = re.compile(r"\b(patrocin|sponsor|c[oó]digo|descuento|invity|promoci[oó]n|oferta|link)\b", re.I)
RE_CIFRA = re.compile(r"\d")
RE_CAPS = re.compile(r"\b[A-ZÁÉÍÓÚÑ]{3,}\b")


def cargar_json3(ruta):
    """Devuelve lista de palabras {w, s, e} (segundos) desde un json3 de YouTube."""
    j = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    out = []
    for ev in j.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        t0 = ev.get("tStartMs", 0) / 1000.0
        dur = ev.get("dDurationMs", 0) / 1000.0
        for k, sg in enumerate(segs):
            w = (sg.get("utf8") or "").replace("\n", " ").strip()
            if not w:
                continue
            ini = t0 + sg.get("tOffsetMs", 0) / 1000.0
            out.append({"w": w, "s": ini, "e": ini + 0.25})
    out.sort(key=lambda x: x["s"])
    # fin de palabra = inicio de la siguiente (tope 1,2 s)
    for a, b in zip(out, out[1:]):
        a["e"] = min(b["s"], a["s"] + 1.2) if b["s"] > a["s"] else a["s"] + 0.25
    return out


def frases(palabras, pausa=0.8):
    """Agrupa palabras en frases por pausa."""
    fr, cur = [], []
    for w in palabras:
        if cur and w["s"] - cur[-1]["e"] > pausa:
            fr.append(cur)
            cur = []
        cur.append(w)
    if cur:
        fr.append(cur)
    return fr


def analizar(ruta, duracion=None):
    pw = cargar_json3(ruta)
    if not pw:
        return {}
    dur = duracion or pw[-1]["e"]
    texto = " ".join(w["w"] for w in pw)
    n = len(pw)
    # palabras por segundo en ventanas de 30 s
    vent = []
    for t in range(0, int(dur), 30):
        c = sum(1 for w in pw if t <= w["s"] < t + 30)
        vent.append(c / 30.0)
    # pausas largas entre palabras
    gaps = [b["s"] - a["e"] for a, b in zip(pw, pw[1:]) if b["s"] - a["e"] > 0.5]
    fr = frases(pw)
    lens = [len(f) for f in fr]
    pos = lambda rx: [round(w["s"]) for w in pw if rx.search(w["w"])]  # noqa: E731
    por_min = lambda lst: round(len(lst) / (dur / 60.0), 2)  # noqa: E731
    preg = [round(f[0]["s"]) for f in fr if RE_PREG.search(" ".join(x["w"] for x in f)) and "?" in " ".join(x["w"] for x in f)]
    bucles = [round(f[0]["s"]) for f in fr if RE_BUCLE.search(" ".join(x["w"] for x in f))]
    ctas = [round(f[0]["s"]) for f in fr if RE_CTA.search(" ".join(x["w"] for x in f))]
    spon = [round(f[0]["s"]) for f in fr if RE_SPONSOR.search(" ".join(x["w"] for x in f))]
    hook = " ".join(w["w"] for w in pw if w["s"] < 30)
    cierre = " ".join(w["w"] for w in pw if w["s"] > dur - 40)
    return {
        "duracion_s": round(dur), "palabras": n, "palabras_por_s": round(n / dur, 2),
        "wps_ventanas_30s": {"min": round(min(vent), 2), "max": round(max(vent), 2), "mediana": round(statistics.median(vent), 2)},
        "pausas_>0.5s": len(gaps), "pausas_>0.5s_por_min": round(len(gaps) / (dur / 60.0), 1),
        "frase_mediana_palabras": statistics.median(lens) if lens else 0,
        "preguntas_retoricas": len(preg), "preguntas_por_min": por_min(preg), "bucles_abiertos": bucles[:12], "cta": ctas[:15], "patrocinio_menciones": spon[:15],
        "mayusculas_enfasis_por_min": round(len(RE_CAPS.findall(texto)) / (dur / 60.0), 2),
        "cifras_por_min": round(len(RE_CIFRA.findall(texto)) / (dur / 60.0), 1),
        "gancho_30s": hook, "cierre_40s": cierre,
    }
