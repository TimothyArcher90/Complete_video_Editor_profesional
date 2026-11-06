"""F5 Cortes técnicos: acorta silencios largos y marca muletillas. Cortes solo entre palabras (nunca a mitad).
Devuelve intervalos a conservar y el mapa de tiempos viejo -> nuevo para re-sincronizar las palabras."""
import json
from pathlib import Path

MULETILLAS = {"eh", "ehh", "mm", "mmm", "hmm", "um", "uh", "aaa", "eee", "ehm"}


def plan_cortes(palabras, dur, pausa_max=0.45, pausa_deja=0.16, quitar_muletillas=True, margen_ini=0.05, margen_fin=0.10):
    """Mantiene todo salvo: (a) huecos entre palabras > pausa_max (se dejan pausa_deja), (b) muletillas puras.
    Regla de corte: solo dentro de [fin_palabra + 0,05 , inicio_palabra - 0,10]."""
    ws = [w for w in palabras]
    quitar = []  # intervalos a eliminar (a, b)
    if quitar_muletillas:
        for w in ws:
            if w["w"].lower().strip(".,;:¿?¡!") in MULETILLAS:
                quitar.append((max(0, w["s"] - 0.03), w["e"] + 0.03, "muletilla"))
    for a, b in zip(ws, ws[1:]):
        hueco = b["s"] - a["e"]
        if hueco > pausa_max:
            ini = a["e"] + margen_ini + pausa_deja / 2
            fin = b["s"] - margen_fin - pausa_deja / 2
            if fin - ini > 0.12:
                quitar.append((ini, fin, "silencio"))
    # silencio inicial y final
    if ws:
        if ws[0]["s"] > 0.6:
            quitar.append((0.0, ws[0]["s"] - 0.25, "silencio_inicial"))
        if dur - ws[-1]["e"] > 1.0:
            quitar.append((ws[-1]["e"] + 0.6, dur, "silencio_final"))
    quitar.sort()
    # fusionar solapes
    fus = []
    for a, b, k in quitar:
        if fus and a <= fus[-1][1] + 0.01:
            fus[-1] = (fus[-1][0], max(fus[-1][1], b), fus[-1][2])
        else:
            fus.append((a, b, k))
    keep, cur = [], 0.0
    for a, b, _ in fus:
        if a - cur > 0.05:
            keep.append((round(cur, 3), round(a, 3)))
        cur = b
    if dur - cur > 0.05:
        keep.append((round(cur, 3), round(dur, 3)))
    return {"keep": keep, "quitados": [{"a": round(a, 3), "b": round(b, 3), "tipo": k} for a, b, k in fus],
            "duracion_original": round(dur, 3), "duracion_final": round(sum(b - a for a, b in keep), 3)}


def mapa_tiempo(keep):
    """Devuelve f(t_viejo) -> t_nuevo (o None si cae en un tramo eliminado)."""
    acum, tabla = 0.0, []
    for a, b in keep:
        tabla.append((a, b, acum))
        acum += b - a

    def f(t):
        for a, b, off in tabla:
            if a - 1e-6 <= t <= b + 1e-6:
                return off + (t - a)
        return None
    return f


def remapear_palabras(palabras, keep):
    f = mapa_tiempo(keep)
    out = []
    for w in palabras:
        s, e = f(w["s"]), f(w["e"])
        if s is None or e is None:
            continue
        out.append({**w, "s": round(s, 3), "e": round(max(e, s + 0.05), 3)})
    return out


def guardar(plan, ruta):
    Path(ruta).write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")


def filtro_concat(keep, video=True, audio=True, afade=0.008):
    """Script de filter_complex para concatenar los tramos (con micro-fundidos de audio de 8 ms anti-clic)."""
    partes, v_lab, a_lab = [], "", ""
    for i, (a, b) in enumerate(keep):
        if video:
            partes.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
            v_lab += f"[v{i}]"
        if audio:
            d = b - a
            partes.append(
                f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={afade},afade=t=out:st={max(0, d - afade):.4f}:d={afade}[a{i}]"
            )
            a_lab += f"[a{i}]"
    n = len(keep)
    if video and audio:
        partes.append(f"{''.join(f'[v{i}][a{i}]' for i in range(n))}concat=n={n}:v=1:a=1[vcat][acat]")
    elif video:
        partes.append(f"{v_lab}concat=n={n}:v=1:a=0[vcat]")
    else:
        partes.append(f"{a_lab}concat=n={n}:v=0:a=1[acat]")
    return ";\n".join(partes)
