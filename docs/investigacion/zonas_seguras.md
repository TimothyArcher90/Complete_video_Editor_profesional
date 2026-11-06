# Zonas seguras y especificaciones de video por plataforma

Fecha de la investigación: 2026-11-05. Lienzo de referencia 9:16 = 1080x1920.

## Leyenda de confianza

- **[OFICIAL]** cifra leída en una página oficial de la plataforma (URL citada).
- **[TERCEROS]** cifra de plantillas, blogs o herramientas de terceros (se indica quién). Muchas dicen "según Meta/TikTok", pero la página oficial no las muestra.
- **[ESTIMADO]** cálculo mío (geometría) o conocimiento previo no re-verificado hoy.

## Hallazgo principal

**Ninguna plataforma publica en texto una zona segura en píxeles para TikTok, Instagram Reels ni YouTube Shorts.**
- TikTok solo ofrece plantillas descargables (Business Help Center) y dice que la zona depende de orientación, longitud del pie de texto y formatos extra.
- Meta tiene una página oficial sobre "texto superpuesto y zona segura para anuncios en Historias y Reels" (facebook.com/business/help/980593475366490), pero el contenido extraído hoy solo devolvió el título, sin cifras. Meta Ads Manager trae un "Safe zone guardrail" (overlay amarillo) que es la verificación real.
- YouTube Shorts no publica margen en píxeles.
- Por eso casi todas las cifras de interfaz son [TERCEROS] o [ESTIMADO].

---

## 1. Zonas de interfaz en 9:16 (1080x1920): lo que tapa el video

| Fuente | Tipo | Arriba | Abajo | Izquierda | Derecha | Notas |
|---|---|---|---|---|---|---|
| Meta Stories (Adnova, adnova.ai/blogs/meta-ad-safe-zones-guide) | TERCEROS | 270 (14 %) | 384 (20 %) | 65 (6 %) | 65 (6 %) | Adnova no atribuye la cifra a Meta |
| Meta Reels (Adnova, mismo enlace; revid.ai/instagram-reels-safe-zone: "~270 arriba, ~670 abajo, 65 izq, 120 der") | TERCEROS | 270 (14 %) | 672 (35 %) | 65 (6 %) | 65 a 120 | Convergen dos terceros en 270/670 |
| Coinis (coinis.com/how-to/best-way-to-put-text-on-instagram-ad), lienzo 1440x2560 | TERCEROS | 250 (14 %) | 340 (20 %) | n/d | n/d | Contradice el 35 % de Reels |
| TikTok socialync.io/tools/safe-zones/tiktok | TERCEROS | 240 | 660 | 120 | 120 | |
| TikTok revid.ai/tiktok-safe-zone | TERCEROS | 220 | 480 | 60 | 140 | |
| TikTok sovran.ai / skedsocial (blogs 2026) | TERCEROS | 130 a 150 | 250 | n/d | 150 | Muy permisivo, contradice a los otros |
| Electric Eye `estandar` (guia_de_direccion, 17-10-2026) | Criterio propio | 220 | 380 | 40 | 140 | Dice no ser oficial |
| Electric Eye `meta-reels` | TERCEROS | 269 | 672 | 65 | 65 | |
| Electric Eye `universal` | TERCEROS (máximo) | 269 | 672 | 122 | 242 | |
| Columna de botones RTL (heredada de Electric Eye) | Criterio propio | n/a | n/a | n/a | x >= 72,2 % (780 px) desde y >= 43,75 % (840 px) | Es una regla de caja, no de márgenes |
| YouTube Shorts | ESTIMADO | ~270 | ~480 a 670 | ~60 | ~120 a 160 | Sin cifra publicada. Botones a la derecha y título/canal abajo; usar la unión de TikTok y Reels |

**Si dos fuentes se contradicen, se recomienda el valor más conservador (la unión).** Los valores en las filas de arriba dan:
- Arriba: máximo = **270 px (14,1 %)**.
- Abajo: máximo = **672 px (35 %)**.
- Izquierda: máximo = **122 px (11,3 %)**.
- Derecha: máximo = **242 px (22,4 %)**. En la columna de botones (y >= 840) la regla RTL es más estricta: **x <= 780** (300 px desde el borde).

### Porcentajes sobre 1080x1920

| Zona | px | % |
|---|---|---|
| Arriba | 270 | 14,1 % |
| Abajo | 672 | 35,0 % |
| Izquierda | 122 | 11,3 % |
| Derecha | 242 (300 en la columna de botones) | 22,4 % (27,8 %) |

---

## 2. Tabla por plataforma

### TikTok (9:16)

| Campo | Valor | Confianza / fuente |
|---|---|---|
| Resolución recomendada | 1080x1920 | TERCEROS (skedsocial, sovran, relevantaudience); no es mínimo oficial |
| Resolución mínima anuncios | 540x960 (9:16), 960x540 (16:9), 640x640 (1:1) | TERCEROS que resumen la página oficial (relevantaudience.com/tiktok-ads/tiktok-video-size-ad-specs/). La URL oficial ads.tiktok.com/help/article/video-ad-specifications devolvió "artículo ya no existe" |
| Formatos | MP4, MOV, MPEG, 3GP, AVI | TERCEROS (relevantaudience) |
| Duración anuncios | hasta 10 min (no Spark); TopView 5 a 60 s (9 a 15 recomendado) | TERCEROS. Blogs antiguos dicen 5 a 60 s: contradicción, usar el valor del que sea más estricto según el uso |
| Peso máximo anuncios | 500 MB | TERCEROS (consistente en todas las fuentes) |
| Bitrate | mínimo 516 kbps (TopView 2.500 kbps) | TERCEROS |
| Códec / fps | H.264, AAC; 30 fps (24 a 60 aceptado) | ESTIMADO |
| Subtítulos | Solo quemados o los nativos de la app; no hay subida SRT en anuncios | ESTIMADO |
| Portada | 9:16; en el perfil se ve recortada ~3:4 | ESTIMADO. Página oficial no especifica portada |
| Zona segura | ver tabla de la sección 1; plantillas oficiales descargables, sin cifra en texto | TERCEROS / ESTIMADO |

### Instagram Reels (9:16)

| Campo | Valor | Confianza / fuente |
|---|---|---|
| Resolución | 1080x1920, 9:16 | TERCEROS (hopperhq, reap.video, invideo) |
| Duración | 3 min desde enero 2025 (Mosseri). 20 min citado por blogs desde finales de 2025, sin fuente primaria | TERCEROS (businesstoday.in, buffer.com/resources/instagram-reels-length). Duda abierta |
| Peso máximo | ~4 GB | ESTIMADO. No verificado hoy |
| Códec / fps | H.264 o HEVC, AAC, 30 fps, ~5 Mbps | ESTIMADO |
| Subtítulos | Sin subida SRT; quemados o stickers nativos | ESTIMADO |
| Cuadrícula de perfil | El Reel 1080x1920 se ve como mosaico 3:4 centrado (1080x1440): se pierden 240 px arriba y 240 px abajo (y visible 240 a 1680) | TERCEROS (hopperhq.com/blog/instagram-reel-size, reap.video). Una fuente da 1080x1350 (4:5): contradicción; la unión conservadora es 4:5 (y visible 285 a 1635). No oficial |
| Cuadrícula antigua / otras vistas | Recorte 1:1 (1080x1080 central, y 420 a 1500) puede aparecer en vistas de seguidores o web | ESTIMADO |
| Zona segura | 270 / 672 / 65 a 120 / 65 a 120 (sección 1) | TERCEROS. Meta indica el "safe zone guardrail" en Ads Manager |
| Cobertura | Se puede recortar manualmente en la pestaña "Profile grid preview" del editor de portada | Fuente: hopperhq / resumen web, ESTIMADO |

### Instagram Stories (9:16)

| Campo | Valor | Confianza |
|---|---|---|
| Resolución | 1080x1920 | TERCEROS |
| Duración | 60 s por clip (anuncios hasta 120 s) | ESTIMADO |
| Zona segura | arriba 270, abajo 384, lados 65 | TERCEROS (Adnova) |

### YouTube Shorts (9:16)

| Campo | Valor | Confianza / fuente |
|---|---|---|
| Resolución | recomendada 1080x1920; mínima 720x1280; máxima 2160x3840 | TERCEROS (shortsync.app/resources/youtube-shorts-upload-requirements-2026) |
| Duración | máx. 3 min (180 s), regla de 2024 | TERCEROS (kapwing, async.com, vidiq). Un 9:16 de 3:01 ya no es Short |
| Relación | 9:16 recomendada; 1:1 contradictorio (una página dice que sí, otra que no cuenta como Short). Usar 9:16 | TERCEROS |
| Peso | 256 GB o 12 h (límite general de la cuenta verificada) | OFICIAL en general (support.google.com/youtube); aplicación a Shorts por TERCEROS |
| Miniatura Shorts | 2160x3840, 9:16, JPG/PNG; mínimo de alto 640 px; 2 MB en móvil, 50 MB en escritorio; solo en YouTube Studio de escritorio y cuenta verificada | **OFICIAL** support.google.com/youtube/answer/72431 |
| Aviso oficial | un video vertical con miniatura 16:9 se sustituye por una miniatura 4:5 autogenerada en inicio/explorar/suscripciones | **OFICIAL** (misma URL) |
| Códec | H.264, AAC, ver tasas en YouTube horizontal | **OFICIAL** support.google.com/youtube/answer/1722171 |
| Subtítulos | Se puede subir SRT en YouTube Studio (aplica a Shorts) | ESTIMADO |
| Zona segura | no publicada; usar unión 270 / 480 a 672 / 60 a 122 / 120 a 242 | ESTIMADO |

### YouTube horizontal (16:9) y miniatura

| Campo | Valor | Confianza / fuente |
|---|---|---|
| Relación | 16:9 estándar en escritorio; vertical y cuadrado se admiten y el reproductor se adapta | **OFICIAL** support.google.com/youtube/answer/1722171 |
| Contenedor / códec | MP4 sin edit lists, moov al inicio, H.264 High Profile, 2 B-frames, GOP cerrado de la mitad del fps, CABAC, 4:2:0 | **OFICIAL** (misma URL) |
| Bitrate SDR 1080p | 8 Mbps (24/25/30 fps), 12 Mbps (48/50/60) | **OFICIAL** |
| Bitrate SDR 4K | 35 a 45 Mbps (24/25/30), 53 a 68 (48/50/60) | **OFICIAL** |
| Bitrate SDR 1440p / 720p | 16 / 24 Mbps y 5 / 7,5 Mbps | **OFICIAL** |
| Bitrate HDR 1080p | 10 Mbps (24/25/30), 15 (48/50/60) | **OFICIAL** |
| Audio | AAC-LC, 48 kHz, estéreo 384 kbps | **OFICIAL** |
| fps | el de grabación (24, 25, 30, 48, 50, 60); desentrelazar | **OFICIAL** |
| Peso máximo | 256 GB o 12 h | ESTIMADO (conocimiento previo, no re-verificado hoy). La página de codificación no lo dice |
| Miniatura | 3840x2160 (mín. 640 px de ancho), 16:9, JPG/PNG; máx. 2 MB en móvil y 50 MB en escritorio | **OFICIAL** support.google.com/youtube/answer/72431 |
| Subtítulos | SRT y otros formatos como pista | ESTIMADO |
| Zona segura 16:9 | márgenes ~5 % laterales, ~6 % arriba, ~10 % abajo (barra de progreso, subtítulos del reproductor y duración en la esquina inferior derecha de la miniatura) | ESTIMADO |

### LinkedIn (video, datos oficiales de anuncios)

Fuente oficial: https://www.linkedin.com/help/lms/answer/85306 (leída hoy).

| Campo | Valor | Confianza |
|---|---|---|
| 16:9 | recomendada 1920x1080 o 1200x675; mín. 640x360; máx. 1920x1080 | **OFICIAL** |
| 1:1 | mín. 360x360; máx. 1920x1920; sin recomendada (usar 1080x1080) | **OFICIAL** (recomendación mía) |
| 4:5 | recomendada 720x900; mín. 360x450; máx. 1080x1350. LinkedIn la llama la relación vertical recomendada | **OFICIAL** |
| 9:16 | recomendada 720x1280; mín. 360x640; máx. 1080x1920. Solo móvil | **OFICIAL** |
| Relación aceptada | entre 9:16 y 16:9 (un 16:3 se rechaza) | **OFICIAL** |
| Duración | 3 s a 30 min; 15 a 30 s entran en todos los emplazamientos; in-stream hasta 90 s; menos de 30 s hace bucle hasta 30 s | **OFICIAL** |
| Peso | 75 KB a 500 MB | **OFICIAL** (blogs que dicen 200 MB son antiguos: contradicción; el oficial manda) |
| Formato / códec | MP4; H.264 o VP8; **ProRes no soportado** | **OFICIAL** |
| fps | menos de 30 fps | **OFICIAL** (conservador: exportar 30 o 29,97) |
| Audio | AAC o MPEG4 | **OFICIAL** |
| Bitrate | no especificado | **OFICIAL** (la página no lo da); recomendar 8 Mbps en 1080p (ESTIMADO) |
| Subtítulos | archivo SRT, solo texto, sin formato; también se pueden quemar | **OFICIAL** |
| Miniatura | JPG o PNG, máx. 2 MB, relación y resolución iguales al video | **OFICIAL** |
| Carga | debe ser desde escritorio; 25 videos / 24 h en Campaign Manager | **OFICIAL** |
| Zonas de interfaz | No hay cifras publicadas. Feed móvil: nombre/avatar arriba y barra de reacciones/comentarios fuera del video (el video 4:5 y 1:1 se ve completo). En 9:16 móvil, texto en pantalla completa con botones sobre el video | ESTIMADO |

Margen recomendado en cada relación de LinkedIn (ESTIMADO): 5 % laterales, 5 % arriba, 12 % abajo para subtítulos quemados y la barra de reproducción.

### Facebook Reels (opcional)

| Campo | Valor | Confianza |
|---|---|---|
| Resolución | 1080x1920, 9:16 | TERCEROS (Adnova) |
| Duración | hasta 90 s históricamente; ampliado en 2025 | ESTIMADO, sin verificar |
| Zona segura | igual que Instagram Reels: 270 / 672 / 65 / 65 | TERCEROS (Adnova agrupa FB e IG) |

---

## 3. Dónde están desactualizados o incorrectos los números del equipo

Fuentes leídas (solo lectura): `Ride-the-Lightning` (motor/diseno.js, CLAUDE.md, docs/ARCHITECTURE.md, docs/research/VISUALIZATION_RESEARCH.md, servidor/render.mjs), la guía de dirección de Electric Eye (sección "Zona segura en 9:16") y `macrowise-video-editor/brand/brand.json` clave `zonas_seguras`.

| Dónde | Valor actual | Problema |
|---|---|---|
| `brand.json` vertical | arriba 14 %, abajo 22 %, derecha 14 %, izquierda 6 % | Arriba (14 % = 269) está bien. **Abajo 22 % (422 px) es muy bajo**: Meta Reels y TikTok dan 660 a 672 (35 %). **Derecha 14 % (151) es bajo** frente a 242 (22,4 %) y a la columna de botones (300). **Izquierda 6 % (65) es bajo** frente a 120 de TikTok/revid. Su `_nota` dice "22 % inferior", que solo corresponde a Stories (20 %) |
| `brand.json` horizontal | 6 / 8 / 5 / 5 % | Sin fuente. Razonable pero debajo de mi estimado (abajo ~10 %) para subtítulos del reproductor de YouTube |
| `brand.json` | no tiene 1:1 ni 4:5 | Falta, y hay que crear los rectángulos de la sección final |
| RTL `ZONA = {x: 0.722, y: 0.4375}` | Nada con x >= 780 y y >= 840 | Esta regla cubre **solo la columna de botones**. Un texto a la izquierda y en la franja inferior (y > 1248) **no está protegido**. Y `margenes()` usa `y1 = 86 %` (y = 1651), es decir un margen inferior de ~14 % (269 px): invade la zona de pie de texto/hashtags (672 px). Además `x0` = 72 px queda debajo de los 120 px de TikTok |
| RTL, pie obligatorio "Fuente: ... · RTL" | `pieY = H - 3 %` (y ~ 1862) | En 9:16 queda **dentro de la zona de interfaz inferior** de TikTok y Reels. Tiene que estar sobre y <= 1248 |
| RTL docs/research (INVESTIGACION_VISUALIZACION) | "120 / 270 / 670" | Correcto como cifra de terceros, pero el código no la aplica por completo (solo x e y del botón) |
| Electric Eye `estandar` (220/380/140/40) | por defecto | **Abajo 380 queda corto** frente a 660 a 672; izquierda 40 es la más baja de todas las fuentes. El propio texto de la guía lo admite: "criterio propio, no oficial". Su afirmación "11 % arriba y 20 % abajo" tampoco coincide con `brand.json` (14 / 22 %) |
| Electric Eye `universal` | 269 / 672 / 242 / 122 | Es la que coincide con la unión. Recomiendo que sea la predeterminada |
| Electric Eye guía | "TikTok y YouTube Shorts no publican cifra oficial legible" | Confirmado hoy: sigue siendo cierto |
| Los tres sistemas | no coinciden entre sí | Hay tres conjuntos de números distintos en el equipo (brand.json, RTL, Electric Eye). Conviene unificar en uno solo |

---

## 4. Zona segura universal recomendada

Criterio: unión de las zonas prohibidas de TikTok, Instagram Reels/Stories, Facebook Reels, YouTube Shorts, el recorte de cuadrícula (3:4 y 4:5) y la regla de la columna de botones. Los valores son [ESTIMADO] derivados de las cifras [TERCEROS] anteriores; ninguno es oficial.

### 9:16 (1080x1920)

- **Texto y datos clave:** rectángulo x 122 a 838, y 270 a 1248 (716 x 978 px).
- **En la franja y 840 a 1248, x máximo 780** (columna de botones): rectángulo reducido x 122 a 780.
- **Para que el título sobreviva al recorte de cuadrícula 4:5 (y 285 a 1635):** mantener el título en y >= 285.
- **Fondo, color y decoración** pueden llegar a los bordes (no son información).
- **Pie de fuente/cifra:** siempre dentro del rectángulo, nunca en y > 1248.

| Margen | px | % |
|---|---|---|
| Arriba | 270 (285 para título) | 14,1 % (14,8 %) |
| Abajo | 672 | 35,0 % |
| Izquierda | 122 | 11,3 % |
| Derecha | 242 (300 si y >= 840) | 22,4 % (27,8 %) |

### 1:1 (1080x1080) - LinkedIn y feed

- Rectángulo seguro: x 65 a 1015, y 65 a 960 (950 x 895).
- Márgenes: 65 px (6 %) en arriba, izquierda y derecha; **120 px (11 %) abajo** para subtítulos quemados/controles. [ESTIMADO]
- Solo si el cuadrado se obtiene recortando un 9:16 para la cuadrícula: el centro es y 420 a 1500 del 9:16.

### 4:5 (1080x1350) - LinkedIn (relación vertical recomendada) y feed de Instagram

- Rectángulo seguro: x 65 a 1015, y 70 a 1200 (950 x 1130).
- Márgenes: 65 px laterales, 70 px arriba, **150 px (11 %) abajo**. [ESTIMADO]
- Si un 4:5 se mostrará en la cuadrícula 3:4: se pierden ~34 px a cada lado (1080 x 1350 -> 1012 x 1350 de ancho visible); mantener el contenido x 100 a 980. [ESTIMADO, geometría]

### 16:9 (1920x1080) - YouTube y LinkedIn

- Rectángulo seguro: x 96 a 1824, y 65 a 970 (1728 x 905).
- Márgenes: 96 px (5 %) laterales, 65 px (6 %) arriba, **110 px (10 %) abajo** (barra de progreso y subtítulos del reproductor). [ESTIMADO]
- Miniatura YouTube 16:9 (3840x2160, escala 2x a 1920x1080): evitar la esquina inferior derecha (duración) ~ 200 x 90 px. [ESTIMADO]

---

## 5. Dudas que requieren verificación humana

1. **Meta:** abrir facebook.com/business/help/980593475366490 en un navegador (la extracción devolvió solo el título) y confirmar 14 % / 35 % / 6 % para Reels y 20 % para Stories. En Ads Manager activar el "Safe zone guardrail".
2. **TikTok:** bajar las plantillas oficiales de zona segura del Business Help Center (In-Feed Standard e In-Feed with Anchor) y medirlas. La URL ads.tiktok.com/help/article/video-ad-specifications devolvió "ya no existe".
3. **Cuadrícula de Instagram:** subir un Reel de prueba y mirar "Profile grid preview" para confirmar 3:4 (1080x1440) frente a 4:5; no hay documento oficial.
4. **Duración Instagram Reels:** 3 min (Mosseri, enero 2025) frente a 20 min (blogs, sin fuente primaria).
5. **TikTok:** duración y peso de subida orgánica (no de anuncios) y bitrate recomendado.
6. **YouTube Shorts:** 1:1 contradictorio entre fuentes; zona segura no publicada.
7. **LinkedIn:** fps "menos de 30" literal y bitrate; zonas de interfaz del feed móvil y escritorio no publicadas.
8. **Facebook Reels:** duración máxima actual.

## Fuentes consultadas

- LinkedIn Help, Video ads specs: https://www.linkedin.com/help/lms/answer/85306
- YouTube, encoding: https://support.google.com/youtube/answer/1722171
- YouTube, miniaturas y Shorts: https://support.google.com/youtube/answer/72431
- Meta Business Help (zona segura; solo título leído): https://www.facebook.com/business/help/980593475366490
- TikTok Business Help (vía resumen): https://www.relevantaudience.com/tiktok-ads/tiktok-video-size-ad-specs/
- Adnova, Meta safe zones: https://adnova.ai/blogs/meta-ad-safe-zones-guide
- Shortsync, Shorts: https://shortsync.app/resources/youtube-shorts-upload-requirements-2026
- revid.ai: https://www.revid.ai/instagram-reels-safe-zone y https://www.revid.ai/tiktok-safe-zone
- socialync.io: https://www.socialync.io/tools/safe-zones/tiktok
- Hopper HQ, Instagram Reel size: https://www.hopperhq.com/blog/instagram-reel-size/
- Business Today (Mosseri, enero 2025): https://www.businesstoday.in/technology/news/story/instagram-head-announces-big-changes-3-minute-reels-and-new-look-for-profile-grid-461527-2025-01-21
- Buffer, Reels length: https://buffer.com/resources/instagram-reels-length
- Coinis: https://coinis.com/how-to/best-way-to-put-text-on-instagram-ad
