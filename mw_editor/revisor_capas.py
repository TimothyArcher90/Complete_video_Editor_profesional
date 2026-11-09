"""Revisor de capas (regla DURA de David, 2026-11-06 / 2026-11-08): NINGUNA tarjeta, cifra, título, infografía ni subtítulo sobre la cara.

Qué hace, por formato, DESPUÉS de renderizar el MP4 base y ANTES de componer ProRes/REFERENCIA:
  1. Mide con YuNet la cara en el base (muestreo `fps`) y la dilata con margen (pelo arriba, lados, barbilla).
  2. Renderiza cada capa (ASS de gráficos, ASS de subtítulos; clips sueltos como rectángulo) a una máscara y mide, en CADA instante muestreado,
     qué fracción de la caja de la cara (con margen) queda cubierta. Geometría-agnóstico: mide píxeles reales, no cajas supuestas.
  3. Si una tarjeta/título/cifra/CTA/lower third choca, la corrige sola con esta escalera (en este orden):
        a) reubicar a una zona libre de cara (y, lado, escala) comprobando la candidata renderizada, dentro de la zona segura y sobre los subtítulos;
        b) acortar a la parte del tiempo en que no choca (si queda >= 1,5 s);
        c) pasar a PANEL a pantalla completa OPACO (Warm Black): el presentador se oculta ese rato, la cara deja de ser un problema.
     Un clip suelto (mapa/gráfica) que tapa la cara se convierte en panel (`paneles`), igual que el estilo cápsula del repo.
  4. Puerta DURA: tras corregir, se vuelve a medir. Si queda solape > TOL en alguna capa de gráficos, `puerta()` lanza ColisionCara con los
     instantes culpables (la renderización se detiene). Subtítulos: criterio del repo (>= 95 % de los fotogramas con cara sin solape).
     MW_SIN_GATE_CARA=1 solo registra y deja pasar (diagnóstico; no usar para entregar).
  5. Escribe 00_DOCS/revision_capas_<formato>_vN.json y una hoja de contactos (04_GRAPHICS/revision_capas_<formato>_vN.png) con la cara
     (verde), la zona de margen y las capas ya quemadas, para MIRAR los fotogramas.

CLI: python -m mw_editor.revisor_capas BASE.mp4 --plan plan.json --formato horizontal [--ass-graficos g.ass] [--ass-subs s.ass]
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .common import FFMPEG, FONTS_DIR, dims, ffq, log, probe
from .zonas import caja_segura_px, es_vertical

# margen de la caja de la cara (fracción del alto/ancho de la caja de YuNet). YuNet encuadra frente-barbilla: el pelo está ARRIBA.
M_ARRIBA, M_LADO, M_ABAJO = 0.30, 0.15, 0.10
M_PX = 0.010                 # + 1 % del alto del lienzo en todos los lados (absorbe el ruido de YuNet)
TOL = 0.002                  # fracción de la caja (con margen) cubierta por píxeles de capa; por encima = solape
UMBRAL_PX = 24               # gris (0-255) de la máscara a partir del cual un píxel cuenta como capa
K_SUBS = 0.25                # margen de la cara para subtítulos (casi la cara a secas: el subtítulo vive pegado a la barbilla por diseño)
CRITERIO_SUBS = 95.0         # % mínimo de fotogramas con cara sin solape de subtítulos (el mismo criterio de verificar_encuadre)
ESCALAS = (1.0, 0.85, 0.7, 0.6)
TIPOS = ("lower_thirds", "titulos", "cifras", "titulos_grandes", "cta")


class ColisionCara(RuntimeError):
    """La puerta dura: una capa sigue tapando la cara tras intentar corregirla."""

    def __init__(self, fallos, informe=None):
        self.fallos, self.informe = fallos, informe
        det = "; ".join(f"{f['capa']} t={f['t0']:.1f}-{f['t1']:.1f}s cubre {f['max'] * 100:.1f}% de la cara" for f in fallos[:8])
        super().__init__(f"CAPA SOBRE LA CARA ({len(fallos)} tramos): {det}")


# ------------------------------------------------------------------------------------------------ geometría
def _dim_mascara(W, H):
    wm = 480 if W >= H else 288
    return wm, int(round(H * wm / W / 2) * 2)


def caja_con_margen(c, W, H, k=1.0):
    """c = (x0,y0,x1,y1) normalizado 0-1 -> caja en px del lienzo, dilatada. k escala el margen (1 = gráficos; subtítulos usan K_SUBS)."""
    x0, y0, x1, y1 = c[0] * W, c[1] * H, c[2] * W, c[3] * H
    w, h = x1 - x0, y1 - y0
    m = M_PX * H * k
    return (max(0.0, x0 - M_LADO * w * k - m), max(0.0, y0 - M_ARRIBA * h * k - m), min(float(W), x1 + M_LADO * w * k + m), min(float(H), y1 + M_ABAJO * h * k + m))


def _union(cajas):
    return (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))


def _a_mascara(caja, W, H, wm, hm):
    x0, y0, x1, y1 = caja
    return (max(0, int(np.floor(x0 * wm / W))), max(0, int(np.floor(y0 * hm / H))), min(wm, int(np.ceil(x1 * wm / W))), min(hm, int(np.ceil(y1 * hm / H))))


def _cubre(mask, caja_px, W, H):
    """Fracción de la caja cubierta por píxeles de capa."""
    hm, wm = mask.shape
    a = _a_mascara(caja_px, W, H, wm, hm)
    if a[2] <= a[0] or a[3] <= a[1]:
        return 0.0
    sub = mask[a[1]:a[3], a[0]:a[2]]
    return float(sub.sum()) / float(sub.size)


def caras_cercanas(caras, t, ventana=0.8):
    """Muestras de cara (t,x0,y0,x1,y1,ojos) a <= ventana s de t; si no hay, [] (sin cara: no se puede medir)."""
    return [c for c in caras if abs(c[0] - t) <= ventana]


# ------------------------------------------------------------------------------------------------ render de máscaras
def _matte(ass, destino):
    from .componer import _ass_matte
    return _ass_matte(ass, destino)


def _flujo_mascaras(ass, W, H, fps, dur):
    """Generador (i, máscara bool [hm,wm]) de la capa ASS renderizada en blanco sobre negro, a `fps`."""
    wm, hm = _dim_mascara(W, H)
    tmp = Path(tempfile.mkdtemp(prefix="mw_rc_"))
    matte = _matte(ass, str(tmp / "m.ass"))
    fd = ffq(FONTS_DIR)
    vf = f"ass=filename='{ffq(matte)}':fontsdir='{fd}',scale={wm}:{hm}:flags=area,format=gray"
    p = subprocess.Popen([FFMPEG, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}:d={dur:.3f}",
                          "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    n, i = wm * hm, 0
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield i, np.frombuffer(buf, np.uint8).reshape(hm, wm) > UMBRAL_PX
            i += 1
    finally:
        p.stdout.close()
        p.wait()
        try:
            Path(matte).unlink(missing_ok=True)
            tmp.rmdir()
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------ medición
def _tramos(filas, fps):
    """Une muestras consecutivas con solape en tramos {t0,t1,max}. filas = [(t, cub)]."""
    out, cur = [], None
    for t, cub in filas:
        if cub > TOL:
            if cur and t - cur["t1"] <= 2.1 / fps:
                cur["t1"], cur["max"] = t, max(cur["max"], cub)
            else:
                cur = {"t0": t, "t1": t, "max": cub}
                out.append(cur)
    for c in out:
        c["t1"] = round(c["t1"] + 0.5 / fps, 2)
        c["t0"], c["max"] = round(c["t0"], 2), round(c["max"], 4)
    return out


def medir_ass(ass, formato, caras, dur, fps=4.0, k_margen=1.0):
    """Mide el solape capa(ASS)-cara en cada instante. Devuelve {filas:[(t,cub)], tramos, con_cara, con_capa, sin_solape_pct}."""
    W, H = dims(formato)
    filas, con_capa = [], 0
    for i, m in _flujo_mascaras(ass, W, H, fps, dur):
        if not m.any():
            continue
        con_capa += 1
        t = i / fps
        cs = caras_cercanas(caras, t)
        if not cs:
            continue
        caja = _union([caja_con_margen(c[1:5], W, H, k_margen) for c in cs if abs(c[0] - t) <= 0.5 / fps + 0.26] or [caja_con_margen(c[1:5], W, H, k_margen) for c in cs])
        filas.append((t, _cubre(m, caja, W, H)))
    n = len(filas)
    malas = sum(1 for _, c in filas if c > TOL)
    return {"filas": filas, "tramos": _tramos(filas, fps), "con_cara": n, "con_capa": con_capa,
            "sin_solape_pct": round(100.0 * (n - malas) / n, 1) if n else 100.0}


def _rect_clip(c, formato):
    from .componer import _caja
    x, y, w, h = _caja(c.get("caja", "panel"), formato)
    return (x, y, x + w, y + h)


def medir_clips(plan, formato, caras, fps=4.0):
    """Clips sueltos (no dentro de una ventana de panel): rectángulo de su caja contra la cara. Devuelve lista de {idx,t0,t1,max}."""
    W, H = dims(formato)
    paneles = [(p["t"], p["t"] + p.get("dur", 3.0)) for p in plan.get("paneles", [])]
    res = []
    for k, c in enumerate(plan.get("clips", [])):
        t0, t1 = c["t"], c["t"] + c["dur"]
        if any(a - 0.05 <= t0 and t1 <= b + 0.05 for a, b in paneles):
            continue
        r = _rect_clip(c, formato)
        peor = 0.0
        for t in np.arange(t0, t1, 1.0 / fps):
            for cs in [caras_cercanas(caras, t, 0.6)]:
                if not cs:
                    continue
                cj = _union([caja_con_margen(x[1:5], W, H) for x in cs])
                iw = max(0.0, min(r[2], cj[2]) - max(r[0], cj[0]))
                ih = max(0.0, min(r[3], cj[3]) - max(r[1], cj[1]))
                peor = max(peor, iw * ih / max(1.0, (cj[2] - cj[0]) * (cj[3] - cj[1])))
        if peor > TOL:
            res.append({"idx": k, "t0": t0, "t1": t1, "max": round(peor, 4)})
    return res


# ------------------------------------------------------------------------------------------------ reubicación
def _ventana(item):
    return item["t"], item["t"] + item.get("dur", 3.0)


def _union_cara_ventana(caras, t0, t1, W, H, pad=0.4):
    cs = [c for c in caras if t0 - pad <= c[0] <= t1 + pad]
    return _union([caja_con_margen(c[1:5], W, H) for c in cs]) if cs else None


def _soporta_lado(tipo):
    return tipo in ("lower_thirds", "titulos", "cifras")


def _clave_y(tipo):
    return "y" if tipo in ("titulos_grandes", "cta") else "y_frac"


def _candidatos(tipo, item, formato, escala):
    """Lista de dict de parámetros (lado, y) para una escala. Orden de preferencia: arriba -> abajo; centro primero."""
    ys = [round(v, 3) for v in np.arange(0.03, 0.90, 0.03)]
    lados = ["centro", "izq", "der"] if _soporta_lado(tipo) else [None]
    out = []
    for lado in lados:
        for y in ys:
            p = {_clave_y(tipo): y, "escala": escala}
            if lado:
                p["lado"] = lado
            out.append(p)
    return out


def _evaluar_candidatas(tipo, item, cands, formato, cara_u, sub_top_px):
    """Renderiza TODAS las candidatas en una sola pasada (cada una en su ranura de 1 s) y devuelve la lista de máscaras-bbox válidas."""
    from . import subs as su
    W, H = dims(formato)
    items = []
    for k, p in enumerate(cands):
        it = {kk: v for kk, v in item.items() if kk not in ("modo", "y_frac", "y", "lado", "escala")}
        it.update(p)
        it["t"], it["dur"] = float(k), 1.0
        items.append(it)
    tmp = Path(tempfile.mkdtemp(prefix="mw_rcc_"))
    ass = tmp / "c.ass"
    su.ass_graficos({tipo: items}, formato, str(ass))
    fps_c = 2.0
    wm, hm = _dim_mascara(W, H)
    seg = caja_segura_px(formato)
    tol_seg = 0.012 * H
    validas = []
    quiere = {2 * k + 1: k for k in range(len(cands))}          # t = k + 0.5 s: la entrada (0,22 s) ya terminó
    for i, m in _flujo_mascaras(str(ass), W, H, fps_c, float(len(cands))):
        k = quiere.get(i)
        if k is None or not m.any():
            continue
        ys, xs = np.where(m)
        bx0, bx1 = xs.min() * W / wm, (xs.max() + 1) * W / wm
        by0, by1 = ys.min() * H / hm, (ys.max() + 1) * H / hm
        dentro = bx0 >= seg[0] - tol_seg and bx1 <= seg[2] + tol_seg and by0 >= seg[1] - tol_seg and by1 <= seg[3] + tol_seg
        if not dentro or (sub_top_px is not None and by1 > sub_top_px):
            continue
        if _cubre(m, cara_u, W, H) <= TOL:
            validas.append((k, (bx0, by0, bx1, by1)))
    try:
        ass.unlink(missing_ok=True)
        tmp.rmdir()
    except OSError:
        pass
    return validas


def _sub_top_px(formato):
    from .planos import tope_subtitulos
    W, H = dims(formato)
    return tope_subtitulos(formato, W, H) * H - 0.01 * H


def reubicar(tipo, item, formato, caras):
    """Intenta sacar `item` de la cara. Devuelve (accion, detalle). Modifica `item` in situ. accion in {reubicado, acortado, pantalla, sin_cara}."""
    W, H = dims(formato)
    t0, t1 = _ventana(item)
    cara_u = _union_cara_ventana(caras, t0, t1, W, H)
    if cara_u is None:
        return "sin_cara", "sin cara detectada en la ventana"
    sub_top = _sub_top_px(formato) if es_vertical(formato) else None
    # a) reubicar (escala de mayor a menor; dentro de cada escala, la primera candidata libre en el orden de preferencia)
    for esc in ESCALAS:
        cands = _candidatos(tipo, item, formato, esc)
        ok = _evaluar_candidatas(tipo, item, cands, formato, cara_u, sub_top)
        if ok:
            k = min(v[0] for v in ok)
            p = cands[k]
            item.update(p)
            return "reubicado", {kk: v for kk, v in p.items()}
    return None, None


def _acortar(item, filas_item, fps):
    """Mayor tramo continuo SIN solape de la ventana del item (con la geometría actual). None si < 1,5 s."""
    t0, t1 = _ventana(item)
    buenos = [t for t, c in filas_item if t0 <= t <= t1 and c <= TOL]
    if not buenos:
        return None
    best, cur = None, [buenos[0], buenos[0]]
    for t in buenos[1:]:
        if t - cur[1] <= 1.6 / fps:
            cur[1] = t
        else:
            best = cur if (best is None or cur[1] - cur[0] > best[1] - best[0]) else best
            cur = [t, t]
    best = cur if (best is None or cur[1] - cur[0] > best[1] - best[0]) else best
    dur = best[1] - best[0] + 1.0 / fps
    return (round(best[0], 2), round(dur, 2)) if dur >= 1.5 else None


# ------------------------------------------------------------------------------------------------ orquestación
def _items_activos(plan, a, b):
    out = []
    for tipo in TIPOS:
        for it in plan.get(tipo, []):
            t0, t1 = _ventana(it)
            if t0 < b and a < t1 and it.get("modo") != "pantalla":
                out.append((tipo, it))
    return out


def revisar_y_corregir(base, plan, formato, ass_graficos_ruta, ass_subs_ruta, docs=None, graficos_dir=None, etiqueta="", fps=None, reparar=True):
    """Mide, corrige el `plan` (se modifica y se devuelve) y re-mide. Reescribe `ass_graficos_ruta` si cambió el plan.
    Devuelve (plan, informe). `informe['fallos']` = tramos de gráficos que siguen sobre la cara (puerta dura)."""
    from . import subs as su
    from . import verificar_encuadre as VE
    base = str(base)
    info = probe(base)
    dur = info["duracion"]
    fps = fps or (4.0 if dur <= 300 else 2.0)
    W, H = dims(formato)
    caras, total = VE.caras_en(base, fps)
    informe = {"base": base, "formato": formato, "fps_muestreo": fps, "muestras_con_cara": len(caras), "muestras": total,
               "tol": TOL, "margen": {"arriba": M_ARRIBA, "lado": M_LADO, "abajo": M_ABAJO, "px_rel": M_PX}, "acciones": [], "antes": {}, "despues": {}}
    tiene_graf = any(plan.get(k) for k in TIPOS)
    if tiene_graf:
        su.ass_graficos(plan, formato, ass_graficos_ruta)
    # ---- medición de gráficos (los paneles a pantalla completa se excluyen: ocultan al presentador A PROPÓSITO)
    ass_med = str(Path(ass_graficos_ruta).with_suffix(".medicion.ass"))

    def medir_graf():
        pm = {k: [it for it in plan.get(k, []) if it.get("modo") != "pantalla"] for k in TIPOS}
        if not any(pm.values()):
            return {"filas": [], "tramos": [], "con_cara": 0, "con_capa": 0, "sin_solape_pct": 100.0}
        su.ass_graficos(pm, formato, ass_med)
        r = medir_ass(ass_med, formato, caras, dur, fps)
        Path(ass_med).unlink(missing_ok=True)
        return r
    mg = medir_graf()
    informe["antes"]["graficos"] = {k: v for k, v in mg.items() if k != "filas"}
    clips_mal = medir_clips(plan, formato, caras, fps)
    informe["antes"]["clips"] = clips_mal
    mg2 = mg
    for ronda in (1, 2):
        if not (reparar and (mg2["tramos"] or (ronda == 1 and clips_mal))):
            break
        # ---- corrección por ítem (ronda 2: lo que siga chocando tras reubicar pasa directo a panel a pantalla completa)
        for tr in mg2["tramos"]:
            for tipo, it in _items_activos(plan, tr["t0"] - 0.01, tr["t1"] + 0.01):
                if it.get("_revisado") and ronda == 1:
                    continue
                t0, t1 = _ventana(it)
                antes = {k: it.get(k) for k in ("y", "y_frac", "lado", "escala", "t", "dur")}
                accion, det = (None, None) if ronda == 2 else reubicar(tipo, it, formato, caras)
                if accion is None:
                    # b) acortar
                    sol = [(t, c) for t, c in mg2["filas"] if t0 <= t <= t1]
                    acorta = _acortar(it, sol, fps) if (ronda == 1 and len(_items_activos(plan, t0, t1)) == 1) else None
                    if acorta:
                        it["t"], it["dur"] = acorta
                        accion, det = "acortado", {"t": acorta[0], "dur": acorta[1]}
                    else:
                        it["modo"] = "pantalla"       # c) panel a pantalla completa opaco
                        accion, det = "pantalla", "no hay zona libre de cara con ese tamaño: panel opaco a pantalla completa"
                it["_revisado"] = True
                informe["acciones"].append({"capa": tipo, "t": t0, "antes": antes, "accion": accion, "detalle": det})
                log(f"revisor_capas: {tipo} t={t0:.1f}s -> {accion} {det if not isinstance(det, dict) else json.dumps(det, ensure_ascii=False)}")
        for ck in (clips_mal if ronda == 1 else []):
            c = plan["clips"][ck["idx"]]
            plan.setdefault("paneles", []).append({"t": c["t"], "dur": c["dur"], "clip": c["archivo"], "caja": c.get("caja", "panel")})
            c["_a_panel"] = True
            informe["acciones"].append({"capa": "clip", "t": c["t"], "accion": "panel", "detalle": "el clip tapaba la cara: pasa a panel en cápsula/pantalla"})
        plan["clips"] = [c for c in plan.get("clips", []) if not c.get("_a_panel")]
        if tiene_graf:
            su.ass_graficos(plan, formato, ass_graficos_ruta)
        mg2 = medir_graf()
    # (re)medición final ya hecha en la última ronda
    informe["despues"]["graficos"] = {k: v for k, v in mg2.items() if k != "filas"}
    informe["despues"]["clips"] = medir_clips(plan, formato, caras, fps)
    ms = {"tramos": [], "sin_solape_pct": 100.0, "con_cara": 0}
    if ass_subs_ruta and Path(ass_subs_ruta).exists():
        ms = medir_ass(ass_subs_ruta, formato, caras, dur, fps, K_SUBS)
    informe["despues"]["subtitulos"] = {k: v for k, v in ms.items() if k != "filas"}
    fallos = [{"capa": "gráficos", **t} for t in mg2["tramos"]] + [{"capa": f"clip {c['idx']}", "t0": c["t0"], "t1": c["t1"], "max": c["max"]} for c in informe["despues"]["clips"]]
    if ms["sin_solape_pct"] < CRITERIO_SUBS:
        fallos += [{"capa": "subtítulos", **t} for t in ms["tramos"]]
    informe["fallos"] = fallos
    informe["estado"] = "PASS" if not fallos else "FAIL"
    informe["panel_completo"] = [{"capa": t, "t": it["t"], "dur": it.get("dur")} for t in TIPOS for it in plan.get(t, []) if it.get("modo") == "pantalla"]
    if docs:
        Path(docs).mkdir(parents=True, exist_ok=True)
        (Path(docs) / f"revision_capas_{formato}{etiqueta}.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return plan, informe


def puerta(informe):
    """Puerta dura. Lanza ColisionCara si quedan capas sobre la cara (salvo MW_SIN_GATE_CARA=1)."""
    if informe["fallos"]:
        if os.environ.get("MW_SIN_GATE_CARA") == "1":
            log("AVISO (MW_SIN_GATE_CARA=1): capas sobre la cara NO bloquean el render:", ColisionCara(informe["fallos"]))
            return
        raise ColisionCara(informe["fallos"], informe)


# ------------------------------------------------------------------------------------------------ hoja visual
def hoja_visual(base, formato, ass_graficos, ass_subs, caras, instantes, salida, ancho=420):
    """Hoja de contactos con las capas YA quemadas, la cara (verde) y su caja con margen (amarillo). Para MIRAR fotogramas."""
    from PIL import Image, ImageDraw
    W, H = dims(formato)
    tiles = []
    for t in instantes:
        cadena = []
        for a in (ass_graficos, ass_subs):
            if a and Path(a).exists():
                cadena.append(f"ass=filename='{ffq(a)}':fontsdir='{ffq(FONTS_DIR)}'")
        vf = ",".join(cadena + [f"scale={ancho}:-2"])
        r = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-copyts", "-ss", f"{max(0.0, t - 0.05):.2f}", "-i", str(base), "-vf", vf,
                            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL)
        if not r.stdout:
            continue
        import io
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        s = im.width / W
        d = ImageDraw.Draw(im)
        cs = caras_cercanas(caras, t, 0.3)
        if cs:
            c = min(cs, key=lambda x: abs(x[0] - t))
            d.rectangle([c[1] * im.width, c[2] * im.height, c[3] * im.width, c[4] * im.height], outline=(60, 220, 90), width=2)
            cm = caja_con_margen(c[1:5], W, H)
            d.rectangle([cm[0] * s, cm[1] * s, cm[2] * s, cm[3] * s], outline=(255, 210, 0), width=1)
        d.text((6, 6), f"t={t:.1f}s", fill=(255, 255, 255))
        tiles.append(im)
    if not tiles:
        return None
    cols = min(len(tiles), 4 if W >= H else 5)
    filas = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    hoja = Image.new("RGB", (cols * tw, filas * th), (20, 20, 20))
    for i, im in enumerate(tiles):
        hoja.paste(im, ((i % cols) * tw, (i // cols) * th))
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    hoja.save(salida)
    return str(salida)


def instantes_de_plan(plan, dur):
    ts = []
    for tipo in TIPOS:
        for it in plan.get(tipo, []):
            t0, t1 = _ventana(it)
            ts.append(min(dur - 0.2, t0 + min(1.2, (t1 - t0) * 0.6)))
    return sorted(set(round(t, 1) for t in ts))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mw_editor.revisor_capas")
    ap.add_argument("base")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--formato", default="horizontal", choices=["vertical", "cuadrado", "4x5", "horizontal"])
    ap.add_argument("--ass-subs")
    ap.add_argument("--out", help="carpeta de salida (informe JSON, plan corregido, hoja). Por defecto, junto al base")
    ap.add_argument("--solo-medir", action="store_true", help="no corrige; solo mide (para ver el ANTES)")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else Path(a.base).parent
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8-sig"))
    g = out / f"revisor_{a.formato}_graficos.ass"
    plan2, inf = revisar_y_corregir(a.base, plan, a.formato, str(g), a.ass_subs, docs=out, etiqueta="_cli", reparar=not a.solo_medir)
    (out / f"plan_corregido_{a.formato}.json").write_text(json.dumps(plan2, ensure_ascii=False, indent=1), encoding="utf-8")
    from . import verificar_encuadre as VE
    caras, _ = VE.caras_en(a.base, 4.0)
    dur = probe(a.base)["duracion"]
    hoja_visual(a.base, a.formato, str(g), a.ass_subs, caras, instantes_de_plan(plan2, dur), out / f"hoja_capas_{a.formato}.png")
    print(json.dumps({"estado": inf["estado"], "fallos": inf["fallos"], "acciones": inf["acciones"]}, ensure_ascii=False, indent=1))
    raise SystemExit(0 if inf["estado"] == "PASS" else 1)


if __name__ == "__main__":
    main()
