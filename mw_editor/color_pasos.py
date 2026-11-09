"""Color en 8 pasos EXPLÍCITOS con hoja de contactos antes/después (David, 2026-11-08: «falta corrección de color profesional y articulada»).

El motor (color.py) ya corre un etalonaje de 8 pasos con parámetros medidos por cámara; lo que faltaba era hacerlo VISIBLE y comprobable.
Este módulo reconstruye la cadena paso a paso (acumulativa, mismos parámetros que 00_DOCS/color.json), mide cada etapa en N fotogramas
repartidos y guarda:
  04_GRAPHICS/color_pasos_<id>.png        filas = fotogramas; columnas = ORIGINAL · 8 pasos · FINAL REAL del motor (rótulo con piel Y y % quemado)
  04_GRAPHICS/color_antes_despues_<id>.png  ORIGINAL | FINAL REAL, a mayor tamaño
  00_DOCS/color_pasos.json                parámetros, métrica por paso y verificación final (PASS/WARN con cifras)

Orden de pasos (el del motor; la piel va ANTES de las curvas para que éstas no amplifiquen la corrección):
  1 Exposición (superblancos + gamma) · 2 Balance de blancos · 3 Protección del tono de piel (giro a la línea de piel) · 4 Contraste (S suave)
  · 5 Luces y sombras (techo rodado, suelo cálido) · 6 Grade (tintes de marca) · 7 Saturación (+ vibrance) · 8 Verificación final (rango legal + medición)
Calidad: denoise ANTES de todo, nitidez suave (unsharp 0,45) al ÚLTIMO; el FINAL REAL de la hoja los incluye. Sin CodeFormer ni restauración de cara.
CLI: python -m mw_editor.color_pasos VIDEO --proyecto DIR [--n 3] [--look warm_black]
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import color as C
from .common import FFMPEG, log

PASOS = ["1 Exposición", "2 Balance de blancos", "3 Protección de piel", "4 Contraste", "5 Luces y sombras", "6 Grade (tintes)", "7 Saturación", "8 Verificación final"]


def etapas(prm, look, matriz="bt709", rango="tv", hdr=False, fuerza=1.0):
    """Lista de (nombre, filtros acumulados terminados en RGB 16 bit) para los pasos 1-7. El paso 8 es la salida legal + medición."""
    base = (C.cadena_hdr_a_sdr() if hdr else []) + C.filtros_entrada(True, matriz, rango)
    L = C.LOOKS.get(look) if look else None
    et = []
    f = base + C.f_exposicion(prm["gamma"])
    et.append((PASOS[0], list(f)))
    f = f + C.f_primaria(tuple(prm["wb"]), 0.0, 1.0)
    et.append((PASOS[1], list(f)))
    f = f + C.f_primaria((1.0, 1.0, 1.0), prm["rot_deg"], prm["sat_piel"])
    et.append((PASOS[2], list(f)))
    if L:
        k = float(fuerza)
        curva = [(x, x + (y - x) * k) for x, y in L["curva"]]
        medios = [(x, y) for x, y in curva if 0.25 <= x <= 0.75]
        mid = [(0.0, 0.0)] + medios + [(1.0, 1.0)]
        f4 = f + C.f_curva(mid)
        et.append((PASOS[3], list(f4)))
        suelo = tuple(c * k for c in L["suelo"])
        techo = tuple(1 + (c - 1) * k for c in L["techo"])
        f5 = f + C.f_curva(curva, suelo, techo)             # curva completa SUSTITUYE a la de medios
        et.append((PASOS[4], list(f5)))
        esc = lambda t: tuple(v * k for v in t)             # noqa: E731
        f6 = f5 + C.f_balance(esc(L["sombras"]), esc(L["medios"]), esc(L["luces"]))
        et.append((PASOS[5], list(f6)))
        f7 = f6 + C.f_saturacion(1 + (L["sat"] - 1) * k, L["vibrance"] * k)
        et.append((PASOS[6], list(f7)))
    else:
        for nom in PASOS[3:7]:
            et.append((nom, list(f)))
    return et


def _frames_con(ruta, tiempos, filtros, ffmpeg=FFMPEG):
    """Un solo proceso ffmpeg: un fotograma por tiempo con la cadena `filtros` (lista) y salida rgb24 8 bit (si la cadena acaba en yuv tv, se convierte con 709)."""
    import cv2
    cierre = ["scale=in_range=tv:out_range=full:in_color_matrix=bt709:flags=accurate_rnd+full_chroma_int", "format=rgb24"] if (filtros and "yuv420p" in ",".join(filtros[-6:])) else ["format=rgb24"]
    vf = ",".join(filtros + cierre) if filtros else ",".join(cierre)
    out = []
    with tempfile.TemporaryDirectory(prefix="mw_cp_") as td:
        cmd = [ffmpeg, "-v", "error", "-y"]
        for t in tiempos:
            cmd += ["-ss", f"{t:.3f}", "-i", str(ruta)]
        for k in range(len(tiempos)):
            cmd += ["-map", f"{k}:v:0", "-frames:v", "1", "-vf", vf, str(Path(td) / f"f{k:02d}.png")]
        r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
        for k in range(len(tiempos)):
            im = cv2.imread(str(Path(td) / f"f{k:02d}.png"), cv2.IMREAD_COLOR)
            if im is None:
                raise RuntimeError(f"ffmpeg no produjo el fotograma {k}: {r.stderr.decode(errors='replace')[:300]}")
            out.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    return out


def _medir(rgb, caja=None):
    """Piel (Y tv, ángulo, croma) en la caja de cara dada + % de luces quemadas (Y>=235) y sombras aplastadas (Y<=17) + luma media."""
    small = rgb[::3, ::3].astype(np.float64) / 255.0
    yy = C.ycc_tv(small)[0]
    p = C.medir_piel(rgb, caja)
    return {"piel_y": round(p["y"], 1) if p else None, "piel_ang": round(p["angulo"], 1) if p else None, "piel_croma": round(p["croma"], 1) if p else None,
            "quemado_pct": round(float((yy >= 235).mean() * 100), 2), "aplastado_pct": round(float((yy <= 17).mean() * 100), 2), "luma_media": round(float(yy.mean()), 1)}


def _tiempos(dur, n):
    return [round(0.08 * dur + 0.84 * dur * (k + 0.5) / n, 2) for k in range(n)]


def generar(video, proyecto, n=3, look=None, ident=None, ancho_tile=300):
    """Genera hoja + JSON para `video` (el ORIGEN, no el base). Devuelve dict con rutas y veredicto."""
    from PIL import Image, ImageDraw
    video, proyecto = Path(video), Path(proyecto)
    docs, graf = proyecto / "00_DOCS", proyecto / "04_GRAPHICS"
    docs.mkdir(parents=True, exist_ok=True)
    graf.mkdir(parents=True, exist_ok=True)
    ident = ident or video.stem[:24]
    res = C.plan_color(video, docs=docs, look=look)
    prm, lk, s = res["params"], res["look"], res["sonda"]
    et = etapas(prm, lk, s["matriz"], s["rango"], s["hdr"])
    t = _tiempos(s["duracion"], n)
    prev = C.cadena_hdr_a_sdr() if s["hdr"] else []
    orig = _frames_con(video, t, prev + [f"scale=in_range={'pc' if s['rango'] == 'pc' else 'tv'}:in_color_matrix={s['matriz']}:out_range=full:flags=accurate_rnd+full_chroma_int"])
    cajas = [C.detectar_cara(f) for f in orig]
    tiles = {"Original": orig}
    medidas = {"Original": [_medir(f, c) for f, c in zip(orig, cajas)]}
    for nombre, filtros in et:
        fr = _frames_con(video, t, filtros)
        tiles[nombre] = fr
        medidas[nombre] = [_medir(f, c) for f, c in zip(fr, cajas)]
    # paso 8: el FINAL REAL del motor (denoise + 8 pasos + nitidez suave), tal cual lo renderiza render.py
    from . import imagen as im
    cad, dec = im.cadena({}, {"bitrate": 8_000_000, "duracion": s["duracion"]}, look=lk, ruta=str(video), proyecto=str(proyecto))
    fin = _frames_con(video, t, cad)
    tiles[PASOS[7]] = fin
    medidas[PASOS[7]] = [_medir(f, c) for f, c in zip(fin, cajas)]
    # --- verificación final (criterios de color.evaluar + highlights/sombras)
    mf = medidas[PASOS[7]]
    pieles = [m for m in mf if m["piel_y"] is not None]
    y_obj = prm.get("objetivo_y") or C.Y_PIEL_OBJETIVO
    ver = []
    if pieles:
        py, pa = float(np.median([m["piel_y"] for m in pieles])), float(np.median([m["piel_ang"] for m in pieles]))
        pc = float(np.median([m["piel_croma"] for m in pieles]))
        ver += [("piel Y (tv)", round(py, 1), f"objetivo {y_obj:.0f} ± 15", abs(py - y_obj) <= 15),
                ("ángulo de piel (°)", round(pa, 1), f"{C.PIEL_LINEA_DEG:.0f} ± {C.PIEL_TOL_DEG:.0f}", abs(pa - C.PIEL_LINEA_DEG) <= C.PIEL_TOL_DEG),
                ("croma de piel", round(pc, 1), "14-40", 14 <= pc <= 40)]
    q = max(m["quemado_pct"] for m in mf)
    a_ = max(m["aplastado_pct"] for m in mf)
    q0 = max(m["quemado_pct"] for m in medidas["Original"])
    ver += [("luces quemadas % (Y>=235)", q, f"<= 1.0 (original {q0})", q <= 1.0),
            ("sombras aplastadas % (Y<=17)", a_, "<= 5.0", a_ <= 5.0)]
    estado = "PASS" if all(v[3] for v in ver) else "WARN"
    # --- hojas
    def rotulo(nombre, m):
        sy = m["piel_y"] if m["piel_y"] is not None else "--"
        return f"{nombre} | piel Y {sy} | quem {m['quemado_pct']}%"
    cols = ["Original"] + PASOS
    h_t = int(round(ancho_tile * orig[0].shape[0] / orig[0].shape[1]))
    lab_h = 18
    hoja = Image.new("RGB", (len(cols) * ancho_tile, n * (h_t + lab_h)), (20, 20, 20))
    d = ImageDraw.Draw(hoja)
    for r in range(n):
        for c, nom in enumerate(cols):
            im_ = Image.fromarray(tiles[nom][r]).resize((ancho_tile, h_t), Image.LANCZOS)
            hoja.paste(im_, (c * ancho_tile, r * (h_t + lab_h) + lab_h))
            d.text((c * ancho_tile + 3, r * (h_t + lab_h) + 3), rotulo(nom, medidas[nom][r])[:46], fill=(235, 235, 235))
    p_hoja = graf / f"color_pasos_{ident}.png"
    hoja.save(p_hoja)
    aw = 640
    ah = int(round(aw * orig[0].shape[0] / orig[0].shape[1]))
    ad = Image.new("RGB", (2 * aw, n * (ah + lab_h)), (20, 20, 20))
    dd = ImageDraw.Draw(ad)
    for r in range(n):
        for c, (nom, lab) in enumerate((("Original", "ANTES"), (PASOS[7], "DESPUES (final real: denoise + 8 pasos + nitidez suave)"))):
            ad.paste(Image.fromarray(tiles[nom][r]).resize((aw, ah), Image.LANCZOS), (c * aw, r * (ah + lab_h) + lab_h))
            dd.text((c * aw + 4, r * (ah + lab_h) + 3), f"{lab} · t={t[r]}s · piel Y {medidas[nom][r]['piel_y']}", fill=(235, 235, 235))
    p_ad = graf / f"color_antes_despues_{ident}.png"
    ad.save(p_ad)
    out = {"video": str(video), "look": lk, "fuerza_look": 1.0, "tiempos_s": t, "orden_calidad": ["denoise hqdn3d", *PASOS, "unsharp 0.45 (suave, al final)"],
           "parametros": {k: prm[k] for k in ("gamma", "wb", "rot_deg", "sat_piel", "objetivo_y", "tipo_piel") if k in prm},
           "filtros_finales": cad, "decisiones": dec, "medidas": medidas,
           "verificacion_final": [{"criterio": a, "valor": b, "umbral": c, "ok": bool(o)} for a, b, c, o in ver], "estado": estado,
           "hoja_pasos": str(p_hoja), "hoja_antes_despues": str(p_ad),
           "limites": "Altas luces quemadas y bitrate de origen bajo no se arreglan en post; si 'luces quemadas' del original es alto, solo se contiene."}
    (docs / "color_pasos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"color_pasos: {estado} · {p_hoja} · {p_ad}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mw_editor.color_pasos")
    ap.add_argument("video")
    ap.add_argument("--proyecto", required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--look", default=None)
    a = ap.parse_args(argv)
    r = generar(a.video, a.proyecto, a.n, a.look)
    print(json.dumps({"estado": r["estado"], "verificacion_final": r["verificacion_final"], "hoja_pasos": r["hoja_pasos"], "hoja_antes_despues": r["hoja_antes_despues"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
