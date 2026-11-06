# Workflow agéntico — de un video de una persona a un paquete publicable

Objetivo: dado UN video (reel de una persona o un master largo), producir sin intervención humana en lo mecánico:
**Reel (9:16) + miniatura + copy**, **Video largo (16:9, y 1:1/4:5 para LinkedIn) + miniatura + copy**, con la marca MacroWise, para TikTok, Instagram Reels, YouTube Shorts, YouTube y LinkedIn. David solo aprueba lo editorial (cifras, titular, CTA).

## Roles (cada uno es un agente o una skill; dueño de sus archivos)
| Rol | Qué decide | Módulos | Entrega |
|---|---|---|---|
| **Director** (Claude principal) | Orquesta, lee el transcript, decide estructura, aprueba/descarta, escribe el copy final | skill `macrowise-editor` | plan.json, informe, URL del Doc |
| **Arte** | Encuadre, zonas seguras por red, color de personas, miniaturas | `zonas.py`, `planos.py`, `color.py`, `imagen.py`, `miniatura.py`, `guias_zonas.py` | base 9:16/1:1/4:5/16:9, miniaturas A/B/C |
| **Subtítulos y texto grande** | Subtítulos dinámicos (4 estilos), énfasis, impacto, CTA | `subs.py`, `enfasis.py`, `plan_auto.py` | ASS/SRT/ProRes alfa, plan inicial |
| **Datos** | Mapas (Electric Eye), gráficas (Ride the Lightning), cifras con fuente | `capas_externas.py` + MCP | clips en 04_GRAPHICS, plan de paneles |
| **Copy** | Título, descripción, hashtags, CTA por plataforma, capítulos | `copy.py`, `copy_playbook.md` | ficha_publicacion.json + Google Doc |
| **Producción** | Elige reels del master, capítulos, exporta por plataforma, sincroniza | `produce.py`, `clips.py`, `capitulos.py`, `exportar.py`, `sync.py` | 07_PUBLICAR/<plataforma>/ |
| **QA / Métricas** | Mide, puntúa 0-100, compara con la corrida anterior | `qc.py`, `qc_extra.py`, `metricas.py`, `manifiesto.py` | metricas.json, RESUMEN_TESTS.md |
| **Investigación** | Mantiene referencias y plataformas al día | `docs/investigacion/*` | reglas candidatas, dudas por verificar |

## Flujo
1. **Entrada.** David deja el video en `…\Video con Ia editor\INPUT_AQUI\` (opcional `brief.txt`: nombre, rol, titulo, tema, etiqueta, idioma, cta, plataformas) o arrastra al `.bat`. `python -m mw_editor entrada` (reel) o `produce MASTER` (largo + reels).
2. **Pasada automática** (sin humano): medir → transcribir en GPU → cortes entre palabras → audio −14 LUFS → imagen y color (look `warm_black`) → encuadre que respeta zonas y NO tapa la cara → subtítulos (estilo por formato) → ProRes con alfa + SRT + REFERENCIA → QC.
3. **Plan de capas** (Director + Subtítulos): leer `03_TRANSCRIPT/transcript_final.txt`, `candidatos.json` y `plan_auto`; decidir lower third, títulos grandes, impactos, cifras (candidatas con `verificada:false`), mapas y gráficas.
4. **Datos** (agente de Datos): pedir mapas y gráficas con las herramientas propias; verificar cada cifra contra fuente oficial antes de poner `verificada:true`; componer con `componer`.
5. **QC en bucle**: `qc` → si hay FAIL (alfa vacío, texto sobre ojos/nariz, cifra sin fuente) se corrige y se repite (máx. 3 vueltas); los WARN se anotan para David.
6. **Miniatura + copy**: `miniatura` (titular ≤ 5 palabras que se cumple en el video) y copy validado con `copy.validar_copy`; el copy va a un Google Doc nativo.
7. **Exportar y sincronizar**: `exportar` por plataforma (subtítulos incrustados solo en la variante de publicación; el master conserva la pista editable) y `sync` a E: (nunca borra).
8. **Informe + aprendizaje**: resumen en 3 bullets, puntuaciones, rutas, decisiones tomadas por Claude; los aprendizajes no triviales van a `CLAUDE.md`.

## Métricas (resumen; detalle en `docs/investigacion/metricas_implementacion.md`)
- Puntuación 0-100 por formato y por output, ponderada por prioridad × confianza del umbral; historial en `HISTORIAL_METRICAS.json` y delta contra la corrida anterior.
- **FAIL solo por defectos objetivos:** alfa vacío, ProRes inválido, cifra sin fuente, texto sobre ojos/nariz. Todo umbral estimado o de terceros se queda en WARN.
- Medidas: tiempo al primer corte, cortes/min, tramo máximo sin cambio, palabras/s, CPS, contraste WCAG, tamaño de texto, zona segura por perfil, solape cara–texto, LUFS/pico, parámetros de entrega, duración por plataforma, manifiesto de IA, cifras con fuente.
- Meta de la noche: media ≥ 88 sin FAIL en los clips de prueba de 10 s (media actual 89,0; t08 re-medido 92,5).

## Reglas que no se negocian
Marca (taxonomía de color, Geist, sin neón/glow/degradados, tarjetas opacas) · `01_RAW` intocable · subtítulos del master como pista editable · cifra rotulada = afirmación de marca (fuente oficial) · sin CodeFormer · sin gastar sin permiso · no se publica nada sin aprobación de David · rotular IA solo si la hay (el manifiesto lo declara) · cada cifra de zona segura declara su confianza.

## Qué NO hace (límites honestos)
No hay zonas seguras oficiales de TikTok/Instagram/Shorts (se usa la unión conservadora y se contrasta con capturas reales). No reemplaza el criterio editorial (hook, titular, cifras). No genera B-roll ni voz. El detector de caras elige la más grande (entrevistas con dos personas necesitan revisión). Whisper se equivoca en nombres propios.
