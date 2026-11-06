"""Manifiesto de IA y procedencia + registro de cifras rotuladas con su fuente (métricas M25 y M26).
Se escribe en 00_DOCS/manifiesto_ia.json. Declara QUÉ filtros/modelos se usaron y si hay escenas generadas o voz clonada,
con la evidencia que lo respalda. Lo que cada plataforma exige declarar NO se puede decidir aquí (cambia y no hay API): se deja
la nota de la investigación (docs/investigacion/metricas.json) y la marca 'verificar en la app antes de publicar'."""
import importlib.metadata as im
import json
import re
import time
from pathlib import Path

from . import metricas as M
from .common import FFMPEG, ROOT, run
from .qc_extra import leer_ass, leer_plan

ETIQUETAS_PLATAFORMA = {
    "instagram_reels": ("Meta 'AI info': por metadatos C2PA/IPTC o autodeclaración (terceros sobre Meta).", "terceros"),
    "tiktok": ("Etiquetar AIGC obligatorio si hay escenas/personas realistas generadas o editadas de forma significativa; lee Content Credentials C2PA (oficial).", "oficial"),
    "youtube_shorts": ("Declaración en Studio para contenido realista alterado/sintético (oficial).", "oficial"),
    "youtube_largo": ("Igual que Shorts (oficial).", "oficial"),
    "linkedin": ("Icono CR si el archivo trae C2PA firmado (ayuda de LinkedIn); sin obligación de declaración verificada.", "oficial"),
}
GENERATIVO = re.compile(r"elevenlabs|replicate|fal_client|diffusers|openai|higgsfield|stable.?diffusion|xtts|bark\b|f5.?tts", re.I)
NUM = re.compile(r"(?<![\w#])\d[\d.,]*\s?(?:%|[kKmMbB]\b)?")


def _version(pkg):
    try:
        return im.version(pkg)
    except im.PackageNotFoundError:
        return None


def _ffmpeg_version():
    try:
        return run([FFMPEG, "-version"], check=False).stdout.splitlines()[0]
    except Exception:  # noqa: BLE001
        return None


def _textos(plan):
    out = []

    def rec(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            [rec(v) for v in x.values()]
        elif isinstance(x, list):
            [rec(v) for v in x]
    rec(plan or {})
    return " | ".join(out)


def _numeros_ass(exp):
    """Números rotulados en los ASS de gráficos (última versión de cada formato). {token: [archivos]}"""
    vistos = {}
    for f in sorted(Path(exp).glob("*_graficos.ass")):
        for e in leer_ass(f):
            if e["dibujo"]:
                continue
            for tok in NUM.findall(e["texto"]):
                tok = tok.strip()
                if re.fullmatch(r"(19|20)\d\d", tok):  # año
                    continue
                vistos.setdefault(tok, set()).add(f.name)
    return vistos


def registro_cifras(proj, plan):
    """Cifras del plan con su fuente + comprobación de que todo número rotulado está registrado."""
    exp = Path(proj) / "06_EXPORT"
    en_pantalla = _numeros_ass(exp)
    corpus = _textos(plan)
    cifras = []
    for c in (plan or {}).get("cifras", []):
        ok_f = bool(str(c.get("fuente", "")).strip()) and c.get("verificada") is True
        valor = str(c.get("valor", "")).strip()
        rotulada = any(valor and (valor == t or valor in t or t in valor) for t in en_pantalla)
        cifras.append({"t": c.get("t"), "valor": valor, "etiqueta": c.get("etiqueta"), "tipo": c.get("tipo"), "fuente": c.get("fuente"), "verificada": c.get("verificada") is True,
                       "rotulada_en_pantalla": rotulada, "estado": "ok" if ok_f else ("SIN_FUENTE_Y_ROTULADA" if rotulada else "descartada_por_el_motor_sin_fuente")})
    sin_registro = sorted(t for t in en_pantalla if t not in corpus)
    return cifras, en_pantalla, sin_registro


def construir(proj):
    proj = Path(proj)
    docs, exp = proj / "00_DOCS", proj / "06_EXPORT"
    rep = {}
    try:
        rep = json.loads((docs / "reparacion.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        pass
    plan = leer_plan(proj)
    cifras, en_pantalla, sin_registro = registro_cifras(proj, plan)
    miniaturas = list((exp / "THUMBNAILS").glob("thumb_*.jpg")) if (exp / "THUMBNAILS").exists() else []
    fuentes = [p for p in (ROOT / "mw_editor").glob("*.py") if p.name not in ("manifiesto.py", "qc_extra.py", "qc.py", "metricas.py")]
    gen_hits = sorted({p.name for p in fuentes if GENERATIVO.search(p.read_text(encoding="utf-8", errors="ignore"))})
    clips = (plan or {}).get("clips", []) + [p for p in (plan or {}).get("paneles", []) if p.get("clip")]
    herramientas = [
        {"nombre": "FFmpeg", "version": _ffmpeg_version(), "licencia": "LGPL/GPL (build full)", "uso": "cortes, reencuadre, denoise hqdn3d, EQ/compresión de audio, composición, codificación", "genera_contenido_sintetico": False},
        {"nombre": "faster-whisper (Whisper)", "version": _version("faster-whisper"), "licencia": "MIT", "uso": "transcripción con tiempos por palabra (modelo: 'medium' por defecto, 'small' en modo --rapido)", "genera_contenido_sintetico": False},
        {"nombre": "YuNet (OpenCV Zoo)", "version": f"opencv {_version('opencv-python') or _version('opencv-python-headless') or '?'}", "licencia": "MIT", "uso": "detección de cara para encuadre y para el QC de solape cara-texto", "genera_contenido_sintetico": False},
    ]
    if miniaturas:
        herramientas.append({"nombre": "BiRefNet-portrait (rembg)", "version": _version("rembg"), "licencia": "MIT", "uso": "recorte de la persona para las miniaturas (fondo sólido de marca)", "genera_contenido_sintetico": False,
                             "nota": "segmentación, no generación; la cara no se redibuja"})
    alteraciones = list(rep.get("imagen", [])) + list(rep.get("audio", {}).get("decisiones", []))
    alteraciones += ["encuadre digital por cara con jump-cuts (recorte/zoom del plano original)", "luz de estudio: máscara elíptica sobre la cara (relight por maskedmerge) salvo --sin-luz; no queda registrado si se aplicó"]
    m = {
        "version": 1, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "proyecto": proj.name,
        "contenido_sintetico": {
            "escenas_generadas_por_ia": False,
            "voz_clonada_o_sintetica": False,
            "personas_o_rostros_generados": False,
            "evidencia": [
                "el audio sale de la pista del vídeo original (02_AUDIO/*_voz_limpia.wav = filtros sobre la misma voz)",
                "las imágenes son fotogramas del original recortados; los gráficos son ASS/vectoriales de marca",
                ("ningún módulo del motor importa servicios generativos" if not gen_hits else f"REVISAR: referencias a servicios generativos en {gen_hits}"),
            ],
            "verificar_manualmente": ["clips/mapas/gráficas insertados desde fuera del motor (Electric Eye, Ride the Lightning): confirmar que no son generados por IA"],
        },
        "herramientas": herramientas,
        "alteraciones_sobre_material_real": alteraciones,
        "clips_insertados": [{"archivo": c.get("archivo"), "origen_declarado": c.get("origen")} for c in clips],
        "etiqueta_ia_por_plataforma": {k: {"nota": v[0], "confianza": v[1], "decision_automatica": "no hace falta etiqueta por contenido sintético: ninguno", "verificar_en_la_app": True} for k, v in ETIQUETAS_PLATAFORMA.items()},
        "c2pa_firmado": False,
        "cifras_rotuladas": cifras,
        "numeros_en_pantalla": {k: sorted(v) for k, v in en_pantalla.items()},
        "plan_conservado": plan is not None,
    }
    return m, plan, sin_registro, gen_hits


def escribir(proj):
    m, plan, sin_registro, gen_hits = construir(proj)
    ruta = Path(proj) / "00_DOCS" / "manifiesto_ia.json"
    ruta.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m, plan, sin_registro, gen_hits, ruta


def metricas_proyecto(proj):
    """M25 manifiesto y M26 cifras verificadas. Escribe el manifiesto como efecto lateral."""
    m, plan, sin_registro, gen_hits, ruta = escribir(proj)
    out = []
    # M25
    prob = []
    if gen_hits:
        prob.append(f"referencias a servicios generativos en {gen_hits}")
    sin_origen = [c for c in m["clips_insertados"] if not c["origen_declarado"]]
    st = "FAIL" if prob else ("WARN" if sin_origen else "PASS")
    det = f"manifiesto escrito: {ruta.name} · sintético: NO (escenas/voz/rostros) · herramientas: {', '.join(h['nombre'] for h in m['herramientas'])}"
    if sin_origen:
        det += f" · {len(sin_origen)} clip(s) insertado(s) sin 'origen' en el plan: declarar si son generados"
    if prob:
        det += " · " + "; ".join(prob)
    out.append(M.metrica("M25", "Manifiesto de IA y procedencia", None, st, "manifiesto presente y coherente", "manifiesto ausente o con clips sin origen", det, "oficial", "media",
                         puntaje=1.0 if st == "PASS" else (0.6 if st == "WARN" else 0.1), duro=bool(prob)))
    # M26
    cifras = m["cifras_rotuladas"]
    pant = m["numeros_en_pantalla"]
    mal = [c for c in cifras if c["estado"] == "SIN_FUENTE_Y_ROTULADA"]
    descart = [c for c in cifras if c["estado"] == "descartada_por_el_motor_sin_fuente"]
    if plan is None and pant:
        out.append(M.metrica("M26", "Cifras en pantalla verificadas", None, "WARN", "100 % con fuente verificada", "cualquier cifra sin fuente = FAIL",
                             f"{len(pant)} número(s) rotulados ({', '.join(list(pant)[:6])}) pero el plan con fuentes no se conservó: no verificable (copiar el plan a 00_DOCS/plan_grafico.json)",
                             "oficial", "alta", puntaje=0.4, duro=False, informativo=False))
    else:
        corpus = _textos(plan)
        huerfanos = [t for t in pant if t not in corpus]
        if mal or huerfanos:
            st = "FAIL"
            det = ((f"cifra(s) rotulada(s) SIN fuente/verificación: {[c['valor'] for c in mal]}; ") if mal else "") + ((f"número(s) en pantalla que no están en el plan: {huerfanos}") if huerfanos else "")
        elif descart:
            st, det = "WARN", f"cifra(s) descartada(s) por el motor por falta de fuente: {[c['valor'] for c in descart]} -> preguntar a David (no se omite en silencio)"
        else:
            st, det = "PASS", f"{len(cifras)} cifra(s) rotulada(s), todas con fuente y verificada:true" if cifras else "0 cifras rotuladas"
        regs = "; ".join(f"{c['valor']} <- {c['fuente']}" for c in cifras if c["estado"] == "ok")
        out.append(M.metrica("M26", "Cifras en pantalla verificadas", len(cifras), st, "100 % con fuente verificada", "cualquier cifra sin fuente = FAIL", det + (f" · registro: {regs}" if regs else ""),
                             "oficial", "alta", puntaje=1.0 if st == "PASS" else (0.5 if st == "WARN" else 0.0), duro=True, informativo=False))
    return out
