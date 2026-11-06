# Zonas seguras y encuadre de cara: implementación (2026-11-05)

Agente 'zonas y arte'. Archivos tocados: `mw_editor/zonas.py`, `planos.py`, `render.py` y nuevos `guias_zonas.py`, `verificar_encuadre.py`.
No se tocó `__main__.py`, `subs.py` ni `componer.py` (componer no necesitó cambios).

## 1. Zonas unificadas (`zonas.py`)

**Ninguna cifra de interfaz es oficial.** Ninguna plataforma publica zona segura en píxeles (ver `zonas_seguras.md`). Cada perfil lleva `confianza`:

| Confianza | Significado |
|---|---|
| `terceros` | cifra de plantillas/blogs de terceros (TikTok, Instagram Reels) |
| `estimado` | cálculo propio, **tratar como estimación** (YouTube Shorts, LinkedIn, feed 4:5, 16:9) |
| `criterio` | criterio propio de Electric Eye (`estandar`, columna de botones) |

Las especificaciones técnicas (resolución, peso, códec) de LinkedIn y YouTube sí son oficiales, pero no hacen oficiales sus zonas.

Perfiles (`zonas.PERFILES`, px sobre el lienzo del formato; coinciden con `zonas_seguras.json`, comprobable con `--comprobar`):

| Perfil | Formato | Arriba | Abajo | Izq | Der | Confianza |
|---|---|---|---|---|---|---|
| `tiktok` | 9:16 1080x1920 | 240 | 660 | 120 | 140 | terceros |
| `instagram-reels` | 9:16 | 270 | 672 | 65 | 120 | terceros |
| `youtube-shorts` | 9:16 | 270 | 480 | 60 | 140 | **estimado** |
| `linkedin-vertical` | 9:16 | 270 | 480 | 65 | 120 | **estimado** |
| `linkedin-cuadrado` | 1:1 1080x1080 | 65 | 120 | 65 | 65 | **estimado** |
| `linkedin-4x5` | 4:5 1080x1350 | 70 | 150 | 65 | 65 | **estimado** |
| `instagram-feed-4x5` | 4:5 | 70 | 150 | 100 | 100 | **estimado** (no está en el JSON: margen lateral de la cuadrícula 3:4) |
| `youtube-16x9` | 16:9 1920x1080 | 65 | 110 | 96 | 96 | **estimado** |
| `linkedin-16x9` | 16:9 | 65 | 110 | 96 | 96 | **estimado** |

Presets heredados de Electric Eye (solo 9:16, se conservan): `estandar` 220/380/40/140 (criterio), `meta-reels` 269/672/65/65 (terceros), `universal` 269/672/122/242 (terceros, **defecto del motor**).

**Unión conservadora** para exportar a varias redes a la vez (máximo de cada margen):

```python
from mw_editor import zonas
zonas.union_px("tiktok+instagram-reels+youtube-shorts", "vertical")   # {'arriba': 270, 'abajo': 672, 'izquierda': 120, 'derecha': 140}
zonas.union_seg(["tiktok", "instagram-reels"], "vertical")            # en fracciones
zonas.confianza_union("tiktok+youtube-shorts", "vertical")           # 'estimado' (la peor de sus miembros)
zonas.resumen_union(zonas.perfiles_de_formato("4x5"), "4x5")          # línea de texto con márgenes, rect y aviso
zonas.set_preset("tiktok+instagram-reels")                           # o MW_ZONA=... : seg()/caja_segura_px() usan la unión
```

Si el preset no nombra perfiles del formato pedido, `seg()` usa la unión de **todos** los perfiles de ese formato (1:1, 4:5 y 16:9 ya no usan los márgenes "provisionales" anteriores; el de 1:1 sube de 8 % a 11 % abajo, el de 4:5 de 9 % a 11 %).
Nota: la unión de plataformas 9:16 (270/672/120/140) es **menos ancha a la derecha** que el preset `universal` del motor (242). Se mantuvo `universal` como defecto por prudencia (columna de botones); la guía dibuja ambos.

## 2. Guías visuales (`guias_zonas.py`)

```
python -m mw_editor.guias_zonas                          # 8 PNG en docs/guias_zonas/
python -m mw_editor.guias_zonas --frame captura.png      # guía sobre una captura de la app
python -m mw_editor.guias_zonas --video clip.mp4 --t 3 --clip   # sobre un fotograma / un MP4 corto con la guía encima
python -m mw_editor.guias_zonas --comprobar              # zonas.py == zonas_seguras.json
```

- `guia_9x16.png`, `guia_1x1.png`, `guia_4x5.png`, `guia_16x9.png`: fondo Warm Black + rejilla del 10 %, banda prohibida de cada plataforma (un color por plataforma: oro, teal, púrpura, terracota; línea discontinua), **unión en lima**, `universal` del motor (9:16), columna de botones, recortes 3:4/4:5 de la cuadrícula de Instagram, banda de ojos objetivo (30-38 %), caja de subtítulos y leyenda con la confianza de cada cifra.
- `guia_*_overlay.png`: RGBA transparente (solo líneas y etiquetas) para superponer encima de una captura real del móvil y contrastar. **Esto es lo que David debe hacer**: capturar cada app con un vídeo de prueba y comprobar si las cifras coinciden; lo que no coincida se corrige en `zonas.PERFILES`.

## 3. Encuadre: la cara ya no queda bajo los subtítulos

Problema medido: con `universal` los subtítulos terminan en y ≈ 65 % y la cara (ojos ≈ 51-55 %) quedaba tapada.

Solución (`planos.recortes`, solo formatos con subtítulo bajo la cara: 9:16, 1:1, 4:5; `horizontal` no cambia):

1. YuNet da caja de cara y ojos por muestra (`detectar_cajas`; ahora respeta la relación de aspecto del origen, antes aplastaba los verticales a 16:9). Por toma: ojos (mediana), cabeza (percentil 15 de la parte alta) y barbilla (percentil 85).
2. Se calcula el tope del bloque de subtítulos (`tope_subtitulos`, lee `zonas.seg()` y los `\fs` de `subs._FS`: una línea que termina en el borde de la zona segura).
3. Objetivo: ojos en **30-38 %** del alto, barbilla ≥ 3 % por encima del bloque de subtítulos, cabeza entera (la caja de YuNet + 35 % de pelo). Se prueba en orden de menos a más intrusivo:
   - **a)** zoom base (1.0 / `--zoom`) con el recorte desplazado, y punch-in algo mayor en pasos de +0.02 (máx. base+0.10, tope 1.30) hasta que los ojos entren en la banda sin salirse del origen;
   - **b)** si no, ojos algo más bajos (≤ 42 %) pero sin solape;
   - **c)** **relleno inferior**: el recorte baja más allá del borde del origen; la parte real va arriba y debajo su propio borde reflejado, desenfocado y 8 % más oscuro, fundido en una franja corta (sin degradados de color ni neón). Cae bajo los subtítulos y la interfaz de la app. Máx. 30 % del recorte;
   - **d)** cara enorme (no cabe cabeza + barbilla sobre los subtítulos): el vídeo se **reduce** (escala k ≥ 0.70) sobre su propio fondo desenfocado y oscurecido, como el modo `pilar`.
4. `render.py` interpreta el 7º elemento opcional de cada recorte (`{'vis': px}` relleno o `{'k','yf'}` encogido). Los recortes sin 7º elemento se renderizan igual que antes. La elipse de la luz de estudio sube de y 40 % a 37 %.
5. A/B con el encuadre antiguo: `MW_ENCUADRE=clasico`.

### Medición (YuNet sobre el MP4 base renderizado, 4 fps; subtítulos reconstruidos del ASS real)

`python -m mw_editor.verificar_encuadre BASE.mp4 SUBS.ass [--formato vertical]`. Métrica A = % de fotogramas con cara **sin** solape entre bbox de la cara y bbox de unión de los subtítulos activos. Criterio ≥ 95 %.

| Clip (origen) | Cara detectada | Sin solape ANTES | Sin solape DESPUÉS | Ojos (alto) antes -> después | Modos usados |
|---|---|---|---|---|---|
| t01 plano medio (16:9) | 40/40 | 2.5 % | **100 %** | 0.51 -> 0.34 | relleno inferior en 3/3 tomas |
| t02 cerca (16:9, cara en recuadro) | 39/40 | 30.8 % | **100 %** | 0.43 -> 0.33 | relleno en 2/3, punch-in en 1/3 |
| t03 raoul wide (16:9, cara enorme) | 21/21 | 33.3 % | **100 %** | 0.34 -> 0.29 | video reducido (k 0.79) |
| t05 reel vertical 720x1280 | 13/15 | 7.7 % | **100 %** | 0.50 -> 0.34 | relleno inferior |
| t08 podcast 1080p | 32/32 | 71.9 % | **100 %** | 0.31 -> 0.30 | reducción k 0.93-0.97 y recorte |
| **Total (5 clips, 145 muestras)** | | **30 %** | **100 %** | | |
| t02 cuadrado 1:1 (extremo a extremo) | 40/40 | n/d | **100 %** | 0.38 | |
| t02 4:5 (extremo a extremo) | 39/40 | n/d | **100 %** | 0.37 | |
| t01 4:5 (extremo a extremo) | 40/40 | n/d | **100 %** | 0.33 | |

"Antes" = encuadre antiguo (`MW_ENCUADRE=clasico`, cara al 40 % del recorte), medido con la misma herramienta y el mismo ASS de esa corrida. Cabeza cortada: 0 % en todos salvo t03 (4.8 %, 1 de 21 muestras) y t08 (31 %); en ambos el **origen** ya tiene la cabeza pegada al borde superior (caja de cara a 11-17 % del alto con la cabeza que sobresale 35 %), antes del cambio t08 daba 28 %; no hay recorte propio por encima de lo que da el origen (visto en fotograma). Los ojos quedan en la banda 30-38 % en 100 % de los fotogramas de t01, t02 y t05, 29 % en t03 y 34 % en t08 (caras enormes: manda no tapar y no cortar).
Medición de t10 (gesto) y t04 (sin cara): no completada (ver pendientes). Archivos de prueba: `_pruebas/agentes/zonas_arte/` (`antes/`, `rap/`, `despues/`, `medidas`).

## 4. 1:1 y 4:5 de extremo a extremo

`python -m mw_editor editar CLIP --out DIR --formato cuadrado|4x5 --rapido` termina sin errores y produce base, ASS, SRT, ProRes 4444 con alfa y REFERENCIA (clips `t02` cuadrado, `t02` y `t01` 4:5). El encuadre de cara aplica a ambos (tope de subtítulos 80 % del alto en 1:1 y 81 % en 4:5). No hubo fallos en `subs.py`.

## 5. Pendiente y avisos

- **Cifras por contrastar con capturas reales** (guías `*_overlay.png`). `youtube-shorts`, LinkedIn, `instagram-feed-4x5` y 16:9 son estimaciones.
- `subs.py` se estaba reescribiendo en paralelo (una línea, `\fs` 94). `planos.tope_subtitulos` y `verificar_encuadre` leen `subs._FS` y `subs.ancho_real`; si se renombran, caen a brand.json (2 líneas, 78 px) y el encuadre se vuelve más conservador.
- Caras enormes (plano muy cerrado en origen 16:9) usan relleno o reducción; si el look no gusta, subir `RELLENO_MAX`/bajar `K_MIN` en `planos.py` o aceptar punch-in mayor.
- Cabeza cortada: solo cuando el propio origen ya la corta (la caja + pelo sale del fotograma original); el encuadre nunca recorta por encima de lo que da el origen.
- `common.run()` no pasa `stdin=DEVNULL` a ffmpeg: lanzado en segundo plano (nohup) a veces se queda colgado esperando stdin. Recomendado `-nostdin` o `stdin=subprocess.DEVNULL` (archivo `common.py`, no mío).
- Sin medir: `t10` (gesto) y `t09` (sin audio, no genera subtítulos) y `t04` (sin cara). Pendiente del lote completo de 10 clips.
- Las medidas 'DESPUÉS' de los 5 clips verticales salen de `_pruebas/agentes/zonas_arte/rapido.py` (mismo `recortes`+`render_base`+`ass_subtitulos_visual` de `editar`, sin audio/ALFA/referencia para iterar); 1:1 y 4:5 salen de `python -m mw_editor editar` completos.
