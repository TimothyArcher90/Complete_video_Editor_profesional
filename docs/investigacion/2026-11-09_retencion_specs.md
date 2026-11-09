# Retención y especificaciones 2026 (contenido financiero/macro, presentador a cámara)
Fecha: 2026-11-09. Etiquetas: VERIFICADO = leído en fuente oficial o LICENSE real; ESTIMADO = terceros, blogs de herramientas o inferencia. No se instaló ni modificó código.

## 0. Límite de la evidencia (leer primero)
- Ninguna plataforma publica umbrales de retención ni de ritmo de cortes. Todo número de "retención a 3 s", "cortes/min" o "duración óptima" viene de blogs de herramientas (Opus, Quso, Bytecap...) sin metodología: ESTIMADO, confianza baja. No encontré estudio primario que fije la toma ideal en contenido financiero.
- Lo único oficial: YouTube Shorts mide "Stayed to watch / Viewed vs swiped away" y calcula duración media solo sobre quienes se quedaron (glosario creatoressentials.com, tercero que cita a YouTube; sin umbral oficial). Hook y retención se miden aparte.
- Cifras sin fuente verificable (no usar como umbral): "70-85 % a 3 s = 2,2x vistas", "decisión de scroll 1,4-2,3 s", "TikTok media 3,75 s".

## 1. Retención y edición
### 1.1 Ritmo y hook
- Consenso cualitativo de blogs, ESTIMADO: cambio visual (corte, zoom, gráfico, texto) cada 2-4 s en reel; cada 5-8 s en largo con presentador.
- Medición propia (docs/investigacion/referencias_largo.md): 2 largos de referencia, 3-7 cambios/min, plano mediano 4,5-5,9 s. Muestra n=2 y el detector cuenta gráficos: ESTIMADO.
- Hook de 3 s (práctica de creadores, ESTIMADO): afirmación o cifra concreta en la primera frase, sin saludo ni logo; primer evento visual/texto antes de 1,5 s; contradicción o pregunta que se responde al cierre; sin silencio inicial.
- Reel 30-60 s (ESTIMADO): hook 0-3 s, tensión 3-15 s, 2-3 puntos con una cifra cada uno, cierre citable, CTA breve, un único mensaje.

### 1.2 Subtítulos
- Velocidad: la comprensión cae al pasar de 12 a 20 a 28 caracteres/s; recomendado < 20 cps (Kruger, Wisniewska y Liao, Applied Psycholinguistics 2021, cambridge.org). Con 74 espectadores a 12/16/20 cps la mayoría seguía bien a 20; los lentos provocan relecturas (Szarkowska y Gerber-Morón, PLoS ONE 2018). VERIFICADO como estudios. Rango útil 12-20 cps.
- Los subtítulos de palabra (2-4 palabras) son estilo, no accesibilidad: hace falta además la pista SRT normal.
- Efecto del resaltado de palabra clave en retención: sin estudio primario hallado. ESTIMADO.
- Tamaño: WCAG llama "texto grande" a 18 pt (≈24 px) o 14 pt negrita. No hay norma en píxeles para vídeo vertical; el 4 % del alto del motor es criterio propio, ESTIMADO.

## 2. Herramientas (LICENSE leída en el repo)
- PySceneDetect: BSD-3-Clause. VERIFICADO. Permitida. ContentDetector/AdaptiveDetector mejoran el scdet de ffmpeg.
- silero-vad: MIT (Silero Team). VERIFICADO. Permitida. VAD para pausas; puede sustituir el umbral de dB de qc_extra.
- WhisperX: BSD-2-Clause. VERIFICADO. Código permitido; el alineamiento usa modelos wav2vec2/pyannote con licencias propias: revisar cada peso.
- auto-editor: Unlicense. VERIFICADO. Permitida; útil como referencia de márgenes de corte.
- pyannote-audio: código MIT (CNRS). VERIFICADO. Los pesos del hub exigen aceptar términos/token: verificar la tarjeta de cada modelo antes de uso comercial.
- whisper-timestamped: AGPL-3.0. VERIFICADO. PROHIBIDA. Usar faster-whisper (ya en el motor) o WhisperX.
- Muletillas en español: no hay repo permisivo dedicado. Lista práctica ESTIMADA: eh, ehm, mm, este, o sea, bueno, pues, digamos, "¿no?", "¿sí?", "como que". Solo eh/ehm/mm son seguras de cortar solas; las léxicas (este, o sea, pues) exigen duración < 0,35 s, pausa alrededor y baja energía. Whisper suele omitirlas al transcribir: detectar con VAD + energía, no solo texto.

## 3. Especificaciones oficiales 2026
### YouTube (support.google.com/youtube/answer/1722171) VERIFICADO
- MP4 con moov al inicio, sin edit lists. H.264 High, CABAC, 2 B-frames, GOP cerrado de medio frame rate, 4:2:0, VBR.
- Bitrate SDR 24-30 fps: 1080p 8 Mbps; 1440p 16; 4K 35-45; 720p 5. Audio AAC-LC u Opus, 48 kHz, estéreo 384 kbps. Color BT.709.
- Shorts: hasta 3 min, cuadrado o vertical (desde 15-oct-2024), máx. 1080p en subida (support.google.com/youtube/answer/12779649 y /15424877). VERIFICADO.
- Safe zone de Shorts: YouTube no publica cifras. Terceros: ~210 px arriba / ~270 px abajo. ESTIMADO.
### Instagram / Meta
- Reels orgánico: relación 1,91:1 a 9:16, mínimo 720 px, mínimo 30 fps (help.instagram.com/1038071743007909). VERIFICADO.
- Reel impulsado: ≤ 90 s y 9:16 (help.instagram.com/570215404599013). VERIFICADO.
- Anuncios de Reels (facebook.com/business/ads-guide): dejar libre ≈14 % arriba, 35 % abajo, 6 % por lado. VERIFICADO solo para anuncios; en 1080x1920 = 269 / 672 / 65 px. Duración orgánica máxima: no confirmada en fuente oficial.
### TikTok (ads.tiktok.com/help/article/video-ads-specifications) VERIFICADO (anuncios)
- 9:16 ≥ 540x960; MP4/MOV/MPEG/3GP/AVI; hasta 10 min; 500 MB; bitrate mínimo 516 kbps. Safe zone: plantillas descargables, sin píxeles en texto (cifras en px de terceros: ESTIMADO). Orgánico no verificado.
### LinkedIn (linkedin.com/help/linkedin/answer/a1311816) VERIFICADO
- MP4; 3 s a 10 min (páginas); 5 GB máx.; 256x144 a 4096x2304; relación 1:2,4 a 2,4:1; 10-60 fps; 192 kbps-30 Mbps. Miembros: 10 min móvil, 15 min escritorio (answer/a527229). Anuncios: 75 KB-500 MB, 1920x1080 recomendado (answer/a424737).
### Miniaturas
- No verifiqué specs oficiales. La cifra habitual de YouTube (1280x720, 16:9, ≤ 2 MB) es de terceros: ESTIMADO.

## 4. Accesibilidad
- Subtítulos como pista aparte: SRT (universal) y WebVTT (W3C), nunca solo quemados (regla de David). Soporte de subida de SRT por plataforma: YouTube sí; LinkedIn y TikTok según tipo de cuenta/anuncio, sin confirmar línea a línea: ESTIMADO.
- Contraste WCAG 2.2 AA: 4,5:1 texto normal, 3:1 texto grande; AAA 7:1 (w3.org/WAI/WCAG22/Understanding/contrast-minimum). VERIFICADO.
- Sobre vídeo el contraste cambia por fotograma: medir contra el píxel real (como M09) y exigir contorno o caja opaca.

## 5. Contraste con los umbrales del motor
Revisados: metricas.py (PLATAFORMAS), qc_extra.py (m_ritmo, m_entrega), cortes.py, subs.py, zonas.py, preset_largo.py.

Alineado con la evidencia
- Bitrate recomendado 8 Mbps 1080p ≤ 30 fps (m_entrega) = tabla YouTube.
- Zona "universal" arriba 269 / abajo 672 coincide exactamente con 14 % y 35 % de Meta: ahora se puede marcar oficial para anuncios (hoy dice "terceros").
- Encode (crf 17 slow, AAC 48 kHz, moov al inicio, BT.709) coincide con YouTube.
- Cortes solo entre palabras con micro-fundido: correcto.

Umbrales dudosos o mal
1. youtube_shorts "optimo" 20-50 s: el máximo 180 s es oficial, pero el óptimo es opinión; no usarlo como umbral duro.
2. instagram_reels max 180 s: no verificado. Lo oficial hallado es 90 s para impulsados. Marcar fuente o bajar a 90 si se pauta.
3. tiktok max 600 s: es el límite de anuncios; la etiqueta debería decir "oficial solo anuncios".
4. linkedin max 600 s: conservador y correcto para móvil; escritorio permite 15 min.
5. Subtítulos: no existe medidor de caracteres por segundo. El agrupador limita palabras (3-4) y duración (1,25-1,7 s), pero nada comprueba cps ni líneas. Para la pista SRT hay que exigir 12-20 cps y ≤ 2 líneas. Falta métrica.
6. Cortes de silencio (pausa_max 0,45 s, deja 0,16 s): sin evidencia primaria. 0,16 s puede sonar atropellado tras una cifra; probar 0,20-0,30 s. ESTIMADO, validar de oído.
7. m_ritmo reel (12-30 cortes/min) y M01 ≤ 1,5 s: razonables pero ESTIMADO. En largo, M01 ≤ 5 s es holgado; ≤ 3 s sería más exigente.
8. Sonoridad -14 LUFS / ≤ -1 dBTP: práctica de industria, no verificada en documentación oficial reciente. ESTIMADO. Medir siempre sobre el MP4 final (ya lo hace gates).
9. Ritmo largo (objetivo 4-8 cambios/min): sale de n=2 referencias; declararlo.
10. Márgenes laterales: universal usa 122 izq / 242 der; Meta oficial dice 65 px por lado. El motor es más estricto: seguro, pero resta ancho a los subtítulos.

## 6. Siguientes pasos
1. Métrica cps/líneas para la pista SRT (12-20 cps, ≤ 2 líneas).
2. Evaluar PySceneDetect y silero-vad (ambas permisivas) para cortes y pausas.
3. Corregir etiquetas de confianza en metricas.PLATAFORMAS (IG 90/180, TikTok orgánico vs anuncio).
4. Verificar pendientes oficiales: duración orgánica de Reels y TikTok, miniaturas, soporte SRT por plataforma.
