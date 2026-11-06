"""Entiende el vídeo de forma determinista: detecta en la transcripción cifras, años, lugares y activos.
Son CANDIDATOS para mapas (Electric Eye), gráficas (Ride the Lightning) y tarjetas de cifra. La decisión editorial es de la skill."""
import json
import re
from pathlib import Path

LUGARES = {
    "estados unidos": "Estados Unidos", "ee. uu": "Estados Unidos", "eeuu": "Estados Unidos", "china": "China", "japón": "Japón", "japon": "Japón",
    "rusia": "Rusia", "ucrania": "Ucrania", "europa": "Europa", "alemania": "Alemania", "francia": "Francia", "españa": "España",
    "méxico": "México", "mexico": "México", "colombia": "Colombia", "brasil": "Brasil", "argentina": "Argentina", "chile": "Chile",
    "perú": "Perú", "venezuela": "Venezuela", "panamá": "Panamá", "india": "India", "taiwán": "Taiwán", "taiwan": "Taiwán",
    "corea": "Corea", "israel": "Israel", "irán": "Irán", "iran": "Irán", "arabia saudita": "Arabia Saudita", "emiratos": "Emiratos Árabes",
    "turquía": "Turquía", "reino unido": "Reino Unido", "suiza": "Suiza", "singapur": "Singapur", "canadá": "Canadá", "australia": "Australia",
    "ormuz": "Estrecho de Ormuz", "suez": "Canal de Suez", "mar rojo": "Mar Rojo", "panamá canal": "Canal de Panamá",
    "wall street": "Nueva York", "silicon valley": "Silicon Valley", "bogotá": "Bogotá", "nueva york": "Nueva York", "londres": "Londres",
}
ACTIVOS = {
    "bitcoin": "BTC", "ethereum": "ETH", "oro": "Oro", "petróleo": "Petróleo", "petroleo": "Petróleo", "brent": "Brent", "cobre": "Cobre",
    "s&p": "S&P 500", "nasdaq": "Nasdaq", "dow jones": "Dow Jones", "nvidia": "NVIDIA", "tesla": "Tesla", "apple": "Apple", "microsoft": "Microsoft",
    "amazon": "Amazon", "google": "Alphabet", "meta": "Meta", "dólar": "Dólar", "dolar": "Dólar", "euro": "Euro", "bonos": "Bonos del Tesoro",
    "tasas de interés": "Tasas Fed", "inflación": "Inflación", "inflacion": "Inflación", "desempleo": "Desempleo", "pib": "PIB",
}
# Variantes en inglés (clips en inglés: la misma etiqueta de salida que en español)
LUGARES.update({
    "united states": "Estados Unidos", "u.s": "Estados Unidos", "japan": "Japón", "russia": "Rusia", "ukraine": "Ucrania", "germany": "Alemania",
    "france": "Francia", "spain": "España", "mexico city": "México", "brazil": "Brasil", "peru": "Perú", "turkey": "Turquía",
    "united kingdom": "Reino Unido", "switzerland": "Suiza", "canada": "Canadá", "korea": "Corea", "saudi arabia": "Arabia Saudita",
    "strait of hormuz": "Estrecho de Ormuz", "red sea": "Mar Rojo", "new york": "Nueva York", "london": "Londres", "bogota": "Bogotá",
})
ACTIVOS.update({
    "gold": "Oro", "oil": "Petróleo", "crude": "Petróleo", "copper": "Cobre", "dollar": "Dólar", "inflation": "Inflación", "gdp": "PIB",
    "treasuries": "Bonos del Tesoro", "interest rates": "Tasas Fed", "unemployment": "Desempleo", "s&p 500": "S&P 500", "alphabet": "Alphabet",
})
STOP_ES = set("a al algo ante bien como con contra cual cuando de del desde donde e el ella ellos en entre era es esa ese eso esta este esto estoy fue ha han hasta hay la las le les lo los me mi mucho muy ni no nos o para pero por porque que se sea ser si sin sobre su sus también te tu un una uno unos y ya yo nuestra nuestro ustedes usted todo toda todos todas más menos entonces pues así aquí allí ahí hoy cada otro otra son soy somos están está estamos va van vamos puede pueden hacer".split())
STOP_EN = set("a an the of to in on at for and or but with by from as is are was were be been being that this these those it its your my our their his her he she we you they i me us them not no do does did have has had will would can could should just so than then there here what which who when where how if about into over more most very also you've i've we've they've i'm you're we're they're it's that's there's don't doesn't isn't aren't wasn't can't won't".split())
RE_FIN = re.compile(r"[.?!…]+[\"')\]”»]*$")


def norm(tok):
    """Token en minúsculas, sin signos de puntuación en los extremos."""
    return tok.lower().strip(".,;:¿?¡!\"'“”«»()[]…—-")


def idioma_probable(palabras):
    """'es' o 'en' contando palabras vacías de cada idioma (determinista; no sustituye al idioma declarado de Whisper)."""
    es = en = 0
    for w in palabras:
        t = norm(w["w"])
        es += t in STOP_ES and t not in STOP_EN
        en += t in STOP_EN and t not in STOP_ES
        if re.search(r"[áéíóúñ¿¡]", t):
            es += 2
    return "en" if en > es * 1.15 else "es"


def oraciones(palabras, pausa=0.9):
    """Lista de listas de índices de palabra: corta en puntuación final (.?!) o en una pausa larga."""
    out, cur = [], []
    for i, w in enumerate(palabras):
        if cur and w["s"] - palabras[cur[-1]]["e"] > pausa:
            out.append(cur)
            cur = []
        cur.append(i)
        if RE_FIN.search(w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


RE_NUM = re.compile(r"\d[\d.,]*\s?(%|por ciento|millones|billones|mil millones|miles de millones|dólares|dolares|usd|puntos básicos|pbs?)?", re.I)


def candidatos(palabras, salida=None):
    """palabras ya re-sincronizadas al timeline final."""
    texto_lc = [w["w"].lower().strip(".,;:¿?¡!") for w in palabras]
    out = []
    n = len(palabras)
    for i, w in enumerate(palabras):
        tok = texto_lc[i]
        # lugares (hasta 2 palabras)
        for span in (2, 1):
            frase = " ".join(texto_lc[i:i + span])
            if frase in LUGARES:
                out.append({"t": w["s"], "tipo": "lugar", "texto": LUGARES[frase], "sugerencia": "mapa Electric Eye"})
                break
        for span in (2, 1):
            frase = " ".join(texto_lc[i:i + span])
            if frase in ACTIVOS:
                out.append({"t": w["s"], "tipo": "activo", "texto": ACTIVOS[frase], "sugerencia": "gráfica Ride the Lightning"})
                break
        if re.search(r"\d", tok):
            ctx = " ".join(x["w"] for x in palabras[i:min(n, i + 4)])
            out.append({"t": w["s"], "tipo": "cifra", "texto": ctx, "sugerencia": "tarjeta de cifra (VERIFICAR contra fuente oficial antes de rotular)"})
    # deduplicar candidatos pegados (misma clase y texto a <3 s)
    ded, vistos = [], {}
    for c in out:
        k = (c["tipo"], c["texto"])
        if k in vistos and c["t"] - vistos[k] < 3.0:
            continue
        vistos[k] = c["t"]
        ded.append(c)
    if salida:
        Path(salida).write_text(json.dumps(ded, indent=1, ensure_ascii=False), encoding="utf-8")
    return ded


def transcript_legible(palabras, salida, bloque=6.0):
    """Texto con marcas de tiempo [mm:ss] cada ~6 s, para que la skill planifique capas sobre el timeline final."""
    lineas, cur, t0 = [], [], None
    for w in palabras:
        if t0 is None:
            t0 = w["s"]
        cur.append(w["w"])
        if w["e"] - t0 >= bloque or re.search(r"[.?!]$", w["w"]):
            lineas.append(f"[{int(t0 // 60):02d}:{t0 % 60:05.2f}] {' '.join(cur)}")
            cur, t0 = [], None
    if cur:
        lineas.append(f"[{int(t0 // 60):02d}:{t0 % 60:05.2f}] {' '.join(cur)}")
    Path(salida).write_text("\n".join(lineas), encoding="utf-8")
    return len(lineas)
