"""Utilidades comunes: rutas, marca, ffmpeg/ffprobe, formatos de tiempo y color."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ffmpeg lee el teclado por la entrada estándar: en procesos de segundo plano (ventana oculta) se queda esperando para siempre.
# Se fuerza stdin=DEVNULL en TODA llamada a subprocess del motor (run, Popen) salvo que quien llama pase stdin/input.
_run_orig, _Popen_orig = subprocess.run, subprocess.Popen


def _run_sin_teclado(*a, **k):
    if "stdin" not in k and "input" not in k:
        k["stdin"] = subprocess.DEVNULL
    return _run_orig(*a, **k)


class _PopenSinTeclado(_Popen_orig):
    def __init__(self, *a, **k):
        if "stdin" not in k:
            k["stdin"] = subprocess.DEVNULL
        super().__init__(*a, **k)


subprocess.run = _run_sin_teclado
subprocess.Popen = _PopenSinTeclado

ROOT = Path(__file__).resolve().parents[1]
BRAND =json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))
FONTS_DIR = ROOT / "brand" / "fonts"
LOGO_BLANCO = ROOT / "brand" / "logos" / "LOGO MW BLANCO.png"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

# Raíz de salidas de David (orden: DÍA-MES-AÑO > nombre del output > 00_DOCS ... 06_EXPORT).
# Si el disco E: no está conectado, cae a Descargas para no perder el trabajo.
RAIZ_E = Path(r"E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados")
PROYECTOS_RAIZ = RAIZ_E if RAIZ_E.parent.exists() else Path(r"C:\Users\tante\Videos\MacroWise_pendiente_de_pasar_a_E\Video con Ia editor\outputs organizados")
SUBCARPETAS = ["00_DOCS", "01_RAW", "02_AUDIO", "03_TRANSCRIPT", "04_GRAPHICS", "05_PROJECT", "06_EXPORT"]


def log(*a):
    print("[mw]", *a, flush=True)


def run(cmd, check=True, capture=True, cwd=None):
    """Ejecuta un comando (lista). Devuelve CompletedProcess con stdout/stderr como texto utf-8."""
    p = subprocess.run(
        [str(c) for c in cmd],
        capture_output=capture,
        stdin=subprocess.DEVNULL,   # ffmpeg en segundo plano se colgaba esperando teclado
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )
    if check and p.returncode != 0:
        tail = (p.stderr or "")[-2500:]
        raise RuntimeError(f"Falló: {' '.join(str(c) for c in cmd[:6])} ...\n{tail}")
    return p


def ffmpeg(args, check=True):
    return run([FFMPEG, "-hide_banner", "-y", "-v", "error", *args], check=check)


def probe(path):
    p = run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", path])
    j = json.loads(p.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    info = {"duracion": float(j["format"].get("duration", 0)), "tiene_audio": a is not None}
    if v:
        num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
        fps = float(num) / float(den or 1)
        info.update(
            ancho=int(v["width"]), alto=int(v["height"]), fps=round(fps, 3),
            codec=v.get("codec_name"), bitrate=int(v.get("bit_rate") or j["format"].get("bit_rate") or 0),
            pix_fmt=v.get("pix_fmt"),
            rotacion=int((v.get("tags") or {}).get("rotate", 0) or 0),
        )
    if a:
        info.update(audio_codec=a.get("codec_name"), audio_hz=int(a.get("sample_rate", 0)), audio_canales=a.get("channels"))
    return info


def ffq(path):
    """Ruta segura para usar dentro de un filtro de ffmpeg (Windows: escapa los dos puntos)."""
    s = str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return s


def hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ass_color(hexcolor, alpha=0):
    """'#C6DD2E' -> '&H002EDDC6' (ASS usa BGR y alfa invertido: 00 = opaco)."""
    r, g, b = hex_rgb(hexcolor)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ass_c(hexcolor):
    """Color para tags inline \\1c: '&HBBGGRR&'."""
    r, g, b = hex_rgb(hexcolor)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def color_marca(nombre):
    """Nombre de color (lima, oro, ...) o clave de taxonomía (valor, tecnico, geo, coste) -> hex."""
    c = BRAND["colores"]
    tax = BRAND["taxonomia"]
    if nombre in tax:
        nombre = tax[nombre]
    return c.get(nombre, nombre)


def dims(formato):
    f = BRAND["formatos"][formato]
    return f["w"], f["h"]


def crear_proyecto(nombre, fecha=None, raiz=None):
    """<raiz>/DD-MM-AAAA/<nombre>/00_DOCS..06_EXPORT. Nunca toca un 01_RAW existente. Referencias van en <raiz>/DD-MM-AAAA/_REFERENCIAS."""
    import datetime as _dt
    fecha = fecha or _dt.date.today().strftime("%d-%m-%Y")
    base = (Path(raiz) if raiz else PROYECTOS_RAIZ) / fecha
    p = base / nombre
    for s_ in SUBCARPETAS:
        (p / s_).mkdir(parents=True, exist_ok=True)
    (base / "_REFERENCIAS").mkdir(exist_ok=True)
    return p


def siguiente_version(carpeta, base, ext):
    """v1, v2, v3... sin sobrescribir."""
    carpeta = Path(carpeta)
    n = 1
    while (carpeta / f"{base}_v{n}{ext}").exists():
        n += 1
    return n

