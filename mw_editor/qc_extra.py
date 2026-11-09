"""Métricas ampliadas del QC (docs/investigacion/metricas.json, prioridad alta). Ver docs/investigacion/metricas_implementacion.md.
Todo se mide con ffmpeg/ffprobe/OpenCV/NumPy locales: sin APIs ni coste. Cada función devuelve métricas (dict de metricas.py)."""
import json
import math
import re
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from . import metricas as M
from .common import FFMPEG, FFPROBE, ROOT, dims, probe, run

MODELO_CARA = ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"


# =====================================================================================
# Lectura de artefactos del proyecto
# =====================================================================================
def leer_words(trn):
    p = Path(trn) / "words_final.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError:
        return []


def _t_srt(s):
    h, m, r = s.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


def leer_srt(path):
    """[(ini, fin, texto_con_saltos)]"""
    if not path or not Path(path).exists():
        return []
    out = []
    for bloque in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8-sig").strip()):
        ls = bloque.strip().splitlines()
        if len(ls) >= 3 and "-->" in ls[1]:
            a, b = [x.strip() for x in ls[1].split("-->")]
            out.append((_t_srt(a), _t_srt(b), "\n".join(ls[2:])))
    return out


def _t_ass(s):
    h, m, r = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


def leer_ass(path):
    """Eventos de un ASS: [{ini, fin, estilo, texto, tam, dibujo, x, y}]. 'tam' = \\fs del evento o el del estilo."""
    if not path or not Path(path).exists():
        return []
    estilos, cols, ev = {}, None, []
    for ln in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if ln.startswith("Format:") and "Fontname" in ln:
            cols = [c.strip() for c in ln[7:].split(",")]
        elif ln.startswith("Style:") and cols:
            v = [c.strip() for c in ln[6:].split(",")]
            d = dict(zip(cols, v))
            try:
                estilos[d["Name"]] = float(d["Fontsize"])
            except (KeyError, ValueError):
                pass
        elif ln.startswith("Dialogue:"):
            p = ln[9:].split(",", 9)
            if len(p) < 10:
                continue
            tags = " ".join(re.findall(r"\{[^}]*\}", p[9]))
            dibujo = bool(re.search(r"\\p1", tags))
            txt = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", "\n").replace("\\n", "\n")
            m = re.search(r"\\fs(\d+(?:\.\d+)?)", tags)
            tam = float(m.group(1)) if m else estilos.get(p[3].strip(), 0.0)
            mv = re.search(r"\\move\(\s*[-\d.]+\s*,\s*[-\d.]+\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", tags) or re.search(r"\\pos\(\s*([-\d.]+)\s*,\s*([-\d.]+)", tags)
            try:
                ev.append({"ini": _t_ass(p[1]), "fin": _t_ass(p[2]), "estilo": p[3].strip(), "texto": txt, "tam": tam, "dibujo": dibujo,
                           "x": float(mv.group(1)) if mv else None, "y": float(mv.group(2)) if mv else None})
            except ValueError:
                continue
    return ev


def leer_plan(proj):
    """Plan de gráficos del proyecto (lote.py lo copia a 00_DOCS/plan_grafico.json). None si no se conserva."""
    proj = Path(proj)
    for c in (proj / "00_DOCS" / "plan_grafico.json", proj / "05_PROJECT" / "plan.json", proj / "05_PROJECT" / "plan_grafico.json"):
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8-sig"))
            except ValueError:
                pass
    return None


# =====================================================================================
# Contexto por formato
# =====================================================================================
class Ctx:
    def __init__(self, proj, exp, base, fm, hay_voz, perfil=None):
        self.proj, self.exp, self.base, self.fm, self.hay_voz, self.perfil = Path(proj), Path(exp), Path(base), fm, hay_voz, perfil
        self.W, self.H = dims(fm)
        pre = base.name[: -len("_base.mp4")]  # nombre_formato_vN
        self.pre = pre
        self.ref = next(iter(sorted(self.exp.glob(pre + "_REFERENCIA.mp4"))), None)
        self.subs_mov = next(iter(sorted(self.exp.glob(pre + "_subtitulos_ALFA.mov"))), None)
        self.graf_mov = next(iter(sorted(self.exp.glob(pre + "_graficos_ALFA.mov"))), None)
        self.subs_ass = next(iter(sorted(self.exp.glob(pre + "_subtitulos.ass"))), None)
        self.graf_ass = next(iter(sorted(self.exp.glob(pre + "_graficos.ass"))), None)
        nombre = pre.split(f"_{fm}_v")[0]
        self.srt = next(iter(sorted(self.exp.glob(nombre + "_v*_subtitulos.srt"))), None)
        self.words = leer_words(self.proj / "03_TRANSCRIPT")
        self.plataformas = [perfil] if perfil in M.PLATAFORMAS else list(M.PLATAFORMAS_POR_FORMATO.get(fm, ()))
        self.futuros = {}
        # ffmpeg tarda varios segundos en ARRANCAR en este equipo: todo lo independiente se lanza a la vez
        self._pool = ThreadPoolExecutor(6)
        self.futuros["info"] = self._pool.submit(probe, str(base))
        self.futuros["scdet"] = self._pool.submit(cortes_scdet, base)
        self.futuros["probe_ref"] = self._pool.submit(_probe_json, self.ref or base)
        for k, mov in (("subs", self.subs_mov), ("graf", self.graf_mov)):
            if mov:
                self.futuros["probe_" + k] = self._pool.submit(_probe_json, mov)
        self.info = self.futuros["info"].result()
        self.dur = self.info["duracion"]
        self.corto = M.es_corto(self.dur, fm)
        self.fps_mue = max(0.5, min(4.0, 480.0 / max(self.dur, 1)))
        for k, mov, cap in (("subs", self.subs_mov, 14), ("graf", self.graf_mov, 8)):
            if mov:
                self.futuros["rgba_" + k] = self._pool.submit(_leer_rgba, mov, self.W, self.H, self.fps_mue, cap)

    def r(self, k):
        f = self.futuros.get(k)
        return f.result() if f else None

    def cerrar(self):
        self._pool.shutdown(wait=False)


# =====================================================================================
# Eventos visuales: cortes (scdet) + tarjetas/gráficos + saltos de montaje
# =====================================================================================
def cortes_scdet(path, umbral=6.0):
    p = run([FFMPEG, "-hide_banner", "-v", "info", "-i", str(path), "-an", "-vf", f"scdet=t={umbral}:s=1", "-f", "null", "-"], check=False)
    return sorted(float(m) for m in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", p.stderr))


def saltos_montaje(proj):
    """Tiempos (en el timeline final) donde el montaje une dos tramos del original: cada uno es un salto visible."""
    p = Path(proj) / "05_PROJECT" / "cut_plan.json"
    if not p.exists():
        return []
    try:
        keep = json.loads(p.read_text(encoding="utf-8-sig")).get("keep", [])
    except ValueError:
        return []
    t, out = 0.0, []
    for a, b in keep[:-1]:
        t += b - a
        out.append(round(t, 3))
    return out


def eventos_visuales(ctx):
    """Devuelve (lista ordenada [(t, tipo)], primer_texto). Subtítulos no cuentan como cambio visual (aparecen siempre)."""
    ev = [(t, "corte") for t in (ctx.r("scdet") or [])]
    ev += [(t, "salto") for t in saltos_montaje(ctx.proj)]
    graf = leer_ass(ctx.graf_ass)
    ev += [(t, "grafico") for t in sorted({round(e["ini"], 2) for e in graf})]
    ev = sorted(e for e in ev if e[0] > 0.05)
    # fusionar eventos a < 0.3 s (un salto + su corte de plano = 1 solo evento)
    fus = []
    for t, k in ev:
        if fus and t - fus[-1][0] < 0.3:
            continue
        fus.append((t, k))
    sub = [e["ini"] for e in leer_ass(ctx.subs_ass) if not e["dibujo"] and e["texto"].strip()]
    textos = sub + [e["ini"] for e in graf if not e["dibujo"] and e["texto"].strip()]
    if not textos and ctx.words:
        textos = [ctx.words[0]["s"]]
    return fus, (min(textos) if textos else None)


def m_ritmo(ctx):
    """M01 primer evento, M03 cortes/min y ASL, M04 máximo tramo sin cambio."""
    ev, t_txt = eventos_visuales(ctx)
    ts = [t for t, _ in ev]
    corto = ctx.corto
    out = []
    # M01
    cand = [t for t in (ts[0] if ts else None, t_txt) if t is not None]
    t1 = min(cand) if cand else None
    if t1 is None:
        out.append(M.na("M01", "Tiempo al primer evento visual/texto", "sin cortes ni texto detectados"))
    else:
        p, w = (1.5, 3.0) if corto else (5.0, 10.0)
        det = f"primer evento {t1:.2f}s (corte/gráfico: {ts[0]:.2f}s)" if ts else f"primer texto {t1:.2f}s; sin cortes ni gráficos"
        det += f" · primer texto {t_txt:.2f}s" if t_txt is not None else ""
        out.append(M.metrica("M01", "Tiempo al primer evento visual/texto", t1, M.estado_max(t1, p, w), f"<= {p} s", f"<= {w} s", det,
                             "estimado", "alta", puntaje=M.lin(t1, p, w, w * 2), unidad="s"))
    # M03
    n = len(ts)
    cpm = 60.0 * n / ctx.dur if ctx.dur else 0
    asl = ctx.dur / (n + 1)
    if ctx.dur < 8:
        out.append(M.na("M03", "Cortes por minuto / ASL", "clip < 8 s: cortes/min poco representativo"))
    else:
        if corto:
            pl, ph, wl, wh, fl, fh = 12, 30, 6, 40, 0, 60
        else:
            pl, ph, wl, wh, fl, fh = 4, 15, 2, 25, 0, 40
        st = M.estado_rango(cpm, pl, ph, wl, wh)
        out.append(M.metrica("M03", "Cortes por minuto / ASL", cpm, st, f"{pl}-{ph} cortes/min", f"{wl}-{wh} cortes/min",
                             f"{n} eventos en {ctx.dur:.1f}s = {cpm:.1f}/min · plano medio {asl:.1f}s ({', '.join(sorted({k for _, k in ev})) or 'ninguno'})",
                             "estimado", "media", puntaje=M.puntaje_rango(cpm, pl, ph, wl, wh, fl, fh), unidad="cortes/min"))
    # M04
    puntos = [0.0] + ts + [ctx.dur]
    gap = max(b - a for a, b in zip(puntos, puntos[1:]))
    p, w = (5.0, 8.0) if corto else (15.0, 30.0)
    out.append(M.metrica("M04", "Máximo tramo sin cambio visual", gap, M.estado_max(gap, p, w), f"<= {p} s", f"<= {w} s",
                         f"tramo más largo {gap:.1f}s", "estimado", "media", puntaje=M.lin(gap, p, w, w * 2), unidad="s"))
    return out


# =====================================================================================
# Voz: inicio, palabras/s, silencio muerto
# =====================================================================================
def m_voz(ctx):
    w = ctx.words
    if not ctx.hay_voz or len(w) < 3:
        return [M.na("M02", "Inicio de voz", "sin voz detectada"), M.na("M05", "Palabras por segundo", "sin voz detectada")]
    out = []
    t0 = w[0]["s"]
    out.append(M.metrica("M02", "Inicio de voz (gancho hablado)", t0, M.estado_max(t0, 1.0, 2.0), "<= 1.0 s", "<= 2.0 s", f"primera palabra a {t0:.2f}s",
                         "estimado", "alta", puntaje=M.lin(t0, 1.0, 2.0, 4.0), unidad="s"))
    pausas = sum(max(0.0, b["s"] - a["e"]) for a, b in zip(w, w[1:]) if b["s"] - a["e"] > 0.4)
    activo = (w[-1]["e"] - w[0]["s"]) - pausas
    wps = len(w) / activo if activo > 0.5 else None
    if wps is None:
        out.append(M.na("M05", "Palabras por segundo", "voz activa < 0.5 s"))
    else:
        out.append(M.metrica("M05", "Palabras por segundo", wps, M.estado_rango(wps, 2.2, 3.3, 1.8, 3.9), "2.2-3.3 pal/s", "1.8-2.2 o 3.3-3.9 pal/s",
                             f"{len(w)} palabras / {activo:.1f}s activos (pausas > 0.4 s descontadas)", "estimado", "media",
                             puntaje=M.puntaje_rango(wps, 2.2, 3.3, 1.8, 3.9, 1.2, 5.0), unidad="pal/s"))
    return out


def m_silencio(ctx):
    """M15 silencio muerto: silencedetect sobre el audio del base."""
    if not ctx.hay_voz or not ctx.info.get("tiene_audio"):
        return [M.na("M15", "Silencio muerto", "sin voz/audio")]
    p = run([FFMPEG, "-hide_banner", "-v", "info", "-i", str(ctx.base), "-vn", "-af", "silencedetect=n=-45dB:d=0.25", "-f", "null", "-"], check=False)
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", p.stderr)]
    ini = re.findall(r"silence_start:\s*([\d.]+)", p.stderr)
    if len(ini) > len(durs):  # silencio abierto hasta el final del archivo
        durs.append(max(0.0, ctx.dur - float(ini[-1])))
    mx, tot = (max(durs) if durs else 0.0), sum(durs)
    pct = 100.0 * tot / ctx.dur if ctx.dur else 0
    pm, wm = (0.6, 1.2) if ctx.corto else (1.5, 3.0)
    st = M.estado_max(mx, pm, wm)
    if pct >= 15 and st == "PASS":
        st = "WARN"
    elif 8 <= pct < 15 and st == "PASS":
        st = "WARN"
    pun = min(M.lin(mx, pm, wm, wm * 2), M.lin(pct, 8, 15, 30))
    return [M.metrica("M15", "Silencio muerto", mx, st, f"máx <= {pm} s y < 8 %", f"máx <= {wm} s y < 15 %",
                      f"máx {mx:.2f}s · total {tot:.1f}s = {pct:.1f}% ({len(durs)} tramos < -45 dB)", "estimado", "media", puntaje=pun, unidad="s")]


# =====================================================================================
# Subtítulos: CPS, líneas, duración de cues, cobertura, grupos dinámicos
# =====================================================================================
def m_subtitulos(ctx):
    out = []
    cues = leer_srt(ctx.srt)
    if not ctx.hay_voz:
        return [M.na("M06", "CPS de subtítulos", "sin voz")]
    if not cues:
        out.append(M.metrica("M06", "CPS de subtítulos", None, "WARN", "p95 <= 17", "p95 <= 21", "no hay SRT que medir", "terceros", "alta", duro=False))
        return out
    cps = [len(c[2].replace("\n", " ")) / max(0.01, c[1] - c[0]) for c in cues]
    p95 = float(np.percentile(cps, 95))
    sobre = sum(1 for v in cps if v > 21)
    st = M.estado_max(p95, 17.0, 21.0)
    if sobre and st == "PASS":
        st = "WARN"
    out.append(M.metrica("M06", "CPS de subtítulos (SRT)", p95, st, "p95 <= 17 y 0 cues > 21", "p95 <= 21",
                         f"p95 {p95:.1f} cps · máx {max(cps):.1f} · {sobre}/{len(cps)} cues > 21 (Netflix; español sin verificar)", "terceros", "media",
                         puntaje=min(M.lin(p95, 17, 21, 30), M.lin(sobre / len(cps), 0, 0.15, 0.5)), unidad="cps"))
    # M07 líneas del SRT (referencia horizontal) + grupos dinámicos ASS (referencia del formato)
    mx_l = max(len(l) for c in cues for l in c[2].split("\n"))
    max_n = max(len(c[2].split("\n")) for c in cues)
    lim_dyn = 42 if ctx.fm == "horizontal" else 28
    grupos_l = _lineas_grupo_ass(ctx.subs_ass)
    mx_g = max(grupos_l) if grupos_l else None
    st7 = "PASS"
    if mx_l > 47 or max_n > 3:
        st7 = "FAIL"
    elif mx_l > 42 or max_n > 2:
        st7 = "WARN"
    if mx_g is not None:
        if mx_g > lim_dyn + 6:
            st7 = "FAIL"
        elif mx_g > lim_dyn and st7 == "PASS":
            st7 = "WARN"
    pun7 = min(M.lin(mx_l, 42, 47, 60), M.lin(mx_g if mx_g is not None else 0, lim_dyn, lim_dyn + 6, lim_dyn + 20), M.lin(max_n, 2, 3, 5))
    out.append(M.metrica("M07", "Caracteres por línea y líneas por cue", mx_l, st7, f"SRT <= 42 car, <= 2 líneas; grupos animados <= {lim_dyn}", f"SRT 42-47, 3 líneas; grupos {lim_dyn}-{lim_dyn + 6}",
                         f"SRT: máx {mx_l} car/línea, {max_n} líneas · grupos animados: máx {mx_g if mx_g is not None else 's/d'} car/línea", "terceros", "media", puntaje=pun7, unidad="car"))
    # M08a duración de cues SRT
    fuera = [c for c in cues if not (0.83 <= c[1] - c[0] <= 7.0)]
    fr = len(fuera) / len(cues)
    # un cue final/único corto no es un defecto: se descuenta si es el último
    out.append(M.metrica("M08", "Duración de cues SRT (0.83-7 s)", 100 * (1 - fr), M.estado_min(100 * (1 - fr), 100, 90), "100 % dentro", ">= 90 % dentro",
                         f"{len(fuera)}/{len(cues)} cues fuera de rango" + (f" (más corto {min(c[1] - c[0] for c in cues):.2f}s)" if cues else ""),
                         "terceros", "baja", puntaje=M.lin(fr, 0, 0.1, 0.4), unidad="%"))
    # M08b cobertura de voz por subtítulos
    w = ctx.words
    if w:
        cubierto = 0.0
        for a in w:
            if any(c[0] - 0.05 <= (a["s"] + a["e"]) / 2 <= c[1] + 0.05 for c in cues):
                cubierto += 1
        cob = 100.0 * cubierto / len(w)
        out.append(M.metrica("M08b", "Cobertura de voz por subtítulos", cob, M.estado_min(cob, 95, 85), ">= 95 %", "85-95 %",
                             f"{int(cubierto)}/{len(w)} palabras con cue activo", "terceros", "media", puntaje=M.lin(cob, 95, 85, 60), unidad="%"))
    # M08c grupos dinámicos: duración mínima por grupo y palabras que casi no se ven
    ev = [e for e in leer_ass(ctx.subs_ass) if not e["dibujo"] and e["texto"].strip()]
    if ev:
        grupos = {}
        for e in ev:
            grupos.setdefault(round(e["fin"], 2), []).append(e)
        dur_g = [g[0]["fin"] - min(x["ini"] for x in g) for g in grupos.values()]
        breves = sum(1 for e in ev if e["fin"] - e["ini"] < 0.1)
        corto_g = sum(1 for d in dur_g if d < 0.25)
        pb = 100.0 * breves / len(ev)
        st = "PASS" if (corto_g == 0 and pb <= 3) else ("WARN" if (corto_g <= max(1, len(dur_g) // 10) and pb <= 10) else "FAIL")
        out.append(M.metrica("M08c", "Grupos animados: duración mínima y palabras fugaces", min(dur_g), st, "grupos >= 0.25 s y <= 3 % de palabras visibles < 0.1 s",
                             "<= 10 % de grupos cortos y <= 10 % fugaces", f"{len(dur_g)} grupos (mín {min(dur_g):.2f}s) · {breves}/{len(ev)} palabras visibles < 0.1 s ({pb:.0f} %) · {corto_g} grupos < 0.25 s",
                             "terceros", "media", puntaje=min(M.lin(pb, 3, 10, 30), M.lin(corto_g / len(dur_g), 0, 0.1, 0.4)), unidad="s"))
    return out


def _lineas_grupo_ass(ass):
    """Caracteres por línea de cada grupo de subtítulo animado (eventos con el mismo Fin, agrupados por fila y)."""
    ev = [e for e in leer_ass(ass) if not e["dibujo"] and e["texto"].strip() and e["y"] is not None]
    grupos = {}
    for e in ev:
        grupos.setdefault(round(e["fin"], 2), []).append(e)
    out = []
    for g in grupos.values():
        filas = {}
        for e in g:
            filas.setdefault(round(e["y"] / 20), []).append(e)
        for f in filas.values():
            out.append(len(" ".join(x["texto"].strip() for x in sorted(f, key=lambda z: z["x"] or 0))))
    return out


# =====================================================================================
# Capas con alfa: escaneo, zona segura por perfil, contraste, tamaño, solape cara-texto
# =====================================================================================
def _leer_rgba(mov, W, H, fps, cap):
    """Una sola pasada de ffmpeg sobre una capa con alfa, a media resolución.
    Devuelve (masks, muestras): masks = lista de máscaras empaquetadas (None = fotograma sin texto opaco), una por fotograma muestreado;
    muestras = {indice: RGBA media-resolución} de hasta `cap` fotogramas con texto repartidos de forma pareja (adelgazado adaptativo)."""
    w2, h2 = W // 2, H // 2
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-i", str(mov), "-vf", f"fps={fps},scale={w2}:{h2}:flags=area,format=rgba", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n, masks, cand, paso = w2 * h2 * 4, [], [], 1
    i = 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(h2, w2, 4)
        m = fr[..., 3] > 110
        con = int(m.sum()) >= 150
        masks.append(np.packbits(m) if con else None)
        if con and i % paso == 0:
            cand.append((i, fr.copy()))
            if len(cand) > 2 * cap:
                cand = cand[::2]
                paso *= 2
        i += 1
    p.wait()
    # quedarse con `cap` repartidas
    if len(cand) > cap:
        cand = [cand[int(j * (len(cand) - 1) / (cap - 1))] for j in range(cap)]
    return masks, dict(cand)


def _mask(packed, W, H):
    if packed is None:
        return None
    n = (W // 2) * (H // 2)
    return np.unpackbits(packed)[:n].reshape(H // 2, W // 2).astype(bool)


def _bbox(m):
    ys, xs = np.where(m)
    if not len(xs):
        return None
    return (int(xs.min()) * 2, int(ys.min()) * 2, int(xs.max()) * 2 + 1, int(ys.max()) * 2 + 1)


_PERF_CACHE = {}


def perfiles_zona(fm):
    """Con caché: la 1.ª llamada debe hacerse en el hilo principal (puede cambiar el preset de zonas.py un instante)."""
    if fm not in _PERF_CACHE:
        _PERF_CACHE[fm] = _perfiles_zona(fm)
    return _PERF_CACHE[fm]


def _perfiles_zona(fm):
    """[(nombre, (x0,y0,x1,y1), activo)]. Con el API ampliado de zonas.py (PERFILES, perfil_px, preset con uniones) devuelve el preset ACTIVO
    (lo que usó el motor) + cada perfil/preset individual del formato. Con el API antiguo (seg()/caja_segura_px()) devuelve solo el activo."""
    from . import zonas
    W, H = dims(fm)
    res = []
    try:
        activo = zonas.preset()
    except Exception:  # noqa: BLE001
        activo = "activo"
    try:
        res.append((f"preset:{activo}", tuple(float(v) for v in zonas.caja_segura_px(fm)), True))
    except Exception:  # noqa: BLE001
        pass
    try:
        nombres = [n for n, p in zonas.PERFILES.items() if p.get("formato") == fm]
        if fm == "vertical":
            nombres = list(getattr(zonas, "PRESETS_VERTICAL_PX", {})) + nombres
        for n in nombres:
            px = zonas.perfil_px(n)
            res.append((n, (float(px["izquierda"]), float(px["arriba"]), float(W - px["derecha"]), float(H - px["abajo"])), False))
    except Exception:  # noqa: BLE001
        pass  # API antiguo sin perfiles: basta con el preset activo
    if not res:
        res.append(("completo", (0.0, 0.0, float(W), float(H)), True))
    return res


def _frames_base(path, indices, fps, W, H):
    """Fotogramas del vídeo base (media resolución, BGR) en los índices dados del muestreo a `fps`. Un solo ffmpeg."""
    if not indices:
        return {}
    w2, h2 = W // 2, H // 2
    sel = "+".join(f"eq(n\\,{i})" for i in indices)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-i", str(path), "-an", "-vf", f"fps={fps},select='{sel}',scale={w2}:{h2}:flags=area", "-fps_mode", "passthrough",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    n = w2 * h2 * 3
    out = {}
    for k, i in enumerate(indices):
        seg = p.stdout[k * n:(k + 1) * n]
        if len(seg) < n:
            break
        out[i] = np.frombuffer(seg, np.uint8).reshape(h2, w2, 3)
    return out


def _lum(rgb01):
    lin = np.where(rgb01 <= 0.03928, rgb01 / 12.92, ((rgb01 + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def _contraste_capa(base_bgr, ov_bgra):
    """Peor contraste WCAG texto-vs-fondo de una capa sobre el fotograma real (ambos a media resolución, el overlay en RGBA).
    None si no hay texto opaco suficiente."""
    b = base_bgr[..., ::-1].astype(np.float32) / 255
    o = ov_bgra
    a = o[..., 3].astype(np.float32) / 255
    orgb = o[..., :3].astype(np.float32) / 255  # RGBA de ffmpeg: R,G,B,A
    opaco = a >= 0.9
    if opaco.sum() < 150:
        return None
    comp = b * (1 - a[..., None]) + orgb * a[..., None]
    lum = _lum(comp)
    ov_lum = _lum(orgb)
    q = (o[..., 0].astype(np.int32) >> 4) << 8 | (o[..., 1].astype(np.int32) >> 4) << 4 | (o[..., 2].astype(np.int32) >> 4)
    claves, cuentas = np.unique(q[opaco], return_counts=True)
    h2, w2 = opaco.shape
    cand, cajas_m, marcos_m = [], np.zeros_like(opaco), np.zeros_like(opaco)
    for k, c in zip(claves, cuentas):
        if c < 30:
            continue
        mk = ((q == k) & opaco).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(mk, connectivity=8)
        glifo = np.zeros_like(opaco)
        # El panel opaco a pantalla completa (revisor_capas) es del mismo color Warm Black que el texto oscuro sobre caja de color: sin esta
        # excepción TODA la clase de color se marcaba «relleno de tarjeta» y el texto oscuro (ej. «El hábito» sobre caja oro) se medía contra sí
        # mismo (1,1:1 falso). El panel sigue contando como fondo (cajas_m), pero no arrastra a las letras de su mismo color.
        if any(st[i, cv2.CC_STAT_AREA] > 300 and st[i, cv2.CC_STAT_AREA] / max(1, st[i, cv2.CC_STAT_WIDTH] * st[i, cv2.CC_STAT_HEIGHT]) > 0.55
               and st[i, cv2.CC_STAT_WIDTH] > 14 and st[i, cv2.CC_STAT_HEIGHT] > 14
               and not (st[i, cv2.CC_STAT_WIDTH] >= 0.9 * w2 and st[i, cv2.CC_STAT_HEIGHT] >= 0.9 * h2) for i in range(1, n)):
            cajas_m |= mk > 0  # este color es relleno de tarjeta: también sus trozos sueltos (huecos de las letras)
            continue
        for i in range(1, n):
            ar, wd, ht = st[i, cv2.CC_STAT_AREA], st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
            fill = ar / max(1, wd * ht)
            if ar > 300 and fill > 0.55 and wd > 14 and ht > 14:
                cajas_m |= lab == i                      # relleno de tarjeta / cápsula
            elif wd > 0.35 * w2 or ht > 0.12 * h2 or (fill < 0.12 and ar > 300) or (fill > 0.8 and min(wd, ht) <= 8 and max(wd, ht) >= 40):
                marcos_m |= lab == i                     # marco, línea o trazo decorativo: no es texto
            else:
                glifo |= lab == i
        if glifo.sum() >= 30:
            cand.append((int(glifo.sum()), k, glifo))
    if not cand:
        return None
    mayor = max(c for c, _, _ in cand)
    # descarta los niveles de gris/color del BORDE SUAVIZADO (antialias): cada nivel intermedio de «blanco sobre oscuro» se medía como si fuera
    # un texto de color apagado y daba 1,2-1,9:1 falsos; el color real del texto es la clase con más píxeles (umbral 0,45 del mayor)
    textos = [(k, m) for c, k, m in cand if c >= 0.45 * mayor]
    # todo lo opaco que NO es relleno de caja ni marco = texto (incluye su borde suavizado); alrededor de eso no se mide el fondo
    texto_todo = opaco & ~cajas_m & ~marcos_m
    k_ex = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    k_cerca = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    excluir = (cv2.dilate(texto_todo.astype(np.uint8), k_ex) > 0) | ((a > 0.02) & (a < 0.9) & (ov_lum > 0.2))
    por_lado = {}
    for k, m in textos:
        lt = float(np.median(_lum(orgb[m])))
        cerca = cv2.dilate(m.astype(np.uint8), k_cerca) > 0
        anillo = cerca & ~excluir
        if anillo.sum() < 25:
            continue
        fondo = lum[anillo]
        lb = float(np.percentile(fondo, 75 if lt >= np.median(fondo) else 25))
        r = (max(lt, lb) + 0.05) / (min(lt, lb) + 0.05)
        lado = lt >= lb                                  # texto más claro (True) o más oscuro (False) que su fondo
        por_lado[lado] = max(por_lado.get(lado, 0.0), r)  # los niveles de antialias están en el mismo lado y con menos contraste que el color real: se queda el mejor
    return min(por_lado.values()) if por_lado else None


@lru_cache(maxsize=4)
def _modelo_cara(w, h):
    return cv2.FaceDetectorYN.create(str(MODELO_CARA), "", (w, h), 0.8, 0.3, 5000)


def _cara_principal(img_bgr):
    """(x,y,w,h, landmarks[5][2]) de la cara más grande, en coordenadas de la imagen dada; None si no hay."""
    h, w = img_bgr.shape[:2]
    det = _modelo_cara(w, h)
    _, c = det.detect(np.ascontiguousarray(img_bgr))
    if c is None or not len(c):
        return None
    f = max(c, key=lambda r: r[2] * r[3])
    lm = [(float(f[4 + 2 * i]), float(f[5 + 2 * i])) for i in range(5)]
    return (float(f[0]), float(f[1]), float(f[2]), float(f[3]), lm)


def m_capas(ctx):
    """Zona segura por perfil (M10), contraste (M09), tamaño de texto (M11), solape cara-texto (M16a), tamaño de cara (M16b)."""
    out = []
    if not ctx.subs_mov and not ctx.graf_mov:
        return [M.na("M10", "Texto en zona segura", "sin capas con alfa")]
    W, H, fps = ctx.W, ctx.H, ctx.fps_mue
    ms, mues_s = ctx.r("rgba_subs") or ([], {})
    mg, mues_g = ctx.r("rgba_graf") or ([], {})
    n = max(len(ms), len(mg))
    ms = ms + [None] * (n - len(ms))
    mg = mg + [None] * (n - len(mg))
    onsets = sorted({e["ini"] for e in leer_ass(ctx.graf_ass)})
    # paneles a pantalla completa decididos por revisor_capas: ocultan al presentador A PROPÓSITO (opacos, fuera de las métricas de cara/zona segura)
    try:
        mv_ = re.search(r"_v(\d+)$", ctx.pre)
        rj = json.loads((ctx.proj / "00_DOCS" / f"revision_capas_{ctx.fm}_v{mv_.group(1)}.json").read_text(encoding="utf-8")) if mv_ else {}
        wins = [(p_["t"], p_["t"] + (p_.get("dur") or 3.0)) for p_ in rj.get("panel_completo", [])]
        for i in range(n):
            if any(a - 0.1 <= i / fps <= b + 0.1 for a, b in wins):
                mg[i] = None
    except (OSError, ValueError, KeyError):
        pass

    def estable_graf(t):
        return not any(o - 0.15 <= t < o + 0.3 for o in onsets)

    # ---------- M10 zona segura por perfil ----------
    perfiles = perfiles_zona(ctx.fm)
    tol = 6
    res_p = {}
    bboxes = []
    for i in range(n):
        t = i / fps
        for pk, es_g in ((ms[i], False), (mg[i], True)):
            if pk is not None and not (es_g and not estable_graf(t)):
                bb = _bbox(_mask(pk, W, H))
                if bb:
                    bboxes.append((t, bb))
    for nombre, (x0, y0, x1, y1), _act in perfiles:
        dentro = sum(1 for _, bb in bboxes if bb[0] >= x0 - tol and bb[2] <= x1 + tol and bb[1] >= y0 - tol and bb[3] <= y1 + tol)
        fuera = [bb for _, bb in bboxes if not (bb[0] >= x0 - tol and bb[2] <= x1 + tol and bb[1] >= y0 - tol and bb[3] <= y1 + tol)]
        res_p[nombre] = (100.0 * dentro / len(bboxes) if bboxes else None, len(bboxes), fuera[0] if fuera else None)
    act = next((p for p in perfiles if p[2]), perfiles[0])[0]
    pct, tot_act, peor = res_p[act]
    if pct is None:
        out.append(M.na("M10", "Texto en zona segura", "sin texto opaco que medir"))
    else:
        st = "PASS" if pct >= 100 else ("WARN" if pct >= 98 else "FAIL")
        falla = [f"{k} {v[0]:.0f}%" for k, v in res_p.items() if v[0] is not None and v[0] < 100 and k != act]
        otros = (", ".join(falla) + " (el resto 100 %)") if falla else f"los {len(res_p) - 1} perfiles restantes 100 %"
        out.append(M.metrica("M10", "Texto en zona segura (por perfil)", pct, st, "100 % de muestras", ">= 98 %",
                             f"'{act}': {pct:.1f}% de {tot_act} muestras dentro" + (f" (ej. caja fuera {peor})" if peor else "") + f" · otros perfiles: {otros} · tolerancia {tol}px; entrada de tarjetas (0.3 s) excluida",
                             "terceros", "alta", puntaje=M.lin(100 - pct, 0, 2, 20), unidad="%", duro=(pct < 90)))

    # ---------- tamaño mínimo de texto (declarado en ASS) ----------
    for etiqueta, ass in (("subtítulos", ctx.subs_ass), ("gráficos", ctx.graf_ass)):
        ev = [e for e in leer_ass(ass) if not e["dibujo"] and e["texto"].strip() and e["tam"]]
        if not ev:
            continue
        mn = min(ev, key=lambda e: e["tam"])
        rel = mn["tam"] / ctx.H
        p_rel, w_rel = (44 / 1920, 36 / 1920) if ctx.fm != "horizontal" else (36 / 1080, 28 / 1080)
        extra = ""
        if etiqueta == "gráficos":
            cif = [e for e in ev if re.search(r"\d", e["texto"]) and e["tam"] >= 90]
            if cif:
                extra = f" · cifras mín {min(e['tam'] for e in cif):.0f}px (>= 64)"
            extra += f" · {sum(1 for e in ev if e['tam'] < p_rel * ctx.H)}/{len(ev)} líneas bajo el umbral"
        out.append(M.metrica("M11" + ("" if etiqueta == "subtítulos" else "b"), f"Tamaño mínimo de texto ({etiqueta})", rel * 100, M.estado_min(rel, p_rel, w_rel),
                             f">= {p_rel * 100:.2f} % del alto (44 px en 1920)", f">= {w_rel * 100:.2f} %",
                             f"mín {mn['tam']:.0f}px = {rel * 100:.2f}% del alto ('{mn['texto'].strip()[:24]}'){extra}", "estimado", "media",
                             puntaje=M.lin(rel, p_rel, w_rel, w_rel * 0.5), unidad="% alto"))

    # ---------- muestras: contraste + cara (un solo ffmpeg para los fotogramas base) ----------
    con_texto = [i for i in range(n) if ms[i] is not None or mg[i] is not None]
    if not con_texto:
        return out
    uniformes = sorted({int(j * (n - 1) / 11) for j in range(12)}) if n > 1 else [0]
    # para el solape cara-texto: fotogramas con texto repartidos + los retenidos para el contraste
    reparto = [con_texto[int(j * (len(con_texto) - 1) / 15)] for j in range(16)] if len(con_texto) > 16 else con_texto
    sel = sorted(set(reparto) | set(mues_s) | set(mues_g) | set(uniformes))
    base = _frames_base(ctx.base, sel, fps, W, H)
    contrastes, filas_cara, tamanos_cara = [], [], []
    for i in sel:
        fr = base.get(i)
        if fr is None:
            continue
        cara = _cara_principal(fr)
        if cara:
            tamanos_cara.append(cara[3] / (H / 2))
        for mues, nombre in ((mues_s, "subs"), (mues_g, "graf")):
            if i in mues and (nombre == "subs" or estable_graf(i / fps)):
                c = _contraste_capa(fr, mues[i])
                if c is not None:
                    contrastes.append((c, i / fps, nombre))
        if cara and (ms[i] is not None or mg[i] is not None):
            mk = np.zeros((H // 2, W // 2), bool)
            for pk in (ms[i], mg[i]):
                if pk is not None:
                    mk |= _mask(pk, W, H)
            fx, fy, fw, fh, lm = cara
            tap = {}
            for nom, (lx, ly) in zip(("ojo_d", "ojo_i", "nariz", "boca_d", "boca_i"), lm):
                cx, cy = int(lx), int(ly)
                tap[nom] = bool(mk[max(0, cy - 3):cy + 4, max(0, cx - 3):cx + 4].any())
            reg = mk[max(0, int(fy)):int(fy + fh), max(0, int(fx)):int(fx + fw)]
            filas_cara.append((i / fps, tap, float(reg.mean()) if reg.size else 0.0))

    # M09 contraste
    if contrastes:
        vals = np.array([c[0] for c in contrastes])
        p20 = float(np.percentile(vals, 20))
        bajos = int((vals < 4.5).sum())
        st = "PASS" if p20 >= 4.5 else "WARN"  # tope WARN: sobre vídeo en movimiento la medición es aproximada
        peor_c = min(contrastes)
        out.append(M.metrica("M09", "Contraste WCAG texto/fondo", p20, st, ">= 4.5:1", "< 4.5:1 (3.0 para texto grande); tope WARN: medición aproximada",
                             f"p20 {p20:.1f}:1 · mín {vals.min():.1f}:1 ({peor_c[2]} a {peor_c[1]:.1f}s) · {bajos}/{len(vals)} muestras < 4.5 · fondo = percentil 75/25 del anillo alrededor del glifo (incluye sombra y cajas)",
                             "oficial", "alta", puntaje=M.lin(p20, 4.5, 3.0, 1.5), unidad=":1", duro=False, informativo=False))
    else:
        out.append(M.na("M09", "Contraste WCAG texto/fondo", "sin muestras de texto opaco", ">= 4.5:1", "3.0-4.5:1", "oficial"))

    # solape cara-texto
    if filas_cara:
        ojos_nariz = [f for f in filas_cara if f[1]["ojo_d"] or f[1]["ojo_i"] or f[1]["nariz"]]
        boca = [f for f in filas_cara if f[1]["boca_d"] or f[1]["boca_i"]]
        cub_max = max(f[2] for f in filas_cara)
        if ojos_nariz:
            st, det = "FAIL", f"texto sobre ojos/nariz en {len(ojos_nariz)}/{len(filas_cara)} muestras (t={', '.join(f'{f[0]:.1f}s' for f in ojos_nariz[:4])})"
        elif boca or cub_max > 0.2:
            st, det = "WARN", f"texto sobre la boca en {len(boca)} muestras · cubre hasta {cub_max * 100:.0f}% de la caja de cara"
        else:
            st, det = "PASS", f"{len(filas_cara)} muestras con cara y texto, sin solape (máx {cub_max * 100:.0f}% de la caja)"
        out.append(M.metrica("M16a", "Solape cara-texto", len(ojos_nariz), st, "0 muestras sobre ojos/nariz", "boca tapada o > 20 % de la caja", det, "estimado", "alta",
                             puntaje=M.lin(len(ojos_nariz) / len(filas_cara), 0, 0.05, 0.3) if ojos_nariz else (1.0 if st == "PASS" else 0.7), duro=True, informativo=False))
    else:
        out.append(M.na("M16a", "Solape cara-texto", "ninguna muestra con cara y texto a la vez (sin cara detectada o sin capas)"))
    if tamanos_cara:
        med = float(np.median(tamanos_cara))
        out.append(M.metrica("M16b", "Tamaño de la cara en cuadro", med * 100, M.estado_rango(med, 0.12, 0.45, 0.08, 0.60), "12-45 % del alto", "8-12 o 45-60 %",
                             f"mediana {med * 100:.0f}% del alto en {len(tamanos_cara)} muestras ({len(tamanos_cara)}/{len(sel)} con cara)", "estimado", "baja",
                             puntaje=M.puntaje_rango(med, 0.12, 0.45, 0.08, 0.60, 0.04, 0.8), unidad="% alto"))
    return out


def m_cara_capas(ctx):
    """M16c puerta dura capas/cara (revisor_capas: ningún gráfico sobre la cara en ningún instante; subtítulos >= 95 % de fotogramas limpios)
    y M16d encuadre (ojos en 30-38 % del alto, cabeza entera) medidos con YuNet sobre el base."""
    import re as _re
    from . import revisor_capas as RC
    from . import verificar_encuadre as VE
    out = []
    mv = _re.search(r"_v(\d+)$", ctx.pre)
    ruta = ctx.proj / "00_DOCS" / f"revision_capas_{ctx.fm}_v{mv.group(1)}.json" if mv else None
    inf = json.loads(ruta.read_text(encoding="utf-8")) if ruta and ruta.exists() else None
    fps = max(0.25, min(2.0, 600.0 / max(ctx.dur, 1.0)))
    caras = None
    if inf is None and (ctx.graf_ass or ctx.subs_ass):
        caras, _ = VE.caras_en(str(ctx.base), fps)
        g = RC.medir_ass(str(ctx.graf_ass), ctx.fm, caras, ctx.dur, fps) if ctx.graf_ass else None
        s_ = RC.medir_ass(str(ctx.subs_ass), ctx.fm, caras, ctx.dur, fps, RC.K_SUBS) if ctx.subs_ass else None
        fallos = (g["tramos"] if g else []) + ([] if (not s_ or s_["sin_solape_pct"] >= RC.CRITERIO_SUBS) else s_["tramos"])
        inf = {"fallos": fallos, "acciones": [], "despues": {"subtitulos": {"sin_solape_pct": s_["sin_solape_pct"] if s_ else None, "con_cara": s_["con_cara"] if s_ else 0},
                                                              "graficos": {"con_cara": g["con_cara"] if g else 0, "con_capa": g["con_capa"] if g else 0}}, "panel_completo": []}
    if inf is None:
        out.append(M.na("M16c", "Capas sobre la cara (puerta dura)", "sin gráficos ni subtítulos que medir"))
    else:
        fl = inf["fallos"]
        sp = inf["despues"]["subtitulos"].get("sin_solape_pct")
        det = (f"{len(inf.get('acciones', []))} capas corregidas por el revisor (reubicar/acortar/panel) · {len(inf.get('panel_completo', []))} a pantalla completa · "
               f"subtítulos sin solape {sp}% de los fotogramas con cara" if sp is not None else "sin subtítulos")
        if fl:
            det = "SOBRE LA CARA: " + "; ".join(f"{f['capa']} {f['t0']:.1f}-{f['t1']:.1f}s" for f in fl[:6]) + " · " + det
        out.append(M.metrica("M16c", "Capas sobre la cara (puerta dura)", len(fl), "FAIL" if fl else "PASS", "0 tramos de capa sobre la cara (margen incluido)", "cualquier tramo = FAIL (regla de David)",
                             det, "oficial", "alta", puntaje=0.0 if fl else 1.0, duro=True, informativo=False))
    r = VE.medir(str(ctx.base), None, ctx.fm, fps)
    n = r["con_cara"]
    if not n:
        out.append(M.na("M16d", "Encuadre: ojos 30-38 % y cabeza entera", "ninguna cara detectada"))
    else:
        o, cc = r["ojos_en_30_38_pct"], r["cabeza_cortada_pct"]
        st = "PASS" if (o >= 80 and cc <= 2) else ("WARN" if (o >= 50 and cc <= 10) else "FAIL")
        out.append(M.metrica("M16d", "Encuadre: ojos 30-38 % y cabeza entera", o, st, ">= 80 % de muestras con ojos en 30-38 % y cabeza cortada <= 2 %", ">= 50 % y <= 10 %",
                             f"ojos {r['ojos_min']:.2f}-{r['ojos_max']:.2f} (media {r['ojos_media']:.2f}) · en banda {o}% · cabeza cortada {cc}% · {n} muestras con cara",
                             "estimado", "media", puntaje=M.puntaje_rango(o / 100.0, 0.80, 1.0, 0.50, 1.0, 0.2, 1.0), unidad="% en banda", duro=False))
    return out


# =====================================================================================
# Entrega: parámetros ffprobe por plataforma, duración
# =====================================================================================
ENTREGA = {  # recomendaciones; youtube_largo = oficial (ayuda de YouTube); resto = terceros (ver metricas.json)
    "youtube_largo": {"audio_kbps": 384, "conf": "oficial"},
    "youtube_shorts": {"audio_kbps": 192, "conf": "oficial"},
    "instagram_reels": {"audio_kbps": 128, "conf": "terceros"},
    "tiktok": {"audio_kbps": 128, "conf": "terceros"},
    "linkedin": {"audio_kbps": 128, "conf": "terceros"},
}


def _atomos_mp4(path):
    out, pos = [], 0
    try:
        sz = Path(path).stat().st_size
        with open(path, "rb") as f:
            while pos < sz and len(out) < 40:
                f.seek(pos)
                h = f.read(8)
                if len(h) < 8:
                    break
                s, t = struct.unpack(">I4s", h)
                if s == 1:
                    s = struct.unpack(">Q", f.read(8))[0]
                out.append(t.decode("latin1"))
                pos += s if s else sz
    except OSError:
        pass
    return out


def _probe_json(path):
    p = run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], check=False)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {}


def m_entrega(ctx):
    arch = ctx.ref or ctx.base
    j = ctx.r("probe_ref") or {}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    out = []
    if not v:
        return [M.metrica("M21", "Parámetros de entrega", None, "FAIL", "", "", f"ffprobe no lee {arch.name}", "oficial", "alta", duro=True)]
    duros, blandos, ok = [], [], []
    fps = _fraccion(v.get("avg_frame_rate")) or _fraccion(v.get("r_frame_rate"))
    rfps = _fraccion(v.get("r_frame_rate"))
    (ok if v.get("codec_name") == "h264" else duros).append(f"códec {v.get('codec_name')}")
    perfil = v.get("profile", "")
    (ok if perfil.startswith("High") or perfil == "Main" else blandos).append(f"perfil {perfil}")
    (ok if v.get("pix_fmt") == "yuv420p" else duros).append(f"pix_fmt {v.get('pix_fmt')}")
    tags = (v.get("color_space"), v.get("color_primaries"), v.get("color_transfer"))
    (ok if all(t == "bt709" for t in tags) else blandos).append(f"color {'/'.join(str(t) for t in tags)}")
    if fps and rfps and abs(fps - rfps) / max(rfps, 1) < 0.005:
        ok.append(f"CFR {fps:.2f} fps")
    else:
        blandos.append(f"fps variable ({v.get('avg_frame_rate')} vs {v.get('r_frame_rate')})")
    if fps and not 24 <= fps <= 60.01:
        blandos.append(f"fps {fps:.1f} fuera de 24-60")
    # bitrate de vídeo vs recomendación escalada por píxeles (8 Mbps 1080p<=30 fps; 12 Mbps 48-60 fps)
    br = int(v.get("bit_rate") or 0) or int(j.get("format", {}).get("bit_rate") or 0)
    px = int(v.get("width", 0)) * int(v.get("height", 0))
    rec = 8e6 * px / (1920 * 1080) * (1.5 if fps and fps > 31 else 1.0)
    if br:
        if br >= rec:
            ok.append(f"bitrate {br / 1e6:.1f} Mbps (rec. {rec / 1e6:.1f})")
        else:
            # El encode ya es x264 crf 17 slow (regla de calidad): el bitrate lo manda el ORIGEN, no se puede inventar detalle. Si el origen es
            # más bajo que lo recomendado y el entregable conserva >= 60 % de su bitrate, se declara como límite del origen (no se finge arreglo).
            sbr = 0
            try:
                for rp in sorted((ctx.proj / "01_RAW").glob("*")):
                    if rp.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v", ".webm"):
                        sbr = int(probe(str(rp)).get("bitrate") or 0)
                        break
            except (OSError, ValueError, KeyError):
                sbr = 0
            if sbr and sbr < rec and br >= 0.6 * sbr:
                ok.append(f"bitrate {br / 1e6:.1f} Mbps = límite del ORIGEN ({sbr / 1e6:.1f} Mbps; rec. {rec / 1e6:.1f}): crf 17 slow ya lo conserva, no se arregla en post")
            else:
                blandos.append(f"bitrate {br / 1e6:.1f} Mbps (rec. {rec / 1e6:.1f})")
    abr = 0
    if a:
        (ok if a.get("codec_name") == "aac" else duros).append(f"audio {a.get('codec_name')}")
        (ok if a.get("sample_rate") == "48000" else blandos).append(f"audio {a.get('sample_rate')} Hz")
        (ok if int(a.get("channels", 0)) == 2 else blandos).append(f"{a.get('channels')} canales")
        abr = int(a.get("bit_rate") or 0)
    else:
        duros.append("sin pista de audio")
    atomos = _atomos_mp4(arch)
    if "moov" in atomos and "mdat" in atomos and atomos.index("moov") < atomos.index("mdat"):
        ok.append("moov al inicio")
    else:
        blandos.append("moov al final (sin faststart)")
    plat = {}
    for pl in ctx.plataformas or ["youtube_largo"]:
        req = ENTREGA[pl]
        falla = list(duros) + ([f"audio {abr // 1000} kbps < {req['audio_kbps']}"] if abr and abr < req["audio_kbps"] * 1000 * 0.9 else [])
        plat[pl] = "FAIL" if duros else ("WARN" if (blandos or falla) else "PASS")
    st = "FAIL" if duros else ("WARN" if blandos else "PASS")
    pun = 0.15 if duros else (max(0.5, 1.0 - 0.1 * len(blandos)) if blandos else 1.0)
    out.append(M.metrica("M21", "Parámetros de entrega (MP4 de referencia)", len(duros) + len(blandos), st,
                         "H.264 High yuv420p · BT.709 · CFR 24-60 · AAC 48 kHz estéreo · moov al inicio · bitrate >= recomendado", "bitrate/tags/faststart fuera de recomendación",
                         "; ".join(([f"FALLA: {', '.join(duros)}"] if duros else []) + ([f"AVISO: {', '.join(blandos)}"] if blandos else []) + [f"OK: {', '.join(ok[:6])}"])
                         + " · por plataforma: " + ", ".join(f"{k} {s}" for k, s in plat.items()) + " · GOP/B-frames no medidos", "oficial", "alta", puntaje=pun, duro=bool(duros),
                         informativo=(not duros)))
    for k, etiqueta in (("subs", "subtítulos"), ("graf", "gráficos")):
        pj = ctx.r("probe_" + k)
        if pj is None:
            continue
        jv = next((s for s in pj.get("streams", []) if s.get("codec_type") == "video"), {})
        okp = jv.get("codec_name") == "prores" and str(jv.get("pix_fmt", "")).startswith("yuva") and jv.get("profile") in ("4444", "4444 XQ")
        out.append(M.metrica("M21b" if k == "subs" else "M21c", f"ProRes 4444 con alfa ({etiqueta})", None, "PASS" if okp else "FAIL",
                             "prores 4444 + pix_fmt yuva*", "", f"{jv.get('codec_name')} {jv.get('profile')} {jv.get('pix_fmt')}", "oficial", "alta", duro=True))
    return out


def _fraccion(s):
    try:
        n, d = (str(s).split("/") + ["1"])[:2]
        return float(n) / float(d) if float(d) else None
    except (ValueError, ZeroDivisionError):
        return None


def m_duracion(ctx):
    d = ctx.dur
    por, mejor = {}, "FAIL"
    orden = {"PASS": 0, "WARN": 1, "FAIL": 2}
    for pl in ctx.plataformas:
        pf = M.PLATAFORMAS[pl]
        lo, hi = pf["optimo"]
        st = "PASS" if lo <= d <= hi else ("WARN" if d <= pf["max"] else "FAIL")
        por[pl] = st
        if orden[st] < orden[mejor]:
            mejor = st
    if not por:
        return [M.na("M20", "Duración vs rango de plataforma", "sin plataforma para este formato")]
    objetivo = min(por, key=lambda k: orden[por[k]])
    lo, hi = M.PLATAFORMAS[objetivo]["optimo"]
    dist = 0 if lo <= d <= hi else (lo - d if d < lo else d - hi)
    return [M.metrica("M20", "Duración vs rango de plataforma", d, mejor, "dentro del rango óptimo de >= 1 plataforma del formato", "dentro del máximo de alguna plataforma",
                      f"{d:.1f}s · " + ", ".join(f"{M.PLATAFORMAS[k]['nombre']} {por[k]} (óptimo {M.PLATAFORMAS[k]['optimo'][0]}-{M.PLATAFORMAS[k]['optimo'][1]}s)" for k in por),
                      "terceros", "baja", puntaje=M.lin(dist, 0, max(5, lo * 0.5), max(15, lo * 1.5)), unidad="s",
                      duro=(mejor == "FAIL" and any(M.PLATAFORMAS[k]["conf"] == "oficial" for k in por)))]


# =====================================================================================
# Envoltorio de los checks antiguos de qc.py como métricas
# =====================================================================================
MAPA_VIEJO = {
    "resolución": ("M30", "alta", "oficial"),
    "duración > 3 s": ("M31", "baja", "oficial"),
    "sincronía A/V": ("M24", "alta", "estimado"),
    "sonoridad": ("M12", "alta", "terceros"),
    "sin fotogramas negros": ("M22", "media", "estimado"),
    "cara visible": ("M16", "media", "estimado"),
    "subtítulos con alfa real": ("M23", "alta", "terceros"),
    "subtítulos en zona segura": ("M10a", "alta", "terceros"),
    "subtítulos": ("M23b", "baja", "estimado"),
}


def envolver_viejos(checks):
    out = []
    for c in checks:
        id_, pr, conf = MAPA_VIEJO.get(c["check"], ("MX", "media", "estimado"))
        m = M.desde_check(id_, c, confianza=conf, prioridad=pr, duro=True)
        m["valor"] = c.get("valor")
        out.append(m)
    return out


def evaluar_formato(ctx, checks_viejos):
    """Todas las métricas de un formato (viejas envueltas + ampliadas). Cada paso falla de forma aislada."""
    ms = envolver_viejos(checks_viejos)
    for f in (m_ritmo, m_capas, m_cara_capas, m_entrega, m_duracion):
        try:
            ms += f(ctx)
        except Exception as e:  # noqa: BLE001
            ms.append(M.metrica("ERR", f"fallo interno en {f.__name__}", None, "WARN", "", "", f"{type(e).__name__}: {e}", "estimado", "baja", informativo=True))
    ctx.cerrar()
    return ms


def evaluar_proyecto(ctx):
    """Métricas que dependen del audio/transcripción/SRT (iguales en todos los formatos): se calculan una vez con el primer formato."""
    ms = []
    for f in (m_voz, m_silencio, m_subtitulos):
        try:
            ms += f(ctx)
        except Exception as e:  # noqa: BLE001
            ms.append(M.metrica("ERR", f"fallo interno en {f.__name__}", None, "WARN", "", "", f"{type(e).__name__}: {e}", "estimado", "baja", informativo=True))
    return ms
