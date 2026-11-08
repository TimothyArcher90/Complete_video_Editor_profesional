# MacroWise Video Editor

Edición automática de reels y vídeos, vertical (9:16) y horizontal (16:9), con la línea gráfica MacroWise.

## Uso sin terminal
Arrastra un vídeo sobre **`EDITAR_REEL (arrastra el video aqui).bat`**. Deja todo en `E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\DD-MM-AAAA\<nombre>\06_EXPORT` (orden día-mes-año; si E: no está, usa `Descargas\MacroWise_Editados`).
Para gráficos, mapas y tarjetas a medida, pásale el vídeo a Claude (skill `macrowise-editor`): escribe el `plan.json` y recompone.

## Qué hace (en este orden; el orden importa)
1. **Mide** audio y imagen (`00_DOCS\analisis.json`) y dice qué no se puede arreglar en post.
2. **Transcribe** por palabra (faster-whisper) y detecta cifras, lugares y activos (`03_TRANSCRIPT`).
3. **Corta** silencios largos y muletillas solo entre palabras.
4. **Audio:** graves → ruido → EQ → de-esser → compresión → −14 LUFS / −1 dBTP; si empeora, revierte.
5. **Imagen:** denoise → exposición/color → luz de estudio suave en la cara → nitidez suave al final.
6. **Planos:** tomas de ~3,6 s con encuadre por cara (YuNet) y punch-in alterno; una sola codificación x264 crf 17 slow.
7. **Subtítulos dinámicos** con colores de marca (ASS) + SRT editable + ProRes 4444 con alfa.
8. **Capas de marca:** nombre, título, título grande, cifra con fuente, cierre "Comenta X", panel en cápsula con clips (mapas, gráficas).

## Entregables (`06_EXPORT`)
`*_base.mp4` · `*_subtitulos_ALFA.mov` · `*_graficos_ALFA.mov` · `*_subtitulos.srt/.ass` · `*_REFERENCIA.mp4` (subtítulos como pista, no quemados) · `*_PREVIEW_…NO_ENTREGAR.mp4` (solo para el móvil).

## Requisitos
Python 3.13 con `faster-whisper`, `opencv-python`, `numpy`, `Pillow`; `ffmpeg` en el PATH. Sin GPU de Whisper (faltan las DLL de CUDA 12): corre en CPU, ~1× tiempo real con `medium`.

## Límites conocidos
- Altas luces quemadas y bitrate de origen bajo no se arreglan en post.
- Sin reverberación real: ffmpeg no desreverbera.
- El detector de caras es de OpenCV (YuNet); con varias personas elige la más grande.
- El filtro `ass` de ffmpeg no escribe alfa: el motor lo resuelve con matte + `alphamerge` + `unpremultiply` (ver `componer.ass_a_alfa`).
- ffmpeg 8: `-filter_complex_script` ya no existe; se usa `-/filter_complex`.
