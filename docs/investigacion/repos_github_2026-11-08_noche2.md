# Repos de GitHub, segunda pasada (2026-11-08 noche)

Metodo: licencia, ultimo push, archivado y estrellas salen de `gh api` (8-nov-2026). README leido en los marcados. Corte: licencia MIT/BSD/Apache/ISC/CC-BY, push < 18 meses. No se repiten los de `repos_github_2026-11-08.md`. Limite: la API de busqueda se agoto a mitad; la cobertura de busqueda libre es parcial, la verificacion de cada candidato listado es completa.

## Candidatos (orden por area)

### 1. Encuadre y reframe
1. **Junhua-Liao/Light-ASD** (https://github.com/Junhua-Liao/Light-ASD) - MIT, push 2025-03, 195 estrellas, pesos en el repo (mAP 94 en AVA; README leido). Problema: quien habla en planos con 2+ personas (el hueco que el informe anterior dejo abierto). Regla: puntuacion de hablante activo por cara y fotograma; el reframe sigue al de mayor media movil de 1 s. Esfuerzo: medio (PyTorch, recortes de cara + audio). Veredicto: INTEGRAR solo si hay planos multi-persona; los pesos salen de AVA (anotaciones CC-BY, videos de YouTube): no verificado el impacto comercial, avisar a David. Alternativa TalkNet-ASD (MIT, 2023-10, 520 estrellas): mas pesado, no preferirlo.
2. **AhmedHisham1/pyautoflip** (https://github.com/AhmedHisham1/pyautoflip) - MIT, push 2026-10, 24 estrellas (README leido). Detecta con InsightFace (pesos buffalo de uso no comercial segun su licencia publica; no verificado en este repo) y satura con UNISAL (Apache-2.0). Aporta: trayectoria de crop suavizada, "split-screen" cuando dos sujetos no caben en un 9:16. Veredicto: INSPIRARSE; reimplementar el suavizado (filtro de Kalman o ventana + zona muerta) con las cajas de YuNet que ya tenemos. No integrar por la dependencia InsightFace.
3. **google-ai-edge/mediapipe** (https://github.com/google-ai-edge/mediapipe) - Apache-2.0, push 2026-11-07, 37,6k. Face Landmarker da linea de ojos y menton, no solo caja. Regla determinista: ojos a ~1/3 superior del cuadro (y = 0,33-0,40 de la altura), headroom = distancia cabeza-borde superior 5-12 % de la altura, cabeza centrada a +-5 % del eje en 9:16. Esfuerzo: bajo-medio (sustituir/complementar YuNet solo para ojos). Veredicto: INTEGRAR landmarks para la regla de ojos; la caja de YuNet no da linea de ojos fiable.

### 2. Color medible
4. **colour-science/colour** (https://github.com/colour-science/colour) - BSD-3-Clause, push hoy, 2,7k. Aporta: CCT/Duv, adaptacion cromatica (Bradford), Delta E 2000, lectura/escritura de LUT .cube, funciones OETF Rec.709. Regla: medir CCT del fondo neutro y Delta E 2000 entre dos tomas; aprobar si Delta E < 3 en tonos de piel y neutros entre tomas contiguas (umbral tipico de la industria; el umbral es practica comun, no del repo). Esfuerzo: medio. Veredicto: INTEGRAR como libreria de medicion en el QC de color (no para filtrar).
5. **homm/pillow-lut-tools** (https://github.com/homm/pillow-lut-tools) - MIT, push 2025-09, 58 estrellas. Carga/crea/concatena LUT 3D .cube, genera LUT de ajuste. Regla: generar una LUT unica por toma (balance + exposicion) y aplicarla con `lut3d` de ffmpeg; la LUT queda versionada y reproducible. Esfuerzo: bajo. Veredicto: INTEGRAR (lo justo; colour tambien lo hace, elegir uno: este es mas ligero).
6. **AcademySoftwareFoundation/OpenColorIO** (https://github.com/AcademySoftwareFoundation/OpenColorIO) - BSD-3, push 2026-10, 2,1k. Gestion de color ACES/Rec.709. Veredicto: INSPIRARSE; sobredimensionado para MP4 Rec.709, solo util si llegara material log.
7. **kornia/kornia** (https://github.com/kornia/kornia) - Apache-2.0, push hoy, 12,3k. Conversiones Lab/HSV/YCbCr en torch. Veredicto: DESCARTAR para esto; OpenCV y colour ya cubren. Match de histograma entre tomas: `color-matcher` es GPL-3.0, SOLO INSPIRACION (usar `skimage.exposure.match_histograms`, licencia BSD-3 segun su LICENSE; el campo de API sale NOASSERTION, comprobar el archivo antes de integrar).
   - SkinToneClassifier (ChenglongMa) es GPL-3.0: solo inspiracion para la regla de piel (medir rango Cb 77-127 / Cr 133-173 en YCbCr, regla clasica de la literatura, no del repo).

### 3. Cortes, ritmo, transiciones
8. **UVA-Computer-Vision-Lab/OmniShotCut** (https://github.com/UVA-Computer-Vision-Lab/OmniShotCut) - MIT, push 2026-11-01, 346 (README leido). Detecta corte duro y TIPO de transicion (disolvencia, fundido, wipe); pesos v1.5 en HuggingFace (licencia de pesos no verificada). Problema: nuestro QC de ritmo cuenta movimiento de pantalla compartida y graficos animados como cortes (aprendizaje del 6-nov). Regla: contar solo cortes de camara reales y clasificar la transicion; objetivo largo 4-8 cambios/min. Esfuerzo: medio (GPU/PyTorch). Veredicto: INTEGRAR solo en QC tras verificar licencia de los pesos; el motor actual con PySceneDetect basta mientras tanto.
9. **soCzech/TransNetV2** (https://github.com/soCzech/TransNetV2) - MIT, push 2023-12 (> 18 meses: ABANDONADO por criterio), 1,1k. Veredicto: DESCARTAR a favor de OmniShotCut. AutoShot (MIT, 2023-04) igual.

### 4. Subtitulos, safe zones, legibilidad
10. **tkarabela/pysubs2** (https://github.com/tkarabela/pysubs2) - MIT, push 2026-10-30, 447. Lee/escribe ASS/SRT, estilos, eventos. Regla: validacion estructural del ASS (sin eventos solapados en la misma capa, duracion minima 0,7 s, maximo 2 lineas, <= 42 caracteres/linea, <= 17 car/s; las cifras son convenciones de subtitulado tipo Netflix, no del repo). Esfuerzo: bajo. Veredicto: INTEGRAR en el QC de subtitulos.
11. **libass/libass** (https://github.com/libass/libass) - ISC. Ya en uso via ffmpeg. Nota del propio motor: `\fs` pinta 0,84x lo que mide PIL. Veredicto: nada que integrar.
12. WCAG: `gsnedders/wcag-contrast-ratio` esta ARCHIVADO (MIT, 2022). Veredicto: NO usar; la formula WCAG 2.x (luminancia relativa sRGB, ratio (L1+0,05)/(L2+0,05)) son 8 lineas de codigo propio. Regla: texto >= 4,5:1 (>= 3:1 si es grande, >= 24 px/18,66 px negrita), medido contra el fondo REAL muestreado detras de la caja del texto en cada fotograma del evento, no contra el color de diseno. Esfuerzo: bajo.

### 5. Musica y mezcla
13. **CPJKU/beat_this** (https://github.com/CPJKU/beat_this) - MIT (codigo y pesos; README advierte que parte de los datos de entrenamiento tiene copyright o CC limitada: evaluar), push 2026-05-28, 473 (README leido). Beats y downbeats sin DBN. Problema: librosa da tempo/beats pobres en pistas con cambios de ritmo. Regla: alinear cada corte de camara o aparicion de grafico al beat mas cercano si |desfase| <= 80 ms; si no, no tocar. Esfuerzo: bajo-medio (PyTorch). Veredicto: INTEGRAR como opcion; mantener librosa de respaldo.
14. **urinieto/msaf** (https://github.com/urinieto/msaf) - MIT, push 2026-05-13, 561. Segmentacion de estructura musical. Regla: bajar la musica a ducking base en intro y subir en el puente; puntos de entrada de B-roll. Veredicto: INSPIRARSE (calidad variable, dependencias antiguas).
15. **slhck/ffmpeg-normalize** (https://github.com/slhck/ffmpeg-normalize) - MIT (texto de LICENSE.md leido; la API reporta NOASSERTION), push 2026-10-14, 1,5k. Normalizacion EBU R128 en dos pasadas. Ya hacemos loudnorm; aporta salida de medicion limpia. Veredicto: INSPIRARSE.
16. **csteinmetz1/pyloudnorm** (https://github.com/csteinmetz1/pyloudnorm) - MIT, push 2026-01-04, 790. Medicion BS.1770 en Python. Regla: integrado -14 LUFS (+-1) para redes, true peak <= -1 dBTP, LRA < 11 LU; voz sola -16 a -19 LUFS con musica 18 dB por debajo (la cifra de 18 dB es practica de David y de este motor, no de un estandar). Esfuerzo: bajo. Veredicto: INTEGRAR para medir musica y voz por separado (loudnorm de ffmpeg solo da el total).
17. **Rikorose/DeepFilterNet** (https://github.com/Rikorose/DeepFilterNet) - doble licencia MIT o Apache-2.0 (README leido; codigo y pesos), push 2026-11-06, 5k. Denoise de voz en tiempo real, ofrece plugin ffmpeg/LADSPA. Regla: aplicar solo si el piso de ruido medido (percentil 10 de RMS en pausas) > -50 dBFS. Esfuerzo: medio. Veredicto: INTEGRAR como paso condicional.
   - Descartados por licencia: spotify/pedalboard (GPL-3.0), MTG/essentia (AGPL-3.0), BeatNet (CC-BY-4.0 pero pesos sin verificar; inferior a Beat This en uso), demucs (MIT, archivo no necesario: no hace falta separar stems de musica ya curada).

### 6. QC de entrega
18. **slhck/ffmpeg-quality-metrics** (https://github.com/slhck/ffmpeg-quality-metrics) - MIT, push 2026-10-25, 561 (README leido). PSNR/SSIM/VMAF por fotograma contra una referencia. Regla: tras el encode final, VMAF >= 93 y PSNR minimo >= 35 dB frente al maestro; bajar de ahi bloquea la entrega. Los umbrales son convencion de ingenieria, no del repo. VMAF de Netflix: licencia reportada NOASSERTION (BSD-2-Clause+Patent segun su archivo, no verificado en esta pasada). Esfuerzo: bajo (ya depende de ffmpeg con libvmaf). Veredicto: INTEGRAR.
19. **UVA/OmniShotCut + YuNet (ya existente)**: colision texto-cara ya cubierta por `evitar_cara.py`; ningun repo nuevo mejora eso.

### 7. Silencios, muletillas, transcripcion
20. **snakers4/silero-vad** (https://github.com/snakers4/silero-vad) - MIT, push 2026-10-22, 10,6k. VAD neural, CPU, ~1 ms/chunk. Problema: cortes de silencio por umbral de volumen cortan colas de palabras o dejan respiraciones. Regla: pausas = tramos sin voz > 350-500 ms; conservar 120-180 ms de respiracion a cada lado (valores razonables, ajustables; no del repo). Esfuerzo: bajo. Veredicto: INTEGRAR (mejor que `silencedetect`).
21. **m-bain/whisperX** (https://github.com/m-bain/whisperX) - BSD-2, push 2026-10-22, 25,1k. Ya en la lista pendiente anterior. Alineacion por wav2vec2: tiempos por palabra mas precisos para cortar sin morder palabras. Evitar la diarizacion (usa pyannote, pesos con terminos propios). Esfuerzo: medio. Veredicto: INTEGRAR solo la alineacion.
22. **clp-research/deep_disfluency** (MIT, push 2026-04, 61 estrellas) y **dougcalobrisi/erm** (MIT, push 2026-08, 112, no leido el README): deteccion de disfluencias sobre texto. Veredicto: INSPIRARSE; mas robusto detectar "eh/um/este/o sea" por lista cerrada de palabras sobre la transcripcion de faster-whisper con `initial_prompt` que las conserve.

## Descartados por licencia/estado (solo inspiracion)
color-matcher (GPL-3.0), SkinToneClassifier (GPL-3.0), pedalboard (GPL-3.0), essentia (AGPL-3.0), whisper-timestamped (AGPL-3.0), insightface (pesos de uso no comercial por su licencia publica; no verificado), wcag-contrast-ratio (archivado), TransNetV2/AutoShot (>18 meses), reframe de kaloyaan (es una camara de papel electronico, falso positivo de la busqueda).

## Hallazgos honestos
- Ningun repo permisivo y mantenido resuelve "reframe 9:16 con regla de ojos/headroom". Lo mas cercano (pyautoflip) arrastra InsightFace. Se construye con YuNet + MediaPipe landmarks.
- Los umbrales (Delta E < 3, VMAF >= 93, 4,5:1) son estandares o convenciones; el repo aporta la medicion, no el umbral.
- Licencia de los pesos de OmniShotCut y Light-ASD NO verificada; tratarlos como pendientes antes de monetizar.

## Top 5 priorizado (valor / esfuerzo)
1. **silero-vad + WhisperX (solo alineacion)**: cortes de silencio/muletillas que no muerden palabras. Bajo-medio.
2. **ffmpeg-quality-metrics + pyloudnorm + validador WCAG propio**: puerta de calidad de entrega 100 % medible. Bajo.
3. **MediaPipe Face Landmarker**: regla de ojos/headroom/tercios sobre el reframe. Bajo-medio.
4. **colour (BSD-3) + pillow-lut-tools**: medir CCT/Delta E entre tomas y generar una LUT por toma. Medio.
5. **OmniShotCut (tras verificar pesos) o, mientras, PySceneDetect ya instalado**: QC de ritmo con cortes reales; con DeepFilterNet como paso condicional de denoise de voz si el piso de ruido lo pide.
