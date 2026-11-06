"""F3 Audio: cadena decidida por lo medido. Orden: graves -> ruido -> EQ -> de-esser -> compresión -> -14 LUFS.
Salvaguarda: si el resultado no mejora lo medido, se revierte al original normalizado y se dice."""
import json
import re
from pathlib import Path

from .common import BRAND, FFMPEG, ROOT, ffq, log, run

MODELO_RNNOISE = ROOT / "brand" / "models" / "rnnoise_bd.rnnn"


def cadena(analisis_audio, usar_rnnoise=True):
    """Devuelve (filtros:list[str], decisiones:list[str]) usando las mediciones."""
    f, dec = [], []
    suelo = (analisis_audio or {}).get("suelo_ruido_db")
    f.append("highpass=f=80:poles=2")
    dec.append("highpass 80 Hz (retumbo/ruido de mesa)")
    if suelo is not None and suelo > -58:
        if usar_rnnoise and MODELO_RNNOISE.exists():
            f.append(f"arnndn=m='{ffq(MODELO_RNNOISE)}':mix=0.85")
            dec.append(f"RNNoise (BSD) mix 0.85: suelo medido {suelo:.0f} dB")
        else:
            nr = 10 if suelo < -50 else 14
            f.append(f"afftdn=nr={nr}:nf={max(-70, min(-30, suelo - 4)):.0f}:tn=1")
            dec.append(f"afftdn nr={nr} dB: suelo medido {suelo:.0f} dB")
    else:
        dec.append("sin reducción de ruido: suelo ya limpio")
    f.append("equalizer=f=300:t=q:w=1.2:g=-1.5")          # quita cuerpo 'caja' (suave)
    f.append("equalizer=f=3200:t=q:w=0.9:g=1.8")          # presencia/inteligibilidad
    f.append("deesser=i=0.25:m=0.5:f=0.5")
    f.append("acompressor=threshold=-21dB:ratio=2.8:attack=12:release=160:makeup=2.5")
    dec.append("EQ -1.5 dB@300 Hz, +1.8 dB@3.2 kHz; de-esser leve; compresión 2.8:1")
    return f, dec


def _medir_loudnorm(filtro_previo, src, extra_in=None):
    chain = (filtro_previo + "," if filtro_previo else "") + "loudnorm=I=-14:TP=-1:LRA=11:print_format=json"
    p = run([FFMPEG, "-hide_banner", "-v", "info", *(extra_in or []), "-i", src, "-vn", "-af", chain, "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    return json.loads(m.group(0)) if m else {}


def procesar(src, wav_out, analisis, keep=None, extra_in=None):
    """Audio limpio en WAV 48 kHz 24-bit. Aplica los cortes (keep) antes de la cadena.
    Devuelve dict con decisiones y verificación."""
    from .cortes import filtro_concat

    cortes = ""
    entrada = ["-i", src]
    if keep:
        guion = Path(wav_out).with_suffix(".cut.txt")
        guion.write_text(filtro_concat(keep, video=False, audio=True).replace("[acat]", "[acat]"), encoding="utf-8")
        cortes = f"@{guion}"
    filtros, dec = cadena((analisis or {}).get("audio"))
    pre = ",".join(filtros)

    def render(chain_str, out):
        if keep:
            # filtro_complex con script + cadena
            script = Path(guion).read_text(encoding="utf-8")
            script += f";[acat]{chain_str}[aout]"
            gs = Path(out).with_suffix(".graph.txt")
            gs.write_text(script, encoding="utf-8")
            run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", src, "-/filter_complex", gs, "-map", "[aout]", "-ar", "48000", "-c:a", "pcm_s24le", out])
            gs.unlink(missing_ok=True)
        else:
            run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", src, "-vn", "-af", chain_str, "-ar", "48000", "-c:a", "pcm_s24le", out])

    tmp = Path(wav_out).with_suffix(".pre.wav")
    render(pre, tmp)
    m = _medir_loudnorm("", tmp)
    objetivo = BRAND["audio"]
    ln = (f"loudnorm=I={objetivo['lufs']}:TP={objetivo['tp']}:LRA={objetivo['lra']}"
          f":measured_I={m.get('input_i')}:measured_TP={m.get('input_tp')}:measured_LRA={m.get('input_lra')}"
          f":measured_thresh={m.get('input_thresh')}:offset={m.get('target_offset')}:linear=true")
    run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", tmp, "-af", ln, "-ar", "48000", "-c:a", "pcm_s24le", wav_out])
    tmp.unlink(missing_ok=True)

    # verificación y salvaguarda
    v = _medir_loudnorm("", wav_out)
    final_lufs = float(v.get("input_i", "nan")) if v else None
    final_tp = float(v.get("input_tp", "nan")) if v else None
    ok = final_lufs is not None and abs(final_lufs - objetivo["lufs"]) <= 1.0 and final_tp is not None and final_tp <= objetivo["tp"] + 0.3
    res = {"decisiones": dec, "lufs_final": final_lufs, "pico_final_dbtp": final_tp, "ok": ok, "revertido": False}
    if not ok:
        log("audio fuera de objetivo -> se revierte a original solo normalizado")
        render("anull", tmp)
        m2 = _medir_loudnorm("", tmp)
        ln2 = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m2.get('input_i')}:measured_TP={m2.get('input_tp')}:measured_LRA={m2.get('input_lra')}"
               f":measured_thresh={m2.get('input_thresh')}:offset={m2.get('target_offset')}:linear=true")
        run([FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", tmp, "-af", ln2, "-ar", "48000", "-c:a", "pcm_s24le", wav_out])
        tmp.unlink(missing_ok=True)
        res["revertido"] = True
    return res
