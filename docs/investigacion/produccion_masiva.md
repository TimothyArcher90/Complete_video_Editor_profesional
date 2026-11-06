# Produccion masiva: de UN video de una persona a un paquete publicable

Estado: implementado y probado el 2026-11-05 con `clip_raoul_75s.mp4` y `clip_aztec_70s.mp4` tratados como masters.
Modulos nuevos: `produce.py` (orquesta + CLI), `clips.py`, `capitulos.py`, `exportar.py`, `sync.py`. El unico cambio en `__main__.py` son dos lineas que registran los subcomandos.

## Flujo

```
                         master.mp4 (largo, 5-60 min)         <- NUNCA se modifica
                                  |
                      copia a 01_RAW del proyecto LARGO
                                  |
        +-------------------------+----------------------------+
        |                                                      |
  editar horizontal (pipeline existente)                 clips.puntuar(words.json del master)
  audio -14 LUFS, imagen, cortes, subtitulos pista,      ventanas 20-90 s, inicio/fin en frase
  lower third si el brief trae `nombre`                  gancho .35 densidad .25 audio .20 cara .15 duracion .05
        |                                                      |
  capitulos.py (words_final.json)                        top-N sin solaparse -> 00_DOCS\clips.json
  capitulos.json + capitulos_youtube.txt                       |
  + capitulos.ffmetadata (marcadores en el MP4)          por clip: proyecto propio  <nombre>_reelNN
        |                                                  01_RAW = copia recortada (ffmpeg -ss/-t, crf 14)
  miniatura 16:9 (titular del brief, o                     03_TRANSCRIPT\words.json = palabras del master desplazadas
  SIN-TITULAR si falta)                                    editar vertical 9:16 -> QC -> portada 9:16
        |                                                      |
        +------------------ exportar.py ----------------------+
                                  |
        07_PUBLICAR\<plataforma>\  mp4 + portada + ficha_publicacion.json (+ srt / capitulos en los largos)
                                  |
                      00_DOCS\SIGUIENTE_PASO.md  +  00_DOCS\produccion.json (manifiesto, tiempos)
```

Estructura de salida (raiz `E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados`, o la carpeta pendiente en C: si E: no esta):

```
<raiz>\DD-MM-AAAA\<nombre>\            proyecto LARGO   (00_DOCS .. 06_EXPORT + 07_PUBLICAR)
<raiz>\DD-MM-AAAA\<nombre>_reel01\     proyecto REEL 1  (idem)
<raiz>\DD-MM-AAAA\<nombre>_reel02\ ...
```

Separacion master / entrega (regla de David: subtitulos siempre como pista editable):
- `06_EXPORT` = MASTER EDITABLE: base, ProRes 4444 con alfa de subtitulos y graficos, SRT, REFERENCIA. Aqui los subtitulos son pista.
- `07_PUBLICAR` = ENTREGA. Instagram, TikTok, Shorts y LinkedIn vertical/cuadrado llevan los subtitulos INCRUSTADOS porque esas redes no importan SRT. YouTube largo y LinkedIn horizontal llevan el SRT al lado y NO quemados. `LEEME_PUBLICAR.txt` lo recuerda en cada carpeta.

## Comandos

```powershell
# Todo en uno (5 reels por defecto; --lento = calidad final: preset slow + Whisper medium)
python -m mw_editor produce MASTER.mp4 --raiz RAIZ --brief brief.txt --reels 5 --min-clip 20 --max-clip 90

# Solo elegir reels (puntua, escribe clips.json; --procesar ademas los renderiza)
python -m mw_editor clips MASTER.mp4 --out CARPETA --n 5 --min 20 --max 90 [--words words.json] [--procesar --raiz RAIZ]

# Variantes de entrega de un proyecto ya editado
python -m mw_editor exportar PROYECTO --tipo corto [--plataformas instagram-reels,tiktok,linkedin-vertical] [--titulo "L1|L2"] [--incrustar]
python -m mw_editor exportar PROYECTO --tipo largo

# Copia segura de la carpeta pendiente (C:) a E:  (nunca borra, nunca /MIR)
python -m mw_editor sync --estado
python -m mw_editor sync [--simular]
```

`brief.txt` (lineas `clave: valor`, todo opcional): `titulo` (`Linea 1|Linea 2`, max 5 palabras), `tema` (lima|valor|tecnico|geo|coste), `etiqueta`, `idioma`, `cta`, `nombre` (persona del lower third), `rol` (cargo del lower third), `proyecto` (nombre de carpeta), `plataformas` (lista). El brief describe el master: los reels no heredan el titular; salen con portada SIN TITULAR hasta que el copy ponga el suyo.

## Plataformas (perfiles en `exportar.PERFILES`)

| Plataforma | Formato | fps | Video | Audio | Subtitulos | Fuente / confianza |
|---|---|---|---|---|---|---|
| instagram-reels | 1080x1920 | <=30 | H.264 High, 8 Mbps | AAC 48 kHz 192k | incrustados | terceros |
| tiktok | 1080x1920 | <=30 | H.264 High, 8 Mbps | AAC 48 kHz 192k | incrustados | terceros |
| youtube-shorts | 1080x1920 | <=30 | H.264 High, 8 Mbps, GOP cerrado fps/2, 2 B-frames | AAC-LC 48 kHz 384k | incrustados | oficial (codificacion) |
| linkedin-vertical | 1080x1350 (4:5) | <30 (29.97) | H.264 High, 8 Mbps | AAC 192k | incrustados | oficial (relacion/peso/fps), bitrate estimado |
| linkedin-cuadrado | 1080x1080 | <30 (29.97) | H.264 High, 8 Mbps | AAC 192k | incrustados | idem |
| youtube-largo | 1920x1080 | el del master (<=60) | H.264 High, 8 Mbps (<=30 fps) / 12 (>30), GOP cerrado, BT.709, faststart | AAC-LC 384k | SRT aparte + capitulos en MP4 y en `_capitulos_para_descripcion.txt` | oficial |
| linkedin-horizontal | 1920x1080 | <30 (29.97) | H.264 High, 8 Mbps | AAC 192k | SRT aparte (`--incrustar` para quemar) | oficial / estimado |

Decision: `linkedin-vertical` = 4:5 (LinkedIn la llama su relacion vertical recomendada; 9:16 es solo movil). Si David prefiere 9:16 en LinkedIn basta con listar `instagram-reels` (mismo 1080x1920).
Todos: loudness del master (-14 LUFS), pixel format yuv420p, `+faststart`, etiquetas BT.709. Cada export se verifica con ffprobe + loudnorm (resolucion, fps, duracion maxima, peso, LUFS) y los desvios van a `avisos` de la ficha. Los formatos 4:5 y 1:1 se renderizan bajo demanda (otra pasada de `editar`) solo si se piden.

## Ficha de publicacion (`07_PUBLICAR\<plataforma>\ficha_publicacion.json`)

Vacios a proposito (los rellena el agente de copy): `titulo`, `descripcion`, `hashtags`, `cta` (precargado con el del brief). Ya rellenos: `duracion_s`, `formato`, `audio` (LUFS/true peak medidos), `subtitulos` (incrustados o SRT), `portada` (+ `portada_pendiente_titular`), `capitulos` (largos), `zona_segura_usada` (perfil + caja en px), `manifiesto_ia`, `master_editable` (rutas ProRes/SRT), `origen_clip` (reels: ventana, puntuacion, gancho), `fuente_especificaciones` y `avisos`. Una exportacion nueva no pisa: la ficha anterior pasa a `ficha_publicacion_vN.json` y el MP4 sube de version (`DD-MM-AAAA_nombre_plataforma_vN.mp4`).

`manifiesto_ia` se calcula de `reparacion.json`: mejora de imagen/audio propia (YouTube la exime), sin restauracion facial, sin IA generativa, sin voz sintetica -> `requiere_declaracion_ia: false`. Si despues se anade IA generativa hay que cambiarlo a mano. No se escriben credenciales C2PA (no se firma el archivo).

## Seleccion de reels (`clips.py`)

Ventanas que empiezan en inicio de frase y terminan en fin de frase (frase = signo final o pausa >= 0.6 s), por lo que no se corta a mitad. Se dejan 0.25 s antes y 0.35 s despues (sin invadir la palabra vecina). Puntuacion 0-100:
- Gancho (0.35): primeros 3 s: pregunta +35, cifra +40, contraste +30, afirmacion fuerte +30, frase corta +10; arrancar con saludo o muletilla -25.
- Densidad (0.25): ritmo 2.3-3.3 pal/s (trapecio), conceptos unicos por segundo, cifras y nombres propios; penaliza silencios largos.
- Claridad de audio (0.20): SNR local (p90-p10 del nivel por 0.5 s), nivel de voz, recortes y confianza media de Whisper.
- Cara (0.15): fraccion de muestras (1 cada 2 s) con cara (YuNet).
- Duracion (0.05): optimo 25-60 s.
Top-N sin solaparse; cada clip lleva `motivo` legible y `componentes`. Los umbrales son heuristicas de oficio (ver `plataformas_metricas.md` secc. 3, todo estimado/terceros): calibrar con retencion real cuando haya datos.

## Capitulos (`capitulos.py`)

TextTiling sobre vocabulario (TF-IDF, sin APIs) + pausas, sobre `words_final.json` (tiempos del video final). Reglas de YouTube: empieza en 00:00, minimo 3 capitulos, cada uno >= 10 s; capitulo minimo por defecto 60 s (se reduce solo en videos cortos y lo avisa). Si el habla es corrida (sin puntos ni pausas largas) usa pausas de 0.3 s. Titulos PROVISIONALES = 3 palabras clave del tramo (`titulo_auto: true`): el copy los reescribe. Salidas: `capitulos.json`, `capitulos_youtube.txt` (`00:00 Titulo`, con horas si dura >= 1 h) y `capitulos.ffmetadata` (se incrusta como marcadores en el MP4 de youtube-largo).

## Sync (`sync.py`)

`robocopy` por carpeta de primer nivel con `/E /XO /COPY:DAT /R:2 /W:2`: sin `/MIR`, `/PURGE` ni `/MOV`; no pisa archivos mas nuevos del destino; no borra nada en ninguno de los dos lados. Verifica despues por ruta relativa + tamano y deja `.sync_log.txt` en el origen. `sync --estado` informa si E: esta montado y cuanto queda pendiente. Mapeo: `C:\Users\tante\Videos\MacroWise_pendiente_de_pasar_a_E\<X>` -> `E:\CARPETA OUTPUTS IA 2026\<X>`. El origen NO se borra: lo revisa David.

## Pruebas reales (2026-11-05)

Masters: `clip_raoul_75s.mp4` (1920x1080, 75 s, ingles) y `clip_aztec_70s.mp4` (1916x1080, 70 s, espanol), 2 reels cada uno con `--min-clip 15 --max-clip 35/30`. Salidas en `C:/Users/tante/Projects/macrowise-video-editor/_pruebas/agentes/produccion/out/05-11-2026/`. Los masters y su copia en 01_RAW son byte a byte iguales (`cmp`).

| Prueba | Salidas verificadas |
|---|---|
| raoul_test (brief con titulo, nombre, rol) | largo 16:9 -14.0 LUFS, lower third "Raoul Pal / Real Vision", 3 capitulos (00:00, 00:30, 00:52) embebidos en el MP4 (ffprobe `-show_chapters`), miniatura 16:9 con titular; `youtube-largo` (1920x1080 30 fps, High, 2 B-frames, BT.709, 7.5 Mbps) y `linkedin-horizontal` (29.97 fps); 2 reels x (instagram-reels, tiktok, youtube-shorts) a 1080x1920 30 fps, 8.3 Mbps, -14.0 LUFS, subtitulos incrustados |
| aztec_test (plataformas con linkedin-cuadrado) | largo + `linkedin-cuadrado` 1080x1080 29.97 fps (formato 1:1 renderizado bajo demanda), 2 reels x (instagram-reels, tiktok, linkedin-cuadrado) |
| sync | probado con carpetas temporales: copia, no borra el origen, conserva un archivo que solo estaba en destino, `--estado` pasa de "faltan 2" a "todo copiado". Con la carpeta pendiente real (no existe hoy) responde "nada pendiente". No se escribio nada en E: |

Tiempos medidos (PC con otros 4-5 agentes transcribiendo/renderizando a la vez, CPU compartida, Whisper `small` en CPU int8 porque falta `cublas64_12.dll`; **tomar como cota superior**, con la maquina libre sale bastante menos):

| Paso | raoul (75 s) | aztec (70 s) |
|---|---|---|
| Largo: editar 16:9 (analisis + Whisper + cortes + audio + render + capas) | 815 s | 513 s |
| Capitulos | 3 s | 4 s |
| Largo: exportar (miniatura con recorte BiRefNet + 2 plataformas) | 598 s | 554 s |
| Seleccion de reels (audio + caras + puntuacion) | 24 s | 10 s |
| Reels: por reel, editar 9:16 + QC | 453 s / 421 s | 201 s / 275 s |
| Reels: por reel, total incl. exportar a 3 plataformas | 741 s / 617 s | 550 s / 602 s |
| TOTAL produce | 49.4 min | 38.2 min |

`clips` solo (con `words.json` ya hecho): 10-24 s para un master de 70 s. Cada exportacion de plataforma son ~10-40 s de ffmpeg para un reel de 20-30 s.

Reels elegidos (puntuacion 0-100): raoul 0-33 s (70.7: cifra "3 %" + frase corta en el gancho, 3.4 pal/s, cara 100 %) y 42-60 s (55.1, gancho debil); aztec 49-70 s (57.7, afirmacion fuerte "Quiero que se lleven algo") y 13-39 s (55.6). Las puntuaciones de master tan cortos son poco informativas: con 30+ min habra de verdad donde elegir.

## Limites y cosas a saber

- **Tiempo en masters largos**: lo caro es Whisper (CPU int8 hoy; con CUDA operativo baja mucho) y el render x264 de `editar`, que escala con la duracion. Un master de 60 min con 5 reels puede llevar horas en este PC: usar `--lento` solo para la corrida final; el modo por defecto es `--rapido` (veryfast + Whisper small). La deteccion de caras para elegir reels muestrea 1 cuadro cada 2 s en una sola pasada (decodifica todo el master: ~1-3 min por hora de video).
- **Memoria/disco**: cada reel copia su recorte en su 01_RAW (crf 14, re-codificado para cortar exacto) y el master se copia entero al 01_RAW del largo: 60 min a 1080p son varios GB por copia. El master original no se toca nunca.
- **Titulos de capitulos y portadas de reels**: provisionales/sin titular a proposito. Los capitulos dependen de cambios de vocabulario, no de comprension: en videos con un solo tema salen capitulos por pausas.
- **Heuristicas de gancho** (pregunta/cifra/contraste/afirmacion fuerte) estan afinadas para espanol e ingles; otros idiomas puntuan gancho bajo. Sin retencion real no hay calibracion: los pesos (0.35/0.25/0.20/0.15/0.05) son criterio de oficio.
- **Subtitulos del largo**: se pide estilo `minimo`; mientras el modulo de subtitulos no lo implemente cae al estilo clasico (el comando ya lo acepta sin cambios).
- **QC**: el QC del master puede marcar FAIL por contraste WCAG de los subtitulos sobre fondos claros (modulo de subtitulos, no de produccion); la ficha lo copia a `avisos` para que nadie publique sin verlo. Las pruebas usan clips de terceros que ya traen captions quemados abajo, lo que ensucia contraste y zonas.
- **LinkedIn**: no hay bitrate oficial (8 Mbps estimado); `<30 fps` se cumple con 29.97. Subtitulos de LinkedIn horizontal van como SRT: si se quiere autoplay mudo, `exportar --incrustar`.
- **IA**: el manifiesto dice "sin IA generativa" porque el pipeline no la usa. No se firma C2PA. Si despues se anade IA generativa o voz sintetica, hay que corregir la ficha.
- **E: desconectado**: `produce --raiz` escribe donde se le diga; sin `--raiz` usa E: si esta montado o la carpeta pendiente de C:. Luego `sync`. No se probo escribir en E: real (regla: probar en C:).
- No hay mascara de 4:5/1:1 para el largo con reencuadre inteligente distinto al de `editar`; si el master es horizontal, el 1:1 y 4:5 usan el recorte de cara de `planos.py`.
- Nada de esto publica ni envia correos: termina en `07_PUBLICAR` + `SIGUIENTE_PASO.md`.
