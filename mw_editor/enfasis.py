"""Énfasis hablado -> propuestas de TEXTO GRANDE sobre el presentador.

Entrada: words_final.json (palabras ya sincronizadas al timeline final: lista de {"w","s","e"}).
Salida (proponer): {"titulos_grandes": [...], "impacto": [...], "cta": [...], "cifras": [...], "descartados": [...], "resumen": {...}}
Los elementos llevan claves con prefijo "_" (tipo, score, motivo, solape) que el motor ignora: sirven a quien revisa el plan.

QUÉ SE DETECTA (cada detector es determinista; ES y EN):
  contraste   "no X sino Y", "no es X, es Y", "not X but Y", "it's not X, it's Y"        -> titulo (linea1 = No X, linea2 = Y)
  pregunta    pregunta retórica (frase que termina en ?)                                      -> titulo (linea1 = etiqueta, linea2 = núcleo)
  imperativo  verbo de atención/acción al inicio de frase (imagina, recuerda, compra...)      -> titulo; CTA (comenta, suscríbete...) -> cta
  superlativo "el mayor", "récord", "nunca", "the biggest", "ever"                           -> titulo, o impacto si es una sola palabra
  nombre      lugares y activos del diccionario de detectar.py + nombres propios              -> titulo con etiqueta de categoría
  pausa       frase corta (2-6 palabras) tras una pausa ≥ 0,8 s                              -> titulo
  cifra       número (con unidad)                                                             -> CANDIDATA de tarjeta de cifra, SIEMPRE verificada:false

REGLAS (parámetros en CFG):
  * El texto AÑADE, no duplica: cada título arranca cuando termina la frase que refuerza (o se desplaza hasta que lo haga) y se
    descarta si más de `max_solape` (50 %) de sus palabras con contenido se están diciendo mientras está en pantalla.
    Excepciones declaradas: el 'impacto' (la palabra gigante ES el énfasis) y las etiquetas de categoría (linea1 no se dice).
  * Lectura: dur >= 0,8 + n_palabras / lectura_pal_s (3 palabras/s como máximo), entre dur_min y dur_max.
  * Separación: mín. `sep_min` s entre inicios y `hueco` s entre el fin de uno y el inicio del siguiente; máx. `max_por_min` por minuto.
  * Ninguna cifra aparece en un texto si no está en el audio (verificar_cifras_en_audio); las cifras nunca son verificada:true aquí."""
import re

from .detectar import ACTIVOS, LUGARES, RE_FIN, STOP_EN, STOP_ES, idioma_probable, norm, oraciones

CFG = {
    "max_por_min": 5,          # textos grandes (título + impacto + cta) como máximo por minuto
    "cifras_por_min": 3,       # candidatas a tarjeta de cifra por minuto (cuota aparte: no le quitan sitio a los títulos)
    "sep_min": 4.0,            # s mínimos entre inicios de dos propuestas
    "hueco": 1.0,              # s mínimos entre el fin de una y el inicio de la siguiente
    "t_min": 0.8,              # nada antes de este instante (deja respirar el arranque / lower third)
    "lectura_pal_s": 3.0,      # velocidad máxima de lectura: 3 palabras por segundo
    "dur_min": 1.6,
    "dur_max": 4.5,
    "max_solape": 0.5,         # fracción máxima de palabras con contenido del título que se dicen mientras está en pantalla
    "impacto_dur": 1.0,        # ≤ 1,2 s por norma de marca
    "impacto_por_min": 2,
    "impacto_sep": 6.0,
    "cifra_dur": 3.0,
    "pausa_larga": 0.8,
    "min_score": 40,
}
ANIMACIONES = ("subir", "escala", "reveal", "barrido")

_COP_ES = {"es", "son", "fue", "fueron", "era", "eran", "será", "serán", "significa", "representa", "implica"}
_COP_EN = {"is", "are", "was", "were", "it's", "its", "they're", "that's", "this", "we're", "he's", "she's", "it", "isnt", "isn't"}
_NEG_EN = {"not", "isn't", "aren't", "wasn't", "weren't", "doesn't", "don't", "didn't", "won't", "can't", "isnt", "arent"}
_CTA_ES = {"comenta", "comenten", "suscríbete", "suscribete", "suscríbanse", "síguenos", "siguenos", "sígueme", "sigueme", "escríbeme", "escribeme", "escríbenos", "comparte", "guarda", "descarga", "regístrate", "registrate", "apúntate", "apuntate", "reserva", "agenda", "visita", "dale"}
_CTA_EN = {"comment", "subscribe", "follow", "share", "save", "download", "join", "click", "book", "grab"}
_IMPER_ES = {"imagina", "piensa", "recuerda", "mira", "fíjate", "fijate", "ojo", "cuidado", "escucha", "evita", "olvida", "compra", "vende", "invierte", "ahorra", "aprende", "descubre", "empieza", "comienza", "prueba", "usa", "haz", "deja", "espera", "pregúntate", "preguntate", "atención", "atencion"}
_IMPER_EN = {"imagine", "think", "remember", "look", "watch", "notice", "listen", "avoid", "forget", "buy", "sell", "invest", "learn", "discover", "start", "try", "use", "make", "stop", "wait", "ask", "beware", "careful"}
_SUPER_ES = {"mayor", "menor", "mejor", "peor", "máximo", "máxima", "maximo", "maxima", "mínimo", "mínima", "minimo", "minima", "récord", "record", "histórico", "histórica", "historico", "historica", "único", "única", "unico", "unica", "primer", "primera", "primero", "último", "última", "ultimo", "ultima", "jamás", "jamas", "nunca", "imposible"}
_SUPER_EN = {"biggest", "largest", "smallest", "best", "worst", "highest", "lowest", "greatest", "record", "ever", "never", "first", "only", "historic", "all-time", "impossible", "fastest", "cheapest"}
_IMPACTO_UNA = {"nunca", "jamás", "jamas", "récord", "record", "histórico", "histórica", "imposible", "gratis", "urgente", "peligro", "ojo", "cuidado", "never", "ever", "record", "historic", "impossible", "free", "urgent", "danger", "careful", "beware", "boom", "crash", "colapso", "collapse"}
_MESES = set("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre lunes martes miércoles jueves viernes sábado domingo january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday".split())
_UNIDADES_ES = {"millones", "millón", "billones", "billón", "mil", "dólares", "dolares", "euros", "pesos", "puntos", "años", "veces", "x", "trillones", "pbs", "usd"}
_UNIDADES_EN = {"million", "billion", "trillion", "thousand", "dollars", "euros", "points", "years", "times", "x", "basis", "bps", "usd", "percent"}
_ETIQ = {
    "es": {"pregunta": "La pregunta", "lugar": "Lugar", "activo": "Activo", "nombre": "Clave"},
    "en": {"pregunta": "The question", "lugar": "Place", "activo": "Asset", "nombre": "Key"},
}
_SCORE = {"contraste": 90, "cta": 85, "pregunta": 70, "impacto": 62, "imperativo": 60, "superlativo": 65, "lugar": 55, "activo": 55, "nombre": 48, "pausa": 45, "cifra": 95}


# ---------- utilidades ----------
def _stop(idioma):
    return STOP_EN if idioma == "en" else STOP_ES


def _txt(pal, a, b):
    """Texto de las palabras a..b (incluidas) sin signos de apertura ni cierre sueltos."""
    s = " ".join(pal[i]["w"] for i in range(a, b + 1))
    return re.sub(r"[¿¡]", "", s).strip(" ,;:.?!…—-\"“”")


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def _recortar_extremos(pal, a, b, idioma):
    """Quita palabras funcionales de los bordes del tramo [a, b] (no deja 'de la' colgando)."""
    st = _stop(idioma)
    while a <= b and norm(pal[a]["w"]) in st:
        a += 1
    while b >= a and norm(pal[b]["w"]) in st:
        b -= 1
    return a, b


def _n_pal(s):
    return len([x for x in s.split() if x])


def _contenido(s, idioma):
    st = _stop(idioma)
    return {norm(t) for t in s.split() if norm(t) and norm(t) not in st}


def _digitos(s):
    return re.findall(r"\d+(?:[.,]\d+)*", s)


def verificar_cifras_en_audio(texto, pal):
    """True si TODAS las cifras de `texto` aparecen en las palabras habladas. Garantía de que no se rotula un número inventado."""
    habladas = {d.strip(".,") for w in pal for d in _digitos(w["w"])}
    return all(d.strip(".,") in habladas for d in _digitos(texto))


def _dur_lectura(n_pal, cfg):
    d = 0.8 + n_pal / cfg["lectura_pal_s"]
    return round(min(cfg["dur_max"], max(cfg["dur_min"], d)), 2)


# ---------- detectores (cada uno devuelve candidatos con tramo [i0, i1] de palabras) ----------
def _cand(tipo, i0, i1, **kw):
    c = {"tipo": tipo, "i0": i0, "i1": i1, "score": _SCORE.get(tipo, 40), "forma": "titulo"}
    c.update(kw)
    return c


def _fin_tramo(pal, desde, sent, max_pal):
    """Último índice del tramo que empieza en `desde` dentro de la frase: corta en puntuación fuerte, coma tras 2+ palabras o max_pal."""
    fin = desde
    for k in sent:
        if k < desde:
            continue
        fin = k
        w = pal[k]["w"]
        if re.search(r"[.?!;…]$", w) or (w.endswith(",") and k - desde >= 1) or k - desde + 1 >= max_pal:
            break
    return fin


def _contraste(pal, toks, sent, idioma):
    out = []
    pos_en_sent = {k: n for n, k in enumerate(sent)}
    for n, i in enumerate(sent):
        t = toks[i]
        es_neg = (t == "no") if idioma == "es" else (t in _NEG_EN)
        if not es_neg:
            continue
        limite = sent[min(len(sent) - 1, n + 11)]
        x_ini = i + 1
        hallado = None
        # A) "... sino (que) Y" / "... but Y"
        for j in range(i + 1, limite + 1):
            if j not in pos_en_sent:
                break
            if toks[j] == ("sino" if idioma == "es" else "but"):
                y_ini = j + 1
                if idioma == "es" and y_ini in pos_en_sent and toks[y_ini] == "que":
                    y_ini += 1
                if y_ini in pos_en_sent:
                    hallado = (j - 1, y_ini)
                break
        # B) "no es X, es Y" / "it's not X, it's Y"
        if not hallado:
            for k in range(i + 1, limite):
                if k + 1 not in pos_en_sent:
                    break
                if pal[k]["w"].endswith(","):
                    sig = toks[k + 1]
                    cop = (_COP_ES if idioma == "es" else _COP_EN)
                    if sig in cop:
                        y_ini = k + 2
                        if idioma == "en" and y_ini in pos_en_sent and toks[k + 1] in ("it", "this") and toks[y_ini] in ("is", "are"):
                            y_ini += 1
                        if y_ini in pos_en_sent:
                            hallado = (k, y_ini)
                    break
        if not hallado:
            continue
        x_fin, y_ini = hallado
        if x_fin < x_ini:
            continue
        y_fin = _fin_tramo(pal, y_ini, sent, 7)
        # X: 'No es una burbuja' (se conserva el verbo copulativo) <= 5 palabras
        x_fin_rec = min(x_fin, x_ini + 4)
        linea1 = ("No " if idioma == "es" else "Not ") + _txt(pal, x_ini, x_fin_rec)
        if idioma == "es" and norm(pal[x_ini]["w"]) in _COP_ES:
            linea1 = "No " + _txt(pal, x_ini, x_fin_rec)
        yi = y_ini
        cop = _COP_ES if idioma == "es" else {"is", "are"}
        if norm(pal[yi]["w"]) in cop and yi < y_fin:
            yi += 1
        linea2 = _cap(_txt(pal, yi, y_fin))
        if _n_pal(linea2) < 1 or _n_pal(linea1) < 2:
            continue
        out.append(_cand("contraste", i, y_fin, linea1=linea1, linea2=linea2, color="lima", anim="reveal",
                         motivo=f"contraste '{_txt(pal, i, y_fin)}'"))
    return out


def _pregunta(pal, toks, sent, idioma):
    if not sent or not pal[sent[-1]]["w"].rstrip("\"”)").endswith("?"):
        return []
    n = len(sent)
    if n < 3 or n > 16:
        return []
    a, b = sent[0], sent[-1]
    for k in reversed(sent[:-1]):                       # 'You got X, are you sure Y?' -> sólo 'are you sure Y?'
        if pal[k]["w"].endswith(",") and b - k >= 3:
            a = k + 1
            n = b - a + 1
        if pal[k]["w"].endswith(","):
            break
    if n <= 6:
        ia, ib = a, b
        nucleo = _txt(pal, ia, ib)
    else:
        ini = max(a, b - 4)
        for k in range(a, b):
            if toks[k] in (("that", "if", "whether") if idioma == "en" else ("que", "si")) and b - k <= 8:
                ini = k + 1
                break
        ia, ib = _recortar_extremos(pal, ini, b, idioma)
        nucleo = _txt(pal, ia, ib)
    if ia > ib or _n_pal(nucleo) < 2:
        return []
    return [_cand("pregunta", a, b, linea1=_ETIQ[idioma]["pregunta"], linea2=_cap(nucleo), color="lima", anim="subir",
                  motivo=f"pregunta retórica '{_txt(pal, a, b)}'")]


def _imperativo(pal, toks, sent, idioma):
    i = sent[0]
    t = toks[i]
    cta_set, imp_set = (_CTA_ES, _IMPER_ES) if idioma == "es" else (_CTA_EN, _IMPER_EN)
    if t in cta_set:
        fin = _fin_tramo(pal, i, sent, 6)
        palabra = None
        if i + 1 <= fin and i + 1 in sent:
            sig = norm(pal[i + 1]["w"])
            palabra = _cap(sig) if (len(sig) >= 3 and sig not in _stop(idioma) and sig not in cta_set and not re.search(r"\d", sig)) else None
        ra, rb = _recortar_extremos(pal, i + 1, min(fin, i + 4), idioma) if fin > i else (1, 0)
        resto = _cap(_txt(pal, ra, rb)) if ra <= rb else ""
        if not palabra and not resto:
            return []
        verbo = _cap(pal[i]["w"].strip(",.;:"))
        return [_cand("cta", i, fin, forma="cta", verbo=verbo, palabra=palabra, linea1=verbo, linea2=resto, color="lima", anim="escala",
                      motivo=f"llamada a la acción '{_txt(pal, i, fin)}'")]
    if t in imp_set:
        fin = _fin_tramo(pal, i + 1, sent, 4) if i + 1 in sent else i
        if fin <= i:
            return []
        a, b = _recortar_extremos(pal, i + 1, fin, idioma)
        if a > b:
            return []
        return [_cand("imperativo", i, fin, linea1=_cap(pal[i]["w"].strip(",.;:")), linea2=_cap(_txt(pal, a, b)), color="lima", anim="escala",
                      motivo=f"imperativo '{_txt(pal, i, fin)}'")]
    return []


def _superlativo(pal, toks, sent, idioma):
    out = []
    S = _SUPER_ES if idioma == "es" else _SUPER_EN
    for n, i in enumerate(sent):
        t = toks[i]
        es_sup = t in S
        if idioma == "es" and not es_sup and t == "más" and n > 0 and toks[sent[n - 1]] in ("el", "la", "lo", "los", "las"):
            es_sup = True
        if idioma == "en" and not es_sup and len(t) > 6 and t.endswith("est") and t not in {"interest", "invest", "request", "suggest", "digest", "protest", "contest", "forest", "harvest"}:
            es_sup = True
        if not es_sup:
            continue
        # impacto: palabra suelta tras pausa o frase de 1-2 palabras
        sola = len(sent) <= 2 and t in _IMPACTO_UNA
        if sola or (t in _IMPACTO_UNA and (n == 0 or pal[i]["s"] - pal[sent[n - 1]]["e"] >= 0.25) and n + 1 >= len(sent)):
            out.append(_cand("impacto", i, i, forma="impacto", palabra=norm(pal[i]["w"]), score=70 if sola else 55, color="lima",
                             motivo=f"palabra de énfasis '{pal[i]['w']}'"))
            continue
        # titulo: [artículo +] superlativo | resto de la frase (<= 4 palabras)
        a = i
        if n > 0 and toks[sent[n - 1]] in ("el", "la", "los", "las", "lo", "the", "is", "es"):
            a = sent[n - 1]
        b_head = i
        if idioma == "es" and t == "más" and n + 1 < len(sent):
            b_head = sent[n + 1]
        resto_ini = b_head + 1
        if resto_ini not in sent:
            continue
        fin = _fin_tramo(pal, resto_ini, sent, 4)
        ra, rb = _recortar_extremos(pal, resto_ini, fin, idioma)
        if ra > rb:
            continue
        out.append(_cand("superlativo", a, fin, linea1=_cap(_txt(pal, a, b_head)), linea2=_cap(_txt(pal, ra, rb)), color="lima", anim="escala",
                         motivo=f"superlativo '{_txt(pal, a, fin)}'"))
    return out


def _nombres(pal, toks, sent, idioma):
    out, usados = [], set()
    # lugares y activos del diccionario (hasta 2 palabras)
    for n, i in enumerate(sent):
        for span in (2, 1):
            if n + span > len(sent):
                continue
            frase = " ".join(toks[k] for k in sent[n:n + span])
            if frase in LUGARES and not usados & set(sent[n:n + span]):
                out.append(_cand("lugar", i, i + span - 1, linea1=_ETIQ[idioma]["lugar"], linea2=LUGARES[frase], color="purpura", caja=True, anim="barrido",
                                 motivo=f"lugar '{frase}'"))
                usados |= set(sent[n:n + span])
                break
            if frase in ACTIVOS and not usados & set(sent[n:n + span]):
                out.append(_cand("activo", i, i + span - 1, linea1=_ETIQ[idioma]["activo"], linea2=ACTIVOS[frase], color="lima", anim="reveal",
                                 motivo=f"activo '{frase}'"))
                usados |= set(sent[n:n + span])
                break
    # nombres propios (mayúscula inicial a mitad de frase) y siglas
    st = _stop(idioma)
    n = 1
    while n < len(sent):
        i = sent[n]
        w = pal[i]["w"].strip(".,;:¿?¡!\"“”()")
        if i in usados or not w or not w[0].isupper() or not w.isalpha() or len(w) < 4 or norm(w) in st or norm(w) in _MESES or norm(w) in LUGARES or norm(w) in ACTIVOS:
            n += 1
            continue
        j = n
        while j + 1 < len(sent) and pal[sent[j + 1]]["w"][:1].isupper() and pal[sent[j + 1]]["w"].strip(".,;:¿?¡!").isalpha() and not RE_FIN.search(pal[sent[j]]["w"]):
            j += 1
        nombre = " ".join(pal[sent[k]]["w"].strip(".,;:¿?¡!\"“”()") for k in range(n, j + 1))
        out.append(_cand("nombre", sent[n], sent[j], linea1=_ETIQ[idioma]["nombre"], linea2=nombre, color="lima", anim="reveal", motivo=f"nombre propio '{nombre}'"))
        n = j + 1
    return out


def _pausa(pal, toks, sent, idioma, pausa_larga):
    """Frase corta (2-6 palabras) justo tras una pausa larga: suele ser el remate."""
    i0 = sent[0]
    if i0 == 0 or pal[i0]["s"] - pal[i0 - 1]["e"] < pausa_larga or not (2 <= len(sent) <= 6):
        return []
    a, b = _recortar_extremos(pal, sent[0], sent[-1], idioma)
    if a > b:
        return []
    texto = _txt(pal, a, b)
    if _n_pal(texto) < 2:
        return []
    return [_cand("pausa", sent[0], sent[-1], linea1="", linea2=_cap(texto), color="lima", anim="subir", motivo=f"frase corta tras pausa de {pal[i0]['s'] - pal[i0 - 1]['e']:.1f}s")]


def _cifras(pal, toks, idioma):
    """Candidatas a tarjeta de cifra. NUNCA verificadas. Salta años (1900-2100 sueltos)."""
    unidades = _UNIDADES_ES if idioma == "es" else _UNIDADES_EN
    st = _stop(idioma)
    out, i, n = [], 0, len(pal)
    while i < n:
        w = pal[i]["w"]
        if not re.search(r"\d", w):
            i += 1
            continue
        j = i
        valor = w.strip(".,;:¿?¡!\"“”()")
        # unidades que siguen: "por ciento", "%", "millones", "mil millones", "dólares"
        k = i + 1
        sufijo = []
        if k + 1 < n and toks[k] == "por" and toks[k + 1] == "ciento":
            sufijo, k = ["%"], k + 2
        else:
            while k < n and toks[k] in unidades and len(sufijo) < 3:
                sufijo.append(pal[k]["w"].strip(".,;:¿?¡!"))
                k += 1
        if sufijo == ["%"]:
            valor = valor.rstrip("%") + "%"
            sep = ""
        else:
            sep = " " if sufijo else ""
        valor = valor + sep + " ".join(sufijo) if sufijo != ["%"] else valor
        j = k - 1
        solo = re.fullmatch(r"\d{4}", re.sub(r"\D", "", w)) and not sufijo and 1900 <= int(re.sub(r"\D", "", w)) <= 2100 and "%" not in w
        if not solo:
            # etiqueta (a revisar por una persona): hasta 2 palabras con contenido antes de la cifra (misma frase), o después si no hay
            ant = []
            m = i - 1
            while m >= 0 and len(ant) < 2 and not RE_FIN.search(pal[m]["w"]):
                if norm(pal[m]["w"]) not in st and not re.search(r"\d", pal[m]["w"]):
                    ant.insert(0, pal[m]["w"].strip(".,;:¿?¡!"))
                m -= 1
            if not ant:
                m = j + 1
                while m < n and len(ant) < 2 and not RE_FIN.search(pal[m - 1]["w"]):
                    if norm(pal[m]["w"]) not in st and not re.search(r"\d", pal[m]["w"]):
                        ant.append(pal[m]["w"].strip(".,;:¿?¡!"))
                    m += 1
            tipo = "tecnico" if "%" in valor else "valor"
            etiqueta = _cap(" ".join(ant)) if ant else ""
            out.append(_cand("cifra", i, j, forma="cifra", valor=valor, etiqueta=etiqueta, tipo_cifra=tipo, motivo=f"cifra '{valor}' dicha en el audio"))
        i = j + 1
    return out


# ---------- selección ----------
def _solape(linea1, linea2, pal, t, dur, idioma):
    """Fracción de las palabras con contenido del título que se dicen mientras está en pantalla [t, t+dur]."""
    titulo = _contenido(f"{linea1} {linea2}", idioma)
    if not titulo:
        return 0.0
    dichas = {norm(w["w"]) for w in pal if t - 0.05 <= w["s"] <= t + dur}
    return len(titulo & dichas) / len(titulo)


def _ocupa_libre(t, dur, aceptados, evitar, cfg):
    for (a, b, ts) in aceptados:
        if t < b + cfg["hueco"] and t + dur > a - cfg["hueco"]:
            return False
        if abs(t - ts) < cfg["sep_min"]:
            return False
    for (a, b) in evitar:
        if t < b + 0.3 and t + dur > a - 0.3:
            return False
    return True


def _tasa_ok(starts, cfg):
    for s in starts:
        if sum(1 for x in starts if s <= x < s + 60.0) > cfg["max_por_min"]:
            return False
    return True


def proponer(pal, formato="vertical", idioma=None, evitar=None, cfg=None, dur_total=None):
    """Devuelve las propuestas ya seleccionadas. `evitar` = [(t0, t1)] de gráficos ya puestos (lower third, tarjetas) que no deben solaparse."""
    c = dict(CFG)
    c.update(cfg or {})
    if not pal:
        return {"titulos_grandes": [], "impacto": [], "cta": [], "cifras": [], "descartados": [], "resumen": {"idioma": idioma or "es", "candidatas": 0}}
    idioma = idioma or idioma_probable(pal)
    toks = [norm(w["w"]) for w in pal]
    fin_video = dur_total or pal[-1]["e"] + 0.3
    cands = []
    for sent in oraciones(pal):
        if not sent:
            continue
        cands += _contraste(pal, toks, sent, idioma) + _pregunta(pal, toks, sent, idioma) + _imperativo(pal, toks, sent, idioma)
        cands += _superlativo(pal, toks, sent, idioma) + _nombres(pal, toks, sent, idioma) + _pausa(pal, toks, sent, idioma, c["pausa_larga"])
    cands += _cifras(pal, toks, idioma)
    # un tramo sólo sirve a un candidato: se queda el de más puntuación
    cands.sort(key=lambda x: (-x["score"], x["i0"]))
    descartados, aceptados, sel = [], [], []
    ocupado_pal = set()
    n_max_total = max(1, int(round(c["max_por_min"] * fin_video / 60.0)))
    n_max_cifras = max(1, int(round(c["cifras_por_min"] * fin_video / 60.0)))
    n_cifras_ok, t_cifras = 0, []
    n_impactos = []
    evitar = list(evitar or [])
    for cd in cands:
        rango = set(range(cd["i0"], cd["i1"] + 1))
        desc = _texto_desc(cd, pal)
        if cd["score"] < c["min_score"]:
            descartados.append({"tipo": cd["tipo"], "texto": desc, "motivo": "puntuación baja"})
            continue
        if rango & ocupado_pal:
            descartados.append({"tipo": cd["tipo"], "texto": desc, "motivo": "tramo ya usado por una propuesta de mayor puntuación"})
            continue
        forma = cd["forma"]
        if forma == "cifra" and n_cifras_ok >= n_max_cifras:
            descartados.append({"tipo": cd["tipo"], "texto": desc, "motivo": f"tope de {c['cifras_por_min']} cifras/min ({n_max_cifras} en este vídeo)"})
            continue
        if forma != "cifra" and len(sel) - n_cifras_ok >= n_max_total:
            descartados.append({"tipo": cd["tipo"], "texto": desc, "motivo": f"tope de {c['max_por_min']}/min ({n_max_total} en este vídeo)"})
            continue
        if forma == "impacto":
            dur = min(1.2, c["impacto_dur"])
            opciones = [pal[cd["i0"]]["s"]]
        elif forma == "cifra":
            dur = c["cifra_dur"]
            opciones = [max(c["t_min"], pal[cd["i0"]]["s"] - 0.05)]
        elif forma == "cta":
            dur = 3.0
            opciones = [pal[cd["i1"]]["e"] + 0.05, pal[cd["i0"]]["s"]]
        else:
            dur = _dur_lectura(_n_pal(cd["linea1"]) + _n_pal(cd["linea2"]), c)
            fin_t, ini_t = pal[cd["i1"]]["e"] - 0.05, pal[cd["i0"]]["s"]
            if cd["tipo"] in ("lugar", "activo", "nombre"):
                opciones = [ini_t, fin_t]
            else:
                opciones = [fin_t, pal[min(cd["i1"], cd["i0"] + max(0, (cd["i1"] - cd["i0"]) // 2))]["s"]]
        ok, motivo, t_ok, sol = False, "", None, 0.0
        for t in opciones:
            t = max(c["t_min"], t)
            if t + dur > fin_video:
                motivo = "no cabe antes del final del vídeo"
                continue
            if not _ocupa_libre(t, dur, aceptados, evitar, c):
                motivo = "choca con otro gráfico o no respeta la separación mínima"
                continue
            if forma == "titulo":
                sol = _solape(cd["linea1"], cd["linea2"], pal, t, dur, idioma)
                if sol > c["max_solape"]:
                    motivo = f"duplicaría el subtítulo ({sol:.0%} de sus palabras se dicen mientras está en pantalla)"
                    continue
                if not verificar_cifras_en_audio(cd["linea1"] + " " + cd["linea2"], pal):
                    motivo = "contiene una cifra que no está en el audio"
                    continue
            if forma == "impacto":
                if len([x for x in n_impactos if abs(x - t) < c["impacto_sep"]]) or not _tasa_impacto(n_impactos + [t], c):
                    motivo = "demasiados impactos seguidos"
                    continue
            if forma != "cifra" and not _tasa_ok([a[2] for a in aceptados if a[2] not in t_cifras] + [t], c):
                motivo = f"más de {c['max_por_min']} por minuto"
                continue
            ok, t_ok = True, t
            break
        if not ok:
            descartados.append({"tipo": cd["tipo"], "texto": desc, "motivo": motivo or "sin hueco"})
            continue
        aceptados.append((t_ok, t_ok + dur, t_ok))
        ocupado_pal |= rango
        if forma == "impacto":
            n_impactos.append(t_ok)
        if forma == "cifra":
            n_cifras_ok += 1
            t_cifras.append(t_ok)
        cd.update({"t": round(t_ok, 2), "dur": dur, "solape": round(sol, 2)})
        sel.append(cd)
    sel.sort(key=lambda x: x["t"])
    return _formatear(sel, descartados, idioma, c, len(cands))


def _tasa_impacto(starts, cfg):
    for s in starts:
        if sum(1 for x in starts if s <= x < s + 60.0) > cfg["impacto_por_min"]:
            return False
    return True


def _texto_desc(cd, pal):
    return cd.get("motivo", "")[:90]


def _formatear(sel, descartados, idioma, c, n_cand):
    out = {"titulos_grandes": [], "impacto": [], "cta": [], "cifras": []}
    ultima = None
    for cd in sel:
        meta = {"_tipo": cd["tipo"], "_score": cd["score"], "_motivo": cd["motivo"]}
        if cd["forma"] == "titulo":
            anim = cd.get("anim", "subir")
            if anim == ultima:                       # variedad: nunca la misma entrada dos veces seguidas
                anim = ANIMACIONES[(ANIMACIONES.index(anim) + 1) % 3] if anim in ANIMACIONES else "subir"
            ultima = anim
            tg = {"t": cd["t"], "dur": cd["dur"], "linea1": cd["linea1"], "linea2": cd["linea2"], "color": cd.get("color", "lima"), "anim": anim}
            if cd.get("caja"):
                tg["caja"] = True
            tg.update(meta)
            tg["_solape"] = cd["solape"]
            out["titulos_grandes"].append(tg)
        elif cd["forma"] == "impacto":
            out["impacto"].append({"t": cd["t"], "dur": cd["dur"], "palabra": cd["palabra"], "color": "lima", **meta})
        elif cd["forma"] == "cta":
            if cd.get("palabra"):
                out["cta"].append({"t": cd["t"], "dur": cd["dur"], "verbo": cd["verbo"], "palabra": cd["palabra"], "extra": "", **meta})
            else:
                out["titulos_grandes"].append({"t": cd["t"], "dur": cd["dur"], "linea1": cd["linea1"], "linea2": cd["linea2"] or cd["linea1"], "color": "lima", "anim": "escala", **meta})
        elif cd["forma"] == "cifra":
            out["cifras"].append({"t": cd["t"], "dur": cd["dur"], "valor": cd["valor"], "etiqueta": cd["etiqueta"], "tipo": cd["tipo_cifra"],
                                  "fuente": "", "verificada": False, "_candidata": True, **meta})
    out["titulos_grandes"].sort(key=lambda x: x["t"])
    out["descartados"] = descartados
    out["resumen"] = {"idioma": idioma, "candidatas": n_cand, "aceptadas": len(sel),
                      "por_tipo": {t: sum(1 for x in sel if x["tipo"] == t) for t in sorted({x["tipo"] for x in sel})}}
    return out


def proponer_desde_archivo(words_json, **kw):
    import json
    from pathlib import Path
    pal = json.loads(Path(words_json).read_text(encoding="utf-8-sig"))
    return proponer(pal, **kw)
