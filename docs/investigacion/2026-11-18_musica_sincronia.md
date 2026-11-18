# Música sincronizada con la edición de un reel hablado (20-90 s) — 2026-11-18

Estado actual (`mw_editor/musica.py`): librosa `beat_track` solo para exponer beats; `ajustar_al_beat` con tol 0,12 s (existe pero NO se usa en cortes); la pista se repite con `aloop` crudo (sin cortar en compás), fade 3 s, elección por mood con la primera coincidencia. `cortes.py` corta por pausas, no por beat. Etiquetas: VERIFICADO = leído en fuente primaria hoy; ESTIMADO = práctica común o inferencia sin fuente que lo mida.

## 1. Detección de tempo/beats/downbeats y licencias

| Herramienta | Licencia (leída) | Veredicto |
|---|---|---|
| librosa | ISC (LICENSE.md, 2013-2026) VERIFICADO | Usar. Beats sí; downbeats no. |
| scipy | BSD (conocida; no la releí) ESTIMADO | Usar para picos/filtros. |
| beat_this (CPJKU, ISMIR 2024) | Código Y pesos MIT, según README VERIFICADO; avisa que algunos datos de entrenamiento tienen licencias limitadas (el usuario debe evaluarlo) | **Recomendado** para downbeats. Requiere PyTorch >= 2.0 + einops, soxr, rotary-embedding-torch. DBN (madmom) es opcional y NO se usa. Python 3.13 no declarado: probar antes. |
| allin1 | Código MIT, pero depende de madmom (instalado desde GitHub), NATTEN (en Windows se compila a mano) y Demucs; licencia de pesos NO indicada VERIFICADO | Descartar: dependencias frágiles y pesos sin licencia. |
| BeatNet | Repo CC-BY-4.0; exige madmom y librosa; pide madmom 0.16.1 con problemas en Python >= 3.10 VERIFICADO | Descartar. |
| madmom | **Corrección a la premisa: el código es BSD, pero los modelos/datos son CC BY-NC-SA 4.0** y piden contactar a Widmer para uso comercial VERIFICADO | Descartar igual (modelos NC; David monetiza). |
| essentia / aubio | AGPL / GPL (declaradas por David; no las releí) | Descartadas. |

Decisión: **librosa por defecto, beat_this como mejora opcional con respaldo a librosa**. Importar beat_this dentro de try/except y, si falla (torch no instalado, Python 3.13), caer a librosa. Pesos de beat_this: confirmar el LICENSE del checkpoint al descargarlo, no solo el README (pendiente; no lo verifiqué en el archivo).

Sin downbeats (librosa): estimarlos con una heurística de compás 4/4: elegir la fase p en {0,1,2,3} que maximice la suma de la energía de onset (o de graves, banda 20-150 Hz) en los beats con índice % 4 == p. Marcar `confianza: baja`. ESTIMADO (heurística común, no la medí aquí).

Detección en el catálogo, no en el momento: calcular tempo/beats/downbeats una vez por pista y guardarlos en `catalogo.json` (`bpm`, `beats`, `downbeats`, `primer_downbeat`, `compases`, `energia`). Así `musicar` no relee audio.

```python
def analizar_pista(ruta, sr=22050):
    y, sr = librosa.load(ruta, sr=sr, mono=True)
    try:                                   # beat_this si está
        from beat_this.inference import File2Beats
        b, d = File2Beats(device="cpu", dbn=False)(ruta)   # segundos
        beats, downs, fuente = list(b), list(d), "beat_this"
    except Exception:
        tempo, fr = librosa.beat.beat_track(y=y, sr=sr, trim=False)
        beats = librosa.frames_to_time(fr, sr=sr)
        downs = estimar_downbeats(y, sr, beats)     # fase de 4 por energia de graves
        fuente = "librosa"
    bpm = 60 / np.median(np.diff(beats))
    # corregir octava: llevar al rango 70-140 BPM
    while bpm < 70: bpm *= 2
    while bpm > 140: bpm /= 2
    return dict(bpm=round(bpm,1), beats=beats, downbeats=downs, fuente=fuente,
                rms=float(np.sqrt(np.mean(y**2))),
                onset_density=len(librosa.onset.onset_detect(y=y, sr=sr)) / (len(y)/sr))
```

Nota de uso: el nombre exacto de la API (`File2Beats`) lo tomo del README de memoria; verificar al integrar.

## 2. Alinear hook y cortes sin que suene forzado

Percepción: el umbral de detectabilidad audio-vídeo es de ~+45 ms (audio adelantado) a -125 ms (audio atrasado); aceptable +90 / -185 ms (ITU-R BT.1359-1) VERIFICADO. Es una norma de sincronía de labios, no de música-corte; aplicarla a música-corte es ESTIMADO. Consecuencia práctica: **si hay que desplazar, que el corte caiga un poco DESPUÉS del beat, nunca antes**. Un corte 0-60 ms tarde se siente "en el beat"; uno 40 ms temprano suena adelantado.

Reglas propuestas (todas ESTIMADO, hay que probarlas con David):

- **Mueve la música, no el vídeo, para el hook.** El discurso manda (la voz no se toca; ya hay regla de no cortar a mitad de palabra). Se desplaza la PISTA para que su primer downbeat caiga en el primer corte/palabra de impacto: `offset = t_hook - downbeat_k` (se recorta el inicio de la pista o se antepone silencio hasta 0,3 s). La precisión sale gratis: es sample-accurate, sin mover cortes.
- **Hook = primeros 1-3 s.** Elegir `t_hook` = inicio de la primera palabra tras el silencio inicial recortado (`plan_cortes` ya deja ~0,25 s). Si la pista tiene intro suave de 1-2 compases, prefiere arrancar EN un downbeat con energía; si no, usa un fade-in de 0,3-0,5 s que llegue a nivel justo en el primer downbeat.
- **Snap de cortes (`cortes.py`):** el corte interno ya es libre dentro de la ventana [fin_palabra+0,05 , inicio_siguiente-0,10]. Se puede mover el punto de corte al beat más cercano SOLO dentro de esa ventana (es la tolerancia natural; típicamente 0,1-0,5 s). Máximo desplazamiento 120 ms (ya es la tol de `ajustar_al_beat`, ≈3 fotogramas a 24 fps), y preferir beats FUERTES (downbeat o beat 3) para cortes de idea, no cada beat.
- **Cuántos cortes snap:** a 90-120 BPM hay un beat cada 0,5-0,67 s; cortar a cada beat sería epiléptico. Snap a lo sumo en 1 de cada 3-4 cortes: los que arrancan una idea nueva (cambio de plano, tarjeta, cifra). Los cortes de pausa/muletilla internos NO se alinean. Sin base medida: ESTIMADO.
- **Gráficos/cifras** (más flexibles que los cortes): su entrada sí se encaja al beat más cercano en +/-150 ms; entrada en downbeat si es el dato clave.
- **Sin snap si el beat grid es poco fiable:** si `fuente == "librosa"` y la confianza de downbeat es baja, snap solo a beats, nunca a downbeat; si el BPM bruto cambia > 3 % entre mitades de la pista (tempo inestable), desactivar el snap.

```python
def planificar_snaps(cortes_t, beats, downs, ventana_por_corte, max_snap=0.12, max_frac=0.3):
    """cortes_t: tiempos de corte de IDEA; ventana_por_corte: (lo, hi) permitido por palabras."""
    out, usados = {}, 0
    cand = []
    for t, (lo, hi) in zip(cortes_t, ventana_por_corte):
        pool = [b for b in downs if lo <= b <= hi and abs(b - t) <= max_snap] or \
               [b for b in beats if lo <= b <= hi and abs(b - t) <= max_snap]
        if pool:
            b = min(pool, key=lambda x: abs(x - t) + (0.0 if x in downs else 0.03))
            cand.append((abs(b - t), t, b))
    cand.sort()
    for d, t, b in cand[: int(len(cortes_t) * max_frac) + 1]:
        out[t] = round(b + 0.015, 3)       # 15 ms DESPUES del beat (audio no adelantado)
    return out
```

## 3. Ajustar la pista a la duración del reel

El reel acabado dura D (conocida tras cortes). La pista natural dura P, con compás T = 4*60/BPM.

Orden de preferencia (menos invasivo primero):

1. **Recorte en frase:** si P >= D + cola, cortar el final en un downbeat (o múltiplo de 4 compases desde el hook) cercano a D. Frase típica = 4 u 8 compases (a 100 BPM: 9,6 s / 19,2 s). El corte natural cae en `downbeat_k` con k = 0 mod 4 (ESTIMADO).
2. **Loop por compases** si P < D: repetir un tramo [downbeat_a, downbeat_b] de longitud de 4 u 8 compases, con crossfade corto (80-150 ms, `acrossfade=d=0.12:c1=qsin:c2=qsin`) puesto EN el downbeat. Se concatena la intro una vez y se repite el cuerpo. Un loop de menos de 1 compás se oye como tartamudeo.
3. **Time-stretch mínimo** solo para que la pista termine en frase sin recortar: tope **±3 %** (a ±5 % el tono sigue pareciendo natural en música percutida; ESTIMADO). Con ffmpeg `atempo` (rango admitido 0,5-100; no leí la sección completa del filtro, VERIFICAR) no cambia el tono ni requiere GPL. Cambia el BPM, así que hay que recalcular beats multiplicando por 1/factor. Preferible a rubberband.
4. **Rubberband:** el filtro `rubberband` de ffmpeg exige un build con `--enable-librubberband`, que arrastra la licencia GPL de la librería (GPL v2+ para uso libre; licencia comercial de pago para productos cerrados) VERIFICADO en breakfastquay.com. La página NO dice nada sobre uso interno de un binario sin redistribuir; el supuesto habitual es que usar un binario GPL para procesar tus propios archivos no obliga a licenciar la SALIDA, y no redistribuir el binario evita las obligaciones de distribución, pero eso es mi lectura, no confirmación del autor ni de abogado (ESTIMADO). Recomendación: **no usarlo**; atempo +/-3 % basta. Si hace falta, usarlo solo en un binario externo no distribuido y anotarlo.

**Cola / fade-out:** la voz termina en t_fin. Dejar que la música llegue a su nivel de "cama" y hacer fade-out de **1,5-2,5 s** que termine entre 0,5 y 1,5 s después de la última palabra, idealmente en un downbeat final (hit/cierre) si la pista lo ofrece. Base actual: fade 3 s (demasiado largo para 20 s de reel: ≥15 % de la duración). Regla propuesta: `fade_out = clamp(0.08*D, 1.2, 2.5)`, curva `qsin` (equipotencia perceptual; `afade=c=qsin`). Valores ESTIMADO. Fade-in: 0,3-0,5 s si el hook arranca en un downbeat fuerte; 1-1,5 s si es cama suave.

Cola de silencio: `plan_cortes` ya deja 0,6 s tras la última palabra; la música debe prolongarse ese tramo y su fade debe cubrirlo.

```python
def ajustar_pista(ruta, an, D, t_hook, t_fin_voz):
    T = 4*60/an["bpm"]
    d0 = next(d for d in an["downbeats"] if d >= 0)              # primer downbeat
    ini = d0 - t_hook if d0 - t_hook >= 0 else 0                  # recorta intro
    pad = max(0, t_hook - d0)                                     # o antepone silencio (<=0.3s)
    cuerpo = D - pad
    fin_nat = [d for d in an["downbeats"] if d - ini >= cuerpo - T and d - ini <= cuerpo + T]
    if an["duracion"] - ini >= cuerpo and fin_nat:
        fin = min(fin_nat, key=lambda d: abs(d - ini - cuerpo))
        return dict(modo="recorte", ini=ini, fin=fin, pad=pad)
    a, b = elegir_loop(an["downbeats"], largo_compases=4)         # segmento repetible
    return dict(modo="loop", ini=ini, a=a, b=b, pad=pad, xfade=0.12)
```

## 4. Estructura de la música en reels educativos/financieros

Evidencia disponible (honestamente escasa):

- **No encontré ningún estudio revisado por pares** que mida el efecto de la sincronía beat-corte, del volumen de música ni del silencio breve sobre la retención en vídeo corto. Las cifras de blogs (p. ej. "15-20 % del volumen de la voz da +5-8 % de retención", FluxNote) no citan estudio: descartarlas.
- Emplifi (análisis de Reels de marcas, proveedor; correlacional, método no descrito): la voz humana en los 3 primeros segundos supera a la música sola, +25 % de retención a 10 s. Sirve para una conclusión: **voz primero, la música es cama, no protagonista**. Evidencia débil.
- Un experimento con 873 participantes (BPS, desmentidos de desinformación en TikTok) halló que los clips con experto + música de tempo alto desmentían mejor que sin música; mide persuasión, no tiempo de visionado, y contradice en parte trabajos previos. No extrapolar a retención.
- Sincronía de labios (ITU-R BT.1359-1): ver §2; normativa, no estudio de retención.

Estructura propuesta (todo ESTIMADO; es práctica común de creadores sin medición en estas fuentes; se valida con A/B de retención propia):

| Tramo | Qué hace la música |
|---|---|
| 0-3 s (hook) | Entra en un downbeat con la primera palabra; fade-in 0,3-0,5 s; nivel normal de cama. |
| 3-70 % (cuerpo) | Cama estable, -18 a -22 dB bajo voz (mantener `DB_BAJO_VOZ` y el sidechain actual; esos valores tampoco están medidos en fuente). Sin melodía que compita con el texto. |
| Frase clave (cifra, conclusión) | Dip de 1-2 dB extra o silencio de 0,4-0,8 s ANTES de la frase y retorno en el siguiente downbeat (efecto "respiro"). Usar 1 o 2 por reel, no más. |
| Cierre | La energía sube 1 compás antes del CTA o final y el fade-out cubre los últimos 1,5-2,5 s (§3). |

El "build" es difícil de lograr con pistas libres de derechos cortas; se aproxima eligiendo pistas con `energia_perfil` creciente (RMS por compases) y recortando el tramo con tendencia ascendente.

## 5. Elegir la pista: score determinista

Hoy `elegir` coge la primera pista del mood. Propuesta: puntuación 0-1 con pesos fijos y desempate por id (reproducible).

Rasgos del reel (de `energia_discurso` + otros): `wps` (palabras/s), `D`, `densidad_cortes` (cortes/min), `tono` (informativo/serio/ligero declarado por David o por el tipo de plantilla).
Rasgos de pista (precalculados en catálogo): `bpm`, `rms`, `onset_density`, `mood`, `dur`, `fiabilidad_beat` (1 si beat_this, 0,7 si librosa), `licencia`.

```python
def score(reel, p, w=(0.30, 0.25, 0.20, 0.15, 0.10)):
    # 1 BPM objetivo ~ f(energia): baja 80-95, media 95-110, alta 110-125   (ESTIMADO)
    obj = {"baja": 88, "media": 102, "alta": 118}[reel["energia"]]
    s_bpm = max(0, 1 - abs(p["bpm"] - obj) / 30)
    # 2 mood coincide con tono
    s_mood = 1.0 if p["mood"] in MOOD_OK[reel["tono"]] else 0.3 if p["mood"] == "neutro" else 0.0
    # 3 energia de la pista modesta: la voz manda (rms y densidad de onsets bajos son mejores)
    s_cama = 1 - min(1, 0.5 * p["rms_norm"] + 0.5 * p["onset_density_norm"])
    # 4 encaje de duracion: sin loop/estiramiento
    s_dur = 1.0 if p["dur"] >= reel["D"] + 2 else max(0, p["dur"] / (reel["D"] + 2))
    # 5 fiabilidad de beats y de licencia
    s_fia = p["fiabilidad_beat"]
    return w[0]*s_bpm + w[1]*s_mood + w[2]*s_cama + w[3]*s_dur + w[4]*s_fia

def elegir_v2(cat, reel, pista_id=None):
    if pista_id: return next(p for p in cat if p["id"] == pista_id)
    return max(cat, key=lambda p: (round(score(reel, p), 4), p["id"]))   # empate -> id
```

Filtros duros antes de puntuar: licencia en `LICENCIAS_OK`, sin Content ID, archivo existente (ya existe); excluir pistas con voz cantada (campo `vocal: false`) porque compiten con el hablante; excluir pistas con `fiabilidad_beat < 0,5`. Los pesos y objetivos de BPM son ESTIMADOS: calibrar con 5-10 reels que David apruebe y ajustar a mano.

## Cambios sugeridos a futuro (no ejecutados; no se modificó código)

1. `catalogo.json`: añadir `bpm, beats, downbeats, dur, rms, onset_density, vocal, fuente_beats` calculados una vez con `analizar_pista`.
2. `musica.py`: `elegir_v2`, `ajustar_pista` (recorte/loop en compás, offset del hook), fade-out `clamp(0,08*D; 1,2; 2,5)` con curva `qsin`, dip de 1-2 dB en la frase clave.
3. `cortes.py`: nueva `planificar_snaps` dentro de la ventana de palabras, con tope del 30 % y offset +15 ms; registro de cuáles cortes se movieron en `00_DOCS/musica.json`.
4. Puerta nueva en `gates.py`: tras mezclar, medir el desfase real entre cortes y beats (media y máximo, ms) y reportarlo; alerta si el máximo > 120 ms o si algún snap es adelantado.
5. Probar beat_this en Python 3.13/Windows antes de depender de él (no lo he ejecutado; solo leí el README).

## Fuentes

- librosa LICENSE (ISC): https://github.com/librosa/librosa/blob/main/LICENSE.md
- beat_this (README, licencia MIT código y pesos): https://github.com/CPJKU/beat_this ; paper https://arxiv.org/abs/2407.21658
- all-in-one: https://github.com/mir-aidj/all-in-one ; BeatNet: https://github.com/mjhydri/BeatNet ; madmom: https://github.com/CPJKU/madmom
- Rubber Band licencias: https://breakfastquay.com/rubberband/license.html
- ffmpeg filtros (acrossfade, afade): https://ffmpeg.org/ffmpeg-filters.html
- ITU-R BT.1359-1: https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-1-199811-I!!PDF-E.pdf
- Emplifi (voz vs música en Reels): https://emplifi.io/resources/facebook-reels-data/ ; BPS (música y debunking): https://bps.org.uk/research-digest/upbeat-tunes-make-tiktoks-expert-debunkers-more-effective
