# Etalonaje integrado al motor: implementacion y verificacion

Fecha: 2026-11-05. Codigo: `mw_editor\color.py` (nuevo) y `mw_editor\imagen.py` (la cadena de `eq` de 8 bit ya no existe). Base: `color.md` / `color_propuesta.py`.
Banco de pruebas y resultados: `_pruebas\agentes\color_integracion\` (hoja antes/despues: `hoja_antes_despues.jpg`; metricas: `out\calidad\metricas.json`, `out\rapido\metricas.json`; proyectos de prueba reales: `proj_e` y `proj_e2`).

## 1. Que hace ahora `imagen.cadena(analisis_video, info, look=None, modo=None, ruta=None, proyecto=None, forzar=False, referencia=None, fuerza_look=1.0)`

Sigue devolviendo `(lista_de_filtros, lista_de_decisiones)` y el `unsharp` sigue siendo el ULTIMO elemento (render.py lo separa como `chain_post`). Orden: hqdn3d (denoise primero) -> etalonaje -> unsharp 0.45.
Etalonaje = los 8 pasos medidos en la investigacion: (0) superblancos + entrada YUV->RGB 16 bit con matriz/rango del fichero, (1) exposicion (gamma), (2) balance de blancos, (3) giro de piel hacia 123 grados (2 y 3 en UNA matriz), (4) curva PCHIP, (5) saturacion + vibrance, (6) look, (7) salida legal 709 tv con dither + limiter + etiquetas. Looks: `warm_black` (defecto), `stone_light`, `oro_editorial`, `teal_sutil`, `ninguno`.

Origen del fichero: si `ruta`/`proyecto` no llegan, `color.contexto_del_llamador()` los toma de las variables `src` y `docs` de `cmd_editar` (asi no hizo falta tocar `__main__.py`). Si algo falla (sin ruta, ffmpeg, YuNet) cae a "look con parametros neutros" y lo dice en las decisiones: nunca rompe el render.

### Parametros por camara (UNA vez, nunca por fotograma)
`color.plan_color` mide 12 fotogramas repartidos con UN solo proceso de ffmpeg (arrancar ffmpeg cuesta ~3 s aqui; en largos usa 12 entradas `-ss`, no decodifica los 40 min), YuNet + mascara de piel Cb/Cr, mediana, y guarda en `00_DOCS\color.json` (clave = nombre+tamano+mtime+version): perfil, parametros (gamma, wb, giro, objetivo, tipo de piel), mascara, look, modo, LUTs y avisos. Segunda llamada = lee del json (no recalcula: `cadena()` se llama dos veces en `cmd_editar`). `forzar=True` recalcula. Para igualar una camara a otra: `referencia=<video>` (modo por referencia; mejor que forzar 123 grados, ver color.md §3).

### Reglas que se anadieron al medir
- Matriz honrada desde la etiqueta (`bt470bg`/`smpte170m` -> 601; sin etiqueta <720 px -> 601; resto 709); rango `yuvj`/`pc` -> full y sin compresion de superblancos; HDR HLG/PQ -> tone-mapping mobius antes de todo (solo probado en sintetico, como en color.md).
- Objetivo de piel: `clip(Y_medida + 20, 100, 150)`. Piel clara/media (Y >= 130) -> 150. Con Y < 130 NO se fuerza 150: se avisa "oscura o subexpuesta" (una sola cara no distingue piel oscura de cara subexpuesta). Contraluz (cara < 125 y fondo p75 >= cara + 45) -> objetivo 135.
- Piel no fiable (croma < 14 o Y < 60: barba, sombra, camisetas grises, cuadriculas de varias personas como t07) -> sin correccion primaria, solo look, con aviso. Sin cara (t04) igual.

## 2. Dos niveles de rendimiento
- `calidad`: cadena viva 16 bit. Seleccion automatica: origen <= 180 s.
- `rapido`: la cadena estatica (pasos 1-6) se HORNEA en una LUT 3D 33^3: una imagen identidad de 33x1089 px (16 bit, r varia mas rapido) pasa por la cadena y se guarda como `.cube`; en el render: `lutyuv` superblancos -> `scale` a gbrp16le -> `lut3d=interp=tetrahedral` -> salida legal. Auto: origen > 180 s. Override: `modo=` o `MW_COLOR_MODO=calidad|rapido`; look con `look=` o `MW_COLOR_LOOK`.
- LUTs en `04_GRAPHICS\luts\<look>_<camara>_<hash>.cube` + `LICENCIA_LUTS.txt` (generadas por nosotros desde curvas/matrices/balances propios: sin material de terceros, uso comercial libre; el .cube lleva la cabecera de licencia).

Medicion (10 clips reales, 8 fotogramas c/u, cadena `calidad` vs `rapido` extremo a extremo hasta yuv420p): dE2000 medio **0.04-0.18** (objetivo <= 1.0), p99 <= 1.31, maximo puntual 3.4 (pixeles aislados de bordes duros). Velocidad (1080p, 30 s de video, maquina cargada por otros agentes, decodificar solo = 4-8x): `rapido` 17 s = **1.74x tiempo real**; `calidad` 62-72 s = 0.42-0.48x. Un largo de 40 min en `rapido`: ~23 min de color; en `calidad` seria ~85 min (inviable, por eso el corte a 3 min). Con el PC libre sale mejor, no se midio.

## 3. Cara subexpuesta con ventana detras
Disparador: piel < 125 y fondo (p75 de luma fuera de la banda de la persona) >= piel + 45, con >= 4 fotogramas con cara. `mascara_persona` (GrabCut con caja YuNet, pluma 1.2 % del ancho) en cada uno de los 12 fotogramas -> MEDIANA = silueta estatica por camara, PNG en `04_GRAPHICS\color_mascara_<clave>.png`. Se mide la estabilidad temporal (IoU de cada fotograma contra la mediana): si el IoU medio < 0.85 la mascara se DESCARTA y se usa exposicion global con aviso (en t07, persona fuera de plano: IoU 0.73, descartada). Cadena: `split` -> rama fondo (sin exposicion) y rama cara (con exposicion) -> `maskedmerge` en RGB 16 bit con la mascara cargada con `movie=` DENTRO de `chain_pre` (un solo elemento con `;` y etiquetas: render.py no cambia). Solo se mueve la exposicion; el color es identico dentro y fuera. En `rapido`: dos LUTs (fondo/cara) + el mismo maskedmerge. Verificado en un render real de `editar` (proj_e2).
Prueba sintetica (t01 con persona -1.8 gamma y fondo claro; piel 100.6, fondo 166): piel -> **142.7** (calidad) / 142.4 (rapido), IoU temporal 0.94. Halo: anillo de 40 px fuera de la silueta +4.2 niveles de luma sobre el fondo lejano = **10 % de lo que sube la piel (+42)**; contra la subida media de la silueta entera (+16, incluye gorra y chaqueta oscuras) seria 32 %.
**Limite documentado**: la mascara es ESTATICA (una por camara). Sirve con presentador sentado y encuadre fijo (lo normal). Si se mueve mucho (manos arriba, se levanta, gira) el IoU baja y cae a global: el fondo sube con la cara. No hay mascara por fotograma y no se midio con video real a contraluz (solo sintetico, y la silueta sintetica coincide exactamente con la mascara usada: el halo real sera algo mayor). Gamma tope 0.72: con >1 EV de subexposicion la piel no llega al objetivo (se avisa).

## 4. Resultados por clip (modo `calidad`, x264 crf17 slow; piel en tv, angulo vectorscopio)

| clip | piel Y antes -> despues | angulo antes -> despues | croma | BRNG % antes -> ANTES de x264 | tras x264 BRNG medio | YMAX/YMIN pre-x264 |
|---|---|---|---|---|---|---|
| t01 aztec plano medio | 152.5 -> 152.5 | 113.8 -> 124.2 | 37.2 | 5.09 -> **0.000** | 0.064 | 226/23 |
| t02 aztec cerca | 148.3 -> 153.8 | 113.5 -> 124.6 | 33.0 | 2.25 -> **0.000** | 1.078 | 226/23 |
| t03 raoul wide | 148.2 -> 152.1 | 113.7 -> 123.8 | 37.7 | 0.10 -> **0.000** | 1.692 | 226/23 |
| t05 reel 720 cajita | 121.0 -> 140.5 | 111.4 -> 121.5 | 25.7 | 0.80 -> **0.000** | 0.145 | 226/24 |
| t06 reel 720 link | 145.0 -> 153.5 | 117.7 -> 126.2 | 40.4 | 0.00 -> **0.000** | 0.560 | 226/23 |
| t08 podcast 1080p | 133.2 -> 150.9 | 118.9 -> 126.6 | 34.0 | 0.00 -> **0.000** | 1.432 | 225/23 |
| t09 story vertical | 144.9 -> 156.4 | 118.3 -> 125.1 | 37.6 | 0.00 -> **0.000** | 0.628 | 225/23 |
| t10 raoul gesto | 149.8 -> 153.3 | 113.1 -> 123.3 | 38.3 | 0.01 -> **0.000** | 0.781 | 226/23 |
| s01 contraluz (sintetico, mascara) | 100.6 -> 142.7 | 112.9 -> 123.3 | 41.2 | 3.34 -> **0.000** | 0.226 | 225/23 |
| t04 sin cara / t07 cuadricula | sin correccion primaria (aviso), solo look | | | 0.01/0.00 -> **0.000** | 0.669/0.555 | 225/23 |

- Angulo 123 +- 6: **todos** entre 121.5 y 126.6. Y de piel 150 +- 15: todos los de piel clara/media entre 150.9 y 156.4 (t05 y s01, subexpuestos de origen, quedan en 140-143: limitados por el tope de gamma, no se fuerza).
- dE2000 de piel entre cortes de la misma persona (despues / antes): aztec t01-t02 **1.75** (1.88); raoul t03-t10 **0.70** (0.69). Ambos <= 2.5. La cadena no empeora una consistencia que ya era buena; el objetivo comun (Y y 123 grados) la mantiene entre camaras distintas.
- BRNG 0 antes de x264 en todos. **Tras x264 crf17 no es 0**: medio 0.06-1.69 %, con YMAX hasta 248 y YMIN hasta 0 (sobreimpulso en bordes duros; t03 supera el 1.5 % por las persianas, igual que en la investigacion). Es x264, no la cadena; no se puede arreglar sin bajar la calidad de borde: se reporta.
- Dispersion de piel entre fotogramas (dE00 p90): 1.3-2.4 en planos de presentador (<= 2.5); t09 7.6 (persona bailando con pelo suelto, la piel cambia de sombra: variacion real del contenido, no de la cadena); t07 21 (medicion no valida, ver reglas).
- Render real: `python -m mw_editor editar <t01 10 s> --formato vertical --rapido` (auto = calidad, 16 bit) y `MW_COLOR_MODO=rapido ... editar <s01> --rapido --sin-cortes` (LUT + mascara dentro del `-/filter_complex`) terminan en LISTO, con REFERENCIA y subtitulos ALFA. Camino `largo`: un archivo de 240 s elige `rapido` solo y mide en 17 s.

## 5. Parametros expuestos
`imagen.cadena(..., look, modo, ruta, proyecto, forzar, referencia, fuerza_look)` y `color.plan_color(ruta, docs, proyecto, duracion, look, modo, fuerza_look, referencia, forzar)`. Entorno: `MW_COLOR_LOOK`, `MW_COLOR_MODO`. Constantes en `color.py`: `UMBRAL_RAPIDO_S=180`, `LUT_N=33`, `IOU_MINIMO_MASCARA=0.85`, `Y_PIEL_OBJETIVO=150`, `PIEL_LINEA_DEG=123`, `LOOKS`. `fuerza_look` 0-1 (0.6 si la cara queda muy tintada).

### Fragmento exacto para `__main__.py` (NO aplicado; lo anade quien tiene el archivo)
En el parser de `editar`:
```python
e.add_argument("--look", choices=["warm_black", "stone_light", "oro_editorial", "teal_sutil", "ninguno"], default=None, help="look de color de marca (defecto warm_black)")
e.add_argument("--color-modo", choices=["auto", "calidad", "rapido"], default="auto", help="calidad = 16 bit vivo (reels <= 3 min); rapido = LUT 3D horneada (largos); auto = por duracion")
```
y las dos llamadas `im.cadena(analisis.get("video"), info)` (lineas 76 y 79) pasan a:
```python
im.cadena(analisis.get("video"), info, look=getattr(a, "look", None), modo=(None if getattr(a, "color_modo", "auto") == "auto" else a.color_modo), ruta=src, proyecto=a.out)
```
(`--rapido` hoy solo cambia x264/Whisper; si se quiere que tambien use la LUT: `modo="rapido" if a.rapido and a.color_modo == "auto"`.)

## 6. Lo que NO se puede / no se probo
- Altas luces quemadas (persianas de t03) y bitrate de origen bajo: se reportan, no se arreglan.
- Piel oscura vs cara subexpuesta: indistinguibles con una cara; no se forzo 150 (aviso). Sin carta de color el dE es relativo.
- No se probo: video real a contraluz (solo sintetico), HDR real (solo sintetico, color.md), escenas con dos personas (t07 se detecta y se deja solo en look), 40 min reales (solo 240 s en bucle).
- `render.py` aplica despues su luz de estudio (`eq` 8 bit + elipse) sobre la cara: sube algo mas la piel. Medido en la base final de `editar` (con luz 1.0, tras recortes y lanczos): t01 piel Y 153.8 / 123.1 grados (cadena sola 152.5 / 124.2), s01 143.3 / 123.6 grados. Efecto ~+1 de Y, dentro de la tolerancia.
- `hqdn3d` y `unsharp` siguen en 8 bit dentro de `chain_pre`/`chain_post` (denoise antes del bloque de 16 bit, nitidez despues de la salida legal): el orden es el medido, la profundidad de esos dos es la de siempre.
