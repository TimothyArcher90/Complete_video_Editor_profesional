# Subtítulos dinámicos y texto grande de énfasis

Fecha: 2026-11-05. Módulos: `mw_editor/subs.py`, `mw_editor/detectar.py`, `mw_editor/enfasis.py`, `mw_editor/plan_auto.py`.
Pruebas y hojas de contacto: `_pruebas/agentes/subs/` (`hojas/`, `hojas_reales/`).

## 1. Subtítulos

### Qué fallaba
- El perfil universal deja **716 px útiles** en 9:16 (x 122-838) y la zona termina en y=1248. El agrupador antiguo cortaba por nº de palabras (≤4) y tiempo, no por anchura: envolvía a 2 líneas con frecuencia y tapaba la cara.
- Se medía con PIL al tamaño `\fs`, pero **libass interpreta `\fs` como altura de celda** (ascent+descent), no como em. Calibrado con ffmpeg: el texto real mide **0,84 ×** la medida de PIL (`K_LIBASS`). Antes las cajas salían ~20 % más anchas que el texto y la agrupación era a ciegas.

### Qué hace ahora
- `agrupar_linea()` mide con la fuente real (`ancho_real` = PIL × 0,84 + espaciado) y **corta antes de pasarse de la línea**; deja reserva para el relleno de la caja; no deja una palabra funcional ("de", "the") colgando al final de un grupo.
- **Una línea por grupo.** Única excepción justificada: una palabra suelta más ancha que la zona ("Anticonstitucionalmente"): se baja el cuerpo hasta que quepa (no se puede partir una palabra). `estadisticas_agrupacion()` lista las excepciones.
- **Tamaño:** `\fs` 94 en 9:16 = em real 79 px = **4,1 % del alto** (requisito ≥ 4 %). 1:1 fs 66 (5,1 %), 4:5 fs 76 (4,8 %), 16:9 fs 68 (5,3 %).
- **Zona:** todo sale de `zonas.caja_segura_px(formato)`; la línea termina en el borde inferior de la zona (en 9:16 universal, y=1248) y se centra en la zona (no en el lienzo). No se tocan perfiles.
- Entrada rápida palabra a palabra (pop de 100 ms, 14 px); palabra clave en caja opaca del color de taxonomía (cifra/importe oro, % teal, coste terracota, lugar púrpura, concepto/sigla lima). Las cajas de concepto genérico (lima) no se repiten en grupos consecutivos, para que sigan siendo señal. Siglas (PIB, ETF, Fed, IBKR…) cuentan como clave.
- Sombra suave, sin glow ni degradados. SRT editable y ProRes con alfa siguen saliendo igual (verificado: bbox del alfa de los subtítulos dentro de la zona, y 1149-1241 en y para 9:16).

### Estilos (`--estilo`)
| estilo | descripción | uso |
|---|---|---|
| `visual` (defecto) | palabra a palabra, 1 línea, caja de color en la palabra clave | reels/shorts |
| `clasico` | 1 línea, grupo entero a la vez, palabra activa en lima | sobrio |
| `karaoke-cajas` | grupo visible desde el inicio; caja opaca que salta a la palabra que se dice | ritmo marcado |
| `minimo` | frases de 1-2 líneas (balanceadas), sólo fundido de 120 ms, sin cajas | largo / horizontal |

Punto de entrada: `subs.ass_subtitulos_estilo(palabras, formato, ruta, estilo, ocultar=None, tam=None)`.
Mientras `__main__` sólo ofrezca `visual`/`clasico`, la variable de entorno **`MW_ESTILO_SUBS`** fuerza cualquiera de los cuatro (los wrappers `ass_subtitulos_visual` / `ass_subtitulos` la respetan).

### Fragmento de CLI para `__main__.py` (otro agente/Claude lo aplica)
```python
# en los 3 add_argument de --estilo (editar, lote, componer):
choices=["visual", "clasico", "karaoke-cajas", "minimo"]
# en _capas(), sustituir la línea de gs = ... por:
gs = su.ass_subtitulos_estilo(pf, fm, ass_s, estilo, ocultar=su.ocultar_desde_plan(plan))
# nuevo subcomando opcional:
#   python -m mw_editor.plan_auto --proyecto <carpeta> [--brief brief.json]   (ya funciona sin tocar __main__)
```

### Resultados medidos (palabras sintéticas con palabras largas, cifras, siglas; ES y EN)
En 9:16 (`estadisticas_agrupacion`): ancho disponible 678 px, 28 grupos para 68 palabras (2,4 palabras/grupo), **0 grupos en 2 líneas**, 1 excepción (palabra de 23 letras, reducida). Antes: la agrupación antigua partía en 2 líneas casi todo grupo de ≥3 palabras con cifras o palabras largas (ver `hojas/ANTES_*.jpg` frente a `DESPUES_*.jpg`).

## 2. Texto grande de énfasis (`enfasis.py`)

`enfasis.proponer(palabras, formato, idioma=None, evitar=None, cfg=None, dur_total=None)` lee `words_final.json` y devuelve `titulos_grandes`, `impacto`, `cta`, `cifras` (candidatas), `descartados` (con motivo) y `resumen`.

### Detectores (ES y EN, deterministas)
| tipo | ejemplo | salida |
|---|---|---|
| contraste | "no es una burbuja, sino un cambio de ciclo" · "it's not a bubble, it's a regime change" | título: línea fina "No es una burbuja", clave "Un cambio de ciclo" (anim `reveal`) |
| pregunta retórica | "¿qué pasa con Nvidia si el petróleo sube?" | etiqueta "La pregunta" + núcleo |
| imperativo / CTA | "compra oro ahora", "comenta link" | título, o `cta` si trae palabra clave |
| superlativo | "el mayor ajuste de la historia", "nunca", "record" | título (`escala`) o `impacto` si es una sola palabra |
| lugar / activo / nombre propio | China, Ormuz, petróleo, Nvidia, "Banco Central" | etiqueta de categoría + nombre canónico; lugares en caja púrpura |
| pausa | frase de 2-6 palabras tras pausa ≥ 0,8 s | título de una línea |
| cifra | "30%", "4,2 por ciento", "2,400 dollars" | **candidata** a tarjeta de cifra |

### Reglas y parámetros (`enfasis.CFG`)
- **No duplica el subtítulo:** el título arranca cuando termina la frase que refuerza (o se desplaza) y se **descarta si > 50 % (`max_solape`) de sus palabras con contenido se dicen mientras está en pantalla**. Excepciones declaradas: `impacto` (la palabra gigante es el énfasis) y la etiqueta de categoría, que no se dice.
- **Lectura:** `dur = 0,8 + palabras / 3` (máx. 3 palabras/s), entre 1,6 y 4,5 s.
- **Separación:** ≥ 4 s entre inicios (`sep_min`), ≥ 1 s de hueco entre fin y siguiente inicio (`hueco`), **máx. 5 por minuto** (`max_por_min`; en clips cortos, `round(5·dur/60)`, mínimo 1). Las cifras tienen cuota aparte (3/min) para no quitar sitio a los títulos. Nada antes de 0,8 s. `evitar=[(t0,t1)]` esquiva lower third/CTA/tarjetas (todos usan la parte alta en vertical).
- **Cifras:** nunca aparece en un texto una cifra que no esté en el audio (`verificar_cifras_en_audio`). Los años sueltos se ignoran.
- Variedad: la misma animación no se repite dos veces seguidas.

### Animaciones de entrada/salida (ASS puro; en `titulos_grandes` clave `anim`)
- `subir` (desplazamiento + fundido) · `escala` (62 % → 108 % → 100 %, curva de desaceleración) · `reveal` (barrido por palabra de izquierda a derecha con `\clip` animado, escalonado 120 ms, sube 22 px) · `barrido` (caja opaca que se abre con `\clip` y el texto encima).
- Salida: fundido de 170 ms. Sin glow, sin degradados. Colores púrpura/terracota (poco legibles como texto sobre vídeo oscuro) van automáticamente en caja opaca con texto blanco; `"caja": true` fuerza caja en cualquier color.
- Ajuste: si la línea no cabe en la zona, primero se parte en 2 líneas grandes (hasta 76 % del tamaño) y sólo si no, se encoge. `linea1` puede ir vacía.

### Modo `impacto` (`plan["impacto"]`)
`{"t", "dur" (≤ 1,2 s, se recorta con aviso), "palabra", "color": "lima"}`: palabra gigante en MAYÚSCULAS, a todo el ancho de la zona segura (tope 22 % del alto), lima con contorno Warm Black opaco (no glow) y golpe de escala 150 % → 100 %. Una palabra con cifra se **rechaza** si no trae `fuente` y `verificada:true`. `subs.ocultar_desde_plan(plan)` da los intervalos para que los subtítulos no compitan.

## 3. `plan_auto.py`
`python -m mw_editor.plan_auto --proyecto <carpeta> [--brief brief.json]` → `05_PROJECT/plan_auto.json` (o `--words … --out …`).
- Lower third en t=0,6 s si el brief trae `nombre` (+ `rol`); CTA al final si el brief trae `cta`; el resto, de `enfasis`.
- **Toda cifra va con `verificada:false` y `fuente:""`: el motor la rechaza ("CIFRA RECHAZADA") hasta que alguien la verifique contra fuente oficial.**
- Claves con `_` (`_tipo`, `_score`, `_motivo`, `_solape`, `_revisar`, `_descartados`) son notas para revisar; el motor las ignora.

## 4. Límites conocidos
- Heurísticas léxicas, no comprensión: los números dichos en palabras ("treinta por ciento") no se detectan como cifra; la etiqueta de una cifra (2 palabras previas) es sólo una sugerencia; "Whisper escribe mal" un nombre → el nombre propio sale mal ("Cloud" por Claude).
- Los títulos refuerzan después de la frase: en clips de ~10 s hay poco sitio (lower third + CTA ocupan la parte alta) y se descartan con motivo.
- Si el vídeo base ya trae texto grande o cara que ocupa todo el plano, los subtítulos (y el impacto) la tapan: la zona segura protege de la UI de la red, no de la cara. Un plano muy cerrado pide `minimo` o subir la línea.
- Medida calibrada para Geist SemiBold con libass de ffmpeg 8; otra fuente exige recalibrar `K_LIBASS`.
- Rendimiento: el `componer` completo (ProRes con alfa x2 + referencia) tardó ~2 min con la máquina saturada; la generación de ASS es instantánea.
