"""Capítulos automáticos (sin APIs de pago): segmentación por cambios de tema + pausas largas.

Método (tipo TextTiling, solo vocabulario):
  1. Frases a partir de las palabras con tiempos (fin de frase = . ? ! o pausa >= 0.8 s).
  2. Para cada frontera entre frases se compara el vocabulario de las ~70 palabras anteriores con las ~70 siguientes
     (coseno sobre TF-IDF, palabras vacías fuera, raíz recortada a 6 letras). Cuanto menos se parecen, más cambio de tema.
  3. Puntuación de frontera = 0.7 * cambio_de_tema + 0.3 * pausa (una pausa de 2 s o más suma completa).
  4. Se eligen las mejores fronteras separadas por al menos `min_cap` segundos (reglas de YouTube: primer capítulo en 00:00,
     mínimo 3 capítulos, cada uno de 10 s o más).
  5. Título provisional = 3 palabras clave del tramo (TF-IDF entre capítulos). Es PROVISIONAL: el copy lo reescribe Claude.
Salidas: capitulos.json, capitulos_youtube.txt (marcas 00:00 …) y capitulos.ffmetadata (marcadores dentro del MP4).
Los tiempos son los del vídeo FINAL (usa words_final.json, ya remapeado tras los cortes técnicos)."""
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

STOP = set("""
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bien cada casi como con contra cual cuales cuando de del desde donde dos e el ella ellas ello ellos en entonces entre era eran es esa esas ese eso esos esta estaba estan estar este esto estos fue fueron ha habia han hasta hay he hemos hace hacer hacia la las le les lo los mas me mi mis mucho muchos muy nada ni no nos nosotros o os otra otras otro otros para pero poco por porque que quien se sea ser si sido sin sobre solo son su sus tambien te tengo tiene tienen todo todos tu tus un una unas uno unos usted va vamos van ver vez voy y ya yo
eh em este pues bueno vale entonces digamos osea ok tipo cosa cosas parte forma manera
the a an and are as at be but by for from has have he i in is it its of on or that the this to was we were what with you your not so if then there they them
would could should when within about which their these those also into than been being just like more some such only over very much many most other who how why where while can will may might must our out up down off again here once any both each few own same too because lets let say said get got going gonna want know think really thing things way kind actually something anything everything
puede pueden podemos hacemos hacen dice dijo digo quiero quieres tengo tenemos sabe saben cosas hacer ahora siempre nunca entonces cuando mismo misma
""".split())


def _quitar_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _limpia(w):
    return re.sub(r"[^\w%$]+", "", _quitar_acentos(w.lower()), flags=re.UNICODE)


def _raiz(w):
    return w[:6]


def frases(palabras, pausa=0.8):
    """[{i0, i1, s, e}] sobre la lista de palabras (índices inclusivos)."""
    out, ini = [], 0
    for i, w in enumerate(palabras):
        fin = bool(re.search(r"[.?!…]$", w["w"]))
        if not fin and i + 1 < len(palabras):
            fin = palabras[i + 1]["s"] - w["e"] >= pausa
        if fin or i == len(palabras) - 1:
            out.append({"i0": ini, "i1": i, "s": palabras[ini]["s"], "e": w["e"]})
            ini = i + 1
    return out


def _contenido(palabras, i0, i1):
    r = []
    for w in palabras[i0:i1 + 1]:
        c = _limpia(w["w"])
        if len(c) >= 3 and c not in STOP and not c.isdigit():
            r.append(c)
    return r


def _coseno(a, b, idf):
    num = sum(a[k] * b[k] * idf.get(k, 1.0) ** 2 for k in a if k in b)
    na = math.sqrt(sum((v * idf.get(k, 1.0)) ** 2 for k, v in a.items()))
    nb = math.sqrt(sum((v * idf.get(k, 1.0)) ** 2 for k, v in b.items()))
    return num / (na * nb) if na and nb else 0.0


def fmt_ts(t, con_horas=False):
    t = int(round(t))
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if con_horas else f"{m:02d}:{s:02d}"


def _segmentar_con(palabras, dur, min_eff, objetivo, ventana, umbral, pausa_frase):
    fr = frases(palabras, pausa=pausa_frase)
    docs = [Counter(_raiz(c) for c in _contenido(palabras, f["i0"], f["i1"])) for f in fr]
    df = Counter(k for d in docs for k in d)
    N = max(1, len(docs))
    idf = {k: math.log((N + 1) / (1 + v)) + 1 for k, v in df.items()}
    cand = []
    for k in range(1, len(fr)):
        t = fr[k]["s"]
        if t < min_eff or dur - t < min_eff:
            continue
        i_ini = fr[k]["i0"]
        izq = Counter(_raiz(c) for c in _contenido(palabras, max(0, i_ini - ventana), i_ini - 1))
        der = Counter(_raiz(c) for c in _contenido(palabras, i_ini, min(len(palabras) - 1, i_ini + ventana)))
        cambio = 1.0 - _coseno(izq, der, idf)
        pausa = min(max(0.0, fr[k]["s"] - fr[k - 1]["e"]) / 2.0, 1.0)
        cand.append((0.7 * cambio + 0.3 * pausa, t))
    n_obj = max(3, round(dur / objetivo))
    elegidos = []
    for sc, t in sorted(cand, reverse=True):
        if any(abs(t - e) < min_eff for e in elegidos + [0.0]):
            continue
        # hasta tener 3 capítulos (YouTube) se acepta cualquier frontera; después solo las claras
        if len(elegidos) + 1 >= 3 and sc < umbral:
            break
        if len(elegidos) + 1 >= n_obj:
            break
        elegidos.append(t)
    if len(elegidos) < 2:       # el voraz se encerró (típico en vídeos cortos): mejor par de fronteras compatibles
        mejor = None
        for i, (s1, t1) in enumerate(cand):
            for s2, t2 in cand[i + 1:]:
                if abs(t1 - t2) >= min_eff and t1 >= min_eff and t2 >= min_eff and (mejor is None or s1 + s2 > mejor[0]):
                    mejor = (s1 + s2, t1, t2)
        if mejor:
            elegidos = [mejor[1], mejor[2]]
    return [0.0] + sorted(elegidos)


def segmentar(palabras, dur, min_cap=60.0, objetivo=150.0, ventana=70, umbral=0.25):
    """Devuelve (lista de tiempos de inicio de capítulo incluyendo 0, avisos)."""
    avisos = []
    if len(palabras) < 12:
        return [0.0], ["transcripción demasiado corta para segmentar por tema"]
    min_eff = min(min_cap, max(10.0, dur / 4.0))
    if min_eff < min_cap:
        avisos.append(f"capítulo mínimo reducido de {min_cap:.0f} s a {min_eff:.0f} s porque el vídeo dura {dur:.0f} s")
    tiempos = _segmentar_con(palabras, dur, min_eff, objetivo, ventana, umbral, 0.8)
    if len(tiempos) < 3:        # habla corrida sin pausas largas ni puntos: se admiten fronteras en pausas cortas (0.3 s)
        t2 = _segmentar_con(palabras, dur, min_eff, objetivo, ventana, umbral, 0.3)
        if len(t2) > len(tiempos):
            tiempos = t2
            avisos.append("habla continua: se usaron pausas cortas (>= 0.3 s) como posibles fronteras")
    if len(tiempos) < 3:
        avisos.append("menos de 3 capítulos: YouTube no los mostrará como capítulos (exige 3 o más)")
    return tiempos, avisos


def titulos(palabras, tiempos, dur):
    """Palabras clave por capítulo (TF-IDF entre capítulos). Devuelve lista de listas de palabras (forma superficial más común)."""
    lim = tiempos + [dur + 1]
    cuentas, superficie = [], defaultdict(Counter)
    for a, b in zip(lim[:-1], lim[1:]):
        c = Counter()
        for w in palabras:
            if a <= w["s"] < b:
                cl = _limpia(w["w"])
                if len(cl) >= 4 and cl not in STOP and not cl.isdigit():
                    c[_raiz(cl)] += 1
                    superficie[_raiz(cl)][w["w"].strip(".,;:!?¿¡\"'()").lower()] += 1
        cuentas.append(c)
    df = Counter(k for c in cuentas for k in c)
    n = len(cuentas)
    res = []
    for c in cuentas:
        pun = sorted(((v * (math.log((n + 1) / (1 + df[k])) + 1), k) for k, v in c.items()), reverse=True)
        res.append([superficie[k].most_common(1)[0][0] for _, k in pun[:3]])
    return res


def _titulo_legible(kws):
    if not kws:
        return "Capítulo"
    if len(kws) == 1:
        return kws[0].capitalize()
    return (", ".join(kws[:-1]) + " y " + kws[-1]).capitalize()


def generar(words_final_path, dur, salida_dir, min_cap=60.0, objetivo=150.0):
    """Escribe capitulos.json, capitulos_youtube.txt y capitulos.ffmetadata. Devuelve el dict."""
    palabras = json.loads(Path(words_final_path).read_text(encoding="utf-8-sig"))
    tiempos, avisos = segmentar(palabras, dur, min_cap=min_cap, objetivo=objetivo)
    kws = titulos(palabras, tiempos, dur)
    con_h = dur >= 3600
    caps = []
    for i, t in enumerate(tiempos):
        fin = tiempos[i + 1] if i + 1 < len(tiempos) else dur
        caps.append({"n": i + 1, "inicio": round(t, 2), "fin": round(fin, 2), "marca": fmt_ts(t, con_h),
                     "titulo": _titulo_legible(kws[i]), "titulo_auto": True, "palabras_clave": kws[i]})
    out = {"duracion": round(dur, 2), "metodo": "TextTiling por vocabulario (TF-IDF) + pausas; sin APIs", "avisos": avisos,
           "cumple_youtube": len(caps) >= 3 and all(c["fin"] - c["inicio"] >= 10 for c in caps),
           "nota": "Los títulos son provisionales (palabras clave del tramo): reescribir en el copy.", "capitulos": caps}
    d = Path(salida_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "capitulos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "capitulos_youtube.txt").write_text("\n".join(f"{c['marca']} {c['titulo']}" for c in caps) + "\n", encoding="utf-8")
    ffmetadata(caps, d / "capitulos.ffmetadata")
    return out


def ffmetadata(caps, ruta):
    """Formato FFMETADATA1: ffmpeg -i video -i capitulos.ffmetadata -map_metadata 1 -c copy ... mete los marcadores en el MP4."""
    ln = [";FFMETADATA1"]
    for c in caps:
        ln += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(c['inicio'] * 1000)}", f"END={int(c['fin'] * 1000)}", f"title={c['titulo']}"]
    Path(ruta).write_text("\n".join(ln) + "\n", encoding="utf-8")
