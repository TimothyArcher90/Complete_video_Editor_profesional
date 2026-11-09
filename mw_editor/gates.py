"""Puertas deterministas: lo que David corrigió a mano en el Arca, convertido en comprobaciones que corren SIEMPRE.
Cada puerta devuelve {"puerta", "estado": PASS|WARN|FAIL, "detalle", ...}. Una puerta FAIL bloquea la entrega; nada se borra solo.
  python -m mw_editor.gates preflight  --destino D:\\ruta [--min-gb 5]
  python -m mw_editor.gates raw        --proyecto P [--sellar]
  python -m mw_editor.gates audio      --video V.mp4
  python -m mw_editor.gates colisiones --base B.mp4 --final F.mp4 --plan plan.json
  python -m mw_editor.gates licencias  --pistas windswept,easy_lemon
  python -m mw_editor.gates entrega    --proyecto P --json entrega.json"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

from .common import FFMPEG, ROOT

LICENCIAS_OK = {"CC-BY", "CC0", "MIT", "BSD-3", "APACHE-2.0"}
LICENCIAS_NO = {"CC-BY-NC", "CC-BY-NC-SA", "S-LAB", "GPL", "AGPL"}


def _r(puerta, estado, detalle, **extra):
    return {"puerta": puerta, "estado": estado, "detalle": detalle, **extra}


# ---------- 1. espacio en disco / herramientas (lección: E: llegó a 0 GB y ffmpeg dejó un MP4 sin moov) ----------
def preflight(destino, min_gb=5.0, dur_min=0.0, mbps=8.0):
    """Falla si el destino no tiene espacio para 3 versiones apiladas (salida + intermedio + margen)."""
    destino = Path(destino)
    base = destino if destino.exists() else next((p for p in destino.parents if p.exists()), Path(destino.anchor))
    libre = shutil.disk_usage(base).free / 1e9
    necesario = max(min_gb, dur_min * 60 * mbps / 8 / 1000 * 3)  # GB: salida a mbps × 3 (v1+intermedio+margen)
    res = [_r("espacio", "PASS" if libre >= necesario else "FAIL", f"{libre:.1f} GB libres en {base.anchor}; hacen falta ≥ {necesario:.1f}", libre_gb=round(libre, 2))]
    res.append(_r("ffmpeg", "PASS" if shutil.which(FFMPEG) or Path(FFMPEG).exists() else "FAIL", str(FFMPEG)))
    modelo = ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"
    res.append(_r("detector de caras (YuNet)", "PASS" if modelo.exists() else "FAIL", str(modelo)))
    return res


def versiones_apiladas(proyecto):
    """PROPUESTA de borrado (jamás borra): versiones antiguas de cada pieza en 06_EXPORT con su peso. David decide."""
    exp = Path(proyecto) / "06_EXPORT"
    grupos = {}
    for p in exp.glob("**/*_v[0-9]*.*"):
        m = re.match(r"(.*)_v(\d+)", p.stem)
        if m:
            grupos.setdefault((p.parent, m.group(1), p.suffix), []).append((int(m.group(2)), p))
    out = []
    for (_, base, ext), lst in grupos.items():
        lst.sort()
        for n, p in lst[:-1]:
            out.append({"archivo": str(p), "version": n, "mb": round(p.stat().st_size / 1e6, 1), "motivo": f"existe v{lst[-1][0]} más nueva"})
    return out


# ---------- 2. 01_RAW intocable (regla cero) ----------
def _huella(p):
    h = hashlib.sha256()
    tam = p.stat().st_size
    with open(p, "rb") as f:
        h.update(f.read(4 << 20))
        if tam > (8 << 20):
            f.seek(-(4 << 20), 2)
            h.update(f.read(4 << 20))
    return {"bytes": tam, "sha256_extremos": h.hexdigest()}


def sellar_raw(proyecto):
    raw = Path(proyecto) / "01_RAW"
    sello = {p.name: _huella(p) for p in sorted(raw.iterdir()) if p.is_file() and not p.name.startswith("_")}
    (Path(proyecto) / "00_DOCS").mkdir(exist_ok=True)
    (Path(proyecto) / "00_DOCS" / "raw_sello.json").write_text(json.dumps(sello, indent=1), encoding="utf-8")
    return _r("01_RAW sellado", "PASS", f"{len(sello)} archivos")


def verificar_raw(proyecto):
    sp = Path(proyecto) / "00_DOCS" / "raw_sello.json"
    if not sp.exists():
        return _r("01_RAW intacto", "WARN", "sin sello previo: corre `gates raw --sellar` al empezar")
    sello = json.loads(sp.read_text(encoding="utf-8"))
    raw = Path(proyecto) / "01_RAW"
    mal = [n for n, h in sello.items() if not (raw / n).exists() or _huella(raw / n) != h]
    return _r("01_RAW intacto", "FAIL" if mal else "PASS", f"modificados o ausentes: {mal}" if mal else f"{len(sello)} archivos idénticos al sello")


# ---------- 2b. candado de exportación (lección: re-componer mientras otro proceso exporta rompió un .mov) ----------
from contextlib import contextmanager


@contextmanager
def candado(proyecto, max_horas=6.0):
    """Un solo exportador por proyecto. Si el candado existe y tiene < max_horas, aborta (no pisa); si es más viejo se considera huérfano y se reemplaza.
    No se usa os.kill(pid, 0): en Windows termina el proceso."""
    import os
    exp = Path(proyecto) / "06_EXPORT"
    exp.mkdir(exist_ok=True)
    lock = exp / ".exportando"
    if lock.exists() and (time.time() - lock.stat().st_mtime) < max_horas * 3600:
        raise SystemExit(f"EXPORTACIÓN EN CURSO: {lock} ({lock.read_text(errors='replace').strip()}). No se toca 06_EXPORT mientras otro proceso exporta; "
                         f"si es un resto de un cierre brusco, borra ese archivo (o espera {max_horas:.0f} h).")
    lock.write_text(f"pid {os.getpid()} · {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


# ---------- 3. audio ----------
def audio(video):
    from .qc import _lufs
    i, tp = _lufs(video)
    if i is None:
        return _r("sonoridad", "WARN", "no medible")
    ok = abs(i + 14) <= 1.5 and tp <= -0.7
    return _r("sonoridad", "PASS" if ok else "FAIL", f"{i:.1f} LUFS · pico {tp:.1f} dBTP (objetivo −14 ±1,5 / ≤ −1)", lufs=i, true_peak=tp)


# ---------- 4. colisiones capa–cara (regla de David: nunca tapar la cara) ----------
def colisiones(base, final, plan):
    from .revisar_colisiones import revisar
    plan = json.loads(Path(plan).read_text(encoding="utf-8-sig")) if not isinstance(plan, dict) else plan
    res = revisar(base, final, plan)
    mal = [x for x in res if x.get("estado") == "TAPA LA CARA"]
    med = [x for x in res if x.get("solape_cara") is not None]
    est = "FAIL" if mal else ("WARN" if (res and not med) else "PASS")      # sin capas en el plan = nada que tapar = PASS
    return _r("capas vs cara", est, f"{len(med)} capas medidas, {len(mal)} tapan la cara" + ("" if res else " (el plan no tiene capas)"), capas=res)


# ---------- 4b. encuadre y franja oscura (lección: cara enorme en reels, poco aire, franja negra abajo) ----------
# Rangos ESTIMADOS (confianza media): tope de cabeza como fracción del alto y ancho de cara como fracción del ancho.
RANGOS_ENCUADRE = {"vertical": {"aire": (0.08, 0.30), "cara_ancho": (0.18, 0.45)},
                   "horizontal": {"aire": (0.06, 0.25), "cara_ancho": (0.06, 0.22)}}


def encuadre(video, formato, n=8, plan=None):
    """plan (dict o ruta a plan.json) opcional: los instantes con panel/clip a pantalla completa se excluyen (no hay presentador que medir)."""
    import cv2
    import numpy as np
    from .qc import _png
    from .common import probe
    dur = probe(str(video))["duracion"]
    if plan and not isinstance(plan, dict):
        plan = json.loads(Path(plan).read_text(encoding="utf-8-sig"))
    huecos = [(p["t"], p["t"] + p.get("dur", 3)) for p in (plan or {}).get("paneles", [])] + [(p["t"], p["t"] + p.get("dur", 3)) for p in (plan or {}).get("clips", [])]
    n = n * 3 if huecos else n
    det = cv2.FaceDetectorYN.create(str(ROOT / "brand" / "models" / "face_detection_yunet_2023mar.onnx"), "", (640, 360), 0.7, 0.3, 5000)
    aires, anchos, franjas = [], [], []
    for i in range(n):
        t = dur * (i + 0.5) / n
        if any(a <= t <= b for a, b in huecos):
            continue
        img = _png(video, t)
        if img is None:
            continue
        h0, w0 = img.shape[:2]
        im = cv2.resize(img, (640, int(640 * h0 / w0)))
        det.setInputSize((im.shape[1], im.shape[0]))
        _, c = det.detect(im)
        if c is not None and len(c):
            f = max(c, key=lambda k: k[2] * k[3])
            aires.append(max(0.0, f[1]) / im.shape[0])
            anchos.append(f[2] / im.shape[1])
        gr = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        g, sd = gr.mean(axis=1), gr.std(axis=1)                          # franja = filas oscuras (≤ Warm Black ≈ luma 34) Y uniformes (sin detalle)
        k = 0
        while k < len(g) and g[-1 - k] < 34 and sd[-1 - k] < 6:
            k += 1
        franjas.append(k / len(g))
    if not aires:
        return [_r("encuadre", "WARN", "sin cara medible")]
    a, w, fr = float(np.median(aires)), float(np.median(anchos)), float(np.median(franjas))
    R = RANGOS_ENCUADRE.get(formato, RANGOS_ENCUADRE["vertical"])
    out = [_r("aire sobre la cabeza", "PASS" if R["aire"][0] <= a <= R["aire"][1] else "WARN", f"{a * 100:.0f} % del alto (rango estimado {R['aire'][0] * 100:.0f}–{R['aire'][1] * 100:.0f} %)", valor=round(a, 3)),
           _r("tamaño de la cara", "PASS" if R["cara_ancho"][0] <= w <= R["cara_ancho"][1] else "WARN", f"{w * 100:.0f} % del ancho (rango estimado {R['cara_ancho'][0] * 100:.0f}–{R['cara_ancho'][1] * 100:.0f} %)", valor=round(w, 3)),
           _r("franja oscura inferior", "PASS" if fr <= 0.06 else "WARN", f"{fr * 100:.0f} % del alto casi negro en el borde inferior", valor=round(fr, 3))]
    return out


# ---------- 4c. color: ¿cambió algo perceptible? (lección: 3 variantes casi idénticas) y contraste de tarjetas ----------
def _lab_medio(video, n=10):
    import cv2
    import numpy as np
    from .qc import _png
    from .common import probe
    dur = probe(str(video))["duracion"]
    labs = []
    for i in range(n):
        img = _png(video, dur * (i + 0.5) / n)
        if img is not None:
            img = cv2.resize(img, (320, int(320 * img.shape[0] / img.shape[1])))
            labs.append(cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2Lab).reshape(-1, 3).mean(axis=0))
    return np.array(labs).mean(axis=0) if labs else None


def delta_color(original, editado, umbral=2.3):
    """ΔE76 entre el Lab medio del original y del editado (10 fotogramas repartidos; los cortes cambian el tiempo, así que es estadístico, no fotograma a fotograma).
    < 2,3 = diferencia apenas perceptible (JND). La puerta NO juzga si el look es bonito: dice si el grade cambió algo."""
    import numpy as np
    a, b = _lab_medio(original), _lab_medio(editado)
    if a is None or b is None:
        return _r("color: cambio perceptible", "WARN", "no medible")
    d = float(np.linalg.norm(a - b))
    return _r("color: cambio perceptible", "PASS" if d >= umbral else "WARN", f"ΔE76 medio {d:.1f} (apenas perceptible < {umbral}); L {a[0]:.0f}→{b[0]:.0f}", valor=round(d, 2))


def contraste_wcag(fg_hex, bg_hex):
    """Razón de contraste WCAG 2.x (4,5:1 texto normal, 3:1 texto grande). Fórmula propia (el paquete wcag-contrast-ratio está archivado)."""
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted((lum(fg_hex), lum(bg_hex)), reverse=True)
    return round((a + 0.05) / (b + 0.05), 2)


def paleta_legible():
    """Cada acento de marca sobre Warm Dark y Warm Black debe pasar 4,5:1 (texto normal)."""
    from .common import BRAND
    out = []
    fondos = {"Warm Black": "#1a1a17", "Warm Dark": "#232320"}
    acentos = {"oro": "#c9a84c", "teal": "#50b5a2", "texto": "#d6d1c8", "blanco": "#ffffff"}
    for fn, fh in fondos.items():
        for an, ah in acentos.items():
            r = contraste_wcag(ah, fh)
            out.append(_r(f"contraste {an} sobre {fn}", "PASS" if r >= 4.5 else "FAIL", f"{r}:1 (mín 4,5:1)", valor=r))
    return out


# ---------- 5. licencias de música (se verifica POR PISTA, no por sitio) ----------
def licencias(pistas, catalogo=None):
    from .musica import cargar_catalogo
    cat = {c["id"]: c for c in (catalogo or cargar_catalogo())}
    out, creditos = [], []
    for pid in pistas:
        c = cat.get(pid)
        if not c:
            out.append(_r(f"música {pid}", "FAIL", "pista no está en catalogo.json"))
            continue
        lic = (c.get("licencia") or "").upper()
        if lic in LICENCIAS_NO or lic not in LICENCIAS_OK:
            out.append(_r(f"música {pid}", "FAIL", f"licencia no permitida o desconocida: {c.get('licencia')}"))
        elif not c.get("atribucion"):
            out.append(_r(f"música {pid}", "FAIL", "falta texto de atribución"))
        else:
            ok = c.get("autoria_verificada_tag") and c.get("fuente_licencia") and c.get("credito_en_descripcion_obligatorio")
            estado = "PASS" if ok else "WARN"
            out.append(_r(f"música {pid}", estado, f"{c['licencia']} · {c['autor']} (autoría por etiqueta del MP3; licencia según FAQ oficial)" + (" · OBLIGATORIO pegar el crédito en la descripción (si no, Content ID puede reclamar)" if ok else " · falta verificación")))
            creditos.append(c["atribucion"])
    return out, "\n\n".join(creditos)


# ---------- 6. entrega: el mensaje final que David pidió, escrito siempre igual ----------
def entrega(proyecto, entregables, decisiones=(), fuera=(), hice=()):
    proyecto = Path(proyecto)
    L = [f"# Entrega — {proyecto.name}", "", f"_{time.strftime('%Y-%m-%d %H:%M')}_", "", "## Qué hice"] + [f"- {x}" for x in hice]
    L += ["", "## Archivos (rutas completas)"]
    for e in entregables:
        p = Path(e)
        L.append(f"- `{p}` — {'EXISTE %.0f MB' % (p.stat().st_size / 1e6) if p.exists() else 'NO EXISTE'}")
    L += ["", "## Decidí por mi cuenta (revisar)"] + [f"- {x}" for x in decisiones]
    L += ["", "## Quedó fuera y por qué"] + [f"- {x}" for x in fuera]
    texto = "\n".join(L) + "\n"
    (proyecto / "00_DOCS").mkdir(exist_ok=True)
    (proyecto / "00_DOCS" / "ENTREGA.md").write_text(texto, encoding="utf-8")
    return texto


def correr_todas(proyecto, destino, base=None, final=None, plan=None, pistas=()):
    """Bloque único para el final de cualquier video. Devuelve (estado_global, lista de puertas)."""
    P = list(preflight(destino))
    P.append(verificar_raw(proyecto))
    if final:
        P.append(audio(final))
    if base and final and plan:
        P.append(colisiones(base, final, plan))
    if pistas:
        P += licencias(pistas)[0]
    est = "FAIL" if any(p["estado"] == "FAIL" for p in P) else ("WARN" if any(p["estado"] == "WARN" for p in P) else "PASS")
    return est, P


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("preflight"); a.add_argument("--destino", required=True); a.add_argument("--min-gb", type=float, default=5.0); a.add_argument("--dur-min", type=float, default=0.0)
    a = sp.add_parser("raw"); a.add_argument("--proyecto", required=True); a.add_argument("--sellar", action="store_true")
    a = sp.add_parser("audio"); a.add_argument("--video", required=True)
    a = sp.add_parser("colisiones"); a.add_argument("--base", required=True); a.add_argument("--final", required=True); a.add_argument("--plan", required=True)
    a = sp.add_parser("encuadre"); a.add_argument("--video", required=True); a.add_argument("--formato", choices=["vertical", "horizontal"], required=True); a.add_argument("--plan")
    a = sp.add_parser("color"); a.add_argument("--original", required=True); a.add_argument("--editado", required=True)
    sp.add_parser("paleta")
    a = sp.add_parser("licencias"); a.add_argument("--pistas", required=True)
    a = sp.add_parser("versiones"); a.add_argument("--proyecto", required=True)
    n = ap.parse_args(argv)
    if n.cmd == "preflight":
        out = preflight(n.destino, n.min_gb, n.dur_min)
    elif n.cmd == "raw":
        out = [sellar_raw(n.proyecto) if n.sellar else verificar_raw(n.proyecto)]
    elif n.cmd == "audio":
        out = [audio(n.video)]
    elif n.cmd == "colisiones":
        out = [colisiones(n.base, n.final, n.plan)]
    elif n.cmd == "encuadre":
        out = encuadre(n.video, n.formato, plan=n.plan)
    elif n.cmd == "color":
        out = [delta_color(n.original, n.editado)]
    elif n.cmd == "paleta":
        out = paleta_legible()
    elif n.cmd == "licencias":
        out, cred = licencias(n.pistas.split(","))
        print(cred)
    else:
        out = versiones_apiladas(n.proyecto)
    for x in out:
        print(json.dumps(x, ensure_ascii=False))
    return 1 if any(x.get("estado") == "FAIL" for x in out) else 0


if __name__ == "__main__":
    sys.exit(main())
