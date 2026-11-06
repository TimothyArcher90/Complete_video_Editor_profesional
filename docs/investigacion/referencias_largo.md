# Referencias de formato largo horizontal: medido sobre los archivos reales (2026-11-06)

Fuentes: UPSB «La tesis de Bitcoin…» (DR0pyraeIBU, 23:33, 1080p, 29,97 fps) y Arte de Invertir «La gente no tiene ni idea…» (6-AzqY6KRWM, 23:12, 1080p).
Método: descarga local (David los dejó en `CONTEXTO`), detección de cambios fotograma a fotograma (`ref_video.py`), hojas de contacto y ráfagas de 10 fps en cada transición, EBU R128, texto por captions (`ref_texto.py`). Lo medido está en `_pruebas/referencias_largo/*.video.json`.

## Ritmo (medido)
- **UPSB:** 165 cortes secos + 3 graduales, **7,1 cambios/min**, plano mediano **5,9 s**, máx. 46,9 s; primer minuto con 12 cambios, luego 1-19 según haya gráficos.
- **Arte de Invertir:** 38 cortes secos + 32 transiciones graduales, **3,0 cambios/min**, plano mediano **4,5 s**, máx. 145 s (presentador a cámara larga) y picos de 13-14 en minutos con montaje de cifras.
- Habla: **3,1-3,2 palabras/s**, 0,1-0,5 pausas largas/min (casi sin silencios), cifras 4,4-11,7/min. Patrocinio/CTA solo ~1 a los 10 min y 1 al final.
- Cuidado: el detector cuenta también gráficos que animan, no solo cortes de cámara. Es el ritmo VISIBLE, que es lo que ve el espectador.

## Transiciones (vistas en ráfagas de 10 fps)
- **Dominante: corte seco.** Cambio de plano, entrada de gráfico a pantalla completa y vuelta al presentador son cortes.
- **Presentador → rótulo sobre B-roll:** disolvencia corta (~0,15 s, mediana medida 0,15 s) con leve caída de luz; luego el texto aparece **de borroso a nítido** en ~0,35 s. Sin whips ni glitch.
- **Tarjeta de gráfica:** pop-in suave sobre el hombro (UPSB): entra con escala y opacidad ~0,25 s; sale igual.
- **Cambio de ánimo por color (UPSB):** todo el cuadro se tiñe de verde (subida) o rojo (bajada) con velas que se dibujan; cierra con una caída a negro. Funciona como puntuación emocional.
- Regla que sacamos: una sola gramática de transición por video.

## Subtítulos (revisados)
- **Ninguna de las dos referencias usa transcripción corrida.** Arte de Invertir pone **píldoras de frase clave** (2-4 palabras, redondeadas, 1 o 2 seguidas) en el tercio inferior izquierdo, fuera de la cara; también chips de nombres (RD / WB / SD / JPM). UPSB casi no subtitula: usa rótulos kinéticos.
- Lo que adoptamos: píldora opaca Warm Dark, texto Stone Light, palabra clave en lima, deslizamiento 0,2 s. **No copiamos** el azul traslúcido (Premiere lo grisea y no es marca).

## Letras grandes (revisadas)
- Arte de Invertir: rótulo central de 2-4 palabras en mayúsculas sobre B-roll desenfocado («LA MAYORÍA», «UNOS POCOS», «BONOS»), con microetiqueta arriba («OPCIÓN 1») y subtítulo de 1 línea abajo. Cifra grande en tarjeta («20 AÑOS»). Cada ~25 s como máximo.
- UPSB: titulares condensados en negrita con palabra clave en amarillo, «AL GRANO, POR FAVOR» sobre el presentador desenfocado, «HOY / NOV 2026» como sello.
- Adoptamos: Geist Bold mayúsculas, ~11 % del alto, entrada blur→nítido, fondo Warm Black o B-roll oscurecido; **sin glow**.

## Gráficos (catálogo)
Tarjeta de línea sobre el hombro; pantalla completa oscura con título + fuente al pie («Fuente: …, fecha»); barras que crecen en secuencia; lista numerada con puntos de progreso; línea de tiempo con hito; termómetro con tope; tinte verde/rojo con velas; mapas de pantalla completa para Electric Eye. **Todas rotulan fuente y fecha.**

## Audio
UPSB −14,3 LUFS; Arte de Invertir **−12,3 LUFS con pico +0,3 dBTP (recorta)**. Nuestro objetivo −14 / −1 dBTP: no imitar el recorte.

## Qué no sirve copiar
Colores de marca ajena (azul eléctrico, amarillo UPSB), logotipos, resplandores, patrocinios, fondos de estudio. Solo la gramática: ritmo, tipo de transición, jerarquía de rótulos.

## Integración
`mw_editor/preset_largo.py` guarda estas reglas como datos (`RITMO`, `TRANSICIONES`, `LETRAS_GRANDES`, `SUBTITULOS_LARGO`, `GRAFICOS`) y `revisar_ritmo()` audita el ritmo de nuestro largo contra ellas. Herramienta: `mw_editor/ref_video.py` (cortes, transiciones, audio de cualquier referencia).

## Límites de este análisis
Dos videos son una muestra; el detector no distingue un zoom digital de un corte; no se midió el audio de música/efectos por separado. Las reglas son punto de partida, se afinan con más referencias.
