# Métricas de calidad, voz y denoise/upscale (2026-11-09)

Leyenda: VERIFICADO = leído hoy en LICENSE/README/API de GitHub o página oficial. ESTIMADO = fuente de terceros o criterio mío (los umbrales PASS/WARN/FAIL son ESTIMADOS hasta calibrarlos con material propio).
No se instaló ni modificó código. Limitación: el último commit sale de `pushed_at` de la API de GitHub (fecha del último push, no de un release).

## Ya hecho en gates.py (no duplicar)
- `audio()` mide LUFS y true peak del MP4 entregado: PASS si |LUFS+14| ≤ 1,5 y TP ≤ -0,7 (VERIFICADO leyendo el código).
- Incoherencia a corregir: el texto del detalle dice "≤ −1" pero el código acepta ≤ -0,7. Spotify recomienda ≤ -1 dBTP (VERIFICADO), así que alinear a -1,0 con WARN entre -1,0 y -0,7.
- Falta: LRA, ruido de fondo, calidad de voz sin referencia, métrica de video (VMAF) y puerta antes/después del denoise.

## A. Métricas objetivas

### Sonoridad por plataforma
- Spotify: -14 LUFS integrado, TP ≤ -1 dBTP (≤ -2 si el master es más fuerte que -14). VERIFICADO (support.spotify.com/us/artists/article/loudness-normalization/).
- YouTube / Shorts: -14 LUFS, -1 dBTP. ESTIMADO: sólo fuentes de terceros; la página oficial de YouTube consultada no menciona la cifra.
- Instagram Reels, TikTok, LinkedIn: ninguna publica objetivo. Terceros dan entre -9 y -16. ESTIMADO. Decisión: un único objetivo -14 LUFS / -1 dBTP para todo (coincide con la puerta actual), y no perseguir cifras por red.
- Podcast (Apple): -16 LUFS según terceros. ESTIMADO. Sólo aplica si David entrega audio de podcast aparte.
- Conclusión: la puerta actual (-14 ±1,5) es correcta; lo único que falta es endurecer el pico y añadir LRA.

### pyloudnorm
- URL: https://github.com/csteinmetz1/pyloudnorm. Licencia MIT, copyright C. Steinmetz. VERIFICADO. Último push 2026-01-04, no archivado. VERIFICADO.
- Resuelve: medir LUFS BS.1770 en Python sin ffmpeg, por segmentos.
- Riesgo Windows/Py3.13: bajo (numpy/scipy). ESTIMADO. Dependencia opcional: `ffmpeg -af ebur128=peak=true` ya da lo mismo y es lo que usa `qc._lufs`.
- Integración: usar sólo para curva de sonoridad corta (3 s) y detectar tramos donde la voz cae. Función `gates.voz_estable(wav)`.
  - PASS: desviación estándar de loudness corto < 3 LU. WARN 3-5. FAIL > 5. ESTIMADO.

### EBU R128 / BS.1770 con ffmpeg
- `ffmpeg -i x.mp4 -af ebur128=peak=true -f null -` devuelve I, LRA y TP. Ya integrado en parte.
- Añadir LRA: PASS ≤ 9 LU, WARN 9-12, FAIL > 12. ESTIMADO (talking head sin música).
- TP: PASS ≤ -1,0; WARN -1,0 a -0,7; FAIL > -0,7. ESTIMADO.

### VMAF / libvmaf
- URL: https://github.com/Netflix/vmaf. Licencia BSD-2-Clause-Patent. VERIFICADO. Los modelos no tienen licencia declarada en esa página: revisar `model/` antes de empaquetar. NO VERIFICADO.
- ffmpeg-quality-metrics: https://github.com/slhck/ffmpeg-quality-metrics. MIT; modelos VMAF con licencia propia en `ffmpeg_quality_metrics/vmaf_models/LICENSE`, sin leer. VERIFICADO (MIT) / PENDIENTE (modelos). Último push 2026-10-25. VERIFICADO. Requiere ffmpeg ≥ 7.1 con libvmaf, Python ≥ 3.10; Linux/macOS/Windows. VERIFICADO.
- Riesgo: el ffmpeg 8 de Windows debe traer `--enable-libvmaf`; comprobar con `ffmpeg -filters | findstr libvmaf`. ESTIMADO. VMAF es de referencia completa: sólo sirve para comparar original vs. editado (¿el denoise/upscale destruyó detalle?), no para juzgar un video aislado.
- Integración: `gates.fidelidad(original_recortado, editado)` con VMAF a 1 fps sobre el mismo tramo.
  - PASS media ≥ 90 y mínimo ≥ 75. WARN media 80-90. FAIL < 80. ESTIMADO.
  - Escalar ambos al mismo tamaño antes (`scale=1080:1920`). El video del reel lleva capas: medir sobre `base.mp4` sin capas.

## B. Voz con eco y ruido

| Herramienta | Licencia (verificada) | Último push | Veredicto |
|---|---|---|---|
| DeepFilterNet (github.com/Rikorose/DeepFilterNet) | MIT o Apache-2.0, código Y pesos. VERIFICADO | 2026-11-06 (la API marca NOASSERTION por dual) | Primera opción |
| RNNoise (github.com/xiph/rnnoise) | BSD-3-Clause. VERIFICADO | no consultado | Respaldo ligero; en ffmpeg es `arnndn` |
| Resemble Enhance (github.com/resemble-ai/resemble-enhance) | MIT (código). VERIFICADO. Pesos: NO VERIFICADO | no consultado | Sólo con prueba A/B; puede "reinventar" la voz |
| Demucs (github.com/facebookresearch/demucs) | MIT. VERIFICADO | 2024-04-24, ARCHIVADO. VERIFICADO | Sólo si hay música debajo; no es denoise |
| ffmpeg afftdn / arnndn / highpass | LGPL/GPL de ffmpeg como binario externo | n/a | Base sin dependencias |
| NISQA (github.com/gabrielmittag/NISQA) | Código MIT, PESOS CC BY-NC-SA 4.0. VERIFICADO | no consultado | PROHIBIDO por pesos NC |
| DNSMOS (microsoft/DNS-Challenge) | El repo DNS-Challenge es CC BY 4.0. VERIFICADO. Licencia del código DNSMOS y de sus ONNX: NO VERIFICADO | no consultado | Candidato, falta verificar los ONNX |

### DeepFilterNet
- Resuelve ruido de fondo de voz (full-band 48 kHz) con baja latencia. No elimina reverberación por completo. ESTIMADO.
- Riesgo Windows 11 / Py3.13: el README lista Windows como plataforma soportada pero el entrenamiento y la demo son sólo Linux, y ofrece el binario precompilado `deep-filter`. VERIFICADO. Los wheels de PyTorch para Py3.13 pueden no estar al día: usar el binario `deep-filter.exe` por línea de comandos, no el paquete pip. ESTIMADO.
- Integración: `deep-filter.exe in.wav -o out/` sobre el WAV extraído, mezclar al 70-80 % con el original (`amix`) para no dejar voz metálica. Después `loudnorm` a -14/-1.
- Puerta: comparar antes/después con SNR estimada (ver abajo).

### RNNoise vía ffmpeg
- `arnndn=m=modelo.rnnn:mix=0.8`. Necesita archivo de modelo aparte; licencia de esos modelos (por ejemplo los de GregorR/rnnoise-models): NO VERIFICADA, hay que mirarla.
- Se usa cuando falla DeepFilterNet o para pasada ligera.

### Dereverb (eco de habitación)
- ffmpeg no tiene un dereverb real. `afftdn` + puerta suave (`agate`) reduce cola de eco pero no la elimina. ESTIMADO.
- Resemble Enhance sí la reduce (es su función), con el riesgo de artefactos. Regla: usar el resultado sólo si pasa la puerta de naturalidad (no hay métrica de naturalidad aprobada en licencia; ver NISQA).
- Lo honesto: eco fuerte de origen no se arregla del todo en post. Declararlo en el informe, no fingirlo (regla de David).

### Métrica sin referencia (calidad de voz)
- NISQA queda fuera por pesos NC. DNSMOS parece utilizable pero la licencia de sus ONNX no se pudo comprobar. Hasta verificarla, usar métricas propias con ffmpeg/numpy, que no tienen riesgo:
  - Relación voz/ruido: RMS de los 10 % tramos más silenciosos vs. mediana de la voz activa.
    - PASS ≥ 35 dB, WARN 25-35, FAIL < 25. ESTIMADO.
  - Sala: ratio de energía en la cola tras una pausa (decaimiento en 200 ms). WARN si cae menos de 20 dB. ESTIMADO.
  - Tras DeepFilterNet: SNR debe subir ≥ 6 dB y VMAF-audio no aplica; comparar espectro 100 Hz-8 kHz para confirmar que no se recortó la voz.

## C. Denoise y upscale de video

| Herramienta | Licencia (verificada) | Último push | Cuándo ayuda | Cuándo daña |
|---|---|---|---|---|
| ffmpeg `hqdn3d` | parte de ffmpeg | n/a | Ruido ligero, barato, apto para 1800 fotogramas | Estela en movimiento si luma > 4 |
| ffmpeg `nlmeans` | idem | n/a | Cuadros fijos o clips cortos | Lentísimo; regla de David: nunca sobre 1800 fotogramas |
| ffmpeg `bm3d` | idem | n/a | Ruido fuerte en pocos segundos | Muy lento; sin ventaja en talking head largo. ESTIMADO |
| Real-ESRGAN (github.com/xinntao/Real-ESRGAN) | Código BSD-3. VERIFICADO. Pesos: README no declara licencia. NO VERIFICADO | 2024-08-06. VERIFICADO | Material blando (<720p efectivo); `realesr-general-x4v3` con `-dn` para controlar el denoise | Plastifica la piel; nunca sin mezclar con el original en caras |
| BasicVSR++ (OpenMMLab) | NO VERIFICADO | no consultado | Restauración temporal | Pesado, instalación frágil en Windows. Descartado por ahora |
| RIFE (github.com/hzwer/ECCV2022-RIFE) | MIT, Megvii. VERIFICADO | 2025-09-10. VERIFICADO | Subir fps de B-roll/gráficos | Prohibido sobre el presentador (labios y manos) |

- Real-ESRGAN en Windows: hay ejecutable portable `realesrgan-ncnn-vulkan.exe` (Vulkan, sin CUDA ni PyTorch), release v0.2.5.0 del 2022-04-24. VERIFICADO. No soporta todas las opciones del script Python (por ejemplo `outscale`). VERIFICADO. Sirve para evitar el problema de Py3.13. Verificar la licencia de los pesos `.bin/.param` antes de usarlo comercialmente.
- Orden fijo (CLAUDE.md global): denoise, exposición/color, estabilización sólo si hay temblor, upscale sólo si hay blandura, nitidez al final.

### Puertas numéricas de video (ESTIMADO, calibrar)
- Ruido: desviación estándar de un parche plano 32x32 en la sombra (promedio de 20 cuadros). PASS < 2,0 (en escala 0-255), WARN 2-4, FAIL > 4.
- Nitidez: varianza del Laplaciano en la cara. Debe subir ≤ 25 % respecto al original. Más es sobre-afilado (FAIL > 40 %).
- Fidelidad: VMAF vs. original (arriba).
- Sin mejora posible: altas luces quemadas y bitrate de origen bajo. Ya se declara el bitrate como "límite del origen" (M21); mantenerlo.

## Top por categoría
- A: libvmaf vía ffmpeg-quality-metrics (MIT, comparación original/editado); `ebur128` de ffmpeg con LRA y TP -1,0; pyloudnorm para estabilidad de sonoridad.
- B: DeepFilterNet (binario, MIT/Apache, mezcla 70-80 %); ffmpeg `arnndn`/`afftdn` como respaldo; métricas propias SNR/cola de sala (NISQA descartado por pesos NC).
- C: `hqdn3d` suave por defecto; Real-ESRGAN ncnn `general-x4v3 -dn` sólo si hay blandura y mezclado en cara; RIFE sólo en B-roll.

## Pendiente de verificar antes de integrar
1. Licencia de los ONNX de DNSMOS y de los pesos de Real-ESRGAN y Resemble Enhance.
2. Licencia de los modelos `.rnnn` de RNNoise.
3. Que el ffmpeg 8 instalado traiga libvmaf.
4. Calibrar todos los umbrales ESTIMADOS con el Arca #39 antes de convertirlos en FAIL duro.
