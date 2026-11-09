"""Marco de métricas del QC: constructor de métrica, evaluación PASS/WARN/FAIL, puntuación 0-100 e historial entre corridas.

Cada métrica es un dict:
  {id, nombre, valor, unidad, umbral_pass, umbral_warn, estado, detalle, confianza_del_umbral, peso, puntaje, informativo}
- estado: PASS / WARN / FAIL / N/A (no aplica o no medible; no puntúa).
- puntaje: 0..1 continuo (1 en el umbral PASS, 0.5 en el borde WARN, 0 en el borde FAIL) para ver mejoras DENTRO de un WARN.
- confianza_del_umbral: oficial / terceros / estimado (docs/investigacion/metricas.json).
- informativo: True = el WARN no cambia el estado global del output (umbral solo orientativo); sí puntúa.
Política anti-falso-FAIL: una métrica con umbral 'estimado' o 'terceros' NO puede dar FAIL salvo que se marque `duro=True`
(defecto objetivo, p. ej. texto tapando los ojos, cifra sin fuente, alfa vacío)."""
import json
import math
import os
import time
from pathlib import Path

CONF_FACTOR = {"oficial": 1.0, "terceros": 0.75, "estimado": 0.5}
PRIORIDAD_PESO = {"alta": 3.0, "media": 2.0, "baja": 1.0}
PUNTOS = {"PASS": 1.0, "WARN": 0.5, "FAIL": 0.0}

# Perfiles de plataforma: duración (s) óptima / máxima, formato objetivo. Fuente: docs/investigacion/metricas.json (confianza terceros salvo indicación).
PLATAFORMAS = {
    "instagram_reels": {"optimo": (15, 35), "max": 180, "max_verificado": False, "formatos": ("vertical",), "conf": "terceros", "nombre": "Instagram Reels"},
    "tiktok": {"optimo": (20, 40), "max": 600, "max_verificado": False, "formatos": ("vertical",), "conf": "terceros", "nombre": "TikTok"},
    "youtube_shorts": {"optimo": (20, 50), "max": 180, "formatos": ("vertical",), "conf": "oficial", "nombre": "YouTube Shorts"},
    "linkedin": {"optimo": (30, 90), "max": 600, "formatos": ("cuadrado", "4x5", "horizontal", "vertical"), "conf": "terceros", "nombre": "LinkedIn"},
    "youtube_largo": {"optimo": (180, 1500), "max": 43200, "formatos": ("horizontal",), "conf": "terceros", "nombre": "YouTube largo"},
}
PLATAFORMAS_POR_FORMATO = {
    "vertical": ("instagram_reels", "tiktok", "youtube_shorts"),
    "cuadrado": ("linkedin",),
    "4x5": ("linkedin",),
    "horizontal": ("youtube_largo", "linkedin"),
}


def es_corto(dur, fm):
    """Clase de ritmo: 'corto' (reel/short) o 'largo'. Vertical/cuadrado/4x5 y <= 3 min se tratan como corto."""
    return dur <= 90 if fm == "horizontal" else dur <= 180


def _f(v, nd=2):
    return None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else round(float(v), nd)


def lin(valor, pass_lim, warn_lim, fail_lim):
    """Puntaje continuo 0..1: 1 en pass_lim, 0.5 en warn_lim, 0 en fail_lim (clamp). Sirve en ambas direcciones."""
    if valor is None:
        return None
    if pass_lim == warn_lim or warn_lim == fail_lim:
        return 1.0 if valor == pass_lim else 0.0
    sentido = 1 if warn_lim > pass_lim else -1
    d = (valor - pass_lim) * sentido
    dw = (warn_lim - pass_lim) * sentido
    df = (fail_lim - pass_lim) * sentido
    if d <= 0:
        return 1.0
    if d <= dw:
        return 1.0 - 0.5 * d / dw
    if d <= df:
        return 0.5 - 0.5 * (d - dw) / (df - dw)
    return 0.0


def estado_max(valor, pass_lim, warn_lim):
    """PASS si valor <= pass_lim; WARN hasta warn_lim; FAIL después (mejor=menor)."""
    if valor <= pass_lim:
        return "PASS"
    return "WARN" if valor <= warn_lim else "FAIL"


def estado_min(valor, pass_lim, warn_lim):
    """PASS si valor >= pass_lim; WARN hasta warn_lim; FAIL por debajo (mejor=mayor)."""
    if valor >= pass_lim:
        return "PASS"
    return "WARN" if valor >= warn_lim else "FAIL"


def estado_rango(v, p_lo, p_hi, w_lo, w_hi):
    if p_lo <= v <= p_hi:
        return "PASS"
    return "WARN" if w_lo <= v <= w_hi else "FAIL"


def puntaje_rango(v, p_lo, p_hi, w_lo, w_hi, f_lo, f_hi):
    if v is None:
        return None
    return lin(v, p_lo, w_lo, f_lo) if v < p_lo else (lin(v, p_hi, w_hi, f_hi) if v > p_hi else 1.0)


def metrica(id_, nombre, valor, estado, umbral_pass, umbral_warn, detalle="", confianza="estimado", prioridad="media",
            puntaje=None, unidad="", duro=False, informativo=None, peso=None):
    """Construye una métrica. Aplica la política anti-falso-FAIL (ver docstring del módulo)."""
    if estado == "FAIL" and not duro and confianza != "oficial":
        estado = "WARN"
        detalle = (detalle + " · umbral no oficial: tope WARN").strip(" ·")
    if puntaje is None:
        puntaje = None if estado == "N/A" else PUNTOS[estado]
    if estado == "N/A":
        puntaje = None
    elif puntaje is not None:
        # coherencia: el puntaje no puede contradecir el estado
        puntaje = max(0.0, min(1.0, puntaje))
        if estado == "PASS":
            puntaje = max(puntaje, 0.9) if puntaje < 1 else puntaje
        elif estado == "WARN":
            puntaje = min(max(puntaje, 0.2), 0.89)
        elif estado == "FAIL":
            puntaje = min(puntaje, 0.25)
    if informativo is None:
        informativo = confianza == "estimado" and not duro
    w = peso if peso is not None else PRIORIDAD_PESO.get(prioridad, 2.0) * CONF_FACTOR.get(confianza, 0.5)
    return {"id": id_, "nombre": nombre, "valor": valor if not isinstance(valor, float) else _f(valor, 3), "unidad": unidad,
            "umbral_pass": umbral_pass, "umbral_warn": umbral_warn, "estado": estado, "detalle": detalle,
            "confianza_del_umbral": confianza, "peso": round(w, 3), "puntaje": _f(puntaje, 3), "informativo": bool(informativo)}


def na(id_, nombre, motivo, umbral_pass="", umbral_warn="", confianza="estimado"):
    return metrica(id_, nombre, None, "N/A", umbral_pass, umbral_warn, motivo, confianza)


def desde_check(id_, check, confianza="oficial", prioridad="alta", duro=True, umbral_pass="", umbral_warn=""):
    """Envuelve un check antiguo {check, estado, detalle} como métrica (los antiguos son objetivos: duro)."""
    return metrica(id_, check["check"], None, check["estado"], umbral_pass, umbral_warn, check.get("detalle", ""), confianza, prioridad, duro=duro, informativo=False)


def puntuacion(metricas):
    """0-100 ponderada. N/A no cuenta. Devuelve (puntos, cobertura) donde cobertura = peso medido / peso total posible."""
    num = den = 0.0
    for m in metricas:
        if m["estado"] == "N/A" or m.get("puntaje") is None:
            continue
        num += m["peso"] * m["puntaje"]
        den += m["peso"]
    return (round(100.0 * num / den, 1) if den else None), den


def estado_global(metricas):
    es = [m["estado"] for m in metricas]
    if "FAIL" in es:
        return "FAIL"
    return "WARN" if any(m["estado"] == "WARN" and not m.get("informativo") for m in metricas) else "PASS"


# ---------- historial entre corridas ----------
def ruta_historial(out_root):
    return Path(os.environ.get("MW_HISTORIAL") or (Path(out_root) / "HISTORIAL_METRICAS.json"))


def cargar_historial(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "corridas": []}


def guardar_corrida(ruta, items, etiqueta=""):
    """items: {clip: {"puntuacion": float, "estado": str, "metricas": {id: puntaje}, "formatos": {fm: puntuacion}}}"""
    h = cargar_historial(ruta)
    corrida = {"id": time.strftime("%Y%m%d-%H%M%S"), "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "etiqueta": etiqueta, "items": items}
    h["corridas"].append(corrida)
    h["corridas"] = h["corridas"][-60:]
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    return corrida


def comparar(corrida, anterior, umbral=1.0):
    """Delta por clip y por métrica vs la corrida anterior. Devuelve {clip: {"delta": x|None, "mejoran": [...], "empeoran": [...]}}."""
    out = {}
    for clip, it in corrida["items"].items():
        prev = (anterior or {}).get("items", {}).get(clip)
        if not prev or it.get("puntuacion") is None or prev.get("puntuacion") is None:
            out[clip] = {"delta": None, "mejoran": [], "empeoran": []}
            continue
        mej, emp = [], []
        for k, v in it.get("metricas", {}).items():
            pv = prev.get("metricas", {}).get(k)
            if pv is None or v is None:
                continue
            if v - pv >= 0.1:
                mej.append(k)
            elif pv - v >= 0.1:
                emp.append(k)
        out[clip] = {"delta": round(it["puntuacion"] - prev["puntuacion"], 1), "mejoran": mej, "empeoran": emp}
    return out


def flecha(delta, umbral=1.0):
    if delta is None:
        return "—"
    if abs(delta) < umbral:
        return f"= ({delta:+.1f})"
    return (f"▲ {delta:+.1f}" if delta > 0 else f"▼ {delta:+.1f}")
