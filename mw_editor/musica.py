"""Música automática para el motor (receta de la investigación del 2026-11-08).

  python -m mw_editor musica PROYECTO [--formato horizontal] [--pista ID]

Flujo: catálogo local con LICENCIA por pista (solo CC0 / Pixabay sin Content ID / YouTube Audio Library sin atribución / CC-BY con crédito)
→ mide la energía del discurso (palabras/s por tramo) → elige pista por mood/BPM → beats con librosa (ISC) → mezcla con sidechain
(música bajo la voz, fade de entrada/salida) → ENTREGA UNA PISTA DE AUDIO APARTE (editable en Premiere), no quemada en el video →
registra la atribución en 00_DOCS/musica_creditos.txt.
No incluye pistas: la biblioteca vive en REFERENCIAS/../MUSICA (David las descarga; cada una con su fila en catalogo.json).
Licencias NO verificadas por mí: abrir la página de cada pista antes de monetizar. Prohibido: MusicGen (pesos CC-BY-NC), madmom, Essentia."""
import json
import subprocess
from pathlib import Path

from .common import FFMPEG, log, probe

MUSICA = Path(r"E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\MUSICA")
LICENCIAS_OK = {"CC0", "Pixabay", "YouTubeAudioLibrary", "CC-BY"}
# nivel de la música bajo la voz (no verificado en fuente: práctica común, ajustable)
DB_BAJO_VOZ = -20.0


def cargar_catalogo():
    f = MUSICA / "catalogo.json"
    if not f.exists():
        return []
    cat = json.loads(f.read_text(encoding="utf-8-sig"))
    return [p for p in cat if p.get("licencia") in LICENCIAS_OK and not p.get("content_id") and (MUSICA / p["archivo"]).exists()]


def energia_discurso(palabras):
    """Palabras/s medianas por ventanas de 30 s -> baja | media | alta."""
    if not palabras:
        return "media", 0.0
    fin = palabras[-1]["e"]
    vent = [sum(1 for w in palabras if t <= w["s"] < t + 30) / 30.0 for t in range(0, int(fin), 30)]
    vent.sort()
    med = vent[len(vent) // 2] if vent else 0.0
    return ("baja" if med < 2.4 else "alta" if med > 3.3 else "media"), med


def elegir(catalogo, energia, pista_id=None):
    if pista_id:
        return next((p for p in catalogo if p["id"] == pista_id), None)
    orden = {"baja": ("calmo", "ambient"), "media": ("neutro", "lofi", "calmo"), "alta": ("energico", "neutro")}[energia]
    for mood in orden:
        c = [p for p in catalogo if p.get("mood") == mood]
        if c:
            return c[0]
    return catalogo[0] if catalogo else None


def beats(ruta_audio, max_s=600):
    """Tempo y tiempos de beat (s) con librosa; sirve para alinear cortes y gráficos."""
    import librosa
    y, sr = librosa.load(str(ruta_audio), sr=22050, mono=True, duration=max_s)
    tempo, fr = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo if getattr(tempo, "ndim", 0) == 0 else tempo[0]), [round(float(t), 3) for t in librosa.frames_to_time(fr, sr=sr)]


def ajustar_al_beat(t, bts, tol=0.12):
    """Mueve un tiempo al beat más cercano si está a menos de `tol` s (≈3 fotogramas a 24 fps)."""
    if not bts:
        return t
    b = min(bts, key=lambda x: abs(x - t))
    return b if abs(b - t) <= tol else t


def mezclar(voz_wav, pista, salida, dur, db=DB_BAJO_VOZ, fade=3.0):
    """Música en bucle, ducking por sidechain con la voz, fades; devuelve SOLO la pista de música ya duckeada (stem aparte)."""
    fg = (f"[0:a]aloop=loop=-1:size=2e9,atrim=0:{dur:.2f},loudnorm=I=-24:TP=-3:LRA=7,volume={db + 20}dB,afade=t=in:st=0:d={fade},afade=t=out:st={max(0, dur - fade):.2f}:d={fade}[m];"
          f"[m][1:a]sidechaincompress=threshold=0.04:ratio=4:attack=50:release=700:makeup=1[d]")
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(pista), "-i", str(voz_wav), "-filter_complex", fg, "-map", "[d]", "-ar", "48000", "-c:a", "pcm_s24le", str(salida)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    return salida


def musicar(proyecto, formato="horizontal", pista_id=None):
    proyecto = Path(proyecto)
    cat = cargar_catalogo()
    if not cat:
        raise SystemExit(f"No hay pistas válidas en {MUSICA}\\catalogo.json (licencia permitida + archivo existente). Descarga pistas y regístralas.")
    pf = json.loads((proyecto / "03_TRANSCRIPT" / "words_final.json").read_text(encoding="utf-8-sig"))
    en, wps = energia_discurso(pf)
    p = elegir(cat, en, pista_id)
    exp = proyecto / "06_EXPORT"
    base = sorted(exp.glob(f"*_{formato}_v*_base.mp4"))[-1]
    dur = probe(str(base))["duracion"]
    voz = proyecto / "02_AUDIO" / "voz_final.wav"
    if not voz.exists():  # la voz tratada vive en el base: se extrae
        voz.parent.mkdir(exist_ok=True)
        subprocess.run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(base), "-vn", "-ar", "48000", "-ac", "2", str(voz)], check=True, stdin=subprocess.DEVNULL)
    out = exp / f"{base.stem.replace('_base', '')}_MUSICA_stem.wav"
    mezclar(voz, MUSICA / p["archivo"], out, dur)
    tempo, bts = beats(MUSICA / p["archivo"])
    (proyecto / "00_DOCS" / "musica.json").write_text(json.dumps({"pista": p, "energia": en, "palabras_por_s": round(wps, 2), "tempo_bpm": round(tempo, 1), "beats": bts[:400]}, ensure_ascii=False, indent=1), encoding="utf-8")
    cred = f"Música: «{p.get('titulo', p['id'])}» — {p.get('autor', '')} · licencia {p['licencia']} · {p.get('url', '')}\n"
    (proyecto / "00_DOCS" / "musica_creditos.txt").write_text(cred, encoding="utf-8")
    log("música:", p["id"], f"({en}, {tempo:.0f} BPM) ->", out)
    return out


def aplicar_musica(mp4_in, stem, mp4_out):
    """Mezcla el stem de música (ya con ducking) con la voz del MP4 y re-normaliza a -14 LUFS / -1 dBTP; el video se copia sin recodificar.
    Así la entrega final lleva la música dentro, y el stem queda aparte por si se quiere cambiar."""
    fg = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[a]"
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(mp4_in), "-i", str(stem), "-filter_complex", fg,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(mp4_out)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    return mp4_out
