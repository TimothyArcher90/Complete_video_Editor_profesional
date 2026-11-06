"""Copy por plataforma: plantilla estructurada, validadores medibles y salida en Markdown.

Este modulo NO redacta: el copy lo escribe Claude con el transcript (no hay LLM de pago aqui).
Solo estructura, valida y formatea. Reglas de marca MacroWise codificadas:
  - una cifra rotulada es una afirmacion de marca: sin fuente verificada -> aviso
  - sin promesas de rentabilidad ni asesoria personalizada
  - espanol colombiano: sin voseo argentino
  - maximo 3 parrafos cortos en textos para terceros
  - sin clickbait que el video no cumpla; sin engagement bait penalizado

Uso:
    from mw_editor.copy import plantilla, validar_copy, a_markdown
    c = plantilla("reel")            # dict listo para rellenar
    avisos = validar_copy(c)         # lista de str: "[ERROR|AVISO|PENDIENTE] plataforma.campo: mensaje"
    md = a_markdown(c)               # texto pegable en un Google Doc
CLI:  python -m mw_editor.copy pieza.json [--md salida.md]

Los limites estan en LIMITES con su fuente y confianza (oficial / terceros / estimado).
Verificar los marcados "verificar" en la app antes de fiarse del tope exacto.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from copy import deepcopy

# ---------------------------------------------------------------------------
# Limites por plataforma (ver docs/investigacion/copy_playbook.md para fuentes)
# visible = caracteres que se ven antes del "ver mas" / corte (estimado salvo nota)
# ---------------------------------------------------------------------------
LIMITES = {
    "youtube_largo": {
        "titulo_max": 100, "titulo_ideal": 60,            # 100: oficial; 60: estimado (corte en busqueda/movil)
        "texto_max": 5000, "visible": 150,                 # 5000: oficial; ~100-150 visibles: estimado
        "hashtags_min": 0, "hashtags_max": 3,              # >15 = YouTube los ignora todos (oficial); 3 sobre el titulo (practica)
        "capitulos": True, "portada_palabras_max": 5,
    },
    "youtube_shorts": {
        "titulo_max": 100, "titulo_ideal": 60,
        "texto_max": 5000, "visible": 100,
        "hashtags_min": 0, "hashtags_max": 3,
        "capitulos": False, "portada_palabras_max": 5,
    },
    "instagram_reels": {
        "titulo_max": 0, "titulo_ideal": 0,
        "texto_max": 2200, "visible": 125,                 # 2200: oficial; 125 antes de "mas": estimado/terceros
        "hashtags_min": 0, "hashtags_max": 5,              # Instagram anuncio tope de 5 (verificar); antes 30
        "capitulos": False, "portada_palabras_max": 5,
    },
    "tiktok": {
        "titulo_max": 0, "titulo_ideal": 0,
        "texto_max": 2200, "visible": 100,                 # tope reciente 4000 (verificar); usamos 2200 por prudencia
        "hashtags_min": 0, "hashtags_max": 5,              # estimado
        "capitulos": False, "portada_palabras_max": 5,
    },
    "linkedin": {
        "titulo_max": 0, "titulo_ideal": 0,
        "texto_max": 3000, "visible": 140,                 # 3000: oficial; corte ~140 movil / ~210 escritorio: terceros
        "hashtags_min": 0, "hashtags_max": 5,              # LinkedIn sugiere 3-5 (terceros)
        "capitulos": False, "portada_palabras_max": 5,
    },
}
PLATAFORMAS = list(LIMITES)

# ---------------------------------------------------------------------------
# Listas de palabras / regex
# ---------------------------------------------------------------------------
# Promesa de rentabilidad o asesoria personalizada (marca: nunca)
RE_PROMESA = [
    r"rentabilidad\s+garantizada", r"retorno[s]?\s+garantizado", r"ganancias?\s+(?:seguras?|aseguradas?|garantizadas?)",
    r"\bgarantizad[oa]s?\b", r"sin\s+riesgo", r"riesgo\s+cero", r"duplic(?:a|ar|as|ando)\s+(?:tu|su|el)\s+(?:dinero|capital|plata|inversi[oó]n)",
    r"\bhazte\s+rico\b", r"\bhacerte\s+rico\b", r"te\s+(?:vas?\s+a\s+)?(?:hac(?:er|es)|volv(?:er|eras?))\s+rico",
    r"libertad\s+financiera\s+en\s+\d", r"dinero\s+f[aá]cil", r"ingresos?\s+pasivos?\s+(?:seguros?|garantizados?)",
    r"\bdeber[ií]as\s+(?:comprar|vender|invertir)", r"te\s+recomiendo\s+(?:comprar|vender|invertir)",
    r"mi\s+recomendaci[oó]n\s+es\s+(?:comprar|vender)", r"\bcompra\s+(?:ya|ahora|hoy)\b", r"\bvende\s+(?:ya|ahora|hoy)\b",
    r"no\s+(?:puedes|vas\s+a)\s+perder", r"\b(?:triplic|cuadruplic)(?:a|ar|as)\b",
]
# Voseo / argentinismos (marca: espanol colombiano). Lista explicita para evitar falsos positivos (mas, pais, despues...).
VOSEO = [
    "vos", "tenés", "sabés", "querés", "podés", "sos", "hacés", "decís", "vivís", "pensás", "creés", "mirá", "fijate", "hacé",
    "decime", "dame", "comentá", "suscribite", "seguime", "dejá", "vení", "andá", "ponete", "poné", "contame", "escribí",
    "descargá", "anotate", "anotá", "fijá", "prestá", "pará", "acordate", "mandame", "compartí", "guardá", "sumate",
    "pibe", "boludo", "che", "laburo", "laburar", "guita", "bondi", "pilcha", "quilombo", "re bueno", "ahora te cuento",
]
# Engagement bait que Meta penaliza ("pide" la interaccion sin dar valor)
RE_BAIT = [
    r"\bdale\s+like\b", r"\blike\s+si\b", r"\bdame\s+un\s+like\b", r"\bcomparte\s+(?:si|con\s+\d|para\s+ganar)",
    r"\betiqueta\s+a\s+(?:un|tu|alguien|3|tres)", r"\bcomenta\s+[\"“']?(?:s[ií]|yo|amen|\+)[\"”']?\s+si\b",
    r"\bsorteo\b", r"\bsigue\s+y\s+gana", r"\b(?:comparte|reenv[ií]a)\s+a\s+\d", r"\bcomenta\s+y\s+comparte\b",
    r"\bsuscr[ií]bete\s+y\s+activa\s+la\s+campanita",
]
# Clickbait / hype que el video dificilmente cumple
RE_CLICKBAIT = [
    r"no\s+vas\s+a\s+creer", r"te\s+va\s+a\s+dejar\s+sin\s+palabras", r"\bincre[ií]ble\b", r"\bshock(?:ante)?\b",
    r"esto\s+(?:lo\s+)?cambia\s+todo", r"nadie\s+te\s+(?:cuenta|dice)\s*(?:esto|la\s+verdad)?\s*[.!]?$", r"\burgente\b",
    r"lo\s+que\s+(?:no\s+)?quieren\s+que\s+(?:sepas|veas)", r"te\s+(?:van\s+a|est[aá]n)\s+enga[nñ]ando",
    r"\bnadie\s+habla\s+de\s+esto\b", r"mira\s+hasta\s+el\s+final\s+para",
]
# Tics de prosa generica (skill anti-ai-writing)
AI_TICS = [
    "desbloquea", "revoluciona", "sumérgete", "sumergete", "en el mundo actual", "en la era digital", "es importante destacar",
    "crucial", "panorama", "paradigma", "sinergia", "holístico", "holistico", "robusto", "transformador", "game changer",
    "vamos a explorar", "vamos a desentrañar", "desentrañar", "tapiz", "en un mundo donde", "a fin de cuentas",
    "de la antigüedad a la modernidad",
]
# Aperturas muertas del gancho
APERTURAS_MUERTAS = [
    "hoy vamos a", "en este video", "en este vídeo", "bienvenidos", "bienvenido", "hola", "te voy a contar", "no te pierdas",
    "en el mundo actual", "en la era", "antes de empezar", "vamos a hablar de", "quiero hablarte", "nadie habla de",
    "esto es lo que nadie te cuenta", "mira hasta el final", "suscríbete", "suscribete",
]
# Hashtags de relleno / spam
HASHTAGS_RELLENO = {
    "#fyp", "#foryou", "#foryoupage", "#parati", "#paratii", "#viral", "#trending", "#tiktok", "#reels", "#reel", "#explore",
    "#explorepage", "#instagood", "#love", "#follow", "#like", "#followforfollow", "#f4f", "#l4l", "#shorts", "#short",
    "#youtube", "#video", "#tendencia", "#xyzbca", "#fypシ",
}
CTA_INICIO = ("comenta", "suscr", "sígueme", "siguenos", "sigue ", "comparte", "dale ", "descarga", "link en", "enlace en")
RE_NO_ASESORIA = re.compile(r"no\s+(?:es|constituye|son)\s+(?:una\s+)?(?:asesor[ií]a|recomendaci[oó]n)|no\s+(?:es|son)\s+asesor", re.I)
RE_PENDIENTE = re.compile(r"\[\s*(?:PENDIENTE|FALTA|COMPLETAR|XXX|TODO)[^\]]*\]", re.I)
RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")
RE_HASHTAG = re.compile(r"(?<!\w)#[\wÁÉÍÓÚÜÑáéíóúüñ]+")
RE_TS = re.compile(r"^\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\b")
RE_URL = re.compile(r"https?://\S+|www\.\S+")
# Cifras: simbolo/unidad financiera o numero >=100 que no sea anio
RE_CIFRA = re.compile(
    r"(?<![\w#/:.])(?:US\$|U\$S|\$|USD\s?|COP\s?)?\d+(?:[.,]\d{3})*(?:[.,]\d+)?\s?"
    r"(?:%|por\s+ciento|mil\s+millones|billones?|trillones?|millones?|miles|mil\b|x\b|veces|USD|COP|d[oó]lares|pesos|puntos\s+b[aá]sicos|pb)?",
    re.I,
)
UNIDADES_CIFRA = re.compile(r"%|por\s+ciento|mil\s+millones|billon|trillon|millon|miles|\bmil\b|\dx\b|\d\s?x\b|veces|usd|cop|d[oó]lar|peso|puntos\s+b|\bpb\b|\$", re.I)


# ---------------------------------------------------------------------------
# Plantilla
# ---------------------------------------------------------------------------
def _bloque_plataforma(pf: str) -> dict:
    b = {
        "titulo": "",            # YouTube; vacio en el resto
        "hook": "",              # primera linea visible (sin 'ver mas'); debe ir ya en el texto
        "cuerpo": "",            # max 3 parrafos cortos
        "cta": "",               # cierre; nunca al inicio
        "hashtags": [],
        "texto_pantalla": [],    # rotulos en video (cada uno corto)
        "texto_portada": "",     # max 5 palabras
        "enlaces": [],           # [{"etiqueta": "...", "url": "..."}]
        "disclaimer": "",        # 'no es asesoria' (YouTube/LinkedIn obligatorio por marca)
    }
    if LIMITES[pf]["capitulos"]:
        b["capitulos"] = []      # [{"t": "00:00", "titulo": "Intro: ..."}]
    if pf == "linkedin":
        b["formato"] = "video"   # "video" | "post"
    return b


def plantilla(tipo: str = "reel") -> dict:
    """Devuelve un copy vacio. tipo: 'reel' (IG, TikTok, Shorts, LinkedIn) | 'largo' (YouTube + LinkedIn) | 'todo'."""
    pfs = {"reel": ["instagram_reels", "tiktok", "youtube_shorts", "linkedin"],
           "largo": ["youtube_largo", "linkedin"], "todo": PLATAFORMAS}[tipo]
    return {
        "meta": {
            "pieza": "", "tipo": tipo, "tema": "", "invitado": "[PENDIENTE: nombre del invitado]", "idioma": "es-CO",
            "duracion_s": 0, "no_publicar": False, "nota": "",
        },
        "cifras": [],   # [{"texto": "40%", "fuente": "url/doc oficial", "verificada": true}]
        "plataformas": {pf: _bloque_plataforma(pf) for pf in pfs},
    }


# ---------------------------------------------------------------------------
# Ensamblado
# ---------------------------------------------------------------------------
def _parrafos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]


def _capitulos_txt(caps: list[dict]) -> str:
    return "\n".join(f"{c.get('t', '')} {c.get('titulo', '')}".strip() for c in caps or [])


def ensamblar(pf: str, d: dict) -> str:
    """Texto final tal como se pegaria en la plataforma (descripcion/caption/post)."""
    partes = []
    if d.get("hook"):
        partes.append(d["hook"].strip())
    if d.get("cuerpo"):
        partes.append(d["cuerpo"].strip())
    if d.get("cta"):
        partes.append(d["cta"].strip())
    enl = [f"{e.get('etiqueta', '')}: {e.get('url', '')}".strip(": ") for e in d.get("enlaces", [])]
    if enl:
        partes.append("\n".join(enl))
    if d.get("capitulos"):
        partes.append(_capitulos_txt(d["capitulos"]))
    if d.get("disclaimer"):
        partes.append(d["disclaimer"].strip())
    if d.get("hashtags"):
        partes.append(" ".join(d["hashtags"]))
    return "\n\n".join(partes)


def _sin_ruido(txt: str) -> str:
    """Quita capitulos (marcas de tiempo), URLs y hashtags antes de buscar cifras."""
    lineas = [l for l in txt.splitlines() if not RE_TS.match(l)]
    t = "\n".join(lineas)
    t = RE_URL.sub(" ", t)
    t = RE_HASHTAG.sub(" ", t)
    return re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", t)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[\s.,]", "", s)


def extraer_cifras(txt: str) -> list[str]:
    """Cifras rotulables: con simbolo/unidad financiera, o numeros >=100 que no sean anios (1900-2100)."""
    out = []
    for m in RE_CIFRA.finditer(_sin_ruido(txt)):
        tok = m.group(0).strip()
        if not tok:
            continue
        mnum = re.search(r"\d[\d.,]*", tok)
        digitos = re.sub(r"\D", "", mnum.group(0)) if mnum else ""
        es_anio = bool(mnum) and re.fullmatch(r"(19|20)\d{2}", mnum.group(0)) is not None
        if UNIDADES_CIFRA.search(tok):
            out.append(tok)
        elif digitos and int(digitos[:9]) >= 100 and not es_anio:
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Validacion
# ---------------------------------------------------------------------------
def _hay(patrones: list[str], txt: str) -> list[str]:
    hallados = []
    for p in patrones:
        m = re.search(p, txt, re.I | re.M)
        if m:
            hallados.append(m.group(0).strip())
    return hallados


def _voseo(txt: str) -> list[str]:
    bajo = txt.lower()
    hall = []
    for w in VOSEO:
        if " " in w:
            if w in bajo:
                hall.append(w)
        elif re.search(rf"(?<![\wáéíóúñ]){re.escape(w)}(?![\wáéíóúñ])", bajo):
            hall.append(w)
    return hall


def _palabras(txt: str) -> list[str]:
    return re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ$%]+", txt or "")


def _mayusculas(txt: str) -> list[str]:
    return [w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ]{4,}\b", txt or "")]


def validar_copy(copy_json: dict | str) -> list[str]:
    """Valida el copy. Devuelve lista de avisos 'NIVEL plataforma.campo: mensaje'.
    ERROR = incumple regla dura o limite oficial; AVISO = riesgo/criterio; PENDIENTE = falta dato de David.
    Lista vacia = sin hallazgos medibles (no garantiza que el copy sea bueno)."""
    c = json.loads(copy_json) if isinstance(copy_json, str) else copy_json
    av: list[str] = []
    meta = c.get("meta", {})
    cifras = c.get("cifras", [])
    cif_ok = [_norm(x.get("texto", "")) for x in cifras if x.get("fuente") and x.get("verificada")]
    cif_pend = [_norm(x.get("texto", "")) for x in cifras if not (x.get("fuente") and x.get("verificada"))]

    def add(nivel, donde, msg):
        av.append(f"[{nivel}] {donde}: {msg}")

    if meta.get("no_publicar"):
        add("AVISO", "meta", "marcado NO PUBLICAR (ejemplo de formato / material de terceros)")
    if RE_PENDIENTE.search(json.dumps(meta, ensure_ascii=False)):
        add("PENDIENTE", "meta.invitado", "falta dato en meta (nombre del invitado u otro)")

    for pf, d in c.get("plataformas", {}).items():
        if pf not in LIMITES:
            add("ERROR", pf, f"plataforma desconocida (validas: {', '.join(PLATAFORMAS)})")
            continue
        L = LIMITES[pf]
        full = ensamblar(pf, d)
        todo = " \n".join([d.get("titulo", ""), full, d.get("texto_portada", ""), " ".join(d.get("texto_pantalla", []))])

        # pendientes
        for m in RE_PENDIENTE.finditer(todo):
            add("PENDIENTE", pf, f"dato por completar: {m.group(0)}")

        # titulo
        t = d.get("titulo", "")
        if L["titulo_max"]:
            if not t.strip():
                add("ERROR", f"{pf}.titulo", "titulo vacio")
            if len(t) > L["titulo_max"]:
                add("ERROR", f"{pf}.titulo", f"{len(t)} car > tope {L['titulo_max']}")
            elif len(t) > L["titulo_ideal"]:
                add("AVISO", f"{pf}.titulo", f"{len(t)} car > {L['titulo_ideal']} ideal (se corta en busqueda/movil)")
            if len(_mayusculas(t)) > 1:
                add("AVISO", f"{pf}.titulo", f"mas de 1 palabra en MAYUSCULAS: {_mayusculas(t)} (regla: maximo 1 de enfasis)")
            if t.strip().endswith("?") is False and not any(ch.isdigit() for ch in t) and len(_palabras(t)) < 4:
                add("AVISO", f"{pf}.titulo", "titulo de menos de 4 palabras sin cifra ni pregunta: poca promesa")

        # hook
        h = d.get("hook", "").strip()
        if not h:
            add("ERROR", f"{pf}.hook", "falta la primera linea (hook)")
        else:
            if len(h) > L["visible"]:
                add("ERROR", f"{pf}.hook", f"{len(h)} car > {L['visible']} visibles antes del 'ver mas': la idea queda cortada")
            if not full.startswith(h):
                add("ERROR", f"{pf}.hook", "el texto publicado no empieza por el hook")
            hl = h.lower()
            for a in APERTURAS_MUERTAS:
                if hl.startswith(a):
                    add("AVISO", f"{pf}.hook", f"apertura muerta: '{a}' (DELAY: el tema debe llegar en la primera frase)")
            if hl.startswith(CTA_INICIO):
                add("ERROR", f"{pf}.hook", "un CTA no abre: los CTA cierran")
            if not (any(ch.isdigit() for ch in h) or "?" in h or re.search(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}", h[1:])):
                add("AVISO", f"{pf}.hook", "sin cifra, pregunta ni nombre propio: probablemente generico (nivel 1-2 de especificidad)")

        # longitud total
        if len(full) > L["texto_max"]:
            add("ERROR", f"{pf}.texto", f"{len(full)} car > tope {L['texto_max']}")
        if pf != "youtube_largo" and len(_parrafos(d.get("cuerpo", ""))) > 3:
            add("AVISO", f"{pf}.cuerpo", f"{len(_parrafos(d['cuerpo']))} parrafos > 3 (regla: maximo 3 parrafos cortos)")
        elif len(_parrafos(d.get("cuerpo", ""))) > 3:
            add("AVISO", f"{pf}.cuerpo", "mas de 3 parrafos en el cuerpo (la lista de capitulos va aparte)")
        for i, p in enumerate(_parrafos(d.get("cuerpo", "")), 1):
            if len(p) > 350:
                add("AVISO", f"{pf}.cuerpo", f"parrafo {i} de {len(p)} car: partirlo (corto = <=350)")

        # hashtags
        hs = d.get("hashtags", [])
        malos = [x for x in hs if not re.fullmatch(r"#[\wÁÉÍÓÚÜÑáéíóúüñ]+", x)]
        if malos:
            add("ERROR", f"{pf}.hashtags", f"formato invalido (sin # o con espacios): {malos}")
        if len(hs) > L["hashtags_max"]:
            add("ERROR" if pf.startswith("youtube") or pf == "instagram_reels" else "AVISO", f"{pf}.hashtags", f"{len(hs)} > maximo recomendado {L['hashtags_max']}")
        if len({x.lower() for x in hs}) != len(hs):
            add("AVISO", f"{pf}.hashtags", "hashtags repetidos")
        relleno = [x for x in hs if x.lower() in HASHTAGS_RELLENO]
        if relleno:
            add("AVISO", f"{pf}.hashtags", f"hashtags de relleno sin tema: {relleno}")
        # hashtags dentro del cuerpo
        if RE_HASHTAG.search(d.get("cuerpo", "")) or RE_HASHTAG.search(h):
            add("AVISO", f"{pf}.cuerpo", "hashtags dentro del texto: van al final y en la lista")

        # cta
        cta = d.get("cta", "").strip()
        if not cta:
            add("AVISO", f"{pf}.cta", "sin CTA (comentar una palabra clave, guardar, enviar o pregunta concreta)")
        elif len(cta) > 220:
            add("AVISO", f"{pf}.cta", "CTA largo (>220 car)")

        # capitulos
        if L["capitulos"]:
            _validar_capitulos(d.get("capitulos", []), meta.get("duracion_s", 0), pf, add)

        # texto en portada / pantalla
        tp = d.get("texto_portada", "")
        if tp and len(_palabras(tp)) > L["portada_palabras_max"]:
            add("ERROR", f"{pf}.texto_portada", f"{len(_palabras(tp))} palabras > {L['portada_palabras_max']}")
        if not tp and pf in ("youtube_largo", "youtube_shorts"):
            add("AVISO", f"{pf}.texto_portada", "sin texto de miniatura/portada")
        for i, r in enumerate(d.get("texto_pantalla", []), 1):
            if len(_palabras(r)) > 8:
                add("AVISO", f"{pf}.texto_pantalla[{i}]", f"rotulo de {len(_palabras(r))} palabras: partirlo (<=8)")

        # reglas de marca sobre todo el texto
        for x in _hay(RE_PROMESA, todo):
            add("ERROR", pf, f"lenguaje de promesa de rentabilidad/asesoria: '{x}'")
        vos = _voseo(todo)
        if vos:
            add("ERROR", pf, f"voseo/argentinismo (marca: espanol colombiano): {sorted(set(vos))}")
        for x in _hay(RE_BAIT, todo):
            add("AVISO", pf, f"engagement bait (Meta/TikTok lo penalizan): '{x}'")
        for x in _hay(RE_CLICKBAIT, todo):
            add("AVISO", pf, f"clickbait que el video debe cumplir o se quita: '{x}'")
        tics = [w for w in AI_TICS if w in todo.lower()]
        if tics:
            add("AVISO", pf, f"tics de prosa generica (anti-ai-writing): {tics}")
        if "—" in todo:
            add("AVISO", pf, "raya larga (—): usar punto, coma o dos puntos")
        if re.search(r"\bno\s+(?:es|son|se\s+trata\s+de)\s+[^.!?\n]{2,60}[,.]\s*(?:es|son|sino)\b", todo, re.I):
            add("AVISO", pf, "formula 'no es X, es Y': solo vale si Y es concreto y el video lo entrega")
        if len(RE_EMOJI.findall(todo)) > 3:
            add("AVISO", pf, f"{len(RE_EMOJI.findall(todo))} emojis > 3")

        # aviso de no-asesoria
        if pf in ("youtube_largo", "youtube_shorts", "linkedin") and not RE_NO_ASESORIA.search(full):
            add("AVISO", f"{pf}.disclaimer", "falta aviso 'no es asesoria de inversion' en la descripcion")

        # cifras sin fuente
        for cif in extraer_cifras(todo):
            n = _norm(cif)
            if any(n and (n in o or o in n) for o in cif_ok):
                continue
            if any(n and (n in o or o in n) for o in cif_pend):
                add("PENDIENTE", pf, f"cifra '{cif}' registrada pero sin fuente oficial verificada")
            else:
                add("ERROR", pf, f"cifra '{cif}' sin fuente: registrarla en 'cifras' con fuente oficial o quitarla")

        # enlaces
        for e in d.get("enlaces", []):
            if not str(e.get("url", "")).startswith("http"):
                add("PENDIENTE", f"{pf}.enlaces", f"enlace '{e.get('etiqueta', '?')}' sin URL valida")
    return av


def _a_seg(ts: str) -> int:
    p = [int(x) for x in ts.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


def _validar_capitulos(caps, dur, pf, add):
    if not caps:
        add("AVISO", f"{pf}.capitulos", "sin capitulos (YouTube: el primero en 00:00, minimo 3, cada uno >=10 s)")
        return
    ok = True
    for c in caps:
        if not re.fullmatch(r"(?:\d{1,2}:)?\d{1,2}:\d{2}", c.get("t", "")):
            add("ERROR", f"{pf}.capitulos", f"marca invalida '{c.get('t')}' (usar mm:ss o h:mm:ss)")
            ok = False
        if not c.get("titulo", "").strip():
            add("ERROR", f"{pf}.capitulos", f"capitulo {c.get('t')} sin titulo")
    if not ok:
        return
    if caps[0]["t"] not in ("0:00", "00:00"):
        add("ERROR", f"{pf}.capitulos", "el primer capitulo debe empezar en 00:00 (si no, YouTube no los activa)")
    if len(caps) < 3:
        add("ERROR", f"{pf}.capitulos", f"{len(caps)} capitulos < 3 (minimo de YouTube)")
    segs = [_a_seg(c["t"]) for c in caps]
    for a, b, c in zip(segs, segs[1:], caps[1:]):
        if b <= a:
            add("ERROR", f"{pf}.capitulos", f"marcas no ascendentes en {c['t']}")
        elif b - a < 10:
            add("ERROR", f"{pf}.capitulos", f"capitulo de {b - a} s antes de {c['t']} (<10 s: YouTube lo ignora)")
    if dur and segs[-1] >= dur:
        add("ERROR", f"{pf}.capitulos", f"ultima marca {caps[-1]['t']} fuera de la duracion ({dur} s)")
    if not caps[0]["titulo"].lower().startswith(("intro", "lo que", "presentaci")):
        add("AVISO", f"{pf}.capitulos", "primer capitulo sin 'Intro: lo que veras' (patron Aztec/Harris)")


# ---------------------------------------------------------------------------
# Markdown listo para Google Doc
# ---------------------------------------------------------------------------
NOMBRES = {
    "youtube_largo": "YouTube (video largo)", "youtube_shorts": "YouTube Shorts", "instagram_reels": "Instagram Reels",
    "tiktok": "TikTok", "linkedin": "LinkedIn",
}


def a_markdown(copy_json: dict | str, con_avisos: bool = True) -> str:
    c = json.loads(copy_json) if isinstance(copy_json, str) else deepcopy(copy_json)
    meta = c.get("meta", {})
    out = []
    if meta.get("no_publicar"):
        out += ["> NO PUBLICAR. Ejemplo de formato sobre material de terceros.", ""]
    out.append(f"# {meta.get('pieza') or 'Copy de pieza'}")
    ficha = [f"Tema: {meta['tema']}" if meta.get("tema") else "", f"Invitado: {meta['invitado']}" if meta.get("invitado") else "",
             f"Duracion: {meta['duracion_s']} s" if meta.get("duracion_s") else ""]
    out += [" | ".join(x for x in ficha if x), ""]
    for pf, d in c.get("plataformas", {}).items():
        out.append(f"## {NOMBRES.get(pf, pf)}" + (f" ({d['formato']})" if d.get("formato") else ""))
        if d.get("titulo"):
            out += ["**Titulo**", d["titulo"], ""]
        if d.get("texto_portada"):
            out += ["**Texto de portada/miniatura**", d["texto_portada"], ""]
        if d.get("texto_pantalla"):
            out += ["**Texto en pantalla**"] + [f"- {x}" for x in d["texto_pantalla"]] + [""]
        etiqueta = "Descripcion" if pf.startswith("youtube") else ("Texto del post" if pf == "linkedin" else "Caption")
        out += [f"**{etiqueta} (copiar y pegar)**", "```", ensamblar(pf, d), "```", ""]
    cifras = c.get("cifras", [])
    if cifras:
        out += ["## Cifras y fuentes"]
        for x in cifras:
            est = "verificada" if x.get("verificada") and x.get("fuente") else "PENDIENTE de verificar"
            out.append(f"- {x.get('texto')}: {x.get('fuente') or 'sin fuente'} ({est})")
        out.append("")
    if con_avisos:
        av = validar_copy(c)
        out += ["## Validacion automatica", *(f"- {a}" for a in av)] if av else ["## Validacion automatica", "- Sin hallazgos medibles."]
        out.append("")
    return "\n".join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Valida y formatea copy por plataforma")
    ap.add_argument("json", nargs="?", help="archivo JSON del copy; sin argumento imprime la plantilla")
    ap.add_argument("--tipo", default="reel", choices=["reel", "largo", "todo"])
    ap.add_argument("--md", help="escribe el Markdown en este archivo")
    a = ap.parse_args(argv)
    if not a.json:
        print(json.dumps(plantilla(a.tipo), ensure_ascii=False, indent=2))
        return 0
    c = json.loads(open(a.json, encoding="utf-8").read())
    av = validar_copy(c)
    print("\n".join(av) or "Sin hallazgos medibles.")
    if a.md:
        open(a.md, "w", encoding="utf-8").write(a_markdown(c))
    return 1 if any(x.startswith("[ERROR]") for x in av) else 0


if __name__ == "__main__":
    sys.exit(main())
