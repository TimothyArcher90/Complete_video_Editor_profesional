# Playbook de copy y portada (nov 2026)

Objetivo: copy con intencion viral que no traicione la marca MacroWise. Lo aplica `mw_editor\copy.py` (plantilla + validador). Ejemplos: `copy_ejemplos.md`.

**Confianza de cada dato:** [OFICIAL] documentacion de la plataforma leida en esta sesion. [TERCEROS] blogs/vendors, sin verificar en la fuente. [ESTIMADO] regla de oficio. [HECHO] metadato de las referencias (`referencias.md`). [INFER]/[HIPOTESIS] patron sin confirmar viendo el video. Donde las fuentes se contradicen, lo digo.

## 0. Reglas de marca que mandan sobre todo lo demas
- Espanol colombiano, tuteo o "ustedes". Nunca voseo (`vos`, `tenes`, `mira` en imperativo voseante, `comenta` con tilde de voseo).
- Maximo 3 parrafos cortos (<=350 car) en textos para terceros. Sin raya larga.
- **Cifra rotulada = afirmacion de marca.** Verificar contra fuente oficial; si no se puede, "pendiente de verificar". Nunca inventar ni omitir en silencio (M26).
- Sin promesa de rentabilidad ni consejo personalizado ("deberias comprar"). Descripcion de YouTube y LinkedIn lleva "Contenido educativo. No es asesoria de inversion." (patron UPSB, M27).
- El titular se cumple en el video. Si no lo entrega, se cambia la portada, no el video.
- Prosa por la skill anti-ai-writing: especificidad nivel 3+ (instancia, cifra verificada, mecanismo); sin "no es X, es Y" hueco; sin metaforas de viaje/ecosistema/motor; sin "desbloquea/potencia/panorama". Aperturas por viral-hooks: tema claro en 1-2 s, relevancia ("tu", no "yo"), contraste A-vs-B concreto; un CTA nunca abre.

## 1. Limites por plataforma (los que valida `copy.py`)

| Plataforma | Titulo | Texto total | Visible sin "ver mas" | Hashtags | Fuente / confianza |
|---|---|---|---|---|---|
| YouTube largo | 100 car max; ideal <=60 | 5000 car | ~100-150 car | max 3 propios (3 se muestran sobre el titulo; con >15 YouTube los ignora todos) | 100/5000/hashtags: conocimiento de Studio, no re-fetcheado [ESTIMADO]. Capitulos [OFICIAL, leido]: https://support.google.com/youtube/answer/9884579 |
| YouTube Shorts | 100 car; ideal <=60 | 5000 car | ~100 car | 2-3 | [ESTIMADO] |
| Instagram Reels | sin titulo | 2200 car | **~125 car** | 3-5 | 2200 y 125 coinciden en 8+ blogs [TERCEROS]. **Tope de hashtags en conflicto:** casi todos dicen 30; un solo sitio dice que Meta lo bajo a 5 desde dic-2025, sin confirmar. Usamos 5 (practica de pocos tags). Verificar en el compositor de la cuenta. |
| TikTok | sin titulo | **2200 o 4000** | ~100 car | 3-5 | Conflicto: guias dicen 4000 en la app; API y schedulers, 2200. Usamos 2200 como tope seguro [TERCEROS, sin fuente oficial]. |
| LinkedIn | titulo de video opcional | 3000 car (post) | ~140 car movil / ~210 escritorio | 3-5 | [TERCEROS]; sin documentacion oficial leida. |

Capitulos de YouTube [OFICIAL]: la lista empieza en 00:00, minimo 3 marcas ascendentes, cada capitulo >=10 s. `copy.py` lo valida como ERROR.
Declaracion de IA y requisitos de entrega: `plataformas_metricas.md` secciones 5-7.

## 2. Reglas por plataforma

### 2.1 YouTube largo
- **Titulo:** tesis + consecuencia, <=60 car, **maximo 1 palabra en MAYUSCULAS** (JH "REAL", UPSB [HECHO]). Cifra solo verificada. Ej.: "La razon REAL por la que el oro sube con tasas altas", solo si el video lo demuestra.
- **Primera linea de la descripcion** (lo unico visible): la promesa concreta, o "Mira el video completo" en capitulos sueltos (patron Pal [HECHO]). Nunca saludo ni "suscribete".
- **Descripcion:** hook, <=2 parrafos de contexto, CTA, enlaces (newsletter; fuentes en un documento enlazado como Johnny Harris [HECHO]), capitulos, aviso de no-asesoria, hashtags al final. UTM distinto por pieza (Aztec [HECHO]).
- **Capitulos:** 00:00 "Intro: lo que veras" (Aztec 2/2, JH 7/10 [HECHO]); uno cada 2,5-3 min en entrevista y 4-6 min en documental [HECHO]. Titulos con sustantivo concreto o tension, no "Parte 2".
- **Miniatura:** ver 2.6. 1280x720, 16:9.
- **CTA:** pregunta concreta en comentarios o suscripcion a la newsletter. Evitar "dale like".
- **Evitar:** hashtags de relleno, titulos de "conspiracion"/"va a QUEBRAR" sin sustento (riesgo de credibilidad, ref. UPSB), cifras sin fuente, abrir con patrocinio (Pal pierde el gancho [HECHO/INFER]).

### 2.2 YouTube Shorts
- **Titulo = tesis de <=8 palabras** (MrBeast 3-7, Pal 5-10 [HECHO]); en Aztec el titulo ES el CTA ("Comenta «X»...") [HECHO].
- Una tesis por Short. El primer plano ya muestra el resultado, la cifra o la escena (hipotesis: primer evento <=1,5 s, M01).
- Descripcion corta: hook, enlace al largo, aviso de no-asesoria, 2-3 hashtags. `#shorts` solo no cuenta como hashtag de tema.
- **Evitar:** clickbait que el Short no cumple (la metrica "viewed vs swiped" lo castiga).

### 2.3 Instagram Reels
- **Hook en <=125 car**; la primera frase debe tener sentido sola.
- Senales a maximizar: watch time, **sends (DMs)** y likes por alcance (Mosseri, ene-2025 [TERCEROS]). CTA util: dar una razon concreta para enviarlo ("Si alguien de tu equipo sigue pagando la tarjeta al minimo, esto le sirve"). Bait: "etiqueta a 3 amigos".
- "Guarda este para cuando..." funciona cuando el contenido es de referencia (checklist, fechas, cifras).
- 3-5 hashtags de tema; ninguno dentro del cuerpo.
- Portada 9:16 con recorte central 3:4 en la grilla [TERCEROS, verificar]; el texto de portada va dentro del recorte.
- **Evitar:** marcas de agua de otras redes (pierden alcance), engagement bait, "comenta SI si estas de acuerdo".

### 2.4 TikTok
- Factores oficiales: interacciones, info del video, ajustes del dispositivo; seguidores no cuentan directo (Newsroom).
- Caption: hook en <=100 car, 1-2 frases, pregunta concreta. Es buscador: la **palabra clave del tema** en la primera frase y en el texto en pantalla [ESTIMADO].
- 3-5 hashtags: 1 amplio + 2 de nicho (#inflacion, #macroeconomia). Nunca `#fyp/#parati` de relleno.
- Etiquetar IA realista (`plataformas_metricas.md` sec. 7).
- Subtitulos incrustados en el MP4 de publicacion (TikTok no importa SRT); el master conserva la pista editable.

### 2.5 LinkedIn (video o post)
- Hook en <=140 car. Dos lineas visibles: la primera nombra el tema, la segunda abre el contraste.
- Parrafos de 1-2 frases, una idea por post. Util para quien dirige equipos o gestiona finanzas, no "tips".
- Video nativo: 16:9 o 9:16, **30-90 s** [TERCEROS]. Subtitulos siempre (autoplay en mudo; la cifra de 80% no esta verificada).
- Enlace externo en el primer comentario o al final, no en el hook. Aviso de no-asesoria en el texto.
- CTA: una pregunta de criterio profesional, no "opina abajo".
- **Evitar:** tono thinkfluencer ("5 lecciones que..."), emojis en cadena, promesas.

### 2.6 Texto en pantalla y texto de portada/miniatura
- **Portada: maximo 5 palabras** (regla propia; la categoria usa 3-4 [INFER]). Una idea, un foco.
- Contraste >=4.5:1 (WCAG, M09); fuente >=44 px a 1080 de ancho en vertical (M11 [ESTIMADO]); dentro de zona segura (`zonas_seguras.md`).
- **Una cara** legible, mirada a camara o al texto [INFER: miniaturas no vistas, ver "Que necesito ver" en `referencias.md`]. Probar 2 variantes.
- **Curiosidad sin mentir:** el texto de portada es un fragmento verdadero del video. Prueba: si el espectador lo comprueba en el minuto 1, existe. Prohibido "mira hasta el final".
- Un numero en la portada es cifra rotulada: va verificado.
- Rotulos en el video: <=8 palabras, una idea cada uno; la palabra clave del CTA como rotulo en el cierre (Aztec [HECHO]). Tarjetas opacas.

### 2.7 CTA y comentarios
- Tres tipos validos: (1) **palabra clave** "Comenta «X» y te envio..." (Aztec 11/12 Shorts [HECHO]), solo si el recurso existe y se entrega; (2) **pregunta que obliga a un caso propio** ("¿Cuando fue la ultima vez que revisaste lo que pagas en comisiones?"); (3) **razon para enviar o guardar**.
- Evitar "dime si estas de acuerdo": respuesta de una palabra, valor cero, suena a bait.
- Va al cierre, nunca al inicio.

### 2.8 Que evitar en todas
1. Spam de hashtags y hashtags de relleno.
2. Engagement bait penalizado: "dale like", "comparte si", "etiqueta a...", sorteos por interaccion.
3. Claims financieros: rentabilidades, "garantizado", "sin riesgo", "duplica tu dinero", "compra ahora".
4. Cifras sin fuente; testimonios con cifras de terceros sin verificar.
5. Titulares que el video no cumple.
6. Tics de IA: raya larga, "no es X, es Y", "desbloquea", "en el mundo actual".
7. Mas de 3 emojis; parrafos largos.

## 3. Quince formulas de gancho (espanol financiero/macro/IA)

Los ejemplos son plantillas: **toda cifra entre corchetes se verifica antes de usarse.** Son [HIPOTESIS] de rendimiento hasta medir en el canal; salen de las skills viral-hooks/anti-ai-writing y de las referencias.

1. **Escena concreta.** Abre en un momento, no en un resumen. "El viernes a las 8:30 a. m. salio el dato de empleo y el dolar [subio/bajo] [X] pesos en cinco minutos."
2. **Contradiccion A vs B.** "Todos esperaban recorte de tasas. El mercado hizo lo contrario: [dato verificado]."
3. **Pregunta ancla** (se responde al cierre casi palabra por palabra). "¿Por que un pais con inflacion a la baja sigue pagando mas por su deuda?"
4. **Numero especifico.** Una cifra verificada y poco obvia, con la fuente en pantalla. "[Cifra oficial]: lo que [entidad] paga solo en intereses."
5. **"Lo que nadie te dice de X" con X nombrado** en los primeros 5 s. "El ETF que compras por comodidad cobra [X]% al ano; esto es lo que paga ese porcentaje."
6. **Costo oculto.** "Tu fondo rinde [X]% bruto. Despues de comisiones e impuestos te quedan [Y]%." (ambas con fuente).
7. **Antes y despues con fecha.** "En [mes ano] la tasa era [X]. Hoy es [Y]. Esto es lo que cambio entre medio."
8. **Error comun del espectador.** "Si miras el IPC del mes y no la tasa real, estas leyendo medio dato."
9. **Mecanismo en una frase.** "Cuando el banco central sube tasas, tu hipoteca variable sube en la siguiente revision. Este es el calendario."
10. **Prediccion con fecha de caducidad.** "El [fecha] sabremos si [indicador] supera [umbral]. Esto es lo que decide."
11. **Comparacion inesperada.** "Colombia y [pais] recaudan parecido; una gasta el doble en intereses. La diferencia esta en [dato]."
12. **Retraso del nombre** (sujeto revelado tras un giro). "Una empresa que casi nadie conoce fabrica las maquinas que hacen los chips de tu celular. No es [la obvia]."
13. **Prueba de trabajo (IA).** "Hace un ano esto me tomaba un fin de semana. Hoy lo hice en medio dia con tres prompts. Estos son."
14. **Regla practica con limite.** "Tres preguntas antes de comprar cualquier activo. La tercera casi nadie la hace." Solo si las tres existen y se dicen.
15. **Cita y desmentido.** "[Cita textual verificable de un banco central o ministerio]. Los datos de [mes] dicen otra cosa." Cita corta, fuente en pantalla.

**Prueba antes de publicar:** (a) ¿se entiende el tema en 2 s? (b) ¿es para MI espectador, no sobre mi? (c) ¿hay un A y un B concretos? (d) ¿el video entrega la respuesta? Si (d) falla, se reescribe el gancho.

## 4. Flujo en el motor
1. Transcribir (`transcribir.py`) y marcar la frase con dato o escena concreta.
2. Registrar las cifras con fuente en `cifras` del JSON.
3. Redactar hook, cuerpo y CTA por plataforma; `python -m mw_editor.copy pieza.json --md pieza.md`.
4. Resolver todos los ERROR y PENDIENTE; revisar los AVISO a mano.
5. Pegar el `.md` en un Google Doc para David. Nada se publica automaticamente.

## 5. Limitaciones
- El validador mide forma, no calidad: no sabe si el gancho engancha ni si el video cumple el titular.
- Los topes de Instagram/TikTok/LinkedIn son de terceros y estan en conflicto: verificar en la app.
- El detector de voseo es una lista explicita (evita falsos positivos como "mas", "pais"), no un analizador morfologico.
- Los patrones de las referencias vienen de metadatos de 12 piezas por canal; lo visual esta sin verificar.
