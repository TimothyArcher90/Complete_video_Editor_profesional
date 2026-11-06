---
name: macrowise-editor
description: "Editor automático de reels y vídeos de MacroWise en vertical (9:16) y horizontal (16:9). Úsala cuando David pase un vídeo (reel, entrevista, take de presentador) y pida editarlo, montarlo, subtitularlo, ponerle gráficas, mapas, luz o corrección de color, o diga 'te paso un reel'. Entiende el vídeo (transcripción + candidatos), limpia audio e imagen, corta silencios, encuadra por la cara con jump-cuts, pone subtítulos dinámicos con colores de marca como pista editable, tarjetas de cifra con fuente, títulos grandes, cierre 'Comenta X', paneles con mapas de Electric Eye y gráficas de Ride the Lightning, y entrega ProRes 4444 con alfa + MP4 de referencia + SRT. Encadena con macrowise y macrowise-video. NO es para generar vídeo desde cero."
---

# macrowise-editor

Motor local: `C:\Users\tante\Projects\macrowise-video-editor` (copia portable en `Descargas\MacroWise_Editor_Video`). Se llama con `python -m mw_editor …` desde esa carpeta. David nunca toca la terminal: lo ejecutas tú.

## Antes de nada
- Carga `macrowise` (marca, reglas) y respeta `macrowise-video` (percepción, medición, alto antes de generar assets de pago).
- **01_RAW es intocable.** El motor solo LEE el original y escribe en `06_EXPORT`, `02_AUDIO`, `03_TRANSCRIPT`, `00_DOCS`, `05_PROJECT`.
- Subtítulos **siempre** como pista editable (SRT + ASS + ProRes con alfa). Nunca quemados en el entregable. El `*_PREVIEW_subs_quemados_NO_ENTREGAR.mp4` es solo para mirar en el móvil.
- Una cifra rotulada es una afirmación de marca: el motor **rechaza** cualquier cifra sin `fuente` y `verificada:true`. Verifica contra fuente oficial antes de ponerla; si no puedes, pregunta a David. Nunca inventes ni omitas en silencio.
- Licencias: CodeFormer PROHIBIDO. Permitidos: FFmpeg, Whisper/faster-whisper (MIT), YuNet (MIT), RNNoise (BSD), DeepFilterNet (MIT/Apache), Real-ESRGAN (BSD-3), GFPGAN (Apache-2.0), RIFE (MIT), HyperFrames.

## Flujo (objetivo: algo que se pueda juzgar en minutos)

**1. Proyecto y pasada automática**
```
python -m mw_editor proyecto "NOMBRE"                      # crea 00_DOCS…06_EXPORT en E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\DD-MM-AAAA\<NOMBRE>\ (+ DD-MM-AAAA\_REFERENCIAS para todo lo usado como referencia)
python -m mw_editor editar "VIDEO" --out "<proyecto>" --nombre NOMBRE --formato vertical|horizontal|ambos --idioma es --preview
```
Hace, en este orden (el orden importa): medición (audio+imagen) → transcripción por palabra (faster-whisper) → cortes de silencio/muletillas (solo entre palabras) → audio (highpass, ruido, EQ, de-esser, compresión, −14 LUFS/−1 dBTP, con salvaguarda de reversión) → imagen (denoise → exposición/color → nitidez suave al final) → luz de estudio suave sobre la cara → tomas de ~3,6 s con encuadre por cara y punch-in alterno (jump-cuts) → una sola codificación x264 crf 17 slow → subtítulos dinámicos + SRT → MP4 de referencia.
Flags útiles: `--sin-cortes`, `--luz 0..1.5`, `--toma 3.6`, `--zoom 1.12`, `--pausa-max 0.45`, `--modelo large-v3` (si hay GPU/tiempo), `--rehacer`.

**2. Entender el vídeo** — lee `03_TRANSCRIPT\transcript_final.txt` (timeline FINAL, ya con cortes) y `candidatos.json` (cifras, lugares, activos detectados). Resume: tema, hook, giro, cierre, 3 momentos fuertes. Lee también `00_DOCS\analisis.json` → `diagnostico` y `no_se_puede_arreglar` y **díselo a David** (altas luces quemadas, bitrate bajo, etc.).

**3. Escribir `plan.json`** (tiempos en segundos del vídeo FINAL):
```json
{
 "lower_thirds":   [{"t":1,"dur":4,"nombre":"Guillermo Valencia","rol":"MacroWise"}],
 "titulos":        [{"t":8,"dur":3,"etiqueta":"Caso de uso","texto":"#1 Título","color":"lima"}],
 "titulos_grandes":[{"t":30,"dur":3.5,"linea1":"Línea fina","linea2":"Línea clave en lima"}],
 "cifras":         [{"t":14,"dur":3.5,"valor":"90%","etiqueta":"Qué mide","tipo":"valor|tecnico|geo|coste","fuente":"INE 2025","verificada":true}],
 "paneles":        [{"t":22,"dur":5,"clip":"C:\\ruta\\mapa_ALFA.mov","caja":"panel"}],
 "clips":          [{"t":40,"dur":4,"archivo":"C:\\ruta\\grafica.mp4","caja":"full|panel|arriba"}],
 "cta":            [{"t":60,"dur":5,"verbo":"Comenta","palabra":"Link","extra":"y te lo envío por mensaje directo"}]
}
```
Reglas de diseño (de las referencias): una idea por tarjeta; el texto **añade**, no repite lo que dice la voz; nada en las zonas seguras de UI (vertical: 14 % arriba, 22 % abajo, 14 % derecha); tarjetas opacas; color = taxonomía (oro valor, teal técnico/%, púrpura geo/macro, terracota coste; lima = palabra clave de subtítulo/CTA).

**4. Mapas y gráficas** (herramientas propias, nunca otra cosa)
- Mapas: **Electric Eye** (MCP `mcp__electric-eye__*`; leer `guia_de_direccion`; flujo `buscar_lugar → nuevo_proyecto → planos_de_camara → anadir_elementos → vista_previa → revisar_proyecto → exportar_video → esperar_render → revisar_video`; el editor debe estar abierto en el navegador: `npm run iniciar`). Exportar en MP4 + ProRes con alfa a `04_GRAPHICS`.
- Gráficas de series: **Ride the Lightning** (`C:\Users\tante\Projects\Ride-the-Lightning`, MCP `ride-the-lightning`; `buscar_series → descargar_serie → compilar_spec → vista_previa → exportar_video`; mirar el informe de compilación y las licencias: Yahoo y Coin Metrics no sirven para contenido monetizado). Historia completa de la serie.
- Infografías complejas (checklists, contadores, calendarios, comparativas de planes): HyperFrames (`npx hyperframes check` antes de renderizar).
- Pon cada clip en `paneles` (cápsula del presentador + panel Warm Black) o en `clips`.

**5. Componer y revisar**
```
python -m mw_editor componer --out "<proyecto>" --plan plan.json --formato ambos --preview
```
Mira fotogramas del preview en los instantes de cada capa (contact sheet con ffmpeg). Corrige y recompón: es barato (no repite audio/imagen). Cada pasada de `editar` crea v2, v3… sin pisar.

**6. Entrega** — carpeta `06_EXPORT` (y copia en `C:\Users\tante\Downloads`): `*_base.mp4`, `*_subtitulos_ALFA.mov`, `*_graficos_ALFA.mov` (ProRes 4444 con alfa, para Premiere), `*_subtitulos.srt` + `.ass`, `*_REFERENCIA.mp4`. Mensaje final de 3 bullets: qué hice, rutas completas, qué decidí yo que debe revisar, qué quedó fuera y por qué.

## Subtítulos visuales (por defecto) y clásicos
`--estilo visual` (defecto): cada palabra entra cuando se dice; UNA palabra clave por grupo en caja opaca con el color de su taxonomía (cifra/importe = oro, % o técnico = teal, coste/riesgo = terracota, lugar = púrpura, concepto = lima); resto en blanco con sombra suave; máx. 2 líneas equilibradas dentro de la zona segura. `--estilo clasico`: una sola línea con la palabra activa en lima. Ambos salen como SRT + ASS + ProRes con alfa (pista editable).

## Miniaturas (siempre, con cada video)
`python -m mw_editor miniatura --video VIDEO --titulo "Línea 1|Línea 2" --tema … --etiqueta "…" --out "<proyecto>\06_EXPORT\THUMBNAILS"` → 4 archivos (A impacto, B cajas, C cinético en vertical; A horizontal) + recorte con alfa + candidatos. El titular sale de lo que dice el video. Reglas completas en `docs\GUIA_MINIATURAS.md`. Mira SIEMPRE los JPG antes de entregar.

## Copy (siempre en Google Doc)
Cada video lleva su copy: hook, caption de máx. 3 párrafos cortos en español colombiano (sin voseo), CTA, hashtags, texto de miniatura y notas de revisión (cifras sin verificar). Se crea como Google Doc nativo en Drive (`create_file` con `text/markdown`) y la URL queda en `00_DOCS\COPY_URL_Drive.txt` y en el mensaje final. Termina con `anti-ai-writing`.

## Dónde van las salidas
`E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados\DD-MM-AAAA\<nombre del output>\` (00_DOCS … 06_EXPORT; miniaturas en `06_EXPORT\THUMBNAILS`; plan en `05_PROJECT\plan.json`), referencias en `…\DD-MM-AAAA\_REFERENCIAS`, e `INDICE.md` por día. Marca oficial: `…\Video con Ia editor\NUEVA IMAGEN MW-…`.

## Qué NO se puede arreglar en post (decirlo, no fingir)
Altas luces quemadas; bitrate de origen bajo (bloques); reverberación fuerte de sala (ffmpeg no desreverbera: si el audio procesado empeora, el motor revierte); caras de menores (siempre difuminadas, no es opcional).

## Recetas de reel (copiar mecánica, nunca marca ajena)
Ver `docs/RECETAS_REELS.md`: pasos con panel, comparativa de planes, "3 códigos" (títulos #1/#2/#3), caso con B-roll, cierre "Comenta X" y bloque de fecha. Referencias analizadas: Aztec Lab (4 reels vertical) y entrevista de Raoul Pal (horizontal con paneles de gráficas), guardadas en `Descargas\Referencias_Edicion`.

## Mejoras gratuitas opcionales (con licencia comercial OK)
| Qué | Repo | Cuándo |
|---|---|---|
| Voz limpia con IA | DeepFilterNet (MIT/Apache), RNNoise modelo `.rnnn` (BSD; el motor lo usa solo si está en `brand\models\rnnoise_bd.rnnn`) | suelo de ruido > −50 dB y afftdn no basta |
| Separar voz de música/ruido | Demucs (MIT) | material con música de fondo |
| Imagen blanda | Real-ESRGAN (BSD-3) solo en `analisis.json` → "blanda"; nunca sobre toda la pieza sin mezclar | origen < 1080p |
| Restaurar cara | GFPGAN (Apache-2.0), mezclado con el original | cara degradada; nunca en todos los fotogramas puros |
| Cámara lenta/interpolación | RIFE (MIT) | solo B-roll, nunca el presentador |
| Silencios y muletillas | auto-editor (Unlicense) | alternativa al motor de cortes |

## Actualización nocturna 2026-11-05 — qué cambió
- **Zonas seguras por red** (`mw_editor\zonas.py`): perfil `universal` por defecto en 9:16 (arriba 269, abajo 672, izq 122, der 242 px sobre 1080x1920; Electric Eye). 9 perfiles por plataforma + uniones (`MW_ZONA=tiktok+instagram-reels`). NINGUNA cifra es oficial: cada perfil declara su confianza. Guías para contrastar con capturas reales: `docs\guias_zonas\*.png` (`python -m mw_editor.guias_zonas`).
- **Encuadre que no tapa la cara** (`planos.py`, `verificar_encuadre.py`): ojos al 30-38 %, subtítulo de una línea bajo la barbilla; mide con `python -m mw_editor.verificar_encuadre BASE.mp4 SUBS.ass`.
- **Color** (`color.py`): 4 looks (`--look warm_black|stone_light|oro_editorial|teal_sutil`), piel a 123°, calidad 16 bit o LUT 3D horneada para largos (`--color-modo`).
- **Subtítulos** (`--estilo visual|clasico|karaoke-cajas|minimo`), texto grande de énfasis y modo impacto (`enfasis.py`, `plan_auto.py`).
- **Formatos**: `--formato vertical|horizontal|cuadrado|4x5|ambos|todos`.
- **Producción masiva**: `produce MASTER --raiz R --brief brief.txt --reels N [--lento]` (largo + capítulos + reels + miniaturas + 07_PUBLICAR por plataforma + fichas), `clips`, `exportar`, `sync`.
- **QC y métricas**: `qc PROYECTO…` (puntuación 0-100, historial, manifiesto de IA); `lote CARPETA --out OUT` para tests masivos con comparación contra la corrida anterior.
- **Copy** (`copy.py`, `docs\investigacion\copy_playbook.md`): estructura y valida; el texto lo redacta Claude.
- **Mapas y gráficas** (`capas_externas.py`, `docs\investigacion\mapas_graficas_receta.md`): Electric Eye vive en `C:\electric-eye` (iniciar con `node servidor\iniciar.mjs`, pestaña en «Editor del mapa»); Ride the Lightning por CLI.
- **Workflow agéntico completo**: `docs\WORKFLOW_AGENTICO.md`.
- Whisper corre en GPU (CUDA) desde que `transcribir._registrar_dll_cuda` registra las DLL de pip nvidia-*. ffmpeg se lanza siempre sin stdin.