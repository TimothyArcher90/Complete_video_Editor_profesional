"""Análisis de VIDEO de una referencia (archivo real): cortes, ritmo, tipo de transición, loudness, hojas de contacto.
Mide, no opina: devuelve JSON con tiempos de corte, duración media de plano, cortes por minuto, mapa de ritmo por minuto,
transiciones graduales (varios fotogramas con diferencia alta seguidos) frente a cortes secos, y niveles de audio."""
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path


def _ff(args, **kw):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def cortes(ruta, umbral=0.25, ancho=480):
    """Detecta cambios de plano. Devuelve [(t, score)] con score 0-1 (cuanto mayor, más brusco)."""
    r = _ff(["-i", str(ruta), "-vf", f"scale={ancho}:-2,select='gt(scene,{umbral})',metadata=print:file=-", "-an", "-f", "null", "-"])
    out, t = [], None
    for ln in (r.stdout + r.stderr).splitlines():
        m = re.search(r"pts_time:([\d.]+)", ln)
        if m:
            t = float(m.group(1))
        m = re.search(r"lavfi.scene_score=([\d.]+)", ln)
        if m and t is not None:
            out.append((t, float(m.group(1))))
    return out


def diferencia_por_fotograma(ruta, ancho=320):
    """Serie (t, score) de TODOS los fotogramas (umbral 0) para ver transiciones graduales (disolvencias, zooms)."""
    r = _ff(["-i", str(ruta), "-vf", f"scale={ancho}:-2,select='gte(scene,0.06)',metadata=print:file=-", "-an", "-f", "null", "-"])
    out, t = [], None
    for ln in (r.stdout + r.stderr).splitlines():
        m = re.search(r"pts_time:([\d.]+)", ln)
        if m:
            t = float(m.group(1))
        m = re.search(r"lavfi.scene_score=([\d.]+)", ln)
        if m and t is not None:
            out.append((t, float(m.group(1))))
    return out


def clasificar(serie, fps=29.97):
    """Agrupa fotogramas consecutivos con cambio > 0.06: 1 fotograma alto = corte seco; varios seguidos = transición gradual."""
    eventos, cur = [], []
    paso = 1.6 / fps
    for t, s in serie:
        if cur and t - cur[-1][0] > paso:
            eventos.append(cur)
            cur = []
        cur.append((t, s))
    if cur:
        eventos.append(cur)
    res = []
    for ev in eventos:
        pico = max(s for _, s in ev)
        dur = ev[-1][0] - ev[0][0] + 1 / fps
        if len(ev) == 1 and pico >= 0.25:
            tipo = "corte_seco"
        elif len(ev) >= 3 and pico >= 0.06:
            tipo = "transicion_gradual"
        elif pico >= 0.25:
            tipo = "corte_seco"
        else:
            tipo = "movimiento_interno"
        res.append({"t": round(ev[0][0], 2), "dur_s": round(dur, 2), "fotogramas": len(ev), "pico": round(pico, 2), "tipo": tipo})
    return res


def audio(ruta):
    r = _ff(["-i", str(ruta), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"])
    txt = r.stderr
    d = {}
    for k, rx in (("lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+([\d.]+) LU"), ("true_peak", r"Peak:\s+(-?[\d.]+) dBFS")):
        m = re.findall(rx, txt)
        if m:
            d[k] = float(m[-1])
    return d


def analizar(ruta, salida_json=None):
    ruta = Path(ruta)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)], capture_output=True, text=True).stdout.strip())
    serie = diferencia_por_fotograma(ruta)
    ev = clasificar(serie)
    secos = [e for e in ev if e["tipo"] == "corte_seco"]
    grad = [e for e in ev if e["tipo"] == "transicion_gradual"]
    tc = [e["t"] for e in secos + grad]
    tc.sort()
    plano = [b - a for a, b in zip(tc, tc[1:])]
    minutos = {}
    for t in tc:
        minutos[int(t // 60)] = minutos.get(int(t // 60), 0) + 1
    res = {
        "archivo": ruta.name, "duracion_s": round(dur, 1), "cortes_secos": len(secos), "transiciones_graduales": len(grad),
        "cambios_por_min": round(len(tc) / (dur / 60), 2), "plano_medio_s": round(statistics.mean(plano), 2) if plano else None,
        "plano_mediano_s": round(statistics.median(plano), 2) if plano else None, "plano_max_s": round(max(plano), 1) if plano else None,
        "ritmo_por_min": [minutos.get(m, 0) for m in range(int(dur // 60) + 1)],
        "audio": audio(ruta), "eventos": ev,
    }
    if salida_json:
        Path(salida_json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = analizar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print({k: v for k, v in r.items() if k != "eventos"})
