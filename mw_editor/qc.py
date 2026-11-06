"""Control de calidad automático de un output. No juzga el gusto: comprueba lo medible.
Estados: PASS / WARN / FAIL. Un FAIL significa que el entregable no sirve tal cual."""
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .common import BRAND, FFMPEG, FFPROBE, ROOT, dims, probe, run
from .zonas import seg as zona_seg, preset as zona_preset


def _frame_rgba(path, t):
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-pix_fmt", "rgba", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_UNCHANGED)


def _lufs(path):
    p = run([FFMPEG, "-hide_banner", "-v", "info", "-i", str(path), "-vn", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return None, None
    j = json.loads(m.group(0))
    try:
        return float(j["input_i"]), float(j["input_tp"])
    except (ValueError, KeyError):
        return None, None


def _conteo(path, vf):
    p = run([FFMPEG, "-hide_banner", "-v", "info", "-i", str(path), "-an", "-vf", vf, "-f", "null", "-"], check=False)
    return p.stderr


def _png(path, t):
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR) if p.stdout else None


def _caras_ratio(path, dur, n=8):
    """Fracción de fotogramas muestreados con cara. Los n fotogramas se extraen en paralelo (ffmpeg tarda en arrancar)."""
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (640, 360), 0.7, 0.3, 5000)
    with ThreadPoolExecutor(n) as ex:
        imgs = list(ex.map(lambda i: _png(path, dur * (i + 0.5) / n), range(n)))
    ok = tot = 0
    for img in imgs:
        if img is None:
            continue
        img = cv2.resize(img, (640, int(640 * img.shape[0] / img.shape[1])))
        det.setInputSize((img.shape[1], img.shape[0]))
        _, c = det.detect(img)
        tot += 1
        ok += 1 if (c is not None and len(c)) else 0
    return (ok / tot) if tot else None


def qc_formato(exp, base, fm, hay_voz):
    """Devuelve lista de checks para un formato (vertical/horizontal). Las mediciones independientes corren en paralelo."""
    W, H = dims(fm)
    ck = []

    def add(nombre, estado, detalle="", valor=None):
        ck.append({"check": nombre, "estado": estado, "detalle": detalle, "valor": valor})

    with ThreadPoolExecutor(5) as ex:
        f_info = ex.submit(probe, str(base))
        f_pa = ex.submit(lambda: run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(base)], check=False))
        f_lufs = ex.submit(_lufs, base) if hay_voz else None
        f_neg = ex.submit(_conteo, base, "blackdetect=d=0.25:pix_th=0.08")
        info = f_info.result()
        f_car = ex.submit(_caras_ratio, base, info["duracion"])
        sub = next(iter(sorted(Path(exp).glob(base.name.replace("_base.mp4", "_subtitulos_ALFA.mov")))), None)
        f_sub = ex.submit(_alfa_subs, sub, info["duracion"]) if (sub and hay_voz) else None

        add("resolución", "PASS" if (info.get("ancho"), info.get("alto")) == (W, H) else "FAIL", f"{info.get('ancho')}x{info.get('alto')} (esperado {W}x{H})")
        add("duración > 3 s", "PASS" if info["duracion"] > 3 else "FAIL", f"{info['duracion']:.1f}s")
        try:
            da = float(f_pa.result().stdout.strip())
            add("sincronía A/V", "PASS" if abs(da - info["duracion"]) < 0.15 else "WARN", f"audio {da:.2f}s vs vídeo {info['duracion']:.2f}s", abs(da - info["duracion"]))
        except ValueError:
            add("sincronía A/V", "WARN", "sin pista de audio")
        if hay_voz:
            i, tp = f_lufs.result()
            if i is None:
                add("sonoridad", "WARN", "no medible")
            else:
                estado = "PASS" if (abs(i + 14) <= 1.5 and tp <= -0.7) else "WARN"
                add("sonoridad", estado, f"{i:.1f} LUFS · pico {tp:.1f} dBTP (objetivo −14 / ≤ −1)", {"lufs": i, "true_peak": tp})
        else:
            add("sonoridad", "WARN", "sin voz detectada: no se normaliza")
        nb = len(re.findall(r"black_start", f_neg.result()))
        add("sin fotogramas negros", "PASS" if nb == 0 else "WARN", f"{nb} tramos negros", nb)
        r = f_car.result()
        if r is None:
            add("cara visible", "WARN", "no medible")
        else:
            add("cara visible", "PASS" if r >= 0.6 else "WARN", f"{r * 100:.0f}% de los fotogramas muestreados", r)
        if f_sub is not None:
            con_alfa, union = f_sub.result()
            seg = zona_seg(fm)
            x0, x1 = W * seg["izquierda"], W * (1 - seg["derecha"])
            y0, y1 = H * seg["arriba"], H * (1 - seg["abajo"])
            add("subtítulos con alfa real", "PASS" if con_alfa else "FAIL", f"{con_alfa}/10 muestras con píxeles opacos", con_alfa)
            if union:
                union = tuple(int(v) for v in union)
                dentro = union[0] >= x0 - 6 and union[2] <= x1 + 6 and union[1] >= y0 - 6 and union[3] <= y1 + 6  # 6 px: desenfoque de la sombra y descendentes
                add("subtítulos en zona segura", "PASS" if dentro else "FAIL", f"caja {union} · zona {zona_preset() if fm == 'vertical' else 'provisional'} x[{int(x0)},{int(x1)}] y[{int(y0)},{int(y1)}]")
        elif not hay_voz:
            add("subtítulos", "WARN", "sin voz: no hay subtítulos")
    if fm == "horizontal" and info["duracion"] > 60:
        try:
            from . import preset_largo as pr, ref_video as rv
            ev = rv.clasificar(rv.diferencia_por_fotograma(base))
            tc = [e["t"] for e in ev if e["tipo"] in ("corte_seco", "transicion_gradual")]
            av = pr.revisar_ritmo(tc, info["duracion"])
            add("ritmo largo (referencias)", "PASS" if not av else "WARN", "; ".join(av) or f"{len(tc) / (info['duracion'] / 60):.1f} cambios/min", len(tc))
        except Exception as e:  # el QC de ritmo nunca debe tumbar la entrega
            add("ritmo largo (referencias)", "WARN", f"no medible: {e}")
    return ck


def _alfa_subs(sub, dur):
    """(muestras con alfa de 10, caja unión del texto opaco) sobre 10 fotogramas repartidos, extraídos en paralelo."""
    with ThreadPoolExecutor(5) as ex:
        frames = list(ex.map(lambda k: _frame_rgba(sub, dur * (k + 0.5) / 10), range(10)))
    union, con_alfa = None, 0
    for f in frames:
        if f is None or f.shape[2] < 4:
            continue
        ys, xs = np.where(f[:, :, 3] > 128)
        if len(xs):
            con_alfa += 1
            b = (xs.min(), ys.min(), xs.max(), ys.max())
            union = b if union is None else (min(union[0], b[0]), min(union[1], b[1]), max(union[2], b[2]), max(union[3], b[3]))
    return con_alfa, union


def _json_default(o):
    return o.item() if hasattr(o, "item") else str(o)


def qc_proyecto_completo(proj, perfil=None):
    """QC completo: checks clásicos + métricas ampliadas (qc_extra) + manifiesto. Escribe 00_DOCS/qc.json, metricas.json y manifiesto_ia.json.
    Devuelve (res, resumen). res = {formato: [métrica con clave 'check'...], 'proyecto': [...], 'miniaturas': [...]} (compatible con qc_proyecto).
    resumen = {puntuacion, estado, cobertura, formatos:{fm:{puntuacion,estado}}, metricas:{'fm:Mxx'|'Mxx': puntaje}}."""
    from . import manifiesto as mf
    from . import metricas as M
    from . import qc_extra as X
    proj = Path(proj)
    exp = proj / "06_EXPORT"
    words = proj / "03_TRANSCRIPT" / "words_final.json"
    hay_voz = words.exists() and len(json.loads(words.read_text(encoding="utf-8-sig"))) >= 3
    res, primero = {}, None
    formatos = []
    for fm in ("vertical", "cuadrado", "4x5", "horizontal"):
        bases = sorted(exp.glob(f"*_{fm}_v*_base.mp4"), key=lambda p: int(re.search(r"_v(\d+)_base", p.name).group(1)))
        if bases:
            X.perfiles_zona(fm)  # precalentar en el hilo principal
            formatos.append((fm, bases[-1]))

    def uno(par):
        fm, base = par
        viejos = qc_formato(exp, base, fm, hay_voz)
        ctx = X.Ctx(proj, exp, base, fm, hay_voz, perfil)
        return fm, ctx, X.evaluar_formato(ctx, viejos)

    with ThreadPoolExecutor(max(1, len(formatos))) as ex:
        for fm, ctx, ms in ex.map(uno, formatos):
            res[fm] = ms
            primero = primero or ctx
    if primero is not None:
        try:
            res["proyecto"] = X.evaluar_proyecto(primero) + mf.metricas_proyecto(proj)
        except Exception as e:  # noqa: BLE001
            res["proyecto"] = [M.metrica("ERR", "fallo interno en métricas de proyecto", None, "WARN", "", "", f"{type(e).__name__}: {e}", "estimado", "baja", informativo=True)]
    thumbs = list((exp / "THUMBNAILS").glob("thumb_*.jpg")) if (exp / "THUMBNAILS").exists() else []
    res["miniaturas"] = [M.desde_check("M28", {"check": "miniaturas generadas", "estado": "PASS" if thumbs else "WARN", "detalle": f"{len(thumbs)} archivos"}, "terceros", "baja", duro=False)]
    for lst in res.values():
        for m in lst:
            m["check"] = m["nombre"]
    todas = [m for lst in res.values() for m in lst]
    punt, cob = M.puntuacion(todas)
    resumen = {"puntuacion": punt, "estado": M.estado_global(todas), "cobertura_peso": round(cob, 2), "formatos": {}, "metricas": {}}
    for k, lst in res.items():
        p, _ = M.puntuacion(lst)
        resumen["formatos"][k] = {"puntuacion": p, "estado": M.estado_global(lst)}
        for m in lst:
            resumen["metricas"][f"{k}:{m['id']}" if k in ("vertical", "cuadrado", "4x5", "horizontal") else m["id"]] = m["puntaje"]
    docs = proj / "00_DOCS"
    docs.mkdir(exist_ok=True)
    (docs / "qc.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=_json_default), encoding="utf-8")
    doc = {"version": 1, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "proyecto": proj.name, "perfil_plataforma": perfil, **resumen,
           "leyenda": "puntaje 0-1 por métrica; peso = prioridad x confianza del umbral; informativo=true: el WARN no cambia el estado global; N/A no puntúa",
           "detalle": {k: v for k, v in res.items()}}
    (docs / "metricas.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=_json_default), encoding="utf-8")
    return res, resumen


def qc_proyecto(proj, perfil=None):
    """Compatibilidad (entrada.py, lote.py antiguo): devuelve solo res."""
    return qc_proyecto_completo(proj, perfil)[0]


def resumen_estado(res):
    """FAIL si algún FAIL; WARN si algún WARN no informativo; si no PASS. (Los WARN 'informativos' solo restan puntuación.)"""
    ms = [c for v in res.values() for c in v]
    if any(c["estado"] == "FAIL" for c in ms):
        return "FAIL"
    return "WARN" if any(c["estado"] == "WARN" and not c.get("informativo") for c in ms) else "PASS"


def tabla_metricas(res, solo_no_pass=False):
    """Markdown: una fila por métrica de todos los formatos."""
    filas = ["| ámbito | id | métrica | estado | valor | confianza | detalle |", "|---|---|---|---|---|---|---|"]
    for k, lst in res.items():
        for m in lst:
            if solo_no_pass and m["estado"] in ("PASS", "N/A"):
                continue
            v = m.get("valor")
            v = f"{v:.2f}" if isinstance(v, float) else ("" if v is None else str(v))
            filas.append(f"| {k} | {m['id']} | {m['nombre']} | {m['estado']}{' (info)' if m.get('informativo') and m['estado'] == 'WARN' else ''} | {v} | {m['confianza_del_umbral']} | {m['detalle'][:140]} |")
    return chr(10).join(filas)
