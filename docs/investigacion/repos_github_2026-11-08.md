# Repos de GitHub revisados (2026-11-08): qué se tomó y qué no

Metodología: 3 agentes buscaron ~150 candidatos; estrellas, último push y licencia salen de `gh api` (8-nov-2026) salvo lo marcado «no verificado». Criterio: licencia COMERCIAL, actividad < 12 meses, pieza concreta reutilizable.

## Tomado e integrado
| Repo | Licencia | Qué se tomó |
|---|---|---|
| browser-use/video-use (30,7k★, MIT) | MIT | Su disciplina, no su código (usa ElevenLabs de pago). 12 reglas: fundidos de audio de **30 ms** en cada corte (aplicado en `cortes.py`, antes 8 ms), no cortar dentro de palabra, subtítulos al final de la cadena, overlays con `setpts=PTS-STARTPTS+T/TB`, autoevaluación del render (filmstrip) |
| Breakthrough/PySceneDetect (BSD-3) | BSD-3 | Instalado; para el QC de ritmo de cortes de cámara reales |
| librosa (ISC) | ISC | Beats/tempo en `musica.py` |
| OpenTimelineIO (Apache-2.0) | Apache-2.0 | Instalado; sus adaptadores EDL/FCPXML NO vienen incluidos y David pidió no depender de Premiere: descartado como entrega |
| auto-editor (Unlicense) | Unlicense | Instalado como alternativa para cortes por silencio; el motor propio sigue |

## Pendiente de evaluar
WhisperX (BSD-2; alineación por palabra más fina, evitar diarización), OpenShorts (MIT; lógica de layout por plano y prompt de selección de clips; revisar dependencias), pycaps (MIT; solo el concepto de estados por palabra, traducido a ASS), MediaPipe AutoFlip (Apache-2.0; solo la idea de suavizar la trayectoria de cámara), Manim/Revideo (alfa por verificar).

## Descartados
Remotion (licencia de pago; además alfa negro en Premiere), MusicGen (pesos CC-BY-NC), madmom (modelos NC), Essentia (AGPL), MoneyPrinterV2/OpenMontage (AGPL), whisper-timestamped (AGPL), lossless-cut/pyvideotrans/gyroflow (GPL), ClipsAI/ShortGPT (abandonados), stable-ts (archivado).

## Hallazgo
Ningún repo resuelve el encuadre 9:16 con control de solape cara–texto: se construyó (`evitar_cara.py`, ver abajo). Tampoco hay un detector de hablante activo permisivo y mantenido.

## Construido a raíz de esto
- `musica.py` (catálogo con licencia, energía del discurso, beats, ducking, stem aparte). Falta que David descargue pistas a `...\MUSICA`.
- `evitar_cara.py`: mide la cara con YuNet y recoloca títulos, cifras y CTA (lado, escala, altura) para que NINGUNA capa toque la cara; verificado en fotogramas del largo de Arca.
- Fundidos de 30 ms en cortes; el CTA y las cifras aceptan `escala`, `lado`, `y_frac`.

## Música: fuentes (licencias NO verificadas por mí; abrir cada página antes de monetizar)
Pixabay Music (sin atribución; descartar las marcadas «Content ID»), YouTube Audio Library (filtrar «sin atribución»), Incompetech (CC-BY: crédito obligatorio), Free Music Archive (solo CC0 y CC-BY). Nivel de la música bajo la voz: –18 a –24 LUFS (práctica común, no verificada en fuente).
