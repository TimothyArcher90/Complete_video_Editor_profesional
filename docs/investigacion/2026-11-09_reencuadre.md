# Reencuadre automático 16:9 -> 9:16 (presentador, regla de ojos) - 2026-11-09

Etiquetas: VERIFICADO = leído hoy en la fuente primaria (API de GitHub, LICENSE raw, README, PyPI). ESTIMADO = conocimiento previo o inferencia, sin lectura hoy.

## Estado del motor (no duplicar)
- `planos.py::_encuadre_cara` ya implementa la regla: ojos en 30-38 % del alto (`OJOS_OBJ`), pelo = 0,35 de la caja YuNet, aire mínimo 3,5 % (`AIRE`), cara <= 32 % del alto (`CARA_MAX`), zoom alterno 1.0/1.12. VERIFICADO (leído).
- Aire pedido por David: 8-15 % sobre la cabeza. El motor usa 3,5 %. **Hueco real a decidir**: subir `AIRE` a 0,08 deja `e_min` mayor y empuja a más zoom/relleno; hoy no está aplicado. Es un cambio de parámetro, no de librería.
- Lo que NO hay: (a) landmarks reales de ojos (los ojos salen de YuNet: puntos 5 landmarks), (b) suavizado temporal entre muestras de una misma toma (se usa mediana/percentiles por toma, el recorte es fijo por toma; no hay deriva intra-toma), (c) filtro anti-tirón si la cara se mueve mucho dentro de una toma larga.

## Candidatos

### 1. OpenCV YuNet (ya usado) - MANTENER
- URL: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Licencia: MIT, (c) Shiqi Yu 2020 - LICENSE raw VERIFICADO. Pesos: `face_detection_yunet_2023mar.onnx` y nuevo `face_detection_yunet_2026may.onnx` (listado API VERIFICADO; mejoras del 2026may NO verificadas).
- Código fuente original libfacedetection: BSD-3-Clause (LICENSE raw VERIFICADO; la API devuelve NOASSERTION por el formato del archivo). Último push 2026-06-28. VERIFICADO.
- Resuelve: caja + 5 puntos (ojos, nariz, comisuras), rápido en CPU.
- Riesgo: 5 puntos dan el centro de los ojos con ruido de ~2 % del alto (valor ya anotado en planos.py como holgura); no hay iris ni párpados.
- Integración: probar el onnx `2026may` en `verificar_encuadre.caras_en` con la misma API `FaceDetectorYN`; A/B contra el 2023mar con la métrica ya existente (solape cara/capa y jitter de ojos). Umbrales: `score_threshold` 0,7, `nms` 0,3, 4 fps.

### 2. MediaPipe Face Landmarker - RECOMENDADO para afinar ojos
- URL: https://github.com/google-ai-edge/mediapipe ; docs https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- Licencia código: Apache-2.0 (LICENSE raw y API VERIFICADO). Último push 2026-11-07. VERIFICADO.
- Modelo `face_landmarker.task`: 478 landmarks 3D, 52 blendshapes opcionales, detector BlazeFace 192x192 + landmarks 256x256 (VERIFICADO en docs). La página NO declara licencia de los pesos: solo enlaza model cards (VERIFICADO que no la declara). La licencia de los pesos en la práctica es Apache-2.0 por el repo, pero **no confirmada en un LICENSE específico del modelo -> riesgo legal bajo-medio, pedir confirmación antes de monetizar en serio**. ESTIMADO.
- Wheel `mediapipe` 1.2.2, licencia Apache-2.0, clasificadores Python 3.9-3.14 (PyPI VERIFICADO); **no se pudo confirmar un wheel cp313 win_amd64** (la lista visible solo llegaba a cp312). Verificar con `pip download mediapipe --only-binary=:all:` antes de depender de ello.
- Resuelve: ojos precisos (puntos de iris 468-477 + párpados), cabeza (frente/mentón con malla 3D), pose (matriz 4x4). Permite medir ojos y aire real, no por heurística de caja.
- Riesgo: dependencia pesada (protobuf, numpy<2 en versiones antiguas; revisar con OpenCV 5), VIDEO mode exige timestamps crecientes en ms.
- Integración concreta: nueva función `landmarks_ojos(video, fps=4, desde, hasta)` en `verificar_encuadre.py` que devuelva `(t, cx, y_ojos, y_frente, y_menton)`. `RunningMode.VIDEO`, `num_faces=1`, `min_face_detection_confidence=0.5`, `min_tracking_confidence=0.5`, blendshapes off. y_ojos = media de los centros de iris (468-472 y 473-477); y_frente = landmark 10, y_menton = 152. Alimentar `_stats_cara` en lugar de `PELO*hf` (la constante 0,35 se sustituye por la frente real; el pelo se estima 0,12 del alto de cara sobre el landmark 10 - ESTIMADO). Fallback automático a YuNet si no hay detección.

### 3. One-Euro filter (suavizado temporal) - RECOMENDADO
- Original: https://gery.casiez.net/1euro/ (Casiez, Roussel, Vogel, CHI 2012). Versiones: Python/C++/JS en BSD; C y C++ templates en MIT (VERIFICADO en la página). Implementación independiente en Python: https://github.com/jaantollander/OneEuroFilter, MIT (API VERIFICADO), pero último push 2023-03-28 (poco mantenimiento; son ~25 líneas, conviene copiar el algoritmo propio con la fórmula del paper).
- Resuelve: suavizar `cx` y `y0` del recorte con retardo bajo cuando el presentador se mueve y sin jitter cuando está quieto. Es lo adecuado para cámara virtual.
- Riesgo: mal ajustado produce lag o deriva; se afina a ojo. Procedimiento oficial (VERIFICADO): beta=0, `mincutoff` ~1 Hz, bajar `mincutoff` hasta quitar jitter parado; luego subir `beta` (0,001 / 0,0001 y x10) hasta que desaparezca el lag al moverse rápido.
- Integración: dentro de una toma larga (> 6 s) calcular el recorte por ventana de 0,5 s en lugar de la mediana de toda la toma, y pasarlo por One-Euro. Parámetros de partida (ESTIMADO, para 4 fps, normalizados al ancho de salida): `mincutoff=0.4`, `beta=0.02`, `dcutoff=1.0`. Limitar además la velocidad del recorte a <= 4 % del ancho de salida por segundo y mantener el recorte quieto si el desplazamiento acumulado < 1,5 % (zona muerta). Cortes entre tomas: reiniciar el filtro (no interpolar a través de un corte).

### 4. Google AutoFlip (MediaPipe) - NO USAR, solo inspiración
- URL: https://github.com/google-ai-edge/mediapipe/tree/master/mediapipe/examples/desktop/autoflip
- Licencia: Apache-2.0 (la del repo, VERIFICADO). Existe aún; último commit tocando la carpeta 2026-11-05 (cambio de BUILD, VERIFICADO), o sea mantenimiento mínimo.
- README dice que solo funciona con OpenCV 3 y se compila con Bazel (VERIFICADO). Inviable en Windows + OpenCV 5.
- Aporta ideas (ESTIMADO, del blog de Google 2020): detección de escenas, tres modos de cámara (estática / seguimiento / mezcla) y trayectoria suavizada. Ya cubierto por `planos.tomas` + un One-Euro.

### 5. InsightFace - DESCARTADO
- URL: https://github.com/deepinsight/insightface . Sin SPDX en la API (license null, VERIFICADO), último push 2026-10-19.
- README (VERIFICADO): "The code of InsightFace is released under the MIT License", pero los datos de entrenamiento y los modelos "are available for non-commercial research purposes only", y los modelos descargados por la librería siguen esa política. **Pesos no comerciales -> prohibido por la regla de David** (mismo problema de pesos != código).

### 6. SmoothNet - DESCARTADO (sobredimensionado)
- URL: https://github.com/cure-lab/SmoothNet . Apache-2.0, último push 2023-05-06 (VERIFICADO). Red para suavizar series de pose humana 3D/2D en lote; para una trayectoria de 1 punto es excesiva, añade PyTorch y sin mantenimiento. One-Euro o Kalman hacen lo mismo con 20 líneas.

### 7. Kalman (filtro de trayectoria) - ALTERNATIVA
- `cv2.KalmanFilter` (OpenCV, Apache-2.0, ya instalado). Modelo de velocidad constante 4 estados (x, y, vx, vy) con `processNoiseCov` 1e-3 y `measurementNoiseCov` 1e-1 (ESTIMADO). Más lag que One-Euro en cambios bruscos; sirve si se quiere predecir durante pérdida de detección (1-2 s). Opcional.

### 8. Saliencia (ViNet, etc.) - NO NECESARIA
- Para un presentador a cámara el sujeto ya está definido (cara). La saliencia sirve en tomas sin cara (gráficos, pantalla compartida). No evaluada la licencia de ViNet hoy: NO VERIFICADO, no recomendada hasta hacerlo.

### 9. Repos "auto reframe" 2025-26
- Búsqueda web (VERIFICADO que se hizo): no apareció un repo permisivo, mantenido y de calidad que resuelva regla de ojos + suavizado. El único candidato listado, https://github.com/a3ro-dev/autofaceframing, es MIT (API VERIFICADO), 1 estrella, push 2025-08-06, pensado para webcam en tiempo real: sin valor útil para offline. Coincide con la nota del 2026-11-08 del CLAUDE.md del proyecto ("ningún repo permisivo resuelve el reframe con regla de ojos").

## Recomendación de integración (orden)
1. Subir `AIRE` a 0,08 (con gate de `gates.encuadre` ajustado a 8-15 %) y revisar cuántas tomas pasan a nivel 3 (relleno): medir antes de decidir.
2. Probar `face_detection_yunet_2026may.onnx` frente a 2023mar con la métrica de jitter de ojos.
3. Añadir MediaPipe Face Landmarker como fuente de ojos/frente/mentón con fallback YuNet, tras confirmar wheel cp313 y licencia de los pesos.
4. Suavizado One-Euro + zona muerta + límite de velocidad dentro de tomas largas.

## Fuera de alcance / no verificado
- Wheel cp313 win_amd64 de mediapipe; licencia explícita de los pesos de Face Landmarker; mejoras del onnx 2026may; licencia de ViNet.
- No se instaló ni se ejecutó nada; no se modificó código.
