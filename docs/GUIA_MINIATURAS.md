# Miniaturas / portadas MacroWise

Comando: `python -m mw_editor miniatura --video VIDEO --titulo "Línea 1|Línea 2" --tema lima|valor|tecnico|geo|coste --etiqueta "TEXTO" --out <proyecto>\06_EXPORT\THUMBNAILS` (opcional `--t SEGUNDO`, `--imagen FOTO`, `--fondo fondo|teal|purpura|oro`).

## Qué se copió de las 3 referencias (y qué no)
| Referencia | Mecánica copiada | Traducción MacroWise |
|---|---|---|
| Raoul "Your house…" (cara grande + cajas apiladas) | Titular en 2 cajas redondeadas sobre el torso, debajo de la boca | Variante **B**: caja 1 Warm Black con texto blanco, caja 2 en color de taxonomía/lima con texto Warm Black |
| Raoul "The next big thing" (recorte sobre color) | Persona recortada, abajo-centro, titular enorme arriba con la 2.ª línea en caja de color | Variante **A** (hero): fondo SÓLIDO Warm Black (sin degradado), titular blanco + caja lima/oro/teal |
| Aztec "Valor vs Ruido" (foto + texto cursivo) | Texto grande inclinado sobre la foto, palabra clave en color | Variante **C**: texto inclinado, línea clave en color de marca, foto oscurecida pareja para contraste |

## Cómo se trata a la persona (reglas)
1. **Real y fiel al video:** el fotograma sale del propio video (nunca de otro), sin deformar ni retocar la cara. El motor puntúa ~36 fotogramas por cara grande y centrada + nitidez + exposición y deja `miniatura_candidatos.jpg` y `miniatura_ranking.json` para que David pueda elegir otro con `--t`.
2. **Recorte limpio (BiRefNet-portrait, MIT):** se conserva solo la persona principal (se eliminan manos/restos flotantes) y se erosiona 1 px para que no quede halo. Si el recorte se ve mal, usar las variantes B o C (foto completa).
3. **Cara 20 % del alto (vertical) / 34 % (horizontal), ojos en el tercio superior,** torso llega al borde inferior; el titular nunca tapa cara ni boca.
4. **Zona segura de Instagram:** el grid recorta 3:4 al centro (y 240–1680 sobre 1920). Etiqueta y logo a y≥262; nada importante fuera.
5. **Titular:** máx. 5 palabras en 2 líneas; línea 1 blanca, línea 2 en caja opaca. Color de la caja = taxonomía (oro valor · teal técnico · púrpura geo · terracota coste · lima = concepto). El titular debe salir de lo que se dice en el video, no de fuera.
6. **Marca:** etiqueta Geist Mono (borde del color del tema) + logo MW blanco. Sin neón, glow ni degradados.

## Límites
- La calidad la limita el video de origen (un fotograma de 517 kbps sale blando).
- Fuente de titulares: Geist **Bold** (la guía fija SemiBold 600; en miniatura se sube el peso para legibilidad: decisión mía, revisar).
- Lima y terracota no están en la paleta oficial; son decisión mía.
