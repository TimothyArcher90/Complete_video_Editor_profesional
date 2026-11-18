# Música bajo voz en reels de 20-90 s: niveles, ducking, EQ y puerta de calidad

Fecha: 2026-11-18. Etiquetas: VERIFICADO = leído en la fuente citada; ESTIMADO = práctica de oficio o deducción mía, sin fuente primaria que dé el número.

## 0. Diagnóstico del código actual (`musica.py` líneas 71-72 y 106)

- Música: `loudnorm=I=-24:TP=-3` y luego `volume={db+20}dB`. Con db=-20 el volumen suma 0 dB y la música queda en -24 LUFS integrados. Con la voz en torno a -16/-14 LUFS la brecha base ya es 8-10 LU **antes** de duckear.
- Sidechain: `threshold=0.04:ratio=4:attack=50:release=700:makeup=1`. Umbral 0.04 (≈ -28 dBFS) es muy bajo: casi toda la voz lo supera, y con ratio 4 la música baja varios dB más. De ahí los 18 dB medidos (suma de brecha base + ducking).
- Mezcla final: `amix normalize=0` + `loudnorm I=-14:TP=-1`. Correcto, pero una pasada de loudnorm mueve la mezcla entera; la proporción voz/música queda donde la dejó el paso anterior, y nadie la mide.
- Causa raíz: se fija la música por **LUFS absolutos** y no **relativos a la voz medida**. Regla nueva: medir la voz, derivar el objetivo de la música como `LUFS_voz - brecha`.

## 1. Niveles

- Fraunhofer (AES): la diferencia de sonoridad voz-fondo (LD, en LU) preferida por oyentes va de 0 a 13 LU, media 7 LU; mayores de 50 años prefieren ≥ 7 LU. Un dB de nivel ≈ 1 LU. VERIFICADO (resumen de buscador sobre el paper; el PDF de Salford dio 403): https://salford-repository.worktribe.com/OutputFile/1488623
- Las guías de la radiodifusión alemana citadas ahí piden LD ≥ 7 LU (y 16-23 LU en algunos casos). VERIFICADO igual que arriba (el detalle del caso no se pudo confirmar).
- WCAG 2.2 SC 1.4.7 (AAA): fondo ≥ 20 dB bajo la voz. Leído en copia de terceros: https://www.disabilityworld.org/toolkit/standards/wcag/1-4-7-low-or-no-background-audio/ (confirmar en w3.org antes de citarlo a clientes).
- Netflix ancla la sonoridad al **diálogo** (-27 LKFS ±2 LU, BS.1770-1, true peak -2 dBFS), no a la mezcla: https://backlothelp.netflix.com/hc/en-us/articles/360001794307-Netflix-Sound-Mix-Specifications-Best-Practices-v1-5 . VERIFICADO. Idea aplicable: la voz manda, lo demás se mide contra ella.
- Práctica de editores: 10-20 dB bajo la voz mientras habla; narración documental 18-24 dB. ESTIMADO (blogs).

Recomendación para reels (móvil, altavoz de teléfono, ruido ambiente). ESTIMADO, anclado a los datos de arriba:

| Tramo | Música vs voz |
|---|---|
| Con voz (tras ducking) | 16-20 LU por debajo (short-term) |
| Intro/outro sin voz | música sube a 6-10 LU por debajo del nivel de voz (≈ -22 a -24 LUFS short-term si la voz va a -14) |
| Fundido entre ambos | 0,3-0,5 s bajada, 0,8-1,2 s subida |

Por qué 16-20 y no el 7 LU de Fraunhofer: ese estudio es de TV en salón; móvil + ruido + espectador sin audífonos pide más margen, y WCAG AAA (20 dB) marca el techo. Por debajo de ~24 LU la música deja de percibirse (el defecto del -33 LUFS ya visto).

## 2. Ducking

Defaults de `sidechaincompress` (documentación ffmpeg, memoria + tabla de `acompressor` leída en https://ffmpeg.org/ffmpeg-filters.html): level_in 1, mode downward, threshold 0.125 (rango 0.00097563-1), ratio 2 (1-20), attack 20 ms (0.01-2000), release 250 ms (0.01-9000), makeup 1 (1-64), knee 2.82843 (1-8), link average|maximum, detection rms|peak, level_sc 1, mix 1. La sección propia de sidechaincompress no se pudo leer en esta sesión (página de 590 k caracteres); verificar con `ffmpeg -h filter=sidechaincompress`.

Parámetros recomendados para voz humana, música ya normalizada a su nivel base. ESTIMADO:

- `threshold=0.02..0.03` si la voz pasa por el sidechain ya normalizada a ~-16 LUFS (picos RMS ≈ -20 dBFS). Mejor: medir la voz y fijar umbral ≈ 10 dB bajo su RMS medio. No dejar 0.04 sin comprobar.
- `ratio=3` y `knee=4`: reducción de 6-9 dB en voz normal, sin efecto "pared".
- `attack=15`: la voz no debe perder las primeras sílabas contra música (50 ms deja pasar la consonante).
- `release=400`: menos de 250 ms bombea con cada pausa de respiración; más de 800 ms deja la música muerta tras la frase. 700 actual está en el borde alto.
- `link=average`, `detection=rms` (la voz es continua; peak dispara con plosivas).
- `makeup=1` (no compensar: queremos la bajada).
- Objetivo medible: ducking total 6-10 dB. Si pasa de 12 dB, subir threshold o bajar ratio.

Alternativa por VAD con curva de ganancia suave (preferible en reels cortos, determinista, reproducible):

1. Detectar habla con `silencedetect` (ffmpeg, LGPL) o Silero-VAD (MIT) sobre la voz.
2. Generar la envolvente de ganancia: `-duck_db` (p. ej. -8 dB) durante habla, 0 dB fuera; transiciones de 0,3-0,5 s (bajada) y 0,8-1,2 s (subida) con curva coseno; histéresis: fusionar pausas < 0,6 s (evita bombeo).
3. Aplicarla con `volume=...:eval=frame` o expresión por tramos, o con `asendcmd`/`sendcmd`. Ventaja: sin umbral dependiente del material; el reporte conoce de antemano la ganancia aplicada.

Comando A (sidechain, voz del MP4 como control; archivos de ejemplo `voz.wav`, `musica.mp3`, 30 fps no relevantes aquí):

```
ffmpeg -y -i musica.mp3 -i voz.wav -/filter_complex duck.txt -map "[mix]" -c:a pcm_s24le mix.wav
```

con `duck.txt` (UNA línea en el archivo; `-/filter_complex` lee el archivo entero):

```
[0:a]aloop=loop=-1:size=2e9,atrim=0:60,highpass=f=100,equalizer=f=2500:t=q:w=1.0:g=-4,equalizer=f=1000:t=q:w=1.2:g=-2,lowpass=f=12000,acompressor=threshold=0.1:ratio=2:attack=30:release=300,pan=mono|c0=0.5*c0+0.5*c1,loudnorm=I=-32:TP=-3:LRA=7,afade=t=in:st=0:d=0.8,afade=t=out:st=59:d=1.2[m];[1:a]asplit=2[v][vsc];[m][vsc]sidechaincompress=threshold=0.025:ratio=3:attack=15:release=400:knee=4:link=average:detection=rms:makeup=1[d];[v][d]amix=inputs=2:duration=first:normalize=0[mix]
```

Sustituir `-32` por `LUFS_voz - brecha` medido (ver sección 5). Nota: `-/filter_complex duck.txt` es sintaxis de ffmpeg 8 (sustituye a `-filter_complex_script`).

## 3. EQ, compresión, mono

- highpass 80-120 Hz en la música (libera graves que enmascaran la voz y consumen headroom). ESTIMADO.
- Corte de presencia 2-4 kHz: -3 a -5 dB, Q ≈ 1; opcional -2 dB a 800 Hz-1,2 kHz para cuerpo vocal. Zona clave de inteligibilidad de consonantes (1-4 kHz, práctica de mezcla; ESTIMADO).
- lowpass 12-14 kHz para quitar brillo que compite con las sibilantes (opcional).
- Compresión suave de la música (ratio 2, attack 30 ms, release 300 ms): iguala picos para que el ducking se comporte igual en toda la pista. ESTIMADO.
- Mono: el altavoz del teléfono suma canales. Convertir la música a mono antes de mezclar evita cancelaciones de fase al sumarse: `pan=mono|c0=0.5*c0+0.5*c1`. Verificar compatibilidad con `aphasemeter`. Nota: el entregable actual usa `-ac 2` por política; mezclar música en mono y duplicar a estéreo conserva ambas cosas.

## 4. Loudness final

- Objetivo -14 LUFS integrado, true peak ≤ -1 dBTP (ya en `gates.audio`). Es práctica de las plataformas, no norma vinculante; YouTube/Spotify normalizan hacia abajo, no hacia arriba. ESTIMADO sobre práctica; las plataformas no publican garantías.
- Una pasada de loudnorm se queda ~0,5 dB corta; ya resuelto en el proyecto con TP -1,5. Mantener.
- Medir sobre la mezcla final:

```
ffmpeg -hide_banner -nostats -i final.mp4 -af ebur128=peak=true -f null - 2>&1 | findstr /C:"I:" /C:"LRA:" /C:"Peak:"
```

- Para dos pasadas exactas: `loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json` y reinyectar `measured_*` con `linear=true`.

## 5. Métricas para la puerta PASS/WARN/FAIL

### 5.1 Relación voz/música (la métrica principal)

Procedimiento determinista (los stems existen: voz del MP4 y el stem de música ya duckeado de `musica.py`):

1. Short-term (ventana 3 s) de cada stem con `ebur128`:

```
ffmpeg -hide_banner -nostats -i voz.wav -af ebur128=metadata=1,ametadata=print:key=lavfi.r128.S:file=voz_S.txt -f null -
ffmpeg -hide_banner -nostats -i musica_duck.wav -af ebur128=metadata=1,ametadata=print:key=lavfi.r128.S:file=mus_S.txt -f null -
```

   (`lavfi.r128.S` = short-term en LUFS; en Windows rutas con `\:` escapadas o relativas.)
2. En Python: alinear por tiempo, quedarse con las ventanas donde la voz S > -45 LUFS (habla; tomar ≥ 70 % del tiempo hablado) y calcular `LU_gap = S_voz - S_musica` por ventana. Reportar mediana, p10 y mínimo.
3. Ducking aplicado: `duck_db = mediana(S_musica_sin_duck_en_pausas) - mediana(S_musica_durante_habla)`. En pausas largas (> 1,5 s) medir también `S_musica - S_voz_media` para la brecha de intro/outro.

Umbrales propuestos. ESTIMADO, anclados en Fraunhofer (7-13 LU preferidos en TV) + WCAG AAA (20 dB) + margen móvil:

| Medida durante habla (mediana) | PASS | WARN | FAIL |
|---|---|---|---|
| LU_gap | 16-22 | 12-16 o 22-26 | < 12 (tapa) o > 26 (inaudible) |
| p10 de LU_gap | ≥ 13 | 10-13 | < 10 |
| duck_db | 4-10 | 10-13 o 2-4 | > 13 (bombeo) o < 2 con LU_gap < 16 |
| Intro/outro sin voz: S_musica vs nivel de voz | -6 a -12 LU | -3 a -6 o -12 a -16 | > -3 (más fuerte que la voz) |

Si tu directriz es ≥ 15-18 LU, equivale a PASS ≥ 15 y WARN 12-15. Declarar los umbrales como ESTIMADO en el informe de la puerta.

### 5.2 Otras puertas medibles

- Sonoridad final y true peak (ya existe): -14 ±1,5 LUFS, ≤ -1 dBTP.
- Bombeo: desviación estándar de la ganancia de ducking en pausas < 0,6 s; contar subidas/bajadas de > 4 dB en < 1 s: > 2 por 10 s = WARN, > 4 = FAIL. ESTIMADO.
- Comienzo/final de música: S_musica en los primeros 0,5 s > -45 LUFS (la música "arranca" con el reel) y fade-out terminado antes del último fotograma. Binario, determinista.
- Salto abrupto: derivada de S_musica > 6 LU/s fuera de las transiciones planificadas = WARN.
- Inteligibilidad objetiva. Todas necesitan referencia (voz limpia) y se aplican a "mezcla vs voz sola":
  - **STOI/ESTOI** (`pystoi`, MIT según su repo; no confirmado en esta sesión, verificar LICENSE): predice inteligibilidad 0-1. Umbral ESTIMADO: ≥ 0,90 PASS, 0,80-0,90 WARN, < 0,80 FAIL. No hay literatura que fije un corte para música de fondo concreto; solo correlación con tests de inteligibilidad.
  - **ViSQOL** (Apache-2.0 según README de `visqol-python`; el original de Google también Apache-2.0): MOS 1-5 en modo audio/speech; umbral ESTIMADO: ≥ 3,5 PASS. Es calidad percibida, no inteligibilidad.
  - **PESQ**: el estándar ITU P.862 tiene código con restricciones de licencia; el paquete `pesq` de pip es un envoltorio y no confirmé su licencia en esta sesión. No usar en comercial sin revisarla. Además está diseñado para telefonía de voz con degradaciones, no para música mezclada.
  - Recomendación: la puerta principal es la del 5.1 (determinista, sin dependencias nuevas); STOI como confirmación opcional si la licencia se verifica.

## 6. Errores típicos (y su comprobación)

1. Música que tapa: LU_gap < 12 en habla. Cura: normalizar por brecha relativa, no por LUFS absolutos.
2. Bombeo audible: release corto (< 250 ms), threshold demasiado bajo, ratio > 4. Cura: release 400 ms, ratio 3, o VAD con histéresis.
3. Música inaudible (caso -33/-50): normalizar a -24 y además duckear 8 dB y luego `loudnorm` global: la brecha se multiplica. Cura: medir antes de decidir; WARN si LU_gap > 22.
4. Cortes abruptos: sin fade-out ni crossfade de bucle; `aloop` sin crossfade puede dar clic. Cura: afade out 1-1,5 s, bucle con `acrossfade` de 1 s si la pista dura menos que el reel.
5. Música que empieza tarde: arrancar con voz y música a 0 s da cold open plano; mejor 0,3-0,5 s de música sola con fade-in corto o ya presente desde el fotograma 0. Verificar S_musica en 0-0,5 s.
6. Mono/fase: pistas con ensanchador estéreo desaparecen en el altavoz del móvil. Comprobar con `aphasemeter` (fase media > 0).
7. Plosivas disparan el sidechain: usar detection=rms y highpass 80 Hz en la señal de control.
8. Loudnorm de una pasada tras mezclar mueve la proporción: medir la brecha **después** de la mezcla final, sobre stems con la misma ganancia aplicada.

## 7. Cambios concretos propuestos (no aplicados)

- `musica.py`: reemplazar `loudnorm=I=-24` por `loudnorm=I={LUFS_voz - 17}` (medido con ebur128 previo de la voz); `threshold=0.025:ratio=3:attack=15:release=400:knee=4`; añadir highpass + cortes 1-4 kHz + mono antes del sidechain.
- `gates.py`: añadir `mezcla_musica(video)` con la tabla 5.1 y los chequeos de arranque/final; mantener `audio` como está.
- Registrar en el informe del gate: gap mediano, p10, duck_db, y las etiquetas ESTIMADO de los umbrales.

## Fuentes

- https://salford-repository.worktribe.com/OutputFile/1488623 (Fraunhofer/AES, LD en LU; resumen vía búsqueda, PDF dio 403)
- https://backlothelp.netflix.com/hc/en-us/articles/360001794307-Netflix-Sound-Mix-Specifications-Best-Practices-v1-5
- https://www.disabilityworld.org/toolkit/standards/wcag/1-4-7-low-or-no-background-audio/
- https://ffmpeg.org/ffmpeg-filters.html (tabla de acompressor; sidechaincompress no leída)
- https://pypi.org/project/visqol-python/
