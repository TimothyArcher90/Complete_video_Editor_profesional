"""Subtítulos dinámicos con marca (ASS) + SRT editable + tarjetas de marca (ASS con dibujo vectorial).
Todo opaco, sin glow ni degradados. Los gráficos usan los colores de la taxonomía (oro valor, teal técnico/%, púrpura geo, terracota coste).

ESTILOS DE SUBTÍTULO (selector `estilo`, ver ass_subtitulos_estilo):
  visual         palabra a palabra, UNA línea, palabra clave en caja opaca de su color de taxonomía (por defecto)
  clasico        UNA línea, todo el grupo a la vez, palabra activa en lima
  karaoke-cajas  grupo completo visible, caja lima/taxonomía que salta a la palabra activa
  minimo         para largo/horizontal: 1-2 líneas por frase, sin caja, sólo fundido

MEDIDA REAL: libass interpreta \\fs como altura de celda (ascent+descent), no como em. Con Geist SemiBold el texto
renderizado mide ≈ 0.84 × lo que PIL mide al mismo tamaño (calibrado con ffmpeg el 2026-11-05). `ancho_real()` aplica ese
factor; todas las decisiones de agrupación y de cajas usan la medida real, no la teórica."""
import functools
import os
import re
from pathlib import Path

from PIL import ImageFont

from .zonas import caja_segura_px, es_vertical, seg as zona_seg
from .common import BRAND, FONTS_DIR, ass_c, ass_color, ass_time, color_marca, dims, srt_time


def _cm(nombre):
    """Línea gráfica OFICIAL en video (David 2026-11-08): acentos solo oro/teal/púrpura (+ rojo para coste). El lima es solo de miniaturas."""
    return color_marca("oro" if nombre == "lima" else nombre)


FUENTE_TITULAR = "Geist SemiBold"
FUENTE_MONO = "Geist Mono Bold"
_TTF = {"titular": FONTS_DIR / "Geist-SemiBold.ttf", "mono": FONTS_DIR / "GeistMono-Bold.ttf"}
K_LIBASS = 0.84            # ancho renderizado / ancho PIL al mismo \fs (calibrado, ver docstring)
ESTILOS_SUBS = ("visual", "clasico", "karaoke-cajas", "minimo", "pildora")
_ALIAS = {"píldora": "pildora", "clásico": "clasico", "karaoke": "karaoke-cajas", "karaoke_cajas": "karaoke-cajas", "mínimo": "minimo"}
# \fs (px ASS) por formato. El em real es 0.84 × fs: 94 -> 79 px = 4.1 % del alto en 9:16 (requisito ≥ 4 %).
_FS = {
    "vertical": {"base": 94, "minimo": 80},
    "cuadrado": {"base": 66, "minimo": 56},
    "4x5": {"base": 76, "minimo": 64},
    "horizontal": {"base": 68, "minimo": 58},
}
_DEBIL = set("el la los las un una unos unas de del al a en con por para y o e u que se su sus mi tu lo le les me te nos como pero si ni ya muy sin sobre the an of to in on at for and or but with by from as is are was be that this its your my our their".split())


@functools.lru_cache(maxsize=64)
def _fuente(rol, px):
    return ImageFont.truetype(str(_TTF[rol]), int(px))


def medir(texto, tam, rol="titular", spacing=0.0):
    """Medida TEÓRICA (PIL) usada por las tarjetas. Para texto sobre vídeo usa ancho_real()."""
    return _fuente(rol, tam).getlength(texto) + spacing * len(texto)


def ancho_real(texto, fs, rol="titular", sp_frac=-0.03):
    """Ancho que libass pinta de verdad (px) para `texto` a \\fs=fs con espaciado sp_frac·fs por carácter."""
    return K_LIBASS * _fuente(rol, fs).getlength(texto) + sp_frac * fs * len(texto)


# ---------- agrupación de palabras ----------
def agrupar(palabras, max_pal=3, max_dur=1.25, pausa=0.45):
    """Agrupación antigua por nº de palabras/tiempo (se conserva por compatibilidad; los estilos nuevos usan agrupar_linea)."""
    grupos, cur = [], []
    for w in palabras:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            dur = w["e"] - cur[0]["s"]
            peso = sum(2 if len(x["w"]) > 11 else 1 for x in cur)
            fin_frase = re.search(r"[.?!;:]$", cur[-1]["w"])
            if gap > pausa or dur > max_dur or peso >= max_pal or fin_frase or (re.search(r",$", cur[-1]["w"]) and len(cur) >= 2):
                grupos.append(cur)
                cur = []
        cur.append(w)
    if cur:
        grupos.append(cur)
    return grupos


def _esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def _debil(w):
    return re.sub(r"[^\wáéíóúñü']", "", w["w"].lower()) in _DEBIL


def _fin_frase(w):
    return bool(re.search(r"[.?!;:…]$", w["w"]))


def _ancho_texto(palabras, fs):
    return ancho_real(" ".join(_esc(w["w"]) for w in palabras), fs)


def agrupar_linea(palabras, fs, ancho_max, max_pal=4, max_dur=1.7, pausa=0.45, reserva=0.0):
    """Grupos que CABEN EN UNA LÍNEA: se mide con la fuente real (PIL × K_LIBASS) y se corta antes de pasarse de `ancho_max`.
    `reserva` (px) deja sitio para el relleno de la caja de la palabra clave. Una palabra suelta más ancha que la línea
    se queda sola y el render le baja el cuerpo (excepción justificada: no se puede partir una palabra)."""
    grupos, cur = [], []
    for w in palabras:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            dur = w["e"] - cur[0]["s"]
            corte = (gap > pausa or dur > max_dur or len(cur) >= max_pal or _fin_frase(cur[-1])
                     or _ancho_texto(cur + [w], fs) + reserva > ancho_max
                     or (cur[-1]["w"].endswith(",") and len(cur) >= 2))
            if corte:
                grupos.append(cur)
                cur = []
        cur.append(w)
    if cur:
        grupos.append(cur)
    # no dejar una palabra funcional (artículo, preposición, conjunción) colgando al final de un grupo
    i = 0
    while i < len(grupos) - 1:
        g, n = grupos[i], grupos[i + 1]
        if (len(g) > 1 and _debil(g[-1]) and not _fin_frase(g[-1]) and n[0]["s"] - g[-1]["e"] <= pausa
                and len(n) < max_pal and _ancho_texto([g[-1]] + n, fs) + reserva <= ancho_max):
            n.insert(0, g.pop())
        elif (len(g) == 1 and _debil(g[0]) and not _fin_frase(g[0]) and n[0]["s"] - g[0]["e"] <= pausa
              and len(n) < max_pal and _ancho_texto(g + n, fs) + reserva <= ancho_max):
            n[:0] = g
            grupos.pop(i)
            continue
        i += 1
    return grupos


def _color_base(token):
    t = token.strip()
    if "%" in t:
        return _cm("tecnico")
    if re.search(r"[$€]|US\$|\bCOP\b", t):
        return _cm("valor")
    return BRAND["colores"]["blanco"]


def _cabecera(w, h, estilos):
    return ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (w, h, estilos)


# ---------- dibujo vectorial ----------
def rrect(w, h, r):
    r = min(r, w / 2, h / 2)
    k = 0.5523 * r
    f = lambda v: f"{v:.1f}"  # noqa: E731
    return (f"m {f(r)} 0 l {f(w - r)} 0 b {f(w - r + k)} 0 {f(w)} {f(r - k)} {f(w)} {f(r)} l {f(w)} {f(h - r)} "
            f"b {f(w)} {f(h - r + k)} {f(w - r + k)} {f(h)} {f(w - r)} {f(h)} l {f(r)} {f(h)} "
            f"b {f(r - k)} {f(h)} 0 {f(h - r + k)} 0 {f(h - r)} l 0 {f(r)} b 0 {f(r - k)} {f(r - k)} 0 {f(r)} 0")


# ---------- palabra clave por taxonomía ----------
_STOP = set("a al algo ante bien como con contra cual cuando de del desde donde e el ella ellos en entre era es esa ese eso esta este esto estoy fue ha han hasta hay la las le les lo los me mi mucho muy ni no nos o para pero por porque que se sea ser si sin sobre su sus también te tu un una uno unos y ya yo nuestra nuestro nuestros ustedes usted esos esas eso todo toda todos todas más menos entonces pues así aquí allí ahí hoy cada otro otra".split())
_STOP_EN = set("about after again all also and are because been before being between both but can could did does doing down during each few for from further had has have having here how into its itself just more most much must not now off once only other our out over own same should some such than that the their them then there these they this those through too under until very was were what when where which while who why will with would you your".split())
_NEG = {"pérdida", "perdida", "pérdidas", "perdidas", "caída", "caida", "riesgo", "deuda", "crisis", "miedo", "error", "problema", "quiebra", "caro", "costo", "coste", "costos", "impuestos", "inflación", "inflacion", "recesión", "recesion", "barreras", "difícilmente",
        "loss", "losses", "risk", "debt", "fear", "mistake", "problem", "cost", "costs", "taxes", "recession", "crash", "bankruptcy", "expensive", "collapse"}
_SIGLAS = {"fed", "etf", "pib", "ibkr", "bce", "ia", "ai", "gpt", "ceo", "usd", "cop", "opep", "opec", "ipo", "roi", "kpi", "ebitda", "sec", "fmi", "imf", "gdp", "cpi", "ipc", "nyse"}
_CAJA_TEXTO_OSCURO = {"lima", "oro", "teal"}


def _categoria(tok, lugares, activos):
    t = tok.lower().strip(".,;:¿?¡!\"'“”()")
    if not t:
        return None, 0
    if re.search(r"\d", t):
        return ("tecnico" if "%" in t else "valor"), 100
    if re.search(r"[$€]", t):
        return "valor", 100
    if t in _NEG:
        return "coste", 80
    if t in lugares:
        return "geo", 70
    if t in activos:
        return "lima", 60
    if t in _SIGLAS or (len(t) >= 2 and tok.strip(".,;:¿?¡!").isupper() and t.isalpha()):
        return "lima", 55
    if t not in _STOP and t not in _STOP_EN and len(t) >= 6:
        return "lima", len(t)
    return None, 0


def _elegir_clave(g, lugares, activos, ultima_lima):
    """(índice, categoría) de la palabra clave del grupo, o (None, None). Los conceptos genéricos (lima, pts < 60) no se cajan
    en dos grupos seguidos: así la caja sigue siendo una señal y no ruido."""
    cat_sel, idx, pts = None, None, 0
    for i, x in enumerate(g):
        c, p = _categoria(x["w"], lugares, activos)
        if c and p > pts:
            cat_sel, idx, pts = c, i, p
    if cat_sel == "lima" and pts < 60 and ultima_lima:
        return None, None
    return idx, cat_sel


def _vocab():
    from .detectar import ACTIVOS, LUGARES
    return {k for k in LUGARES if " " not in k}, {k for k in ACTIVOS if " " not in k}


# ---------- infraestructura de los estilos ----------
class _P:
    """Parámetros de lienzo y zona segura para un formato y estilo."""

    def __init__(self, formato, estilo, tam=None):
        self.w, self.h = dims(formato)
        self.x0, self.y0, self.x1, self.y1 = caja_segura_px(formato)
        clave = "minimo" if estilo == "minimo" else "base"
        t = _FS.get(formato)
        self.fs = int(tam) if tam else (t[clave] if t else int(round(self.h * (0.042 if clave == "minimo" else 0.05))))
        self.cx = (self.x0 + self.x1) / 2
        self.zw = self.x1 - self.x0
        self.pad = 0.20 * self.fs                      # relleno horizontal de las cajas
        self.ancho_max = self.zw - 2 * self.pad        # ancho máximo del texto de una línea (la caja nunca sale de la zona)
        self.yc = self.y1 - 0.58 * self.fs             # centro de la línea: la caja termina justo en el borde de la zona
        self.formato = formato


def _estilos_pal(P):
    C = BRAND["colores"]
    pal = (f"Style: Pal,{FUENTE_TITULAR},{P.fs},{ass_color(C['blanco'])},{ass_color(C['blanco'])},{ass_color('#000000')},{ass_color('#000000', 0x70)},"
           f"0,0,0,0,100,100,{-0.03 * P.fs:.2f},0,1,0,0,5,0,0,0,1")
    card = f"Style: Card,{FUENTE_TITULAR},40,{ass_color(C['blanco'])},{ass_color(C['blanco'])},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1"
    return pal + "\n" + card


def _tiempos(grupos, i, extra=0.14, minimo=0.3):
    g = grupos[i]
    ini = g[0]["s"]
    fin = g[-1]["e"] + extra
    if i + 1 < len(grupos):
        fin = min(fin, grupos[i + 1][0]["s"] - 0.01)
    return ini, max(fin, ini + minimo)


def _ocultos(ini, fin, ocultar):
    """True si el grupo cae (en su mayor parte) dentro de un intervalo donde otro elemento ocupa la pantalla (p. ej. 'impacto')."""
    for a, b in ocultar or []:
        solape = min(fin, b) - max(ini, a)
        if solape > 0.5 * (fin - ini):
            return True
    return False


def _layout(textos, fs, claves, P):
    """Posiciones de cada palabra en UNA línea centrada. Devuelve (fs_efectivo, [(centro_x, ancho)], ancho_total).
    Si la línea no cabe (palabra suelta larguísima) baja el cuerpo hasta que quepa; entre una palabra clave y su vecina deja aire para la caja."""
    for _ in range(3):
        anchos = [ancho_real(t, fs) for t in textos]
        esp = ancho_real(" ", fs)
        gaps = [esp + (0.16 * fs if (claves[i] or claves[i + 1]) else 0.0) for i in range(len(textos) - 1)]
        total = sum(anchos) + sum(gaps)
        if total <= P.ancho_max or len(textos) == 0:
            break
        fs = fs * P.ancho_max / total * 0.985
    x = P.cx - total / 2
    cs = []
    for i, a in enumerate(anchos):
        cs.append((x + a / 2, a))
        x += a + (gaps[i] if i < len(gaps) else 0)
    return fs, cs, total


def _grupos_estilo(palabras, P, estilo):
    caja = estilo in ("visual", "karaoke-cajas")
    reserva = 0.40 * P.fs if caja else 0.0
    if estilo == "clasico":
        return agrupar_linea(palabras, P.fs, P.zw * 0.96, max_pal=4, max_dur=1.5, pausa=0.45)
    return agrupar_linea(palabras, P.fs, P.ancho_max, max_pal=4, max_dur=1.7, pausa=0.45, reserva=reserva)


def _escribir(ev, ruta):
    Path(ruta).write_text("".join(ev), encoding="utf-8")


NL = "\\N"                 # salto de línea ASS (barra invertida + N)
_SOMBRA = "\\bord2.2\\3c&H171A1A&\\shad3\\blur1.4\\4c&H000000&\\4a&H60&"   # contorno fino Warm Black (contraste sobre paredes claras) + sombra suave


def _caja_dialogo(t0, t1, bx, by, bw, bh, col, fad="\\fad(50,40)", entrada=True, layer=2):
    mov = f"\\move({bx:.0f},{by + 12:.0f},{bx:.0f},{by:.0f},0,100)" if entrada else f"\\pos({bx:.0f},{by:.0f})"
    return (f"Dialogue: {layer},{ass_time(t0)},{ass_time(t1)},Card,,0,0,0,,"
            f"{{\\an7{mov}\\1c{ass_c(col)}\\bord0\\shad0{fad}\\p1}}{rrect(bw, bh, bh * 0.20)}{{\\p0}}\n")


# ---------- estilo VISUAL ----------
def _visual(palabras, formato, ruta, ocultar=None, tam=None):
    """Cada palabra aparece cuando se dice (pop corto); UNA palabra clave por grupo va en caja opaca con el color de su taxonomía:
    cifra/valor = oro · % o técnico = teal · coste/riesgo = terracota · lugar = púrpura · concepto/sigla = lima.
    Texto blanco con sombra suave. UNA línea por grupo (medida real), dentro de la zona segura."""
    lugares, activos = _vocab()
    P = _P(formato, "visual", tam)
    C = BRAND["colores"]
    ev = [_cabecera(P.w, P.h, _estilos_pal(P))]
    grupos = _grupos_estilo(palabras, P, "visual")
    ultima_lima = False
    for gi, g in enumerate(grupos):
        ini, fin = _tiempos(grupos, gi)
        if _ocultos(ini, fin, ocultar):
            continue
        textos = [_esc(x["w"]) for x in g]
        idx, cat = _elegir_clave(g, lugares, activos, ultima_lima)
        ultima_lima = cat == "lima"
        claves = [i == idx for i in range(len(g))]
        fs, cs, _ = _layout(textos, P.fs, claves, P)
        for i, wd in enumerate(g):
            xc, a = cs[i]
            t0 = wd["s"]
            if claves[i]:
                col = _cm(cat)
                bw, bh = a + 2 * (0.20 * fs), 0.98 * fs
                ev.append(_caja_dialogo(t0, fin, xc - bw / 2, P.yc - bh / 2 + 2, bw, bh, col))
                txt_col = C["fondo"] if cat in _CAJA_TEXTO_OSCURO else C["blanco"]
                ev.append(f"Dialogue: 3,{ass_time(t0)},{ass_time(fin)},Pal,,0,0,0,,{{\\an5\\fs{fs:.0f}\\move({xc:.0f},{P.yc + 12:.0f},{xc:.0f},{P.yc:.0f},0,100)\\1c{ass_c(txt_col)}\\fad(50,40)\\fscx90\\fscy90\\t(0,90,\\fscx106\\fscy106)\\t(90,190,\\fscx100\\fscy100)}}{textos[i]}\n")
            else:
                ev.append(f"Dialogue: 3,{ass_time(t0)},{ass_time(fin)},Pal,,0,0,0,,{{\\an5\\fs{fs:.0f}\\move({xc:.0f},{P.yc + 12:.0f},{xc:.0f},{P.yc:.0f},0,100)\\1c{ass_c(_color_base(wd['w']))}{_SOMBRA}\\fad(50,40)\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}}{textos[i]}\n")
    _escribir(ev, ruta)
    return len(grupos)


# ---------- estilo CLÁSICO ----------
def _clasico(palabras, formato, ruta, ocultar=None, tam=None):
    """Clásico: una línea por grupo, blanco con sombra suave y la palabra activa en lima (se enciende al decirla)."""
    P = _P(formato, "clasico", tam)
    C = BRAND["colores"]
    ev = [_cabecera(P.w, P.h, _estilos_pal(P))]
    grupos = _grupos_estilo(palabras, P, "clasico")
    activa = ass_c(_cm(BRAND["subtitulos"]["color_activa"]))
    for gi, g in enumerate(grupos):
        ini, fin = _tiempos(grupos, gi, extra=0.10, minimo=0.25)
        if _ocultos(ini, fin, ocultar):
            continue
        fs = P.fs
        tot = _ancho_texto(g, fs)
        if tot > P.zw * 0.96:
            fs = fs * P.zw * 0.96 / tot * 0.985
        partes = [f"{{\\an5\\fs{fs:.0f}\\pos({P.cx:.0f},{P.yc:.0f}){_SOMBRA}\\fscx92\\fscy92\\fad(40,30)\\t(0,120,\\fscx100\\fscy100)}}"]
        for wd in g:
            a = int(round((wd["s"] - ini) * 1000))
            b = int(round((wd["e"] - ini) * 1000))
            base = ass_c(_color_base(wd["w"]))
            partes.append(f"{{\\1c{base}\\t({a},{a + 40},\\1c{activa})\\t({b},{b + 40},\\1c{base})}}{_esc(wd['w'])} ")
        ev.append(f"Dialogue: 2,{ass_time(ini)},{ass_time(fin)},Pal,,0,0,0,,{''.join(partes).rstrip()}\n")
    _escribir(ev, ruta)
    return len(grupos)


# ---------- estilo KARAOKE-CAJAS ----------
def _karaoke(palabras, formato, ruta, ocultar=None, tam=None):
    """El grupo entero está en pantalla desde que empieza; una caja opaca salta a la palabra que se está diciendo
    (lima; si la palabra tiene categoría de taxonomía, el color de su categoría). Texto activo oscuro sobre lima/oro/teal, blanco sobre púrpura/terracota."""
    lugares, activos = _vocab()
    P = _P(formato, "karaoke-cajas", tam)
    C = BRAND["colores"]
    ev = [_cabecera(P.w, P.h, _estilos_pal(P))]
    grupos = _grupos_estilo(palabras, P, "karaoke-cajas")
    for gi, g in enumerate(grupos):
        ini, fin = _tiempos(grupos, gi)
        if _ocultos(ini, fin, ocultar):
            continue
        textos = [_esc(x["w"]) for x in g]
        fs, cs, _ = _layout(textos, P.fs, [True] * len(g), P)
        for i, wd in enumerate(g):
            xc, a = cs[i]
            c, p = _categoria(wd["w"], *_vocab_cache(lugares, activos))
            col = _cm(c) if (c and p >= 55) else C["oro"]
            oscuro = (c in _CAJA_TEXTO_OSCURO) or not (c and p >= 55)
            a0 = wd["s"]
            a1 = g[i + 1]["s"] if i + 1 < len(g) else fin
            a1 = max(a1, a0 + 0.12)
            ms0 = int(round((a0 - ini) * 1000))
            ms1 = int(round((a1 - ini) * 1000))
            txt_act = ass_c(C["fondo"] if oscuro else C["blanco"])
            blanco = ass_c(C["blanco"])
            ev.append(f"Dialogue: 3,{ass_time(ini)},{ass_time(fin)},Pal,,0,0,0,,{{\\an5\\fs{fs:.0f}\\pos({xc:.0f},{P.yc:.0f})\\1c{blanco}{_SOMBRA}\\fad(60,40)"
                      f"\\t({ms0},{ms0 + 30},\\1c{txt_act}\\shad0)\\t({ms1},{ms1 + 30},\\1c{blanco}\\shad3)}}{textos[i]}\n")
            bw, bh = a + 2 * (0.20 * fs), 0.98 * fs
            ev.append(_caja_dialogo(a0, a1, xc - bw / 2, P.yc - bh / 2 + 2, bw, bh, col, fad="", entrada=False, layer=2))
    _escribir(ev, ruta)
    return len(grupos)


def _vocab_cache(lugares, activos):
    return lugares, activos


# ---------- estilo MÍNIMO (largo / horizontal) ----------
def _lineas_equilibradas(palabras, fs, ancho_max, max_lineas=2):
    """Reparte las palabras en 1 o 2 líneas lo más iguales posible (medida real). None si no caben en max_lineas."""
    textos = [_esc(w["w"]) for w in palabras]
    if ancho_real(" ".join(textos), fs) <= ancho_max:
        return [" ".join(textos)]
    if max_lineas < 2 or len(textos) < 2:
        return None
    mejor, dmin = None, 1e9
    for k in range(1, len(textos)):
        a, b = ancho_real(" ".join(textos[:k]), fs), ancho_real(" ".join(textos[k:]), fs)
        if max(a, b) <= ancho_max and abs(a - b) < dmin:
            mejor, dmin = k, abs(a - b)
    if mejor is None:
        return None
    return [" ".join(textos[:mejor]), " ".join(textos[mejor:])]


def _minimo(palabras, formato, ruta, ocultar=None, tam=None):
    """Para vídeo largo / horizontal: frases de 1-2 líneas, blanco con sombra suave, sólo fundido de 120 ms (sin cajas ni pop).
    Más legible en pantallas grandes y menos fatigoso a lo largo de minutos. Cada frase = un evento (editable en Premiere)."""
    P = _P(formato, "minimo", tam)
    C = BRAND["colores"]
    ancho = P.zw * 0.94
    ev = [_cabecera(P.w, P.h, _estilos_pal(P))]
    frases, cur = [], []
    for w in palabras:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            dur = w["e"] - cur[0]["s"]
            corte = (gap > 0.6 or dur > 5.0 or (_fin_frase(cur[-1]) and dur >= 1.2)
                     or _lineas_equilibradas(cur + [w], P.fs, ancho) is None)
            if corte:
                frases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        frases.append(cur)
    for i in range(len(frases) - 1):                  # no dejar 'de los' / 'the' colgando al final de una frase
        g, nx = frases[i], frases[i + 1]
        while len(g) > 2 and _debil(g[-1]) and not _fin_frase(g[-1]) and nx[0]["s"] - g[-1]["e"] <= 0.6 and _lineas_equilibradas([g[-1]] + nx, P.fs, ancho):
            nx.insert(0, g.pop())
    n = 0
    for gi, g in enumerate(frases):
        ini, fin = _tiempos(frases, gi, extra=0.25, minimo=0.6)
        if _ocultos(ini, fin, ocultar):
            continue
        fs = P.fs
        lineas = _lineas_equilibradas(g, fs, ancho)
        while lineas is None and fs > P.fs * 0.6:     # palabra suelta enorme: baja el cuerpo
            fs *= 0.93
            lineas = _lineas_equilibradas(g, fs, ancho)
        lineas = lineas or [" ".join(_esc(w["w"]) for w in g)]
        ev.append(f"Dialogue: 2,{ass_time(ini)},{ass_time(fin)},Pal,,0,0,0,,{{\\an2\\fs{fs:.0f}\\pos({P.cx:.0f},{P.y1:.0f})\\1c{ass_c(C['blanco'])}{_SOMBRA}\\fad(120,100)}}{NL.join(lineas)}\n")
        n += 1
    _escribir(ev, ruta)
    return n


# ---------- estilo PÍLDORA (largo / horizontal; gramática medida en referencias reales) ----------
def _pildora(palabras, formato, ruta, ocultar=None, tam=None):
    """Largo horizontal: NO transcripción corrida. Sólo frases clave de 2-4 palabras en una píldora opaca (Warm Dark) en el tercio inferior
    izquierdo, como máximo una cada `sep` s (por defecto 9). Texto Stone Light en mayúsculas; la palabra clave toma el color de su taxonomía.
    La transcripción completa sigue en el SRT/ASS editable aparte (accesibilidad y YouTube). Ver docs/investigacion/referencias_largo.md."""
    lugares, activos = _vocab()
    P = _P(formato, "minimo", tam)
    C = BRAND["colores"]
    fs = P.fs * 0.82
    sep = float(os.environ.get("MW_PILDORA_SEP", "9"))
    ev = [_cabecera(P.w, P.h, _estilos_pal(P))]
    grupos = agrupar_linea(palabras, fs, P.zw * 0.45, max_pal=4, max_dur=2.2, pausa=0.5)
    cand = []
    for g in grupos:
        if len(g) < 2:
            continue
        idx, cat = _elegir_clave(g, lugares, activos, False)
        if idx is None:
            continue
        pts = _categoria(g[idx]["w"], lugares, activos)[1]
        if pts < 60:
            continue
        cand.append((pts + (10 if cat in ("valor", "tecnico", "coste") else 0), g, idx, cat))
    elegidas, ult = [], -1e9
    for pts, g, idx, cat in sorted(cand, key=lambda c: c[1][0]["s"]):
        ini = g[0]["s"]
        if ini - ult >= sep and not _ocultos(ini, g[-1]["e"], ocultar):
            elegidas.append((g, idx, cat))
            ult = ini
    alto = 1.05 * fs
    px = 0.55 * fs
    for g, idx, cat in elegidas:
        ini = g[0]["s"]
        fin = min(max(g[-1]["e"] + 0.35, ini + 1.8), ini + 3.2)
        textos = [_esc(x["w"]).upper() for x in g]
        total = sum(ancho_real(t, fs) for t in textos) + ancho_real(" ", fs) * (len(g) - 1)
        bw = total + 2 * px + 0.45 * fs
        bx, by = P.x0, P.y1 - alto
        ev.append(f"Dialogue: 2,{ass_time(ini)},{ass_time(fin)},Card,,0,0,0,,{{\\an7\\move({bx:.0f},{by + 12:.0f},{bx:.0f},{by:.0f},0,180)\\1c{ass_c(C['tarjeta'])}\\bord0\\shad0\\fad(160,140)\\p1}}{rrect(bw, alto, alto / 2)}{{\\p0}}\n")
        d = 0.22 * fs
        ev.append(f"Dialogue: 3,{ass_time(ini)},{ass_time(fin)},Card,,0,0,0,,{{\\an7\\move({bx + px:.0f},{by + alto / 2 - d / 2 + 12:.0f},{bx + px:.0f},{by + alto / 2 - d / 2:.0f},0,180)\\1c{ass_c(C['lima'])}\\bord0\\shad0\\fad(160,140)\\p1}}{rrect(d, d, d / 2)}{{\\p0}}\n")
        partes = []
        for i, t in enumerate(textos):
            col = _cm(cat) if i == idx else C["texto"]
            partes.append(f"{{\\1c{ass_c(col)}}}{t}")
        x_txt = bx + px + d + 0.35 * fs
        ev.append(f"Dialogue: 4,{ass_time(ini)},{ass_time(fin)},Pal,,0,0,0,,{{\\an4\\fs{fs:.0f}\\move({x_txt:.0f},{by + alto / 2 + 12:.0f},{x_txt:.0f},{by + alto / 2:.0f},0,180)\\fad(160,140)}}{' '.join(partes)}\n")
    _escribir(ev, ruta)
    return len(elegidas)


# ---------- selector ----------
def estilo_valido(estilo):
    e = _ALIAS.get(estilo, estilo)
    if e not in ESTILOS_SUBS:
        raise ValueError(f"estilo de subtítulo desconocido: {estilo} (usa {', '.join(ESTILOS_SUBS)})")
    return e


def ass_subtitulos_estilo(palabras, formato, ruta, estilo="visual", ocultar=None, tam=None):
    """Punto de entrada único. estilo: visual | clasico | karaoke-cajas | minimo. La variable de entorno MW_ESTILO_SUBS lo fuerza
    (útil mientras __main__ sólo conozca 'visual'/'clasico'). Devuelve el nº de grupos."""
    e = estilo_valido(os.environ.get("MW_ESTILO_SUBS") or estilo)
    fn = {"visual": _visual, "clasico": _clasico, "karaoke-cajas": _karaoke, "minimo": _minimo, "pildora": _pildora}[e]
    return fn(palabras, formato, ruta, ocultar=ocultar, tam=tam)


def ass_subtitulos_visual(palabras, formato, ruta, ocultar=None, tam=None):
    """Compatibilidad con __main__: estilo 'visual' (o el que fuerce MW_ESTILO_SUBS)."""
    return ass_subtitulos_estilo(palabras, formato, ruta, "visual", ocultar, tam)


def ass_subtitulos(palabras, formato, ruta, ocultar=None, tam=None):
    """Compatibilidad con __main__: estilo 'clasico' (o el que fuerce MW_ESTILO_SUBS)."""
    return ass_subtitulos_estilo(palabras, formato, ruta, "clasico", ocultar, tam)


def estadisticas_agrupacion(palabras, formato, estilo="visual", tam=None):
    """Para pruebas y documentación: nº de grupos, palabras por grupo, ancho máximo real frente al disponible, excepciones."""
    e = estilo_valido(estilo)
    P = _P(formato, e, tam)
    if e == "minimo":
        return {"estilo": e, "fs": P.fs, "ancho_disponible": round(P.zw * 0.94)}
    gr = _grupos_estilo(palabras, P, e)
    anchos = [_ancho_texto(g, P.fs) + (0.40 * P.fs if e in ("visual", "karaoke-cajas") else 0) for g in gr]
    exc = [" ".join(w["w"] for w in g) for g, a in zip(gr, anchos) if a > (P.zw * 0.96 if e == "clasico" else P.ancho_max)]
    return {"estilo": e, "fs": P.fs, "em_pct_alto": round(100 * 0.84 * P.fs / P.h, 2), "grupos": len(gr), "pal_por_grupo": round(sum(map(len, gr)) / max(1, len(gr)), 2),
            "ancho_disponible": round(P.ancho_max), "ancho_max_usado": round(max(anchos or [0])), "excepciones": exc}


def ocultar_desde_plan(plan):
    """Intervalos (t0, t1) donde un 'impacto' ocupa la pantalla: se pasan como `ocultar=` para que el subtítulo no se pelee con la palabra gigante."""
    # + paneles/clips a pantalla (infografías, ecuaciones, mapas): ahí el subtítulo tapa el gráfico; la voz sigue y el SRT queda completo
    ocultos = [(i["t"], i["t"] + min(float(i.get("dur", 1.0)), 1.2)) for i in (plan or {}).get("impacto", [])]
    ocultos += [(p["t"], p["t"] + float(p.get("dur", 3.0))) for k in ("paneles", "clips") for p in (plan or {}).get(k, [])]
    return ocultos


# ---------- SRT editable (frases, no palabra a palabra) ----------
def srt_frases(palabras, ruta, max_chars=38, max_dur=4.5, max_lineas=2):
    bloques, cur = [], []

    def vaciar():
        nonlocal cur
        if cur:
            bloques.append(cur)
            cur = []

    for w in palabras:
        if cur:
            largo = len(" ".join(x["w"] for x in cur + [w]))
            if w["s"] - cur[-1]["e"] > 0.7 or w["e"] - cur[0]["s"] > max_dur or largo > max_chars * max_lineas or re.search(r"[.?!]$", cur[-1]["w"]):
                vaciar()
        cur.append(w)
    vaciar()
    out = []
    for i, b in enumerate(bloques, 1):
        fin = b[-1]["e"] + 0.15
        if i < len(bloques):
            fin = min(fin, bloques[i][0]["s"] - 0.02)
        txt = " ".join(x["w"] for x in b)
        if len(txt) > max_chars:  # partir en 2 líneas por la mitad
            mid = len(txt) // 2
            sp = [m.start() for m in re.finditer(" ", txt)]
            cut = min(sp, key=lambda p: abs(p - mid)) if sp else None
            if cut:
                txt = txt[:cut] + "\n" + txt[cut + 1:]
        out.append(f"{i}\n{srt_time(b[0]['s'])} --> {srt_time(fin)}\n{txt}\n")
    Path(ruta).write_text("\n".join(out), encoding="utf-8")
    return len(bloques)


def _forma(layer, t0, t1, x, y, w, h, r, fill, borde=None, entra=None, sale=None, bord=0):
    """Rectángulo redondeado opaco. entra/sale = desplazamiento (dx,dy) de animación de 220 ms."""
    mov = f"\\pos({x:.0f},{y:.0f})"
    if entra:
        dx, dy = entra
        mov = f"\\move({x + dx:.0f},{y + dy:.0f},{x:.0f},{y:.0f},0,220)"
    b = f"\\bord{bord}\\3c{ass_c(borde)}" if (borde and bord) else "\\bord0"
    return (f"Dialogue: {layer},{ass_time(t0)},{ass_time(t1)},Card,,0,0,0,,"
            f"{{\\an7{mov}\\1c{ass_c(fill)}{b}\\shad0\\p1}}{rrect(w, h, r)}{{\\p0}}\n")


def _texto(layer, t0, t1, x, y, txt, estilo, color, an=7, tam=None, entra=None, spacing=None, sombra=False, fade=False):
    mov = f"\\pos({x:.0f},{y:.0f})"
    if entra:
        dx, dy = entra
        mov = f"\\move({x + dx:.0f},{y + dy:.0f},{x:.0f},{y:.0f},0,220)"
    extra = ""
    if tam:
        extra += f"\\fs{tam}"
    if spacing is not None:
        extra += f"\\fsp{spacing:.2f}"
    if sombra:
        extra += "\\shad5\\blur2\\4c&H000000&\\4a&H70&"
    if fade:
        extra += "\\fad(160,140)"
    return (f"Dialogue: {layer},{ass_time(t0)},{ass_time(t1)},{estilo},,0,0,0,,"
            f"{{\\an{an}{mov}\\1c{ass_c(color)}{extra}}}{_esc(txt)}\n")


def _estilos_tarjetas():
    b = ass_color(BRAND["colores"]["blanco"])
    return ("Style: Card,%s,40,%s,%s,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
            "Style: Tit,%s,60,%s,%s,&H00000000,&H00000000,0,0,0,0,100,100,-1.8,0,1,0,0,7,0,0,0,1\n"
            "Style: Mono,%s,26,%s,%s,&H00000000,&H00000000,0,0,0,0,100,100,4.7,0,1,0,0,7,0,0,0,1\n"
            "Style: Fino,Geist,60,%s,%s,&H00000000,&H00000000,0,0,0,0,100,100,-1.2,0,1,0,0,7,0,0,0,1") % (
        FUENTE_TITULAR, b, b, FUENTE_TITULAR, b, b, FUENTE_MONO, b, b, b, b)


# ---------- texto grande: ajuste, animaciones, impacto ----------
ANIMACIONES = ("subir", "escala", "reveal", "barrido")
_COLOR_EN_CAJA = {"purpura", "terracota"}     # sobre vídeo oscuro estos colores no leen como texto: van en caja opaca con texto blanco


def _partir_real(texto, fs, ancho_max):
    pal, lineas, cur = texto.split(), [], ""
    for p in pal:
        prueba = (cur + " " + p).strip()
        if ancho_real(prueba, fs) > ancho_max and cur:
            lineas.append(cur)
            cur = p
        else:
            cur = prueba
    if cur:
        lineas.append(cur)
    return lineas


def _ajustar(texto, fs, ancho_max, max_lineas=2, min_frac=0.62):
    """(fs, líneas) tal que el texto cabe en `ancho_max` (medida real): primero baja el cuerpo hasta min_frac, luego parte en líneas."""
    if ancho_real(texto, fs) <= ancho_max:
        return fs, [texto]
    if max_lineas >= 2 and len(texto.split()) >= 2:       # mejor dos líneas grandes que una línea pequeña
        for k in (1.0, 0.92, 0.84, 0.76):
            lin = _partir_real(texto, fs * k, ancho_max)
            if len(lin) <= max_lineas and all(ancho_real(l, fs * k) <= ancho_max for l in lin):
                return fs * k, lin
    f = fs
    while ancho_real(texto, f) > ancho_max and f > fs * min_frac:
        f *= 0.94
    if ancho_real(texto, f) <= ancho_max:
        return f, [texto]
    f = fs
    for _ in range(14):
        lin = _partir_real(texto, f, ancho_max)
        if len(lin) <= max_lineas and all(ancho_real(l, f) <= ancho_max for l in lin):
            return f, lin
        f *= 0.93
    return f, _partir_real(texto, f, ancho_max)


def _entrada_tags(anim, x, y, n_ms=260):
    """Tags de entrada/salida para un texto de una pieza (todo en ASS puro)."""
    if anim == "escala":
        return (f"\\pos({x:.0f},{y:.0f})\\fscx62\\fscy62\\t(0,{n_ms - 60},0.55,\\fscx108\\fscy108)\\t({n_ms - 60},{n_ms + 60},\\fscx100\\fscy100)\\fad(110,170)")
    return f"\\move({x:.0f},{y + 34:.0f},{x:.0f},{y:.0f},0,{n_ms})\\fad(160,170)"


def _titulo_grande(ev, tg, P, esc, C):
    """Línea fina + línea clave (lima o color de taxonomía). anim: subir | escala | reveal | barrido. Sin glow ni degradados."""
    w, h, cxs, zw = P["w"], P["h"], P["cx"], P["zw"]
    t0, t1 = tg["t"], tg["t"] + tg.get("dur", 3.0)
    dur_ms = int(round((t1 - t0) * 1000))
    anim = tg.get("anim", "subir")
    if anim not in ANIMACIONES:
        anim = "subir"
    yb = P["y_top"]
    nombre_col = tg.get("color", "lima")
    col = _cm(nombre_col)
    en_caja = bool(tg.get("caja", nombre_col in _COLOR_EN_CAJA))
    fs1, fs2 = 66 * esc, 118 * esc
    amax = zw * 0.96 - (2 * 0.2 * fs2 if en_caja else 0)
    f1, l1 = _ajustar(tg["linea1"], fs1, zw * 0.96) if tg.get("linea1") else (fs1, [])
    f2, l2 = _ajustar(tg["linea2"], fs2, amax)
    y = yb
    for ln in l1:                          # línea fina, siempre blanca con sombra suave
        ev.append(_linea_fina(t0, t1, cxs, y, ln, f1, anim, C))
        y += f1 * 1.22
    y += f1 * 0.10 if l1 else 0
    for ln in l2:
        aw = ancho_real(ln, f2)
        if en_caja:
            bw, bh = aw + 2 * 0.2 * f2, 1.0 * f2
            by = y + 0.12 * f2
            bx = cxs - bw / 2
            dly = 90
            ev.append(f"Dialogue: 1,{ass_time(t0)},{ass_time(t1)},Card,,0,0,0,,"
                      f"{{\\an7\\pos({bx:.0f},{by:.0f})\\clip({bx:.0f},{by:.0f},{bx:.0f},{by + bh:.0f})\\t(0,260,0.6,\\clip({bx - 4:.0f},{by:.0f},{bx + bw + 4:.0f},{by + bh:.0f}))\\1c{ass_c(col)}\\bord0\\shad0\\fad(0,170)\\p1}}{rrect(bw, bh, bh * 0.18)}{{\\p0}}\n")
            txt_col = C["fondo"] if nombre_col in _CAJA_TEXTO_OSCURO else C["blanco"]
            ev.append(_linea_clave(t0, t1, cxs, y, ln, f2, anim, txt_col, C, delay=dly, sombra=False))
        else:
            ev.append(_linea_clave(t0, t1, cxs, y, ln, f2, anim, col, C))
        y += f2 * 1.12 + (0.12 * f2 if en_caja else 0)
    return y


def _linea_fina(t0, t1, x, y, txt, fs, anim, C):
    tags = _entrada_tags("escala" if anim == "escala" else "subir", x, y)
    return (f"Dialogue: 2,{ass_time(t0)},{ass_time(t1)},Fino,,0,0,0,,{{\\an8{tags}\\1c{ass_c(C['blanco'])}\\fs{int(fs)}\\fsp{-0.02 * fs:.2f}"
            f"\\shad5\\blur2\\4c&H000000&\\4a&H70&}}{_esc(txt)}\n")


def _linea_clave(t0, t1, x, y, txt, fs, anim, color, C, delay=0, sombra=True):
    sh = "\\shad5\\blur2\\4c&H000000&\\4a&H70&" if sombra else ""
    base = f"\\an8\\1c{ass_c(color)}\\fs{int(fs)}\\fsp{-0.03 * fs:.2f}{sh}"
    if anim != "reveal":
        if anim == "barrido":
            tags = f"\\pos({x:.0f},{y:.0f})\\fad(140,170)"
        else:
            tags = _entrada_tags(anim, x, y)
        return f"Dialogue: 3,{ass_time(t0)},{ass_time(t1)},Tit,,0,0,0,,{{{base}{tags}}}{_esc(txt)}\n"
    # reveal: cada palabra se destapa con un barrido de izquierda a derecha, escalonado 120 ms, mientras sube 22 px
    palabras = txt.split()
    esp = ancho_real(" ", fs)
    anchos = [ancho_real(p, fs) for p in palabras]
    total = sum(anchos) + esp * (len(palabras) - 1)
    xx = x - total / 2
    out = []
    for j, p in enumerate(palabras):
        a = anchos[j]
        xc = xx + a / 2
        d0 = delay + j * 120
        cy0, cy1 = y - 0.2 * fs, y + 1.35 * fs
        out.append(f"Dialogue: 3,{ass_time(t0)},{ass_time(t1)},Tit,,0,0,0,,"
                   f"{{{base}\\move({xc:.0f},{y + 24:.0f},{xc:.0f},{y:.0f},{d0},{d0 + 260})"
                   f"\\clip({xx - 8:.0f},{cy0:.0f},{xx - 8:.0f},{cy1:.0f})\\t({d0},{d0 + 260},0.6,\\clip({xx - 8:.0f},{cy0:.0f},{xx + a + 8:.0f},{cy1:.0f}))\\fad(0,170)}}{_esc(p)}\n")
        xx += a + esp
    return "".join(out)


def _impacto(ev, im, P, C, avisos):
    """Palabra gigante en lima, a todo el ancho de la zona segura, ≤ 1,2 s. Contorno Warm Black opaco (no glow) para leer sobre cualquier plano."""
    palabra = str(im.get("palabra", "")).strip()
    if not palabra:
        return
    if re.search(r"\d", palabra) and not (im.get("fuente") and im.get("verificada")):
        avisos.append(f"IMPACTO RECHAZADO '{palabra}' en t={im.get('t')}: lleva cifra y falta 'fuente' y 'verificada:true'")
        return
    dur = float(im.get("dur", 1.0))
    if dur > 1.2:
        avisos.append(f"IMPACTO '{palabra}': dur {dur:.2f}s recortada a 1.2s (límite de marca)")
        dur = 1.2
    t0, t1 = im["t"], im["t"] + dur
    txt = palabra.upper() if im.get("mayusculas", True) else palabra
    fs = 100.0
    fs = fs * (P["zw"] * 0.98) / max(1.0, ancho_real(txt, fs))
    fs = min(fs, P["h"] * 0.22)
    col = _cm(im.get("color", "lima"))
    y = (P["y_top"] + P["y_bot"]) / 2 if "y" not in im else P["h"] * im["y"]
    ms = int(dur * 1000)
    ev.append(f"Dialogue: 5,{ass_time(t0)},{ass_time(t1)},Tit,,0,0,0,,"
              f"{{\\an5\\pos({P['cx']:.0f},{y:.0f})\\fs{fs:.0f}\\fsp{-0.03 * fs:.2f}\\1c{ass_c(col)}\\bord{max(4, fs * 0.05):.0f}\\3c{ass_c(C['fondo'])}\\shad{max(4, fs * 0.04):.0f}\\4c&H000000&\\4a&H40&"
              f"\\fscx150\\fscy150\\t(0,130,0.5,\\fscx100\\fscy100)\\t({max(0, ms - 160)},{ms},\\fscx108\\fscy108)\\fad(0,140)}}{_esc(txt)}\n")


# ---------- tarjetas de marca ----------
def _pantalla(ev, t0, t1, w, h, C):
    """Panel a pantalla completa, OPACO (Warm Black, sin transparencia: Premiere mezcla las semitransparentes más grisáceas).
    Lo usa revisor_capas cuando una tarjeta no cabe en ninguna zona libre de cara: el presentador se oculta ese rato (el audio sigue)."""
    ev.append(f"Dialogue: 0,{ass_time(t0)},{ass_time(t1)},Card,,0,0,0,,"
              f"{{\\an7\\pos(0,0)\\1c{ass_c(C['fondo'])}\\bord0\\shad0\\fad(120,120)\\p1}}{rrect(w, h, 0)}{{\\p0}}\n")


def ass_graficos(plan, formato, ruta, sin_panel=False):
    """lower_thirds, titulos, cifras, titulos_grandes, impacto, cta -> un ASS. Las cifras exigen 'fuente' y 'verificada': si no, se rechazan (regla de marca)."""
    w, h = dims(formato)
    seg = zona_seg(formato)
    sx, sy_top = w * seg["izquierda"], h * seg["arriba"]
    sy_bot, sw_right = h * (1 - seg["abajo"]), w * (1 - seg["derecha"])
    cxs = (sx + sw_right) / 2   # centro horizontal de la zona segura
    C = BRAND["colores"]
    esc = h / 1080 if formato == "horizontal" else w / 1080  # escala relativa a 1080 de lado corto
    ev = [_cabecera(w, h, _estilos_tarjetas())]
    avisos = []
    _pant = (lambda *a, **k: None) if sin_panel else _pantalla   # sin_panel: el revisor mide las tarjetas SIN el panel opaco de fondo

    for lt in plan.get("lower_thirds", []):
        t0, t1 = lt["t"], lt["t"] + lt.get("dur", 4.0)
        if lt.get("modo") == "omitir":              # revisor_capas: no cabe ni como cápsula sin tapar la cara -> no se dibuja (queda en el informe)
            continue
        if lt.get("modo") == "capsula":             # CÁPSULA: píldora pequeña opaca Warm Black con solo el nombre, en la banda libre más baja
            kc = float(lt.get("escala", 1.0))
            tc = 42 * esc * kc
            wc = medir(lt["nombre"], tc, "titular", -0.03 * tc)
            pc = 16 * esc * kc
            cwc, chc = wc + pc * 2, tc * 1.18 + pc * 0.9
            xc = {"izq": sx, "der": sw_right - cwc}.get(lt.get("lado"), cxs - cwc / 2)
            yc = h * lt.get("y_frac", 0.80)
            ev.append(_forma(0, t0, t1, xc, yc, cwc, chc, chc / 2, C["fondo"], borde=C["oro"], bord=max(2, int(2 * esc)), entra=(0, 24 * esc)))
            ev.append(_texto(2, t0, t1, xc + pc, yc + pc * 0.45, lt["nombre"], "Tit", C["blanco"], tam=int(tc), spacing=-0.03 * tc, entra=(0, 24 * esc)))
            continue
        klt = float(lt.get("escala", 1.0))
        tn, tr = 50 * esc * klt, 24 * esc * klt
        wn = medir(lt["nombre"], tn, "titular", -0.03 * tn)
        wr = medir(lt.get("rol", "").upper(), tr, "mono", 0.18 * tr)
        pad = 26 * esc * klt
        cw, ch = max(wn, wr) + pad * 2 + 12 * esc * klt, tn + tr + pad * 1.8
        x, y = sx, sy_bot - ch - (h * 0.04 if es_vertical(formato) else 0)
        if es_vertical(formato):
            y = sy_top + 14 * esc  # arriba, justo bajo el margen seguro: el subtítulo ocupa la parte baja de la zona
        if lt.get("lado") == "der":
            x = sw_right - cw
        elif lt.get("lado") == "centro":
            x = cxs - cw / 2
        if "y_frac" in lt:                       # reubicado por revisor_capas (nunca sobre la cara)
            y = h * lt["y_frac"]
        if lt.get("modo") == "pantalla":
            _pant(ev, t0, t1, w, h, C)
            x, y = cxs - cw / 2, (h - ch) / 2
        ev.append(_forma(0, t0, t1, x, y, cw, ch, 14 * esc, C["tarjeta"], entra=(-60 * esc, 0)))
        ev.append(_forma(1, t0, t1, x, y, 9 * esc, ch, 4 * esc, C["oro"], entra=(-60 * esc, 0)))
        ev.append(_texto(2, t0, t1, x + pad + 9 * esc, y + pad * 0.85, lt["nombre"], "Tit", C["blanco"], tam=int(tn), spacing=-0.03 * tn, entra=(-60 * esc, 0)))
        if lt.get("rol"):
            ev.append(_texto(2, t0, t1, x + pad + 9 * esc, y + pad * 0.85 + tn + 6 * esc, lt["rol"].upper(), "Mono", C["texto"], tam=int(tr), spacing=0.32 * tr, entra=(-60 * esc, 0)))

    for ti in plan.get("titulos", []):
        t0, t1 = ti["t"], ti["t"] + ti.get("dur", 3.0)
        kti = float(ti.get("escala", 1.0))
        tt, tl = 92 * esc * kti, 26 * esc * kti
        lineas = _partir(ti["texto"], tt, (sw_right - sx) - 80 * esc)
        anchos = [medir(l, tt, "titular", -0.03 * tt) for l in lineas]
        cw = max(max(anchos), medir(ti.get("etiqueta", "").upper(), tl, "mono", 0.18 * tl)) + 90 * esc
        ch = tl + len(lineas) * tt * 1.12 + 90 * esc
        x, y = cxs - cw / 2, (sy_top + 24 * esc + ch / 2 if es_vertical(formato) else h * 0.36 - ch / 2) - (ch / 2 if es_vertical(formato) else 0)
        if "y_frac" in ti:
            y = h * ti["y_frac"]
        if ti.get("lado") == "der":
            x = sw_right - cw
        elif ti.get("lado") == "izq":
            x = sx
        if ti.get("modo") == "pantalla":
            _pant(ev, t0, t1, w, h, C)
            x, y = cxs - cw / 2, (h - ch) / 2
        cxt = x + cw / 2
        borde = _cm(ti.get("color", "lima"))
        ev.append(_forma(0, t0, t1, x, y, cw, ch, 22 * esc, C["fondo"], borde=borde, bord=max(2, int(3 * esc)), entra=(0, 40 * esc)))
        if ti.get("etiqueta"):
            ev.append(_texto(2, t0, t1, cxt, y + 40 * esc, ti["etiqueta"].upper(), "Mono", _cm("oro"), an=8, tam=int(tl), spacing=0.32 * tl, entra=(0, 40 * esc)))
        for i, l in enumerate(lineas):
            ev.append(_texto(2, t0, t1, cxt, y + 40 * esc + tl + 18 * esc + i * tt * 1.12, l, "Tit", C["blanco"], an=8, tam=int(tt), spacing=-0.03 * tt, entra=(0, 40 * esc)))

    for ci in plan.get("cifras", []):
        if not (ci.get("fuente") and ci.get("verificada")):
            avisos.append(f"CIFRA RECHAZADA '{ci.get('valor')}' en t={ci.get('t')}: falta 'fuente' y 'verificada:true' (una cifra rotulada es una afirmación de marca)")
            continue
        t0, t1 = ci["t"], ci["t"] + ci.get("dur", 3.5)
        col = _cm(ci.get("tipo", "valor"))
        k = float(ci.get("escala", 1.0))
        tv, tl, tf = 150 * esc * k, 32 * esc * k, 24 * esc * k   # etiqueta/fuente más grandes (antes 26/20 px: ilegibles en móvil y bajo el umbral M11b)
        zona_w = (sw_right - sx) - 90 * esc
        wv = medir(ci["valor"], tv, "titular", -0.03 * tv)
        if wv > zona_w:                                   # cifra más ancha que la zona segura (ej. «10.000 USD» a 150 px = 840 px): se reduce lo justo para que quepa
            tv *= zona_w / wv * 0.985
            wv = medir(ci["valor"], tv, "titular", -0.03 * tv)
        # se mide con el MISMO espaciado con que se dibuja (0.32): antes se medía a 0.18 y la línea de fuente se salía de la zona segura
        def _envolver(txt, tam, partir=()):
            """Parte `txt` (mono, espaciado 0.32) en líneas que caben en la zona segura, sin reducir el tamaño: primero por los separadores, luego por palabras."""
            if medir(txt, tam, "mono", 0.32 * tam) <= zona_w:
                return [txt]
            for sep in partir:
                ps = txt.split(sep)
                if len(ps) > 1 and all(medir(p_, tam, "mono", 0.32 * tam) <= zona_w for p_ in ps):
                    return ps
            lns, cur_ = [], ""
            for p_ in txt.split():
                if cur_ and medir(cur_ + " " + p_, tam, "mono", 0.32 * tam) > zona_w:
                    lns.append(cur_)
                    cur_ = p_
                else:
                    cur_ = (cur_ + " " + p_).strip()
            return lns + [cur_]
        lin_e = _envolver(ci.get("etiqueta", "").upper(), tl, (" + ", " · "))
        lin_f = _envolver("FUENTE: " + ci["fuente"].upper(), tf, (" · ",))
        wl = max(medir(l_, tl, "mono", 0.32 * tl) for l_ in lin_e)
        wf = max(medir(l_, tf, "mono", 0.32 * tf) for l_ in lin_f)
        ex_e = tl * 1.45 * (len(lin_e) - 1)
        cw = max(wv, wl, wf) + 90 * esc
        ch = tl + ex_e + tv * 1.1 + tf * (1 + 1.45 * (len(lin_f) - 1)) + 100 * esc
        x = cxs - cw / 2 if es_vertical(formato) else (sx if ci.get("lado") == "izq" else sw_right - cw)
        y = sy_top + 24 * esc if es_vertical(formato) else (h * ci["y_frac"] if "y_frac" in ci else sy_top + 30 * esc)
        if es_vertical(formato):
            if "y_frac" in ci:
                y = h * ci["y_frac"]
            if ci.get("lado") == "izq":
                x = sx
            elif ci.get("lado") == "der":
                x = sw_right - cw
        if ci.get("modo") == "pantalla":
            _pant(ev, t0, t1, w, h, C)
            x, y = cxs - cw / 2, (h - ch) / 2
            try:    # sobre el panel los subtítulos siguen visibles abajo: la tarjeta se sube para no chocar con ellos (capa-vs-capa)
                from .planos import tope_subtitulos
                y = max(sy_top, min(y, tope_subtitulos(formato, w, h) * h - ch - 24 * esc))
            except (ImportError, AttributeError, KeyError):
                pass
        ev.append(_forma(0, t0, t1, x, y, cw, ch, 22 * esc, C["tarjeta"], borde=col, bord=max(2, int(3 * esc)), entra=(0, 40 * esc)))
        for j_, l_ in enumerate(lin_e):
            ev.append(_texto(2, t0, t1, x + cw / 2, y + 36 * esc + j_ * tl * 1.45, l_, "Mono", col, an=8, tam=int(tl), spacing=0.32 * tl, entra=(0, 40 * esc)))
        ev.append(_texto(2, t0, t1, x + cw / 2, y + 36 * esc + tl + ex_e + 10 * esc, ci["valor"], "Tit", col, an=8, tam=int(tv), spacing=-0.03 * tv, entra=(0, 40 * esc)))
        for j_, l_ in enumerate(lin_f):
            ev.append(_texto(2, t0, t1, x + cw / 2, y + ch - 34 * esc - tf * (1 + 1.45 * (len(lin_f) - 1)) + j_ * tf * 1.45, l_, "Mono", C["texto"], an=8, tam=int(tf), spacing=0.32 * tf, entra=(0, 40 * esc)))

    # Títulos grandes sobre el presentador (estilo reels Aztec Lab, paleta MacroWise): línea fina + línea clave en lima, sin caja salvo púrpura/terracota.
    # Claves: t, dur, linea1, linea2, color (lima|oro|teal|purpura|terracota), anim (subir|escala|reveal|barrido), caja (bool), y (fracción del alto, sólo no verticales).
    Pz = {"w": w, "h": h, "cx": cxs, "zw": sw_right - sx, "y_top": (sy_top + 20 * esc) if es_vertical(formato) else None, "y_bot": sy_bot}
    for tg in plan.get("titulos_grandes", []):
        Pz["y_top"] = (sy_top + 20 * esc) if es_vertical(formato) else h * tg.get("y", 0.14)
        if es_vertical(formato) and "y" in tg:
            Pz["y_top"] = h * tg["y"]
        if tg.get("modo") == "pantalla":
            _pant(ev, tg["t"], tg["t"] + tg.get("dur", 3.0), w, h, C)
            Pz["y_top"] = h * 0.36
        _titulo_grande(ev, tg, Pz, esc * float(tg.get("escala", 1.0)), C)

    # Modo impacto: palabra gigante a todo el ancho seguro, ≤ 1,2 s
    Pz["y_top"] = sy_top
    for im in plan.get("impacto", []):
        _impacto(ev, im, Pz, C, avisos)

    # Cierre CTA: "Comenta" + palabra clave grande en lima
    for cta in plan.get("cta", []):
        t0, t1 = cta["t"], cta["t"] + cta.get("dur", 4.0)
        yb = (sy_top + 20 * esc) if es_vertical(formato) else h * cta.get("y", 0.30)
        if es_vertical(formato) and "y" in cta:
            yb = h * cta["y"]
        if cta.get("modo") == "pantalla":
            _pant(ev, t0, t1, w, h, C)
            yb = h * 0.34
        kc = float(cta.get("escala", 1.0))
        tv, tp, te = 62 * esc * kc, 140 * esc * kc, 36 * esc * kc
        ev.append(_texto(2, t0, t1, cxs, yb, cta.get("verbo", "Comenta"), "Fino", C["blanco"], an=8, tam=int(tv), spacing=-0.02 * tv, entra=(0, 30 * esc), sombra=True, fade=True))
        ev.append(_texto(2, t0, t1, cxs, yb + tv * 1.2, "“" + cta["palabra"] + "”", "Tit", _cm("lima"), an=8, tam=int(tp), spacing=-0.03 * tp, entra=(0, 30 * esc), sombra=True, fade=True))
        if cta.get("extra"):
            ev.append(_texto(2, t0, t1, cxs, yb + tv * 1.2 + tp * 1.25, cta["extra"], "Fino", C["blanco"], an=8, tam=int(te), entra=(0, 30 * esc), sombra=True, fade=True))

    Path(ruta).write_text("".join(ev), encoding="utf-8")
    return avisos


def _partir(texto, tam, ancho_max):
    pal, lineas, cur = texto.split(), [], ""
    for p in pal:
        prueba = (cur + " " + p).strip()
        if medir(prueba, tam, "titular", -0.03 * tam) > ancho_max and cur:
            lineas.append(cur)
            cur = p
        else:
            cur = prueba
    if cur:
        lineas.append(cur)
    return lineas
