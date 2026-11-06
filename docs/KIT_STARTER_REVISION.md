# Revisión del «Free AI Video Editor Starter Kit» (25-oct-2026) y qué se aplicó

Fuente: https://docs.google.com/document/d/1nzXe3OBqps4v5puTv_rGI0YyJ2dTuE7w8qkh4aZEg5g/mobilebasic (leído 2026-11-06).

| Idea del kit | Decisión | Dónde |
|---|---|---|
| Carpeta de referencias que Claude estudia | **Aplicado.** `E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\REFERENCIAS\{largo_horizontal,reels_vertical,miniaturas,brand_sheet_aprobado,storyboards}` | `mw_editor/referencia.py` |
| Aprender el estilo de 3-5 referencias y producir un brand sheet que se REVISA antes de aprobar | **Aplicado.** `python -m mw_editor referencia VIDEO` mide la referencia (ritmo, transiciones, audio), saca hojas de contacto y escribe `BORRADOR_<nombre>.md` pendiente de aprobación | `referencia.py` |
| Storyboard para aprobar ANTES de exportar | **Aplicado.** `python -m mw_editor storyboard PROYECTO` hoja de contacto de los momentos con rótulo/cifra/lower third | `referencia.py` |
| Corregir de a un cambio, en lenguaje simple | Ya era nuestro modo de trabajo | — |
| Quitar toda pausa > 0,1 s | **No como defecto**: corta la respiración y suena robótico. Se mantiene 0,45 s; para reels de mucha energía se puede bajar con `--pausa-max 0.25` | `editar --pausa-max` |
| Remotion | **No** para montaje: su alfa WebM/VP9 se ve negro en Premiere. HyperFrames (ProRes 4444 con alfa) sigue siendo el estándar | CLAUDE.md |
| HyperFrames, FFmpeg | Ya en uso (mantener HyperFrames y sus skills al día) | — |
| whisper.cpp | **No**: usamos faster-whisper en GPU (37 min en ~8 min), con timestamps por palabra | `transcribir.py` |
| yt-dlp | Útil para descargar referencias; dio 403 con la versión vieja → actualizarlo. No se elude la protección anti-bot: si falla, David baja el archivo a `REFERENCIAS` | — |
| Referencias desde Instagram | Se admiten reels como referencia vertical (`--tipo reels_vertical`) | `referencia.py` |
| Licencias de cada herramienta | Ver `NOTICE.md`; CodeFormer sigue prohibido | — |
