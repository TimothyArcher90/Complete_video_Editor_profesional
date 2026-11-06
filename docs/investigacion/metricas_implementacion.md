# Métricas del QC: implementación (2026-11-05)

Código: `mw_editor/metricas.py` (marco, puntuación, historial), `mw_editor/qc_extra.py` (las mediciones), `mw_editor/manifiesto.py` (M25, M26), `mw_editor/qc.py` (orquesta y mantiene `qc_proyecto()` / `resumen_estado()`), `mw_editor/lote.py` (cuadro comparativo).
Todo se mide en local con ffmpeg/ffprobe/OpenCV/NumPy: **0 coste, 0 APIs**. Umbrales: `docs/investigacion/metricas.json` (columna `confianza`).

## Cómo se usa

- Automático: `lote` y `entrada` ya llaman a `qc_proyecto()`; ahora además escriben `00_DOCS\metricas.json`, `00_DOCS\manifiesto_ia.json` y `00_DOCS\qc.json`.
- Solo medir proyectos ya editados (sin re-renderizar): `from mw_editor.lote import qc_proyectos; qc_proyectos([carpeta_de_proyectos_o_proyecto], etiqueta="v3 zonas")`. Guarda la corrida y escribe `CUADRO_METRICAS.md`.
- Iterar toda la noche: cada `lote(...)` guarda su puntuación en `HISTORIAL_METRICAS.json` (en `out_root`, o donde diga la variable `MW_HISTORIAL`) y `RESUMEN_TESTS.md` abre con el cuadro: puntuación 0-100 por clip, flecha contra la corrida anterior (▲ ▼ =), y qué métricas mejoraron o empeoraron.
- Para que el QC de cifras vea las fuentes, `lote(..., plan=ruta_plan.json)` copia el plan a `00_DOCS\plan_grafico.json`. Con `editar` suelto hay que copiarlo a mano (el motor no guarda el plan; ver "Pendiente en `__main__`").
- Perfil de plataforma: `qc_proyecto(proj, perfil="tiktok")` (o `instagram_reels`, `youtube_shorts`, `linkedin`, `youtube_largo`) limita duración y entrega a esa plataforma; sin perfil se evalúan todas las del formato.

## Formato de cada métrica

`{id, nombre, valor, unidad, umbral_pass, umbral_warn, estado, detalle, confianza_del_umbral, peso, puntaje, informativo}` (+ `check` = `nombre`, para compatibilidad con lote/entrada).

- **estado**: PASS / WARN / FAIL / N/A (no aplica o no medible: no puntúa).
- **puntaje** 0-1 continuo: 1 en el umbral PASS, 0.5 en el borde WARN, 0 en el borde FAIL. Sirve para ver mejoras dentro de un mismo WARN.
- **peso** = prioridad (alta 3, media 2, baja 1) × factor de confianza (oficial 1, terceros 0.75, estimado 0.5).
- **Puntuación 0-100** = Σ peso·puntaje / Σ peso de las métricas medibles (N/A no cuenta). Se calcula por formato, por "proyecto" (voz/SRT/manifiesto) y global.
- **Política anti-falso-FAIL**: una métrica con umbral `estimado` o `terceros` **no puede dar FAIL** (se degrada a WARN y lo dice en el detalle) salvo defecto objetivo marcado `duro` (alfa vacío, ProRes mal, texto sobre ojos/nariz, cifra sin fuente, parámetros de entrega rotos, resolución).
- **informativo**: WARN que no cambia el estado global del output (`resumen_estado`) pero sí resta puntuación. Lo son todas las de umbral `estimado`/`terceros` no duras. El estado global es FAIL si hay algún FAIL; WARN si hay algún WARN no informativo; si no, PASS.

## Qué se mide, cómo, umbral y confianza

| Id | Métrica | Cómo | PASS / WARN | Confianza |
|---|---|---|---|---|
| M01 | Tiempo al primer evento visual/texto | `scdet` (umbral 6) sobre el base + saltos de montaje (`cut_plan.json`) + inicio de tarjetas (ASS de gráficos) + primer texto (ASS de subtítulos). Eventos a < 0.3 s se funden en uno | corto ≤ 1.5 s / ≤ 3 s; largo ≤ 5 / ≤ 10 | estimado |
| M02 | Inicio de voz | primera palabra de `words_final.json` | ≤ 1.0 s / ≤ 2.0 s | estimado |
| M03 | Cortes por minuto y plano medio (ASL) | eventos de M01 / duración. N/A en clips < 8 s | corto 12-30 / 6-40; largo 4-15 / 2-25 | estimado |
| M04 | Máximo tramo sin cambio visual | mayor hueco entre 0, eventos y fin | corto ≤ 5 s / ≤ 8; largo ≤ 15 / ≤ 30 | estimado |
| M05 | Palabras por segundo | palabras / (voz − pausas > 0.4 s) | 2.2-3.3 / 1.8-3.9 | estimado |
| M06 | CPS de subtítulos | SRT: caracteres sin saltos / duración del cue; p95 y cues > 21 | p95 ≤ 17 / ≤ 21 | terceros (Netflix; español sin verificar) |
| M07 | Caracteres por línea y líneas por cue | SRT (≤ 42, ≤ 2 líneas) y grupos animados del ASS (≤ 28 vertical, ≤ 42 horizontal) | PASS dentro; WARN +5 car / 3 líneas | terceros |
| M08 | Duración de cues SRT | % de cues entre 0.83 y 7 s | 100 % / ≥ 90 % | terceros |
| M08b | Cobertura de voz por subtítulos | palabras cuyo centro cae dentro de un cue | ≥ 95 % / ≥ 85 % | terceros |
| M08c | Grupos animados | duración mínima de grupo (≥ 0.25 s) y % de palabras visibles < 0.1 s (≤ 3 %) | ver detalle | terceros |
| M09 | Contraste WCAG | ver abajo | p20 ≥ 4.5:1; si no, WARN (tope) | oficial (la fórmula), medición aproximada |
| M10 | Texto en zona segura **por perfil** | máscara alfa a media resolución, 4 muestras/s (menos en clips largos); caja del texto frente a la caja segura del **preset activo** de `zonas.py` (`preset:universal` por defecto; decide el estado) y de cada perfil/preset del formato (se listan los que fallan); tolerancia 6 px; se excluye la entrada deslizante de tarjetas (−0.15 s / +0.3 s) | 100 % / ≥ 98 % | terceros (las cifras de zona no son oficiales) |
| M10a | Caja unión de subtítulos en zona segura | check clásico de `qc.py`, 10 fotogramas, tolerancia 6 px (antes 2 px en x y 0 en y: daba FAIL por 2-3 px de sombra/descendentes) | PASS/FAIL | terceros |
| M11 / M11b | Tamaño mínimo de texto (subtítulos / gráficos) | `\fs` y estilos de los ASS ÷ alto del lienzo | ≥ 2.29 % del alto vertical (44 px en 1920) o 3.33 % horizontal (36 px en 1080); WARN ≥ 1.9 % / 2.6 % | estimado |
| M12 | Sonoridad y true peak | `loudnorm` (clásico) | −14 ± 1.5 LUFS y ≤ −0.7 dBTP | terceros |
| M15 | Silencio muerto | `silencedetect` −45 dB, ≥ 0.25 s, sobre el audio del base | máx ≤ 0.6 s y < 8 % (corto) | estimado |
| M16 | Cara visible | YuNet en 8 fotogramas (clásico) | ≥ 60 % | estimado |
| **M16a** | **Solape cara-texto** | YuNet (cara principal, ≥ 0.8) frente a la máscara alfa de subtítulos+tarjetas **en el mismo fotograma**; se prueba si el texto opaco cubre los landmarks de ojos y nariz (±3 px a media resolución); boca y % de la caja de cara como aviso | **FAIL si cubre ojos/nariz en ≥ 1 muestra**; WARN boca o > 20 % de la caja | estimado, pero defecto objetivo (`duro`) |
| M16b | Tamaño de la cara | alto de la caja de cara ÷ alto del cuadro | 12-45 % | estimado |
| M20 | Duración vs rango de plataforma | duración frente al óptimo/máximo de cada plataforma del formato (tabla en `metricas.PLATAFORMAS`) | PASS si cae en el óptimo de ≥ 1 plataforma | terceros (Shorts: máximo oficial) |
| M21 | Parámetros de entrega | ffprobe del MP4 de referencia: H.264, perfil High, yuv420p, tags BT.709, CFR 24-60, bitrate vs 8 Mbps (×px, ×1.5 si > 30 fps), AAC 48 kHz estéreo, `moov` antes de `mdat` | FAIL (duro) si códec/pix_fmt/audio mal; WARN si tags/bitrate/faststart/CFR | oficial (YouTube); el bitrate es recomendación, no requisito |
| M21b/c | ProRes 4444 con alfa | ffprobe: `prores`, perfil 4444, `pix_fmt` `yuva*` | PASS/FAIL | oficial |
| M22, M23, M24, M30 | Negros, alfa real, sincronía A/V, resolución | checks clásicos envueltos | igual que antes | |
| M25 | Manifiesto de IA | `manifiesto.py` escribe `00_DOCS\manifiesto_ia.json` y comprueba coherencia (clips sin `origen`, referencias a servicios generativos) | PASS / WARN | oficial |
| M26 | Cifras en pantalla | ver abajo | FAIL (duro) si una cifra rotulada no tiene fuente y `verificada:true`, o si hay un número en pantalla que no está en el plan | oficial |

### M09 contraste: cómo se mide
Sobre 14 fotogramas de subtítulos y 8 de tarjetas se compone la capa sobre el fotograma real (media resolución). Se separan los colores opacos de la capa en: relleno de caja (componente grande y compacto), marcos/barras decorativas (descartados) y glifos (el resto). Para cada color de glifo: luminancia WCAG del texto frente a la del fondo alrededor (anillo a 3-5 px del glifo, sin el borde suavizado del propio texto; **la sombra cuenta**, las cajas cuentan como fondo). Se toma el percentil 75 del fondo si el texto es más claro y el 25 si es más oscuro (peor caso razonable). Valor = percentil 20 de las muestras. Tope WARN porque sobre vídeo en movimiento la medición es aproximada.

### M26 cifras: cómo se registran
`manifiesto_ia.json › cifras_rotuladas` lista cada cifra del plan con `valor`, `fuente`, `verificada` y si está rotulada. Se leen los números realmente dibujados en los ASS de gráficos y se exige que cada uno esté en el plan. Si el plan no se conservó (`00_DOCS\plan_grafico.json` ausente) y hay números en pantalla: WARN "no verificable". Si el motor descartó una cifra por falta de fuente: WARN "preguntar a David" (no se omite en silencio). Números en títulos libres ("45 %") no tienen campo de fuente: hoy solo se comprueba que estén en el plan.

## Manifiesto de IA y procedencia (`00_DOCS\manifiesto_ia.json`)
Declara: escenas generadas = NO, voz clonada/sintética = NO, rostros generados = NO, con su evidencia (el audio sale de la pista original; los gráficos son ASS vectoriales; ningún módulo del motor importa servicios generativos). Lista herramientas con versión y licencia (FFmpeg, faster-whisper, YuNet; BiRefNet-portrait solo si hay miniaturas), las alteraciones sobre el material real (denoise, EQ, compresión, encuadre/zoom, luz de estudio) y, por plataforma, la nota de etiquetado de la investigación con `verificar_en_la_app: true`. **No decide** si una plataforma obliga a etiquetar: eso cambia y no hay API.

## Qué NO se puede medir automáticamente
- Si el gancho es bueno, si el corte "se siente" ágil, si el subtítulo distrae: se mide el ritmo, no el gusto.
- Retención real, swipe-away, CTR: solo existen en las analíticas de cada plataforma tras publicar.
- Contraste exacto: el vídeo cambia por fotograma; se muestrea (22 fotogramas) y se aproxima el fondo.
- Tamaño de texto realmente renderizado: se lee lo declarado en el ASS (no los píxeles); Premiere puede escalarlo.
- GOP cerrado, B-frames, perfil de color real del archivo que subirá Premiere: no se leen (solo tags).
- Si un clip insertado (mapa, gráfica de otro programa) es o no generado por IA: hay que declarar `origen` en el plan.
- Si hace falta etiqueta de IA en cada plataforma y la zona segura real de Reels/TikTok/Shorts: verificar en la app (Safe zone guardrail de Meta Ads Manager).
- Verdad de las cifras: el QC comprueba que tengan fuente y estén marcadas verificadas, no que la fuente diga eso.
- Loudness/LRA, nitidez, ruido residual y exposición (M13-M14, M17-M19) quedan fuera de esta entrega (prioridad media).

## Rendimiento
En este equipo `ffmpeg` tarda 3-5 s solo en arrancar, así que el QC lanza en paralelo todo lo independiente (hilos) y lee cada capa con alfa **una sola vez**. Un proyecto de 10 s con 2 formatos tarda ~2 min con el PC cargado (medido con 4 proyectos a la vez); el coste es casi todo arranque de ffmpeg, no cálculo.

## Pendiente en `__main__.py` (otro agente; no editado aquí)
1. Guardar el plan al editar: tras leer `plan`, `if a.plan: shutil.copyfile(a.plan, C["00_DOCS"] / "plan_grafico.json")`.
2. Subcomando `qc`:
```python
def cmd_qc(a):
    from .lote import qc_proyectos
    qc_proyectos(a.proyectos, historial=a.historial, perfil=a.perfil, etiqueta=a.etiqueta)
# en main(): q = sp.add_parser("qc"); q.add_argument("proyectos", nargs="+"); q.add_argument("--perfil"); q.add_argument("--historial"); q.add_argument("--etiqueta", default=""); q.set_defaults(fn=cmd_qc)
```
