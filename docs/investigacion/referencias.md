# Referencias de estilo de edicion (nov 2026)

Alcance y metodo: yt-dlp solo metadatos (12 ultimos videos largos y 12 Shorts por canal; JSON crudo en `docs\investigacion\meta\*.jsonl`, resumen en `meta\resumen.txt`) mas WebSearch. NO se vio ningun fotograma ni se descargo video ni miniatura. Todo lo visual (subtitulos, color, sonido, composicion de miniatura) es por tanto INFERENCIA o conocimiento general, y esta marcada. Etiquetas: **[HECHO]** = dato de metadatos/pagina con URL; **[INFER]** = deduccion mia, a confirmar viendo el video.

Aviso de muestra: 12 piezas por canal no son el canal entero. Las vistas de piezas recientes (dias) no son comparables con las de meses.

---

## 1. Raoul Pal (The Journey Man / Real Vision)

Canal identificado: "Raoul Pal The Journey Man", https://www.youtube.com/channel/UCVFSzL3VuZKP3cN9IXdLOtw (el handle @RealVision NO es este canal: es otro con 57k seguidores, descartado). Muchos videos salen co-publicados con Real Vision.

### (a) Que hace distinto
- **[HECHO]** Convierte un solo contenido largo en una familia de piezas: la pelicula "Four Frameworks, One Code" (2314 s, https://www.youtube.com/watch?v=KLk55NI9DOY) se parte en capitulos publicados aparte: Ch.1 691 s, Ch.2 510 s, Ch.3 453 s, Ch.4 798 s (https://www.youtube.com/watch?v=k-f4aWJS4Ck). Cada capitulo apunta a "Watch the full film" en la primera linea de la descripcion.
- **[HECHO]** Las entrevistas largas llevan muchos capitulos: 15 a 23 (p. ej. https://www.youtube.com/watch?v=QXYVspXQfeo, 3772 s, 23 capitulos; https://www.youtube.com/watch?v=L2sWTZLyHiQ, 3453 s, 20). Un capitulo cada ~2,5-3 min de media.
- **[HECHO]** Titulo formula: "Tema afirmativo/pregunta | Raoul Pal The Journey Man" (+ "w/ Invitado"). Los Shorts tienen titulo-tesis en una frase ("The Stock Market Is One Headline Away From Trouble").
- **[HECHO]** Shorts muy cortos: mediana 43,5 s, rango 20-123 s (12 Shorts); vistas 1.000-14.000, muy por debajo del largo (21k-130k).
- **[INFER]** El Short es un recorte de entrevista: una tesis, cierre en la frase fuerte. Confirmar viendo.
- **[HECHO]** Cadencia: ~3-4 publicaciones largas al mes mas Shorts casi diarios (4 Shorts entre 31 oct y 5 nov).

### (b) Duracion y estructura
- Largo entrevista: 38-77 min (2268-4603 s). Capitulos-pieza: 7,5-13 min. Shorts: ~20-75 s.
- **[HECHO via WebSearch]** Muchos episodios abren con lectura de patrocinador (listados de podcast) -> el gancho del largo NO esta en los primeros segundos sino en el titulo/miniatura. https://podcasts.apple.com/gb/podcast/id1581019716
- Gancho/giros/cierre en pantalla: **no verificado** (ver "Que necesito ver").

### (c) Texto y subtitulos
- **No verificado.** [INFER] En entrevistas de este tipo: lower-third con nombre/cargo del invitado al inicio, subtitulos solo en Shorts. Confirmar.

### (d) Mapas/graficas/datos
- **[INFER]** La marca de Raoul es el grafico de series (macro, liquidez, BTC). No hay evidencia en metadatos de como se superponen (pantalla completa vs. PiP). Confirmar viendo.
- **[HECHO]** El tema de los capitulos ("Debt, Demographics and Liquidity") es dato macro -> encaja con Ride the Lightning.

### (e) Replicable
- SI: familia de piezas (pelicula + capitulos + Shorts) desde un master; capitulos con marcas de tiempo en descripcion; titulo-tesis; Shorts 20-60 s con una sola tesis; graficas de series con RtL superpuestas sobre entrevista; lower-third con alfa ProRes.
- NO: dos camaras de estudio/multicam real si no hay material; sesion con invitado.

### (f) Riesgos
- Material de Real Vision/Raoul (video, voz, imagen) es de terceros. Copiar estructura/formato es libre; no reutilizar sus clips. Graficos de terceros (fuentes de datos con licencia) hay que re-sacarlos de fuente oficial.

---

## 2. MrBeast (solo Shorts)

Canal: https://www.youtube.com/@MrBeast (525 M seguidores en el JSON).

### (a) Que hace distinto
- **[HECHO]** Shorts MUY cortos: mediana 37,5 s, rango 8-74 s (12 Shorts, 17 jul-30 oct 2026). Uno de 8 s ("Mr Rizz IRL") tiene 124 M vistas; "Don't Pop the Balloon" 51 s tiene 306 M (https://www.youtube.com/watch?v=egvLKQe6I4I).
- **[HECHO]** Titulos de 3-7 palabras, en forma de pregunta/reto o resultado: "Can A Robot Do My Chores?", "Last To Fall Wins", "Giving $10,000 To A Random Subscriber". Un reto o premio visible en el titulo.
- **[HECHO]** Fuentes en 4K 3840 (11 de 12) y 30 fps; sin capitulos (Shorts).
- **[HECHO via WebSearch, fuente debil]** El estilo "retention editing": cortes rapidos, SFX fuertes, sin pausas, texto de 3-4 palabras; la cifra "cambio visual cada ~1,1 s" es de un blog sin verificar (https://sozai.app/transcript/mrbeast-youtube-greatest-video-strategy/). En marzo 2024 se reporto que MrBeast dijo que dejaba ese estilo por uno mas lento (https://www.tubefilter.com/?p=178861). Tratar "cada 1 s" como hipotesis, no como regla.
- **[INFER]** Los Shorts son recortes verticales de contenido ya producido con presupuesto enorme; el diferencial es el material (reto fisico), no el montaje.

### (b) Duracion y estructura
- 8-74 s. [INFER] Estructura: promesa/reto en el primer plano -> escalada -> resultado en el ultimo plano, sin intro. Confirmar con video.

### (c) Texto y subtitulos
- **[INFER, conocimiento general]** Subtitulos quemados palabra a palabra, grandes, 1-4 palabras, color de enfasis. No verificado en este material.

### (d) Mapas/graficas/datos
- **[INFER]** Casi nada; el dinero/cifra aparece como rotulo grande ($10,000). Verificar.

### (e) Replicable
- SI: Shorts de 20-45 s; titulo-reto de <=7 palabras; cifra grande como rotulo; subtitulos palabra a palabra como pista editable (ASS); SFX de impacto en cortes.
- NO: el material (retos fisicos con presupuesto), cámaras multiples 4K, dinero real en pantalla.

### (f) Riesgos
- Todo su material es de terceros; solo copiar patron, nunca clips. Marca "MrBeast", premios y cifras no se pueden usar como ganchos propios.

---

## 3. Aztec Lab (@azteclabco)

Identidad: Aztec Lab, 15.600 seguidores [HECHO]. https://www.youtube.com/channel/UC-m9oy7lD0tbW0teZSLf5ng. **[HECHO via WebSearch, tercero]** Salomon Zarruk figura como CEO/fundador de Aztec Lab (Bogota, formacion/automatizacion con IA): https://andresospina.co/lideres-tech/salomon-zarruk/ (a verificar en azteclab.co).

### (a) Que hace distinto
- **[HECHO]** Embudo por palabra clave en comentarios: 11 de 12 Shorts titulan "Comenta «X» y te respondo/envio el link a la guia/clase" (ej. https://www.youtube.com/watch?v=lDHFBzRIQ1U, 3645 vistas). El titulo ES la llamada a la accion.
- **[HECHO]** Shorts largos para ser Shorts: mediana 100,5 s, rango 49-180 s. Formato "explicacion practica", no entretenimiento breve.
- **[HECHO]** Video largo con capitulos propios en descripcion cuando el video es didactico: 9 capitulos en 1189 s (https://www.youtube.com/watch?v=WLYTwnWjSFs), 12 en 2117 s (https://www.youtube.com/watch?v=3COQYXm5DeY, 13.310 vistas). Primer capitulo siempre "Intro: lo que vas a ver/poder hacer".
- **[HECHO]** Serie de casos con titulo-testimonio entre comillas: "Pase de $56 millones de pesos a costo $0, Gracias a la IA", "Ahorro 30 minutos por consulta..." (360-766 s, 96-857 vistas). Mismo patron: `"[resultado cuantificado]" | Todo empezo con...`.
- **[HECHO]** Descripcion con UTM por video (`utm_source=ytjs281026computeruse`) -> miden que video convierte.
- **[HECHO]** Mezcla de formatos: clases en vivo de 5276 y 6703 s ("Automatiza la extraccion...") junto a videos editados de 6-20 min.

### (b) Duracion y estructura
- Largo editado: 6-35 min; en directo: 88-112 min. Shorts 49-180 s.
- **[HECHO]** Estructura declarada en capitulos: Intro (promesa) -> Que es / por que mejoro -> Como activarlo -> Ejemplo real extenso -> Limites -> Reflexion final (3COQYXm5DeY). El "ejemplo real" ocupa ~7 min de 33.
- Gancho en segundos: no verificado.

### (c) Texto y subtitulos
- **[INFER]** Pantalla compartida (captura de pantalla) con zoom y subtitulos. No verificado.
- **[HECHO]** Palabra clave de la CTA entre comillas angulares en el titulo: puede reutilizarse como rotulo en pantalla para casar titulo y video.

### (d) Mapas/graficas/datos
- **[HECHO]** Cifras en el titulo como argumento ($56 millones, 2 horas a 1 minuto, 100 facturas al dia). **Segun nuestra regla de marca, cada cifra rotulada debe verificarse; aqui son testimonios de terceros.**
- Graficos animados: no verificado.

### (e) Replicable
- SI: CTA por palabra clave en comentarios + UTM por pieza; capitulos con "Intro: lo que van a ver" en 0:00; Shorts 50-100 s didacticos; testimonios con cifra en el titulo (si la cifra es verificable); rotulo de la palabra clave en el cierre del video.
- NO: capturas de pantalla de herramientas ajenas sin autorizacion; clases en directo.

### (f) Riesgos
- Capturas de ChatGPT/Claude/Chrome/Google = marcas de terceros (uso informativo, no como fondo propio). Testimonios con cifras: no copiar los casos ni las cifras.

---

## 4. Johnny Harris (@johnnyharris)

Canal: https://www.youtube.com/channel/UCmGSJVG3mCRXVOP4yZrU1Dw (8,01 M seguidores). Ex-Vox Borders; "Search Party", "Tunnel Vision" en tags.

### (a) Que hace distinto
- **[HECHO]** Documental largo con vistas muy altas: 2.370-3.071 s (40-51 min) -> 3,6 M-7,9 M vistas (https://www.youtube.com/watch?v=-DDbYSg0Alw 6,5 M; https://www.youtube.com/watch?v=axRhjqd-rus 5,7 M). Todos 4K 24 fps (los Shorts tambien 24 fps casi siempre) -> aspecto cinematografico.
- **[HECHO]** Capitulos con tension narrativa en lugar de tema seco: "Intro / Chinese Characteristics / Party-State / Modest Prosperity / Lying Flat / Maintaining Stability" (https://www.youtube.com/watch?v=axRhjqd-rus). Intro de 282 s (casi 5 min) antes del primer capitulo temático.
- **[HECHO]** Maratones/compilaciones de 2,9-3,2 h ("The American war machine", 11.596 s; "How Money Actually Works", 10.710 s) con 6-9 capitulos que son videos independientes agrupados.
- **[HECHO]** Titulo afirmativo-provocador con "REAL" en mayusculas: "The REAL reason China built so much", "The REAL reason the US can't beat Iran".
- **[HECHO]** Fuentes publicadas: cada descripcion enlaza un Google Doc con todas las fuentes y una lista de lectura. Confianza como parte del formato.
- **[HECHO via WebSearch]** Herramienta de mapas: After Effects (+ plugin GeoLayers) e Illustrator, segun su video "How I Make My Maps" (https://rosetta.to/u/johnnyharris/how-i-make-my-maps y resumenes de tutoriales).
- **[HECHO]** Shorts: mediana 95,5 s, rango 43-172 s; titulos casuales/personales ("Meta glasses? Woof.", "I pushed Google Docs to its limit"); 34 k-630 k vistas. Mezclan narrativa y "detras de camaras"/anuncios.

### (b) Duracion y estructura
- Largo: 33-52 min (documental); 107 s para el trailer anual (https://www.youtube.com/watch?v=sOz7gG74OIw); maratones 2,9-3,2 h. Shorts 43-172 s.
- **[INFER]** Estructura documental: escena/pregunta -> contexto historico -> giro "en realidad es..." -> sistema/mecanismo -> "y ahora que". Los nombres de capitulo ("The Briefcase", "The Maze", "The Pyramid", "Source Code") sugieren metaforas visuales recurrentes (https://www.youtube.com/watch?v=4S25FfbFw4M). Confirmar viendo.

### (c) Texto y subtitulos
- **No verificado.** [INFER] Texto en pantalla corto y animado integrado en el mapa/collage; subtitulos YouTube normales. Confirmar.

### (d) Mapas/graficas/datos
- **[HECHO]** Los mapas son su firma: tres de los titulos de capitulo citan literalmente "Mapped" ("The Iran-Iraq War, Mapped", "The Rise of Hezbollah, Ma[pped]", https://www.youtube.com/watch?v=bLOEhycMG78). Entrevista con Max Fisher incluye capitulo "Inventing the map format" (https://www.youtube.com/watch?v=vmGm8xn_1Ro).
- **[INFER]** Mapas con camara que viaja, rutas, banderas y fronteras animadas, collage de recortes de prensa/archivo; 24 fps con motion blur. Confirmar.

### (e) Replicable
- SI (con Electric Eye): mapas animados con ruta/frontera/zoom, capitulos con nombres narrativos, lista de fuentes en documento enlazado (alineado con la regla de cifras verificadas), titulo "La razon REAL de...", 24 fps para pieza documental, MG de Ride the Lightning para series.
- NO: B-roll de archivo con licencia, entrevistas en 4K con equipo, texturas 3D/escenografia, el equipo de produccion (guion + investigacion de semanas).

### (f) Riesgos
- Mapas/animacion de Johnny Harris: copiar el LOOK no es problema; reutilizar sus clips, su motion o titulos exactos si. Imagenes de archivo, prensa y videos con marca propia hay que licenciarlos o rehacerlos. Los 3 Shorts marcados #ad (Circle) son contenido patrocinado: no tomar de modelo para marca.

---

## 5. @upsb = "Un Podcast Sobre Bitcoin" (Alberto Mera)

Identidad **[HECHO]**: canal https://www.youtube.com/channel/UCZgWeZC8XoUQF5Md1DHXkVw, uploader "Un Podcast Sobre Bitcoin", 72.400 seguidores; la descripcion cita la newsletter `albertomeraupsb.substack.com` y el correo `hola@unpodcastsobrebitcoin.com`; WebSearch (https://podnews.net/podcast/i98bw) lo atribuye a Alberto Mera. Es un podcast en solitario de finanzas/macro/Bitcoin en espanol (tags: bitcoin, inversion, finanzas, cripto, economia, macro, mercados).

### (a) Que hace distinto
- **[HECHO]** Cadencia muy alta y regular: 12 videos largos en 28 dias (7-4 nov: casi uno cada 2 dias) mas 2 Shorts/dia (dos el 5 y el 4 nov). Todos 4K 30 fps.
- **[HECHO]** Duracion constante: mediana 1291 s (21,5 min), rango 1099-1477 s -> formato cerrado de ~20 min.
- **[HECHO]** Titulos con palabra en MAYUSCULAS de enfasis en 6 de 12: "SUBIDA", "ROMPE", "QUEBRAR", "BITCOIN", "EL PAPEL DE BITCOIN", "OLA DE DERECHA", "NO RESCATAR". Estructura: noticia macro + consecuencia para Bitcoin/ahorro ("Lo que la OLA DE DERECHA va a hacer con tu ahorro", 163.834 vistas).
- **[HECHO]** Mejores rendimientos en temas de miedo/conflicto: "¿Ha perdido el oro su escasez?" 230.404; "La mayor conspiracion sobre Bitcoin acaba de caer" 182.748; "El plan de Europa para NO RESCATAR a Francia" 177.379.
- **[HECHO]** Una noticia (Binance) se explota en 3 formatos en dias seguidos: largo de 1477 s (https://www.youtube.com/watch?v=Sibf33CR6D4) + dos Shorts (73 s y 77 s) (https://www.youtube.com/watch?v=SgXvX881Eio). Idem oro (dos Shorts de 70 y 99 s, 99 s con 7.331 vistas, el mas visto).
- **[HECHO]** Sin capitulos en ninguno de los 12 largos (0 capitulos).
- **[HECHO]** Descripcion estandar: newsletter, patrocinador (VPN con descuento), descargo de responsabilidad "entretenimiento, no asesoramiento". Patron legal que conviene copiar.

### (b) Duracion y estructura
- Largo ~18-25 min; Shorts mediana 72,5 s, rango 24-112 s. Gancho/estructura interna: **no verificado**.
- **[INFER]** Un tema por episodio (noticia del dia + contexto + implicacion), formato monologo con soporte grafico.

### (c) Texto y subtitulos
- **No verificado.**

### (d) Mapas/graficas/datos
- **[INFER]** Series (precio oro/BTC/bolsa) y titulares. Sin evidencia visual.

### (e) Replicable
- SI: serie diaria de Shorts de 45-100 s sobre la misma noticia que el largo; titulo "noticia + consecuencia" con 1 palabra en mayusculas; descargo legal fijo; newsletter en descripcion; graficas de datos con RtL.
- NO: cadencia de 1 largo cada 2 dias sin equipo; entrevistas.

### (f) Riesgos
- Titulares y marcas de terceros (Binance, noticias): citar con fuente; cifras de precio verificadas a fuente oficial antes de rotular. Cuidado con titulos tipo "conspiracion" / "va a QUEBRAR": son afirmaciones de marca (riesgo de credibilidad).

---

## Matriz de patrones (de 5 referencias)

| Patron | Aparece en | Evidencia |
|---|---|---|
| Un master -> varias piezas (largo + capitulos/Shorts de la misma idea) | 3/5 (Pal, UPSB, JH maratones) | Pal Ch.1-4 de la pelicula; UPSB largo + 2 Shorts Binance; JH maratones |
| Capitulos con marcas de tiempo en descripcion | 3/5 con capitulos (Pal 8 de 12, JH 10 de 12, Aztec 2 de 12 largos); UPSB 0/12 | metadatos |
| Titulo-tesis afirmativa/provocadora (promesa o conflicto) | 5/5 | titulos |
| Palabra en MAYUSCULAS de enfasis en titulo | 2/5 (JH "REAL", UPSB) | titulos |
| Shorts <60 s mediana | 2/5 (MrBeast 37,5 s, Pal 43,5 s) | metadatos |
| Shorts 70-100 s | 3/5 (UPSB 72,5, JH 95,5, Aztec 100,5) | metadatos |
| CTA explicita en titulo/descripcion (comenta X, newsletter, UTM) | 2/5 (Aztec, UPSB) | descripciones |
| Fuentes/descargo publicados | 2/5 (JH doc de fuentes, UPSB descargo) | descripciones |
| 4K de origen | 5/5 | height 2160/3840 |
| 24 fps documental / 30 fps resto | JH 24 (4K), resto 30 | fps |
| Titulos con cifra cuantificada | 1/5 (Aztec) + MrBeast ($10,000) = 2/5 | titulos |
| Mapas animados como firma | 1/5 (JH) | capitulos "Mapped" |
| Subtitulos quemados palabra a palabra | MrBeast [INFER], resto no verificado | -- |
| Cadencia >=1 pieza/dia | 2/5 (UPSB, Pal Shorts) | fechas |

## Reglas candidatas para el motor

Las reglas con [HECHO] salen de datos medidos; las de [INFER]/[HIPOTESIS] hay que calibrarlas viendo los videos (ver abajo).

1. **Duracion Short**: objetivo 25-45 s para entretenimiento/dato unico; 60-100 s para explicacion practica; tope 120 s. Fuente: MrBeast 37,5 s mediana; Pal 43,5 s; Aztec 100,5 s; UPSB 72,5 s [HECHO medianas].
2. **Un Short = una sola tesis** en titulo de <=8 palabras (MrBeast 3-7 palabras; Pal 5-10) [HECHO titulos].
3. **Largo estudio**: capitulos con marca de tiempo; un capitulo cada 2,5-3 min en entrevistas (Pal 15-23 caps en 38-77 min) y cada 4-6 min en documental (JH 8 caps en ~50 min) [HECHO].
4. **Capitulo 0:00 siempre "Intro: lo que veras"** (Aztec 2/2 con capitulos; JH 7/10 empiezan en "Intro") [HECHO].
5. **Un master -> 1 pelicula + 3-4 capitulos de 7,5-13 min + Shorts** (Pal) [HECHO]. El motor genera los recortes desde las marcas de capitulo.
6. **Titulo**: tesis + consecuencia; maximo 1 palabra en MAYUSCULAS de enfasis (UPSB 6/12, JH "REAL") [HECHO titulos, regla de uso mia].
7. **CTA por palabra clave** en cada Short y rotulo en pantalla en el cierre; UTM distinto por pieza (Aztec 11/12 Shorts) [HECHO].
8. **Descripcion fija**: fuentes (enlace a documento), descargo "no es asesoramiento", newsletter (JH, UPSB) [HECHO].
9. **Cifra rotulada = verificada contra fuente oficial** antes de salir (Aztec/MrBeast/UPSB abusan de cifras en titulo) [regla de marca; evidencia: patron presente en 3/5].
10. **Cadencia**: serie Shorts diaria sobre el mismo tema del largo de la semana (UPSB 2 Shorts/dia, largo cada 2 dias) [HECHO fechas].
11. **Mapas**: capitulo del largo puede nombrarse "[Tema], Mapped" y cada tema geopolitico lleva al menos un mapa animado (JH 3 de 9 caps en "Modern Middle East") [HECHO capitulos]. Uso: Electric Eye.
12. **Documental 24 fps / 4K; resto 30 fps** (JH 24 fps casi todo; UPSB/Aztec/Pal 30) [HECHO fps]. Elegir 24 solo si hay look cine.
13. **Subtitulos Short**: 1-4 palabras por linea, palabra a palabra, pista ASS editable (nunca quemados) [MrBeast, INFER; consistente con regla de marca].
14. **Primer corte antes de 2-2,5 s en Short** [HIPOTESIS: fuente debil, blogs de retencion]. Validar midiendo con scene detect sobre material propio, no copiar la cifra.
15. **Cambio visual (corte, zoom o MG) cada 3-5 s en largo, cada 1-2 s en Short** [HIPOTESIS: MrBeast 4 s en blogs, "1,1 s" sin verificar; MrBeast dijo en 2024 que iba a ir mas lento]. Calibrar con scene detect de las referencias antes de fijarlo.
16. **Gancho de Short en los primeros 3 s**: la tesis o el resultado en el primer plano, sin intro/logo [HIPOTESIS, practica comun; Aztec/UPSB titulan el Shorts como el gancho].
17. **No abrir Short con lectura de patrocinador**: el patrocinio va al final o en descripcion (Pal abre largos con patrocinador y el gancho se pierde) [HECHO via listados; INFER sobre el efecto].
18. **Tarjetas y lower-thirds opacos con alfa ProRes 4444** (regla de marca; coincide con el uso de lower-third/etiqueta en entrevista, INFER).
19. **Etiqueta de patrocinio** (#ad / "Publicidad") visible cuando aplique (JH marca #ad en el titulo) [HECHO].
20. **Miniatura**: una cara + max 3-4 palabras (la practica de la categoria; no verificada porque no se vieron miniaturas) [INFER]. Probar 2 variantes por pieza.

## Que necesito ver (no confirmable sin fotogramas/audio)

- **Raoul Pal**: minuto 0-60 s de una entrevista y de un Short: lower-third, graficos a pantalla completa vs. PiP, subtitulos, musica, multicam.
- **MrBeast**: 3 Shorts (el de 8 s y los de 24 y 40 s): cortes por segundo reales (scene detect), tamano y color de subtitulos, SFX, si el texto sale palabra a palabra, si la cifra va como rotulo.
- **Aztec Lab**: 1 Short y 1 largo (3COQYXm5DeY): gancho en los primeros 5 s, rotulos de la palabra clave, captura de pantalla vs. camara, subtitulos.
- **Johnny Harris**: un capitulo de mapas (p. ej. "The Iran-Iraq War, Mapped") 60-90 s: camara de mapa, tipografia, colores, motion blur, SFX, musica, ritmo de cortes en la intro de 282 s.
- **UPSB**: un largo (Sibf33CR6D4) y un Short: si es video de estudio o voz sobre graficos, tipo de grafico, subtitulos, miniaturas (MAYUSCULAS tambien en la miniatura?).
- **Miniaturas de las 5 referencias**: composicion (cara/recorte, palabras, colores, bordes). No se descargaron; si David autoriza, verlas con una captura manual.
- Los datos de vistas son de 12 piezas; hace falta una muestra mayor (50) para separar tipo de pieza de efecto del tema.

## Archivos

- `docs\investigacion\meta\resumen.txt` (tabla de las 5 referencias), `*.jsonl` (JSON de metadatos de yt-dlp, grandes: no abrir a mano), `rp_search.txt`.
