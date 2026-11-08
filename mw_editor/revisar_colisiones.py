"""Revisor de colisiones (regla de David: nada sobre la cara). Compara el video FINAL con el BASE en el instante de cada capa del plan:
los píxeles que cambian son la capa; la cara sale de YuNet sobre el BASE. Informa solape cara-capa por ítem. Los paneles (pantalla/cápsula) se omiten.
  python -m mw_editor.revisar_colisiones BASE.mp4 FINAL.mp4 plan.json"""
import json
import subprocess
import sys

import cv2
import numpy as np

from .common import FFMPEG, ROOT

W, H = 640, 360


def _frame(ruta, t):
    r = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-ss", f"{t:.2f}", "-i", str(ruta), "-frames:v", "1", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL)
    return np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3) if len(r.stdout) == W * H * 3 else None


def revisar(base, final, plan):
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (W, H), 0.7, 0.3, 5000)
    items = []
    for k in ("lower_thirds", "titulos_grandes", "titulos", "cifras", "cta", "impacto"):
        for x in plan.get(k, []):
            items.append((k, x))
    paneles = [(p["t"], p["t"] + p.get("dur", 3)) for p in plan.get("paneles", [])]
    res = []
    for k, x in items:
        t = x["t"] + min(1.2, x.get("dur", 3.0) * 0.5)
        if any(a <= t <= b for a, b in paneles):
            continue
        fb, ff = _frame(base, t), _frame(final, t)
        if fb is None or ff is None:
            continue
        d = cv2.cvtColor(cv2.absdiff(fb, ff), cv2.COLOR_BGR2GRAY)
        m = (d > 30).astype(np.uint8)
        _, caras = det.detect(np.ascontiguousarray(fb))
        if caras is None or not len(caras) or m.sum() < 50:
            res.append({"capa": k, "t": round(t, 1), "solape_cara": None, "nota": "sin cara o sin capa visible"})
            continue
        c = max(caras, key=lambda c: c[2] * c[3])
        fx, fy, fw, fh = [int(v) for v in c[:4]]
        mm = np.zeros_like(m)
        mm[max(fy, 0):fy + fh, max(fx, 0):fx + fw] = 1
        sol = float((m & mm).sum()) / max(1.0, float(mm.sum()))
        res.append({"capa": k, "t": round(t, 1), "solape_cara": round(sol, 3), "estado": "OK" if sol < 0.01 else "TAPA LA CARA"})
    return res


if __name__ == "__main__":
    r = revisar(sys.argv[1], sys.argv[2], json.load(open(sys.argv[3], encoding="utf-8-sig")))
    for x in r:
        print(x)
    mal = [x for x in r if x.get("estado") == "TAPA LA CARA"]
    print("RESULTADO:", "FALLA" if mal else "OK", len(r), "capas medidas")
    sys.exit(1 if mal else 0)
