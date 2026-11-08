"""Regla de David (2026-11-06): NINGUNA tarjeta, cifra, título ni CTA sobre la cara. Este módulo mide la cara con YuNet en el video
final y recoloca cada capa (lado, escala, altura) hasta que su rectángulo no toque la cara + margen; si no hay sitio, lo avisa.
Solo formatos no verticales (en vertical el encuadre ya deja la zona alta libre y se verifica con verificar_encuadre)."""
from .common import dims, log
from .planos import detectar_cajas
from .subs import ancho_real, medir
from .zonas import caja_segura_px


def _cara_en(caras, t0, t1, W, H, margen=0.035):
    c = [x for x in caras if t0 - 0.5 <= x["t"] <= t1 + 0.5]
    if not c:
        return None
    x0 = min(x["x"] for x in c) - margen
    x1 = max(x["x"] + x["w"] for x in c) + margen
    y0 = min(x["y"] for x in c) - margen
    y1 = max(x["y"] + x["h"] for x in c) + margen
    return x0 * W, y0 * H, x1 * W, y1 * H


def _choca(r, f):
    return not (r[2] <= f[0] or r[0] >= f[2] or r[3] <= f[1] or r[1] >= f[3])


def ajustar(base, plan, formato="horizontal", caras=None):
    W, H = dims(formato)
    if H > W:
        return plan, []
    esc = H / 1080
    seg = caja_segura_px(formato)
    sx, sy_top, sw_right, sy_bot = seg[0], seg[1], seg[2], seg[3]
    cxs = (sx + sw_right) / 2
    if caras is None:
        caras = detectar_cajas(str(base), fps=1.0)
    avisos = []

    # títulos grandes: arriba o abajo de la cara
    for tg in plan.get("titulos_grandes", []):
        t0, t1 = tg["t"], tg["t"] + tg.get("dur", 3.0)
        f = _cara_en(caras, t0, t1, W, H)
        if not f:
            continue
        fs1, fs2 = 66 * esc, 118 * esc
        bh = (fs1 * 1.32 if tg.get("linea1") else 0) + fs2 * 1.24
        bw = max(ancho_real(tg.get("linea2", ""), fs2) + 0.4 * fs2, ancho_real(tg.get("linea1", ""), fs1) if tg.get("linea1") else 0)
        resuelto = False
        for yf in (0.03, tg.get("y", 0.14), (f[3] + 0.02 * H) / H):
            y0 = yf * H
            r = (cxs - bw / 2, y0, cxs + bw / 2, y0 + bh)
            if y0 + bh <= H * 0.97 and not _choca(r, f):
                tg["y"] = round(yf, 3)
                resuelto = True
                break
        if not resuelto:
            avisos.append(f"título «{tg.get('linea2')}» t={t0}: sin sitio libre de cara (acortar o pasar a panel)")

    # cifras: lado y escala
    for ci in plan.get("cifras", []):
        t0, t1 = ci["t"], ci["t"] + ci.get("dur", 3.5)
        f = _cara_en(caras, t0, t1, W, H)
        if not f:
            continue
        resuelto = False
        for k in (1.0, 0.8, 0.65):
            tv, tl, tf = 150 * esc * k, 26 * esc * k, 20 * esc * k
            cw = max(medir(ci["valor"], tv, "titular", -0.03 * tv), medir(ci.get("etiqueta", "").upper(), tl, "mono", 0.18 * tl),
                     medir("FUENTE: " + ci.get("fuente", "").upper(), tf, "mono", 0.18 * tf)) + 90 * esc * k
            ch = tl + tv * 1.1 + tf + 100 * esc * k
            for lado in ("der", "izq"):
                x = sw_right - cw if lado == "der" else sx
                for yf in (sy_top / H + 0.03, 0.62):
                    y = yf * H if yf > 0.2 else sy_top + 30 * esc
                    r = (x, y, x + cw, y + ch)
                    if y + ch <= H * 0.95 and not _choca(r, f):
                        ci.update({"escala": k, "lado": lado})
                        if yf > 0.2:
                            ci["y_frac"] = yf
                        resuelto = True
                        break
                if resuelto:
                    break
            if resuelto:
                break
        if not resuelto:
            avisos.append(f"cifra «{ci.get('valor')}» t={t0}: sin sitio libre de cara")

    # CTA: bloque centrado, arriba o abajo de la cara
    for cta in plan.get("cta", []):
        t0, t1 = cta["t"], cta["t"] + cta.get("dur", 4.0)
        f = _cara_en(caras, t0, t1, W, H)
        if not f:
            continue
        resuelto = False
        for k in (1.0, 0.75, 0.6):
            bh, bw = (62 * 1.2 + 140 * 1.25 + 40) * esc * k, 0.5 * W * k
            for yf in (0.03, (f[3] + 0.015 * H) / H):
                y0 = yf * H
                r = (cxs - bw / 2, y0, cxs + bw / 2, y0 + bh)
                if y0 + bh <= H * 0.985 and not _choca(r, f):
                    cta.update({"y": round(yf, 3), "escala": k})
                    resuelto = True
                    break
            if resuelto:
                break
        if not resuelto:
            avisos.append(f"CTA t={t0}: sin sitio libre de cara")
    for a in avisos:
        log("AVISO:", a)
    return plan, avisos
