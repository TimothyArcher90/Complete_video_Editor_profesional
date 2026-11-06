# Metricas por plataforma y catalogo de QC medible (nov 2026)

Confianza: **oficial** = documentacion de la plataforma o estandar. **terceros** = blogs, vendors, prensa. **estimado** = regla de oficio, calibrar con el corpus propio.
Hallazgo principal: casi ninguna plataforma publica umbrales. Las senales de ranking son declaradas en general; los numeros (3 s, % de retencion, duracion optima) son de terceros. Lo medible antes de publicar son proxies de esas senales.

## 1. Senales de ranking declaradas

| Plataforma | Senales declaradas | Umbral publicado | Confianza |
|---|---|---|---|
| Instagram Reels | Watch time, likes por alcance, sends (DMs) por alcance: las 3 principales (Mosseri, ene-2025). Sends = senal fuerte. Reposts con marca de agua de otra red pierden alcance. | Ninguno. "1-3 s" es regla de creadores. Posibles senales 2026 (replay, originalidad) sin verificar. | Mosseri via terceros; umbrales estimado |
| TikTok | Interacciones (likes, shares, comentarios, seguidos), info del video, ajustes de dispositivo (peso bajo). Seguidores y exito previo NO son factores directos. Pesos reevaluados (Newsroom 2023). | Ninguno. Finalizacion/watch time citado por terceros. | Newsroom oficial para factores; pesos terceros |
| YouTube Shorts | Metrica "Viewed vs Swiped Away" (se ve en Studio). "Engaged view" = se quedo pasados los primeros segundos, sin loops; desde 24-ago-2026 las vistas cuentan desde el primer cuadro. Retencion/AVD se calculan sobre engaged views. | YouTube no publica corte de viewed vs swiped. 70-80% es folklore de terceros. | Definiciones oficial; umbrales terceros |
| YouTube largo | CTR de miniatura/titulo, AVD, % promedio visto, retencion a 30 s ("Intro"), sesion. | Sin oficial. Referencias: ~30% promedio visto; 60%+ aun viendo a 30 s = gancho sano; media 23.7% (Retention Rabbit). | terceros |
| LinkedIn | Dwell time y completacion (terceros). Sin documentacion oficial del algoritmo. | "70% completacion = 3.5x" no verificable. | terceros |

## 2. Duraciones

| Plataforma | Maximo | Optimo publicado | Confianza |
|---|---|---|---|
| Reels | 3 min (verificar) | 15-35 s; fuentes dan desde 7 hasta 90 s | terceros, divergente |
| TikTok | 10 min en app (verificar) | 20-40 s (24-38 s en un estudio) | terceros |
| Shorts | 3 min desde 15-oct-2024 | 20-58 s | maximo oficial; optimo terceros |
| YouTube largo | sin tope practico | depende; mid-roll desde 8 min | terceros |
| LinkedIn | 10 o 15 min (discrepan) | 30-90 s; retencion cae pasados 45 s segun una fuente | terceros |

## 3. Gancho y ritmo (todo estimado/terceros)
- Primer evento visual o de voz en <= 1.5 s en corto. Ninguna plataforma lo documenta.
- Cortes: 12-30 por minuto en corto (plano medio 2-5 s); 4-15 en largo hablado. Maximo tramo sin cambio: 5 s corto, 15 s largo.
- Voz en espanol: 150-190 palabras/min = 2.5-3.2 w/s.
- Subtitulos: Netflix fija 42 car/linea, 2 lineas, cue 5/6 s a 7 s. CPS depende del idioma (17 en indonesio adulto, 22 en telugu adulto; 20 ingles adulto segun terceros). Espanol: verificar.
- Texto legible en movil: >= 44 px de fuente a 1080 de ancho (estimado); contraste WCAG >= 4.5:1 (oficial W3C).

## 4. Loudness
| Plataforma | Objetivo | Nota | Confianza |
|---|---|---|---|
| YouTube | ~-14 LUFS-I, TP -1 dBTP | Solo baja volumen, no sube | terceros muy consistentes |
| Instagram, TikTok | sin spec publica; -14 como seguro (algunos dicen -10 a -12) | Recomprimen AAC | terceros, conflicto |
| LinkedIn | sin dato | usar -14 | estimado |
| General | EBU R128: -23 LUFS broadcast, TP -1 | No aplica a social | oficial |

## 5. Entrega y recompresion
- YouTube (oficial, Help 1722171): MP4, moov al inicio, sin edit lists; H.264 High, 2 B-frames, GOP cerrado = fps/2, CABAC; 1080p SDR 8 Mbps (24-30 fps) / 12 Mbps (48-60); 4:2:0; AAC-LC 48 kHz estereo 384 kbps; BT.709; no usar matriz RGB, convierte full a limited.
- Instagram: recodifica siempre. MP4 H.264/AAC, 1080x1920, 30 fps, 48 kHz (terceros). Bitrates sugeridos 3.5-12 Mbps (terceros, rango amplio).
- TikTok y LinkedIn: MP4 H.264/AAC; LinkedIn acepta 16:9, 1:1, 4:5, 9:16 (terceros). Todas recomprimen: entregar la mejor calidad razonable (crf 17 de la casa lo cubre).
- Hay que verificar en la app: bitrate maximo aceptado y comportamiento de recompresion; no hay doc oficial en las busquedas.

## 6. Subtitulos
- YouTube: pista SRT/VTT editable (oficial). LinkedIn: SRT en video nativo (verificar; algunos vendors recomiendan quemar para autoplay mudo).
- Instagram y TikTok organico: sin importacion de SRT (terceros): el MP4 de publicacion lleva los subtitulos incrustados. Choca con la regla "nunca quemados": hay que definir una variante "para publicar" distinta del master editable.
- Plataformas auto-subtitulan; no evita el caso mudo (cifras de 80-85% de LinkedIn en silencio, terceros no verificadas).

## 7. IA y finanzas
- **YouTube (oficial)**: declarar contenido realista alterado o sintetico en Studio. Exento: sharpening, upscaling, reparacion de video/audio, color, filtros, subtitulos, clonar tu propia voz, guion/miniatura asistidos por IA. Obligatorio: persona diciendo/haciendo lo que no hizo, escena realista generada, alterar metraje de evento real. Recortar o reeditar a una persona sin cambiar el sentido = menor; si el recorte altera el sentido, declarar.
- **TikTok (oficial)**: etiquetar AIGC con escenas o personas realistas; etiqueta automatica con efectos TikTok y por Content Credentials C2PA; "significativamente editado con IA" puede etiquetarse. Prohibe IA que engane sobre hechos reales.
- **Meta (terceros sobre politica Meta)**: "AI info" por metadatos C2PA/IPTC o autodeclaracion. Prueba de insignia "AI creator" (may-2026). Sin penalizacion de alcance confirmada.
- **LinkedIn (oficial)**: icono Content Credentials si el archivo trae C2PA firmado; sin obligacion de declaracion verificada.
- **UE**: Art. 50 AI Act, marcado legible por maquina desde ago-2026 (terceros; no verificado contra el texto).
- **Finanzas**: FTC exige divulgar relaciones comerciales de forma visible; SEC/FINRA vigilan "finfluencers" (terceros juridicos). No se hallaron politicas especificas por plataforma para contenido financiero. Jurisdiccion de MacroWise por validar.
- Mejorar el video propio (denoise, upscale, estabilizar) NO requiere etiqueta en YouTube. Restauracion facial mezclada con original, IA generativa de clips o voz de otra persona SI debe declararse.

## 8. Miniaturas
- YouTube: 1280x720, 16:9, minimo 640 de ancho (conocido); limite de peso reciente por verificar. Texto breve y alto contraste.
- Instagram: portada 9:16 con recorte central 3:4 en la grilla (terceros, verificar).
- LinkedIn y TikTok: portada elegible de un cuadro / subida; sin especificacion oficial verificada.

## 9. Catalogo de metricas medibles (resumen; detalle en metricas.json)
Estado QC = lo que hoy hace `mw_editor/qc.py`.

| ID | Metrica | Formula corta | PASS | WARN | Estado QC |
|---|---|---|---|---|---|
| M01 | Tiempo al primer evento visual | min t de scdet/overlay | <=1.5 s corto | 1.5-3 s | falta |
| M02 | Inicio de voz | primera palabra | <=1.0 s | <=2.0 s | falta |
| M03 | Cortes/min y ASL | 60*cortes/dur | 12-30 cpm corto | 6-12 / 30-40 | falta |
| M04 | Max tramo sin cambio | max gap eventos | <=5 s corto, 15 s largo | <=8 / 30 s | falta |
| M05 | Palabras/s | palabras / tiempo hablado | 2.2-3.3 | 1.8-2.2 / 3.3-3.9 | falta |
| M06 | CPS subtitulos (p95) | chars / dur cue | <=17 | 17-21 | falta |
| M07 | Car/linea y lineas | max len | <=42 horiz, 28 vert, 2 lineas | +5 car, 3 lineas | falta |
| M08 | Dur. cue y cobertura | dur, cobertura voz | 0.83-7 s, >=95% | cobertura 85-95% | falta |
| M09 | Contraste WCAG | (L1+.05)/(L2+.05) | >=4.5 | 3-4.5 | falta |
| M10 | % texto en zona segura | area dentro/area texto | 100% todas muestras | >=98% | parcial (caja union binaria, 10 muestras) |
| M11 | Tamano de texto | px a 1080 ancho | >=44 vert / 36 horiz | 36-44 / 28-36 | falta |
| M12 | LUFS integrado | loudnorm | -14 +/-1 | +/-2.5 | cubierto (usa +/-1.5) |
| M13 | True peak | dBTP | <=-1.0 | -1.0 a -0.3 | parcial (acepta <=-0.7) |
| M14 | LRA y suelo de voz | ebur128 | LRA<=8-11, S>=-20 | LRA 8-14 | falta |
| M15 | Silencio muerto | silencedetect | max<=0.6 s, <8% | 0.6-1.2 s | falta |
| M16 | Cara visible y encuadre | % cuadros, tamano, posicion | >=80% | 60-80% | parcial (>=60%, 8 muestras) |
| M17 | Nitidez | var Laplaciano, ratio vs origen | ratio>=0.9 | 0.7-0.9 | falta |
| M18 | Ruido residual | sigma parches planos | <= origen | +10% | falta |
| M19 | Exposicion de cara | luma media region cara | 90-190 | 70-90 / 190-210 | falta |
| M20 | Duracion vs rango | pertenencia a rango | tabla seccion 2 | dentro del maximo | parcial (solo >3 s) |
| M21 | Parametros de entrega | ffprobe codec/bitrate/CFR/color | cumple perfil YouTube | bitrate 5-8 Mbps | parcial (solo resolucion) |
| M22 | Negros y congelados | blackdetect, freezedetect | 0 | 1 tramo | parcial (solo negros) |
| M23 | Subtitulos alfa real y pista | alfa>128, SRT existe | >=8/10 y SRT | 1-7/10 | cubierto (falta comprobar SRT) |
| M24 | Sync A/V y deriva cues | dur, mediana error | <0.15 s, <=0.08 s | hasta 0.3 / 0.2 | parcial (solo duracion) |
| M25 | Declaracion IA (manifiesto) | flags de pipeline | manifiesto coherente | ausente | falta |
| M26 | Cifras verificadas | cifras con fuente/cifras | 100% | cualquiera sin fuente = FAIL | falta |
| M27 | Aviso no-asesoria | OCR/descripcion | presente | solo descripcion | falta |
| M28 | Miniatura/portada | res, aspecto, contraste titulo | cumple | titulo largo | parcial (solo cuenta archivos) |
| M29 | Cierre apto para loop | SSIM ultimo/primero | informativo | voz cortada | falta |

Ya cubierto por QC actual: resolucion exacta, duracion >3 s, sincronia A/V (por duracion), LUFS/TP (objetivo -14, TP<=-0.7), tramos negros, cara visible (8 muestras), subtitulos con alfa real, subtitulos en zona segura (caja union), miniaturas existen.
Falta: M01-M09, M11, M14-M15, M17-M19, M25-M27, M29 y los matices de M10, M13, M16, M20-M22, M24, M28.
Prioridad sugerida (alto valor, bajo costo): M01/M03/M04/M15 (scdet+silencedetect), M05/M06/M08 (words_final y SRT), M09/M11 (alfa de subtitulos), M21 (ffprobe), M25-M26 (manifiesto).

## Fuentes
Oficiales
- YouTube, ajustes de codificacion: https://support.google.com/youtube/answer/1722171
- YouTube, divulgacion de contenido alterado o sintetico: https://support.google.com/youtube/answer/14328491
- YouTube, engaged views: https://blog.youtube/inside-youtube/engaged-views-youtube-explained/
- YouTube, como se cuentan las metricas: https://support.google.com/youtube/answer/2991785
- YouTube, politicas de monetizacion Shorts: https://support.google.com/youtube/answer/12504220
- TikTok, IA transparente y C2PA: https://www.tiktok.com/transparency/en/supporting-responsible-transparent-ai-generated-content/
- TikTok, como recomienda videos: https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you/
- LinkedIn, Content Credentials: https://www.linkedin.com/help/linkedin/answer/a6282984
- W3C WCAG 2.1 contraste: https://www.w3.org/TR/WCAG21/#contrast-minimum
- EBU R128: https://tech.ebu.ch/docs/r/r128.pdf
- Netflix Timed Text: https://backlothelp.netflix.com/hc/en-us/articles/217349997-Castilian-Latin-American-Spanish-Timed-Text-Style-Guide ; https://backlothelp.netflix.com/hc/en-us/articles/215274938

Terceros
- Instagram ranking (Mosseri via blogs): https://www.eclincher.com/articles/how-the-instagram-algorithm-works-in-2026 ; https://virlo.ai/blog/instagram-reels-algorithm-2026-decoded
- Viewed vs swiped (glosario): https://www.creatoressentials.com/glossary/viewed-vs-swiped-away/
- Shorts retencion: https://vidiq.com/blog/post/youtube-shorts-algorithm/
- Duracion por plataforma: https://biteable.com/blog/marketing-video-length-by-social-platform/ ; https://joyspace.ai/ideal-video-length-social-platform-2026 ; https://quso.ai/blog/social-media-video-length-best-practices.html
- LinkedIn video: https://ligosocial.com/blog/linkedin-video-post-best-practices ; https://blog.hootsuite.com/linkedin-video/
- Reels specs: https://socialrails.com/sizes/instagram/reels ; https://argil.ai/blog/instagram-reel-size-e350f
- Loudness: https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026
- Retencion YouTube: https://vidiq.com/blog/post/increase-audience-retention-youtube/ ; https://tubelab.net/blog/youtube-audience-retention
- Meta AI info: https://www.gradually.ai/en/instagram-ai-label/ ; https://www.mediapost.com/publications/article/414862/instagram-unveils-new-ai-creator-account-label.html
- Finfluencers: https://innreg.com/resources/regulatory-updates/finra-and-sec-increase-focus-on-social-media-finfluencers
- Shorts 3 min: https://petapixel.com/2024/10/04/youtube-shorts-expands-video-length-to-three-minutes/
