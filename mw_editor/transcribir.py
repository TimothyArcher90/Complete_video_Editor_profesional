"""F4 Transcripción con timestamps por palabra (faster-whisper, MIT). Salida: words.json."""
import json
import re
from pathlib import Path

from .common import FFMPEG, log, run

# Términos que Whisper suele escribir mal en contenido financiero en español. Se corrigen de forma determinista.
CORRECCIONES = {
    r"\bnasdaq\b": "Nasdaq", r"\bs&p\b": "S&P", r"\bs and p\b": "S&P", r"\bbitcoin\b": "Bitcoin",
    r"\bethereum\b": "Ethereum", r"\bnvidia\b": "NVIDIA", r"\bfed\b": "Fed", r"\bbce\b": "BCE",
    r"\bpib\b": "PIB", r"\bibkr\b": "IBKR", r"\betf\b": "ETF", r"\bmacrowise\b": "MacroWise",
    r"\bchat gpt\b": "ChatGPT", r"\bchatgpt\b": "ChatGPT", r"\bclaude\b": "Claude", r"\bgpt\b": "GPT",
}


def extraer_audio(src, wav):
    run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav])


def corregir(palabra):
    p = palabra
    for pat, rep in CORRECCIONES.items():
        if re.fullmatch(pat.replace(r"\b", ""), p.strip(".,;:¿?¡!").lower()):
            core = p.strip(".,;:¿?¡!")
            return p.replace(core, rep)
    return p


def _registrar_dll_cuda():
    """Whisper en GPU: las DLL de cuBLAS/cuDNN vienen en los paquetes pip nvidia-cublas-cu12 y nvidia-cudnn-cu12
    (carpeta site-packages\\nvidia\\*\\bin). Windows no las encuentra solo: se registran antes de importar faster-whisper."""
    import os
    import sys
    try:
        import nvidia  # type: ignore
    except ImportError:
        return
    for base in list(getattr(nvidia, "__path__", [])):
        try:
            for sub in os.listdir(base):
                b = os.path.join(base, sub, "bin")
                if os.path.isdir(b):
                    os.add_dll_directory(b)
                    os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
        except OSError:
            pass


def transcribir(src, salida_json, idioma="es", modelo=None, prompt_inicial=None):
    idioma = None if idioma in (None, "auto") else idioma
    """Devuelve lista de {w, s, e, p}. Usa GPU (CUDA) si está disponible; si no, CPU int8."""
    _registrar_dll_cuda()
    from faster_whisper import WhisperModel

    import numpy as np

    # Decodificamos con ffmpeg (no con PyAV: su versión es incompatible con faster-whisper en este equipo)
    import subprocess as _sp
    proc = _sp.run([FFMPEG, "-hide_banner", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                   capture_output=True)
    wav = np.frombuffer(proc.stdout, dtype=np.float32)
    modelo = modelo or "medium"
    modelo_obj = None
    for dev, ct in (("cuda", "float16"), ("cpu", "int8")):
        try:
            modelo_obj = WhisperModel(modelo, device=dev, compute_type=ct)
            log(f"Whisper '{modelo}' en {dev}/{ct}")
            # prueba rápida para detectar DLLs CUDA ausentes (falla recién al transcribir)
            list(modelo_obj.transcribe(wav[:16000 * 3], language=idioma, beam_size=1, without_timestamps=True, condition_on_previous_text=False)[0])
            break
        except Exception as e:  # noqa: BLE001
            log(f"{dev} no disponible ({str(e)[:80]}) -> siguiente")
            modelo_obj = None
    if modelo_obj is None:
        raise RuntimeError("No se pudo cargar faster-whisper")
    segs, _ = modelo_obj.transcribe(
        wav, language=idioma, beam_size=5, word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350}, initial_prompt=prompt_inicial,
        condition_on_previous_text=False,
    )
    palabras = []
    for s in segs:
        for w in s.words or []:
            txt = w.word.strip()
            if not txt:
                continue
            palabras.append({"w": corregir(txt), "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)})
    Path(salida_json).write_text(json.dumps(palabras, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"{len(palabras)} palabras -> {salida_json}")
    return palabras
