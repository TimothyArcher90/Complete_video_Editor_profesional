# Música en reels/shorts de cuenta business (2026-11-18)

Marca: VERIFICADO = leído en página oficial de la plataforma en esta sesión. ESTIMADO = blogs/terceros o inferencia. Estado del motor: `mw_editor/musica.py` ya usa solo CC0 / Pixabay / YouTube Audio Library / CC-BY con crédito, ducking, y mezcla final a -14 LUFS / -1 dBTP.

## 1. Música comercial/tendencia en cuentas business

- **TikTok: no.** VERIFICADO: la Commercial Music Library (CML) es una biblioteca "pre-cleared" de 1 millón de canciones, gratuita para empresas; los negocios deben usarla para "all commercial TikTok activities" (orgánico, anuncios, branded) y no pueden usar la biblioteca general con fines comerciales. Los sonidos originales de otros usuarios exigen licencia propia (consultar a legal). https://ads.tiktok.com/help/article/commercial-music-library
  - ESTIMADO: la licencia de la CML cubre solo la plataforma TikTok, no re-publicar en otras apps. https://www.soundstripe.com/blogs/tiktok-music-library-explained
  - La CML aplica a la selección dentro de la app; la página oficial no menciona APIs ni schedulers.
- **Instagram/Meta: no para tendencia en business.** VERIFICADO (parcial): la ayuda de Instagram indica que ciertas cuentas business y ciertos tipos de publicación no tienen acceso a la biblioteca licenciada (página: https://help.instagram.com/ipad-app/402084904469945; el fetch devolvió solo el encabezado, la frase viene del extracto del buscador, tratar como ESTIMADO-alto). La alternativa para marcas es la **Sound Collection** (pistas libres de regalías, ~14.000 según terceros; uso limitado a apps de Meta, ESTIMADO). https://www.soundstripe.com/blogs/instagram-music-library
  - VERIFICADO: la documentación de Meta menciona los tracks "royalty-free Sound Collection" para reemplazar música con copyright antes de promocionar un Reel (flujo ADS, release limitado, permiso `ads_management`). https://developers.facebook.com/docs/instagram-platform/content-publishing/audio-api/
- **YouTube Shorts.** VERIFICADO: música de la YouTube Audio Library no recibe reclamo Content ID. https://support.google.com/youtube/answer/13486873?hl=en-419 La música de otros sí puede reclamarse (ver 2).
- **LinkedIn:** no encontré política oficial de música; no hay biblioteca equivalente. NO VERIFICABLE. Regla segura: solo música propia/licenciada embebida.

## 2. MP4 con música royalty-free embebida: qué pasa

- **Content ID (YouTube).** VERIFICADO: un claim se genera automáticamente al coincidir con una referencia; el dueño elige bloquear, monetizar (anuncios, reparte ingresos) o rastrear; los Shorts de 1 a 3 min con claim activo se **bloquean sin importar la política**; los claims normalmente no afectan el canal, los strikes vienen de solicitudes de retiro válidas. Opciones: quitar audio ("Erase song"), recortar, reemplazar por Audio Library, o disputar (solo con derechos; disputar sin base puede llevar a strike). https://support.google.com/youtube/answer/6013276?hl=en
  - Un dueño desconocido "no significa necesariamente que el claim sea inválido".
- **CC BY con atribución vs sin ella.** El claim no depende de la atribución: Content ID compara audio, no el texto de la descripción. La atribución es una condición de la licencia (incumplirla es infracción de licencia), no un escudo contra Content ID. ESTIMADO (YouTube no trata CC por página oficial). Guía de Incompetech (Kevin MacLeod): poner el crédito en la descripción, y si hay claim, disputar indicando permiso del titular; hay falsos claims por software o por terceros que registran música CC. https://incompetech.com/music/royalty-free/contentid.html
- **Reclamos falsos: cómo evitarlos (ESTIMADO, buenas prácticas):**
  1. Preferir CC0/Pixabay/Audio Library sin atribución; evitar CC-BY para reels de TikTok/IG donde no hay campo de crédito visible (el motor ya lista créditos en `00_DOCS/musica_creditos.txt`).
  2. Guardar prueba por pista: URL, licencia, fecha y captura en `00_DOCS`.
  3. Subir primero en privado/no listado en YouTube y revisar "Copyright" en Studio antes de publicar.
  4. Un Short de 1-3 min con claim se bloquea: si hay claim falso, disputar de inmediato con la prueba de licencia.
  5. Pistas "libres" distribuidas por agregadores a veces están registradas en Content ID: la columna `content_id` del catálogo ya las excluye; mantenerla honesta.
- **Meta/TikTok al subir MP4 con audio propio:** no hallé página oficial que describa el detector exacto. Instagram avisa de música con copyright y puede silenciar el audio (ESTIMADO, https://www.foximusic.com/blog/instagram-reels-music-copyright-legal-guide/). NO VERIFICABLE con fuente oficial.

## 3. Estrategia: entregar dos versiones

**Recomendación: sí, entregar (a) MP4 con música royalty-free embebida y (b) versión limpia sin música (voz sola, loudness igual).**

Evidencia:
- Los schedulers no pueden añadir audio de tendencia. VERIFICADO (Buffer): para TikTok, audio en tendencia exige "notification publishing" (finalizar en la app), porque Buffer no tiene acceso a la biblioteca de TikTok; en Instagram, música en Posts y Stories también por notificación. https://support.buffer.com/article/933-adding-music-stickers-and-other-effects-to-instagram-and-tiktok-posts
- Excepción: VERIFICADO (Buffer) que en **Reels de Instagram** se puede añadir canción u original sound y publicar automáticamente, con cuenta Business/Creator conectada vía Facebook; el track empieza desde el principio (no se elige el tramo). El FAQ de Buffer dice lo contrario para "trending music" (https://support.buffer.com/article/554-frequently-asked-questions); sin reconciliar, NO VERIFICABLE cuál prevalece.
- Meta Audio API: VERIFICADO, soporta buscar audio y adjuntarlo a Reels solo con Facebook Login / Unified Login (no Instagram Login); solo audio "authorized for third party use", catálogo distinto al de la app; sin preview con audio. https://developers.facebook.com/docs/instagram-platform/content-publishing/audio-api/
- Para una cuenta business, la música "de tendencia" no es usable comercialmente (ver 1), así que la versión (b) sirve solo para añadir música de CML (TikTok) o Sound Collection (Meta) dentro de la app. Cuando el track de la plataforma se superpone a una versión con música embebida, se duplican pistas; por eso (b) es el archivo para esas plataformas.

Reparto sugerido:
| Destino | Archivo |
|---|---|
| YouTube Shorts, LinkedIn | (a) con música Audio Library / CC0 embebida |
| Instagram Reels | (a) embebida con Sound Collection-compatible o (b) + música Meta en la app |
| TikTok | (b) + música CML en la app (la embebida solo si es CC0/propia) |

## 4. Loudness por plataforma

| Plataforma | Objetivo | Estado |
|---|---|---|
| YouTube | ~-14 LUFS integrado; solo baja, no sube | ESTIMADO (no leí página oficial de YouTube; varios blogs coinciden) |
| Instagram Reels | -14 LUFS, TP -1 dBTP | ESTIMADO; Meta no publica objetivo |
| TikTok | -14 LUFS (algunos blogs dicen -10 a -12) | ESTIMADO; sin especificación oficial, fuentes en conflicto |
| LinkedIn | -14 LUFS / -1 dBTP | ESTIMADO; sin spec oficial hallada |
| Spotify (referencia) | -14 LUFS, -1 dBTP | ESTIMADO (blogs) |

Fuentes (todas de terceros): https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026 ; https://openclip.app/learn/audio-normalization . Conclusión: ninguna fuente oficial publica el número para Reels/TikTok/LinkedIn; mantener -14 LUFS / TP -1,5 (política vigente del motor, `brand.json`) con la música unos 18-20 dB bajo la voz.

## Licencias

Solo se recomienda lo permisivo/comercial: CC0, Pixabay, YouTube Audio Library, CC-BY con crédito, TikTok CML, Meta Sound Collection. Nada GPL/AGPL/NC.

## No verificable (resumen)

- Texto exacto de la ayuda de Instagram sobre cuentas business (el fetch devolvió solo el encabezado).
- Si Buffer publica automático trending audio de Reels (dos páginas se contradicen).
- Política oficial de loudness (YouTube, IG, TikTok, LinkedIn).
- Cómo detecta y trata Meta/TikTok el audio con copyright en un MP4 subido por API.
- Música en LinkedIn.
- Licencia por pista de cada track del catálogo local (ya pendiente en `musica.py`).
