"""Música para reels/videos (v2, 2026-11-18) — la voz manda, la música es cama; todo medido, nada a ojo.

  python -m mw_editor musica PROYECTO [--formato vertical] [--pista ID]
  python -m mw_editor.musica probar VIDEO_SOLO_VOZ PISTA.mp3 SALIDA.mp4 [words.json]     (prueba suelta, sin proyecto)

Qué corrige respecto a v1 (la música quedaba a -33 / -50 LUFS, inaudible, porque se fijaba en LUFS ABSOLUTOS):
 1. El nivel de la música es RELATIVO a la voz MEDIDA: cama sin voz = LUFS_voz - 9; con voz = LUFS_voz - 17 (ducking 8 dB).
 2. El ducking NO es un sidechain con umbral: es una envolvente determinista construida con las palabras (o con un detector de energía):
    baja 0,25 s antes de la voz, sube en 0,9 s tras ella, fusiona pausas < 0,6 s (sin bombeo), curvas coseno.
 3. La música se prepara para ir bajo una voz en un móvil: highpass 100 Hz, -4 dB a 2,5 kHz y -2 dB a 1 kHz (hueco de inteligibilidad),
    lowpass 13 kHz, compresión suave, MONO (el altavoz del teléfono suma canales).
 4. Sincronía: el primer downbeat de la pista cae en el fotograma 0 (la música «arranca con el reel»); bucle por compases con crossfade
    de 120 ms; fade-out de 1,2-2,5 s que termina en el último fotograma.
 5. Puerta medible (`medir_mezcla` -> gates.mezcla_musica): brecha voz/música en LU durante el habla (mediana y p10), arranque y cierre.
Informes: docs/investigacion/2026-11-18_musica_{plataformas,mezcla,sincronia,biblioteca}.md. Los umbrales son ESTIMADOS (sin norma publicada).

Entrega: el stem de música queda APARTE (editable) y se mezcla en un MP4 «con_musica»; además siempre se conserva el MP4 limpio
(para TikTok/Instagram, donde la marca debe añadir el audio desde la biblioteca comercial de la app).
Licencias: solo CC0 / Pixabay / YouTube Audio Library / CC-BY (con crédito en descripción). Prohibido: MusicGen (NC), madmom (modelos NC), Essentia."""
import json
import subprocess
from pathlib import Path

import numpy as np

from .common import FFMPEG, log, probe

SR = 48000
CANDIDATAS = [Path(r"E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\MUSICA"), Path(r"C:\Users\tante\MacroWise\MUSICA")]
LICENCIAS_OK = {"CC0", "Pixabay", "YouTubeAudioLibrary", "CC-BY", "Mixkit"}
BRECHA_CAMA = 9.0        # LU: música sin voz por debajo de la voz (intro/outro)
BRECHA_VOZ = 17.0        # LU: música CON voz por debajo de la voz (16-20 = PASS). ELEGIDA POR DAVID el 2026-11-18 tras A/B 13/15/17 LU
PRE, BAJA, SUBE, GAP_FUSION = 0.12, 0.25, 0.9, 0.6      # s
CADENA_EQ = ("highpass=f=100,equalizer=f=1000:t=q:w=1.2:g=-2,equalizer=f=2500:t=q:w=1.0:g=-4,lowpass=f=13000,"
             "acompressor=threshold=0.1:ratio=2:attack=30:release=300")


def dir_musica():
    for d in CANDIDATAS:
        if (d / "catalogo.json").exists():
            return d
    d = CANDIDATAS[-1]
    d.mkdir(parents=True, exist_ok=True)
    return d


MUSICA = dir_musica()


def cargar_catalogo():
    f = MUSICA / "catalogo.json"
    if not f.exists():
        return []
    cat = json.loads(f.read_text(encoding="utf-8-sig"))
    return [p for p in cat if p.get("licencia") in LICENCIAS_OK and not p.get("content_id") and (MUSICA / p["archivo"]).exists()]


# ───────────────────────── utilidades de audio ─────────────────────────
def _decodificar(src, filtros=None, sr=SR, canales=2):
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-i", str(src), "-vn"]
    if filtros:
        cmd += ["-af", filtros]
    cmd += ["-ar", str(sr), "-ac", str(canales), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[-400:])
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, canales).copy()


def _escribir(ruta, arr, sr=SR):
    import soundfile as sf
    sf.write(str(ruta), arr, sr, subtype="PCM_24")


def _lufs(arr, sr=SR):
    import pyloudnorm as pln
    if len(arr) < int(0.45 * sr):
        return -70.0
    v = pln.Meter(sr).integrated_loudness(arr.astype(np.float64))
    return float(v) if np.isfinite(v) else -70.0


def mascara_habla(palabras, dur, voz=None):
    """Intervalos de habla [(s, e)] fusionando pausas < GAP_FUSION. Con palabras (words_final.json) o, sin ellas, por energía de la voz."""
    iv = []
    if palabras:
        for w in palabras:
            s, e = float(w["s"]), float(w["e"])
            if iv and s - iv[-1][1] < GAP_FUSION:
                iv[-1][1] = max(iv[-1][1], e)
            else:
                iv.append([s, e])
    elif voz is not None:
        m = voz.mean(axis=1) if voz.ndim > 1 else voz
        ven = int(0.05 * SR)
        n = len(m) // ven
        rms = np.sqrt((m[:n * ven].reshape(n, ven) ** 2).mean(axis=1) + 1e-12)
        db = 20 * np.log10(rms)
        act = db > (np.percentile(db, 95) - 28.0)
        t = 0
        while t < n:
            if act[t]:
                a = t
                while t < n and act[t]:
                    t += 1
                s, e = a * 0.05, t * 0.05
                if iv and s - iv[-1][1] < GAP_FUSION:
                    iv[-1][1] = e
                else:
                    iv.append([s, e])
            t += 1
    return [(s, min(e, dur)) for s, e in iv if e > s]


def lufs_de_la_voz(voz, intervalos):
    """LUFS de la voz SOLO en los tramos de habla (la integrada incluye silencios y subestima)."""
    trozos = [voz[int(s * SR):int(e * SR)] for s, e in intervalos if e - s > 0.2]
    return _lufs(np.concatenate(trozos)) if trozos else _lufs(voz)


def curva_ducking(intervalos, dur, duck_db):
    """Ganancia en dB (≤ 0) a 1 kHz: -duck_db en el habla, 0 fuera; bajada coseno BAJA s antes, subida coseno SUBE s después."""
    n = int(dur * 1000) + 1
    t = np.arange(n) / 1000.0
    env = np.zeros(n)
    for s, e in intervalos:
        a0, a1 = s - PRE - BAJA, s - PRE
        b0 = e + PRE
        f_down = (1 - np.cos(np.pi * np.clip((t - a0) / BAJA, 0, 1))) / 2
        f_up = (1 + np.cos(np.pi * np.clip((t - b0) / SUBE, 0, 1))) / 2
        k = np.where(t < a1, f_down, np.where(t < b0, 1.0, f_up))
        env = np.minimum(env, -duck_db * k)
    return t, env


# ───────────────────────── análisis de pista ─────────────────────────
def analizar_pista(ruta, max_s=240):
    """tempo, beats y downbeats (librosa, ISC) + LUFS + densidad de onsets. Se guarda en el catálogo para no recalcular."""
    import librosa
    y, sr = librosa.load(str(ruta), sr=22050, mono=True, duration=max_s)
    env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, fr = librosa.beat.beat_track(onset_envelope=env, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    if tempo > 140 and len(fr) >= 8:                           # librosa tiende al doble tempo: se pliega a la mitad (media-velocidad)
        k = int(np.argmax([env[fr[o::2]].mean() for o in (0, 1)]))
        fr, tempo = fr[k::2], tempo / 2
    bt = librosa.frames_to_time(fr, sr=sr)
    fase = 0
    if len(fr) >= 8:                                           # el compás cuyo beat 1 tiene más energía de onset
        fase = int(np.argmax([env[fr[f::4]].mean() for f in range(4)]))
    down = [float(x) for x in bt[fase::4]]
    dur = float(librosa.get_duration(y=y, sr=sr))
    return {"bpm": round(tempo, 1), "beats": [round(float(x), 3) for x in bt][:400], "downbeats": [round(x, 3) for x in down][:100],
            "primer_downbeat": round(down[0], 3) if down else 0.0, "dur": round(dur, 2),
            "lufs": round(_lufs(_decodificar(ruta)), 1),
            "onset_density": round(float((env > env.mean() + env.std()).sum() / max(dur, 1)), 3), "fuente_beats": "librosa"}


# ───────────────────────── preparación de la pista ─────────────────────────
def preparar_pista(ruta, dur, an):
    """Pista lista para el reel: EQ+mono, arranca en el primer downbeat, bucle por compases con crossfade, fade-out al final."""
    m = _decodificar(ruta, CADENA_EQ)
    m = np.repeat(m.mean(axis=1, keepdims=True), 2, axis=1)    # mono real, duplicado a estéreo
    n = int(dur * SR)
    m = m[int(an.get("primer_downbeat", 0.0) * SR):]
    compas = int(round(4 * 60.0 / (an.get("bpm") or 100.0) * SR))
    L = (len(m) // compas) * compas if len(m) > compas * 2 else len(m)
    base = m[:L]
    xf = min(int(0.12 * SR), len(base) // 4)
    out = base.copy()
    while len(out) < n:                                        # bucle en compás con crossfade de 120 ms
        rampa = np.linspace(0, 1, xf)[:, None]
        out[-xf:] = out[-xf:] * (1 - rampa) + base[:xf] * rampa
        out = np.concatenate([out, base[xf:]])
    out = out[:n].copy()
    fi = int(0.12 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(min(2.5, max(1.2, 0.08 * dur)) * SR)              # fade-out 1,2-2,5 s que termina en el último fotograma
    out[-fo:] *= (np.cos(np.linspace(0, np.pi / 2, fo)) ** 2)[:, None]
    return out


def mezclar_stem(voz, pista, intervalos, dur, an, brecha_cama=BRECHA_CAMA, brecha_voz=BRECHA_VOZ):
    """Devuelve (stem_musica, info). Nivel RELATIVO a la voz medida; ducking determinista por envolvente."""
    l_voz = lufs_de_la_voz(voz, intervalos)
    mus = preparar_pista(pista, dur, an)
    l_mus = _lufs(mus)
    ganancia = (l_voz - brecha_cama) - l_mus                   # cama = voz - 9 LU
    mus = mus * 10 ** (ganancia / 20)
    t, env = curva_ducking(intervalos, dur, brecha_voz - brecha_cama)
    mus = mus * (10 ** (np.interp(np.arange(len(mus)) / SR, t, env) / 20))[:, None]
    pico = float(np.abs(mus).max())
    if pico > 0.7:                                             # el stem nunca recorta
        mus *= 0.7 / pico
    return mus.astype(np.float32), {"lufs_voz": round(l_voz, 1), "lufs_pista_antes": round(l_mus, 1), "ganancia_db": round(ganancia, 1),
                                    "cama_lufs": round(l_voz - brecha_cama, 1), "habla_lufs": round(l_voz - brecha_voz, 1), "duck_db": brecha_voz - brecha_cama}


# ───────────────────────── puerta de calidad ─────────────────────────
def medir_mezcla(voz, stem, intervalos, dur):
    """Brecha voz/música (LU) durante el habla, ventanas de 3 s cada 1 s con ≥ 60 % de habla. Umbrales ESTIMADOS (informe 2026-11-18_musica_mezcla)."""
    import pyloudnorm as pln
    mt = pln.Meter(SR)
    gaps, w = [], 3.0
    for t0 in np.arange(0, max(dur - w, 0.5), 1.0):
        cubre = sum(max(0, min(e, t0 + w) - max(s, t0)) for s, e in intervalos) / w
        if cubre < 0.6:
            continue
        a, b = int(t0 * SR), int((t0 + w) * SR)
        lv = mt.integrated_loudness(voz[a:b].astype(np.float64))
        lm = mt.integrated_loudness(stem[a:b].astype(np.float64))
        if np.isfinite(lv):
            gaps.append(lv - lm if np.isfinite(lm) else 40.0)
    if not gaps:
        return {"estado": "WARN", "detalle": "sin ventanas de habla medibles", "gaps": []}
    med, p10 = float(np.median(gaps)), float(np.percentile(gaps, 10))
    est = "FAIL" if (med < 12 or med > 26 or p10 < 10) else "WARN" if (med < 16 or med > 22 or p10 < 13) else "PASS"
    ini = float(20 * np.log10(np.sqrt((stem[:int(0.5 * SR)] ** 2).mean()) + 1e-9))
    fin = float(20 * np.log10(np.sqrt((stem[-int(0.1 * SR):] ** 2).mean()) + 1e-9))
    if ini < -60 and est == "PASS":
        est = "WARN"
    return {"estado": est, "gap_mediano_lu": round(med, 1), "gap_p10_lu": round(p10, 1), "arranque_dbfs": round(ini, 1), "cierre_dbfs": round(fin, 1),
            "detalle": f"voz−música en habla: mediana {med:.1f} LU (PASS 16-22) · p10 {p10:.1f} · arranque {ini:.0f} dBFS · cierre {fin:.0f} dBFS"}


# ───────────────────────── selección ─────────────────────────
MOOD_OK = {"serio": ("calmo", "ambient", "cinematico"), "informativo": ("neutro", "calmo", "lofi", "ambient"), "ligero": ("energico", "neutro", "lofi")}


def energia_discurso(palabras):
    """Palabras/s medianas por ventanas de 30 s -> baja | media | alta."""
    if not palabras:
        return "media", 0.0
    fin = palabras[-1]["e"]
    vent = sorted(sum(1 for w in palabras if t <= w["s"] < t + 30) / 30.0 for t in range(0, int(fin), 30))
    med = vent[len(vent) // 2] if vent else 0.0
    return ("baja" if med < 2.4 else "alta" if med > 3.3 else "media"), med


def score(reel, p, w=(0.30, 0.25, 0.20, 0.15, 0.10)):
    """Puntuación 0-1 reproducible (pesos ESTIMADOS; calibrar con reels aprobados). Informe 2026-11-18_musica_sincronia §5."""
    obj = {"baja": 88, "media": 102, "alta": 118}[reel["energia"]]
    s_bpm = max(0.0, 1 - abs(p.get("bpm", obj) - obj) / 30)
    s_mood = 1.0 if p.get("mood") in MOOD_OK[reel.get("tono", "informativo")] else 0.3 if p.get("mood") == "neutro" else 0.0
    s_cama = 1 - min(1.0, 0.5 * min(1.0, max(0.0, (p.get("lufs", -16) + 30) / 20)) + 0.5 * min(1.0, p.get("onset_density", 1.0) / 3.0))
    D = reel["D"]
    s_dur = 1.0 if p.get("dur", 0) >= D + 2 else max(0.0, p.get("dur", 0) / (D + 2))
    s_fia = 1.0 if p.get("fuente_beats") == "beat_this" else 0.7
    return w[0] * s_bpm + w[1] * s_mood + w[2] * s_cama + w[3] * s_dur + w[4] * s_fia


def elegir(catalogo, energia, pista_id=None, D=30.0, tono="informativo", excluir=()):
    if pista_id:
        return next((p for p in catalogo if p["id"] == pista_id), None)
    cand = [p for p in catalogo if not p.get("vocal") and p["id"] not in excluir]
    return max(cand, key=lambda p: (round(score({"energia": energia, "D": D, "tono": tono}, p), 4), p["id"])) if cand else None


# ───────────────────────── flujo de proyecto ─────────────────────────
def _analisis_en_catalogo(p):
    if "primer_downbeat" in p and p.get("bpm"):
        return p
    an = analizar_pista(MUSICA / p["archivo"])
    p.update(an)
    f = MUSICA / "catalogo.json"
    todo = json.loads(f.read_text(encoding="utf-8-sig"))
    for q in todo:
        if q["id"] == p["id"]:
            q.update(an)
    f.write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def musicar(proyecto, formato="horizontal", pista_id=None, tono="informativo"):
    proyecto = Path(proyecto)
    cat = cargar_catalogo()
    if not cat:
        raise SystemExit(f"No hay pistas válidas en {MUSICA}\\catalogo.json (licencia permitida + archivo existente). Ver docs/investigacion/2026-11-18_musica_biblioteca.md")
    palabras = json.loads((proyecto / "03_TRANSCRIPT" / "words_final.json").read_text(encoding="utf-8-sig"))
    en, wps = energia_discurso(palabras)
    exp = proyecto / "06_EXPORT"
    base = sorted(exp.glob(f"*_{formato}_v*_base.mp4"))[-1]
    dur = probe(str(base))["duracion"]
    p = _analisis_en_catalogo(elegir(cat, en, pista_id, dur, tono))
    voz = _decodificar(base)
    iv = mascara_habla(palabras, dur, voz)
    stem, info = mezclar_stem(voz, MUSICA / p["archivo"], iv, dur, p)
    out = exp / f"{base.stem.replace('_base', '')}_MUSICA_stem.wav"
    _escribir(out, stem)
    q = medir_mezcla(voz, stem, iv, dur)
    doc = proyecto / "00_DOCS"
    doc.mkdir(exist_ok=True)
    (doc / "musica.json").write_text(json.dumps({"pista": p, "energia": en, "palabras_por_s": round(wps, 2), "nivel": info, "puerta": q,
                                                 "intervalos_habla": [[round(a, 2), round(b, 2)] for a, b in iv]}, ensure_ascii=False, indent=1), encoding="utf-8")
    cred = p.get("atribucion") or f"Música: «{p.get('titulo', p['id'])}» — {p.get('autor', '')} · {p['licencia']} · {p.get('url', '')}"
    (doc / "musica_creditos.txt").write_text(cred + "\n", encoding="utf-8")
    log("música:", p["id"], f"({en}, {p.get('bpm')} BPM) gap {q.get('gap_mediano_lu')} LU -> {q['estado']}", out)
    return out


def aplicar_musica(mp4_in, stem, mp4_out):
    """Mezcla el stem (ya con nivel y ducking) con la voz del MP4 y normaliza a -14 LUFS / -1,5 dBTP; el video se copia sin recodificar."""
    fg = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(mp4_in), "-i", str(stem), "-filter_complex", fg,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(mp4_out)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    return mp4_out


def musica_para_publicar(proyecto, archivos, formato="vertical", tono="informativo", pista_id=None):
    """Genera la versión «con_musica» de cada MP4 de 07_PUBLICAR (el limpio se conserva SIEMPRE: TikTok/Instagram piden añadir el audio comercial
    desde la app; ver docs/investigacion/2026-11-18_musica_plataformas.md). Sin pistas válidas -> no hace nada y lo dice."""
    proyecto = Path(proyecto)
    if not cargar_catalogo():
        return {"estado": "SIN_PISTAS", "detalle": f"no hay pistas válidas en {MUSICA}", "archivos": []}
    stem = musicar(proyecto, formato, pista_id, tono)
    q = json.loads((proyecto / "00_DOCS" / "musica.json").read_text(encoding="utf-8"))["puerta"]
    salidas = []
    for a in archivos:
        a = Path(a)
        if a.suffix.lower() != ".mp4" or a.stem.endswith("_con_musica"):
            continue
        out = a.with_name(a.stem + "_con_musica.mp4")
        aplicar_musica(a, stem, out)
        salidas.append(str(out))
    return {"estado": q["estado"], "detalle": q.get("detalle", ""), "archivos": salidas, "stem": str(stem)}


def probar(video_voz, pista, salida, palabras_json=None, brecha_voz=BRECHA_VOZ):
    """Prueba suelta: un MP4 solo con voz + una pista -> MP4 con música y el informe de la puerta. No toca catálogos."""
    video_voz, pista, salida = Path(video_voz), Path(pista), Path(salida)
    dur = probe(str(video_voz))["duracion"]
    voz = _decodificar(video_voz)
    palabras = json.loads(Path(palabras_json).read_text(encoding="utf-8-sig")) if palabras_json else None
    iv = mascara_habla(palabras, dur, voz)
    an = analizar_pista(pista)
    stem, info = mezclar_stem(voz, pista, iv, dur, an, brecha_voz=brecha_voz)
    stem_wav = salida.with_name(salida.stem + "_stem.wav")
    _escribir(stem_wav, stem)
    aplicar_musica(video_voz, stem_wav, salida)
    q = medir_mezcla(voz, stem, iv, dur)
    print(json.dumps({"pista": pista.name, "bpm": an["bpm"], "primer_downbeat": an["primer_downbeat"], "nivel": info, "puerta": q,
                      "habla": [[round(a, 1), round(b, 1)] for a, b in iv][:12]}, ensure_ascii=False, indent=1))
    return q


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 5 and sys.argv[1] == "probar":
        probar(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None, float(sys.argv[6]) if len(sys.argv) > 6 else BRECHA_VOZ)
    else:
        print(__doc__)
