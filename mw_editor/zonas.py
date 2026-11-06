"""Zonas seguras por formato y por perfil de plataforma (fuente única de verdad).

IMPORTANTE - HONESTIDAD DE LAS CIFRAS
  Ninguna plataforma publica una zona segura en píxeles para TikTok, Instagram Reels ni YouTube Shorts.
  Por eso NINGUNA cifra de interfaz de este archivo es 'oficial'. Cada perfil lleva su `confianza`:
    terceros : cifra publicada por plantillas/blogs de terceros (se citan en docs/investigacion/zonas_seguras.md)
    estimado : cálculo propio (geometría) o conocimiento previo no re-verificado -> TRATAR COMO ESTIMACIÓN
    criterio : criterio propio de Electric Eye (preset 'estandar'), medido sobre capturas, no verificado
  Las ESPECIFICACIONES técnicas (resolución, peso, códec) de LinkedIn/YouTube sí son oficiales, pero eso
  no hace oficiales sus zonas de interfaz.
  Verificación real: docs/guias_zonas/*.png (python -m mw_editor.guias_zonas) para contrastar con capturas de las apps,
  y el 'Safe zone guardrail' de Meta Ads Manager.

Fuente: docs/investigacion/zonas_seguras.json (2026-11-05) + preset 'universal' de Electric Eye (src/formatos.ts, 2026-10-17).

API estable (la usan subs.py, componer.py y los demás módulos):
  set_preset(nombre) / preset()      'universal' (defecto), 'estandar', 'meta-reels', un perfil ('tiktok') o una unión
                                     ('tiktok+instagram-reels+youtube-shorts') para exportar a varias redes a la vez
  seg(formato)                       fracciones {arriba, abajo, izquierda, derecha} NO utilizables
  caja_segura_px(formato)            (x0, y0, x1, y1) dentro de la cual puede ir texto/gráficos
  es_vertical(formato)               9:16, 1:1 y 4:5 usan el diseño 'vertical' (subtítulo bajo la cara)
Nuevas: PERFILES, perfil_px, union_px, union_seg, confianza_union, resumen_union, perfiles_de_formato.
"""
import os

from .common import dims

# --------------------------------------------------------------------------------------------------
# Presets heredados de Electric Eye (solo 9:16, px sobre 1080x1920). Se mantienen tal cual.
# --------------------------------------------------------------------------------------------------
PRESETS_VERTICAL_PX = {
    "estandar": {"arriba": 220, "abajo": 380, "derecha": 140, "izquierda": 40},       # criterio propio EE (no verificado)
    "meta-reels": {"arriba": 269, "abajo": 672, "derecha": 65, "izquierda": 65},      # terceros (Adnova/revid)
    "universal": {"arriba": 269, "abajo": 672, "derecha": 242, "izquierda": 122},     # máximo EE de Meta y TikTok (terceros)
}

# --------------------------------------------------------------------------------------------------
# Perfiles por plataforma. px sobre el lienzo `formato` (vertical 1080x1920, cuadrado 1080x1080,
# 4x5 1080x1350, horizontal 1920x1080). `confianza` aplica a las zonas de interfaz (NO a las specs).
# --------------------------------------------------------------------------------------------------
PERFILES = {
    "tiktok": {
        "nombre": "TikTok", "formato": "vertical", "confianza": "terceros",
        "px": {"arriba": 240, "abajo": 660, "izquierda": 120, "derecha": 140},
        "rango_terceros": {"arriba": (130, 240), "abajo": (250, 660), "izquierda": (60, 120), "derecha": (120, 150)},
        "fuente": "relevantaudience.com/tiktok-ads/tiktok-video-size-ad-specs ; socialync.io/tools/safe-zones/tiktok ; revid.ai/tiktok-safe-zone",
        "nota": "Los terceros se contradicen (abajo 250-660). Se usa el extremo conservador.",
    },
    "instagram-reels": {
        "nombre": "Instagram Reels", "formato": "vertical", "confianza": "terceros",
        "px": {"arriba": 270, "abajo": 672, "izquierda": 65, "derecha": 120},
        "fuente": "adnova.ai/blogs/meta-ad-safe-zones-guide ; revid.ai/instagram-reels-safe-zone ; facebook.com/business/help/980593475366490 (oficial, sin cifras extraídas)",
        "nota": "Dos terceros convergen en ~270/670. La cuadrícula de perfil recorta a 3:4 (240 px arriba y abajo).",
    },
    "youtube-shorts": {
        "nombre": "YouTube Shorts", "formato": "vertical", "confianza": "estimado",
        "px": {"arriba": 270, "abajo": 480, "izquierda": 60, "derecha": 140},
        "fuente": "ESTIMACIÓN propia: YouTube no publica cifra (support.google.com/youtube/answer/72431 solo da specs)",
        "nota": "Botones a la derecha y título/canal abajo; se asume la unión de TikTok y Reels. 1:1 contradictorio.",
    },
    "linkedin-vertical": {
        "nombre": "LinkedIn 9:16", "formato": "vertical", "confianza": "estimado",
        "px": {"arriba": 270, "abajo": 480, "izquierda": 65, "derecha": 120},
        "fuente": "ESTIMACIÓN propia; specs oficiales en linkedin.com/help/lms/answer/85306 (solo móvil)",
        "nota": "Specs oficiales (<=1080x1920, H.264, 500 MB); la zona de interfaz es estimada.",
    },
    "linkedin-cuadrado": {
        "nombre": "LinkedIn 1:1", "formato": "cuadrado", "confianza": "estimado",
        "px": {"arriba": 65, "abajo": 120, "izquierda": 65, "derecha": 65},
        "fuente": "ESTIMACIÓN propia; specs oficiales en linkedin.com/help/lms/answer/85306",
        "nota": "Barra de progreso/controles abajo; el feed no superpone nada más.",
    },
    "linkedin-4x5": {
        "nombre": "LinkedIn 4:5", "formato": "4x5", "confianza": "estimado",
        "px": {"arriba": 70, "abajo": 150, "izquierda": 65, "derecha": 65},
        "fuente": "ESTIMACIÓN propia; specs oficiales en linkedin.com/help/lms/answer/85306",
        "nota": "Relación vertical recomendada por LinkedIn para móvil.",
    },
    "instagram-feed-4x5": {
        "nombre": "Instagram feed 4:5", "formato": "4x5", "confianza": "estimado",
        "px": {"arriba": 70, "abajo": 150, "izquierda": 100, "derecha": 100},
        "fuente": "ESTIMACIÓN propia a partir de la nota del JSON: en la cuadrícula 3:4 el recorte deja x entre 100 y 980",
        "nota": "No hay cifra de terceros para el feed; se toma el margen lateral de la cuadrícula 3:4 y los verticales de LinkedIn 4:5.",
    },
    "youtube-16x9": {
        "nombre": "YouTube 16:9", "formato": "horizontal", "confianza": "estimado",
        "px": {"arriba": 65, "abajo": 110, "izquierda": 96, "derecha": 96},
        "fuente": "ESTIMACIÓN propia; specs oficiales en support.google.com/youtube/answer/1722171",
        "nota": "Barra de progreso, títulos de crédito y título flotante; sin cifra publicada.",
    },
    "linkedin-16x9": {
        "nombre": "LinkedIn 16:9", "formato": "horizontal", "confianza": "estimado",
        "px": {"arriba": 65, "abajo": 110, "izquierda": 96, "derecha": 96},
        "fuente": "ESTIMACIÓN propia; specs oficiales en linkedin.com/help/lms/answer/85306",
        "nota": "Mismo margen que YouTube 16:9.",
    },
}

# Perfiles que cuentan como "todas las redes" por formato cuando el preset no nombra ninguno de ese formato.
PERFILES_POR_DEFECTO = {fm: [n for n, p in PERFILES.items() if p["formato"] == fm]
                        for fm in ("vertical", "cuadrado", "4x5", "horizontal")}

# Columna de botones de la derecha en 9:16 (regla de caja heredada de Electric Eye, criterio propio): x <= 780 desde y >= 840.
COLUMNA_BOTONES_PX = {"x_max": 780, "desde_y": 840, "confianza": "criterio"}

# Recortes de la cuadrícula de perfil de Instagram sobre 1080x1920 (y visible). Terceros / estimado.
CUADRICULA_INSTAGRAM = {"3:4": {"y_visible": (240, 1680), "confianza": "terceros"},
                        "4:5": {"y_visible": (285, 1635), "confianza": "terceros"},
                        "1:1": {"y_visible": (420, 1500), "confianza": "estimado"}}

_ORDEN_CONF = {"oficial": 0, "terceros": 1, "criterio": 2, "estimado": 3}   # de más a menos fiable
_preset = os.environ.get("MW_ZONA", "universal")


def _spec(spec):
    return "+".join(spec) if isinstance(spec, (list, tuple)) else str(spec)


def _nombres(spec):
    return [s.strip() for s in _spec(spec).replace(",", "+").split("+") if s.strip()]


def _validar(spec):
    for n in _nombres(spec):
        if n not in PRESETS_VERTICAL_PX and n not in PERFILES:
            raise ValueError(f"zona desconocida: {n} (usa {', '.join(list(PRESETS_VERTICAL_PX) + list(PERFILES))}; une con '+')")


def set_preset(nombre):
    global _preset
    _validar(nombre)
    _preset = _spec(nombre)


def preset():
    return _preset


def es_vertical(formato):
    """Formatos que usan el diseño 'vertical' (títulos arriba, subtítulo bajo la cara): 9:16, 1:1 y 4:5."""
    return formato in ("vertical", "cuadrado", "4x5")


# --------------------------------------------------------------------------------------------------
# Unión conservadora
# --------------------------------------------------------------------------------------------------
def perfil_px(nombre, formato=None):
    """Márgenes px de un preset o perfil. `formato` (opcional) valida que el perfil sea de ese lienzo."""
    if nombre in PRESETS_VERTICAL_PX:
        if formato and formato != "vertical":
            raise ValueError(f"{nombre} es de formato vertical, no {formato}")
        return dict(PRESETS_VERTICAL_PX[nombre])
    p = PERFILES[nombre]
    if formato and p["formato"] != formato:
        raise ValueError(f"{nombre} es de formato {p['formato']}, no {formato}")
    return dict(p["px"])


def _seleccion(spec, formato):
    """Nombres de `spec` aplicables a `formato`; si ninguno lo es, todos los perfiles por defecto de ese formato."""
    sel = []
    for n in _nombres(spec):
        fm = "vertical" if n in PRESETS_VERTICAL_PX else PERFILES[n]["formato"]
        if fm == formato:
            sel.append(n)
    return sel or list(PERFILES_POR_DEFECTO[formato])


def union_px(spec, formato):
    """UNIÓN CONSERVADORA: el máximo de cada margen entre todos los perfiles de `spec` que aplican a `formato`.
    spec: 'tiktok+instagram-reels+youtube-shorts' o lista. Es lo que hay que respetar al exportar a varias redes a la vez."""
    _validar(spec)
    sel = _seleccion(spec, formato)
    return {k: max(perfil_px(n)[k] for n in sel) for k in ("arriba", "abajo", "izquierda", "derecha")}


def union_seg(spec, formato):
    """Igual que union_px pero en fracciones del lienzo."""
    w, h = dims(formato)
    px = union_px(spec, formato)
    return {"arriba": px["arriba"] / h, "abajo": px["abajo"] / h, "izquierda": px["izquierda"] / w, "derecha": px["derecha"] / w}


def confianza_union(spec, formato):
    """Confianza de la unión = la PEOR de sus miembros (nunca 'oficial': ninguna zona de interfaz lo es)."""
    sel = _seleccion(spec, formato)
    cs = [(("terceros" if n in ("meta-reels", "universal") else "criterio") if n in PRESETS_VERTICAL_PX else PERFILES[n]["confianza"]) for n in sel]
    return max(cs, key=lambda c: _ORDEN_CONF[c])


def resumen_union(spec, formato):
    """Texto de una línea para logs/docs: márgenes, rectángulo seguro y aviso de estimación."""
    w, h = dims(formato)
    px = union_px(spec, formato)
    c = confianza_union(spec, formato)
    aviso = "  [ESTIMACIÓN: ninguna cifra es oficial]" if c != "oficial" else ""
    return (f"{formato} {w}x{h} · {'+'.join(_seleccion(spec, formato))} · márgenes px arriba {px['arriba']} / abajo {px['abajo']} / "
            f"izq {px['izquierda']} / der {px['derecha']} · rect ({px['izquierda']},{px['arriba']})-({w - px['derecha']},{h - px['abajo']}) · confianza {c}{aviso}")


def perfiles_de_formato(formato):
    return list(PERFILES_POR_DEFECTO[formato])


# --------------------------------------------------------------------------------------------------
# API heredada
# --------------------------------------------------------------------------------------------------
def seg(formato):
    """Fracciones {arriba, abajo, izquierda, derecha} del lienzo que NO se pueden usar (según el preset activo).
    9:16: el preset activo ('universal' por defecto, o una unión de perfiles). 1:1, 4:5 y 16:9: la unión de los perfiles
    de ese formato (o los que el preset nombre)."""
    return union_seg(_preset, formato)


def caja_segura_px(formato):
    """(x0, y0, x1, y1) en píxeles dentro de la cual puede ir texto/gráficos."""
    w, h = dims(formato)
    s = seg(formato)
    return (w * s["izquierda"], h * s["arriba"], w * (1 - s["derecha"]), h * (1 - s["abajo"]))
