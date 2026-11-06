# Corrección y etalonaje de color para presentadores a cámara (FFmpeg 9.0.2 + Python 3.13)

Fecha: 2026-11-05. Todo lo de abajo está **probado** sobre `clip_aztec_70s.mp4` y `clip_raoul_75s.mp4` (solo lectura). Laboratorio: `_pruebas\color_lab\` (scripts `lab1..lab6`, `out\` con renders, hojas y JSON). Módulo propuesto (no integrado): `docs\investigacion\color_propuesta.py`.
Nota de versión: el ffmpeg instalado es **9.0.2 full_build** (gyan.dev), no 8.x; todos los filtros pedidos existen (lut3d, curves, colorbalance, colorcorrect, colorchannelmixer, eq, vibrance, selectivecolor, tonemap, zscale, signalstats, vectorscope, histogram, geq, colortemperature, huesaturation, maskedmerge).

## 0. Hallazgos que cambian cómo se hace (todos verificados)

1. **`eq` y `huesaturation` degradan a 8 bit**: con `-v verbose` se ve que ffmpeg inserta `auto_scale` a `yuv444p` / `rgb24` alrededor de ellos. `lutrgb`, `colorchannelmixer`, `curves` (sube a rgb48), `colorbalance`, `vibrance`, `selectivecolor` sí aguantan `gbrp16le`. El `mw_editor/imagen.py` actual usa `eq` (8 bit): conviene sustituirlo.
2. **`signalstats` HUE no es el ángulo del vectorscopio**: HUE = atan2(U-128, V-128)+180°. Medido en el parche de mejilla: HUEMED 157 ↔ ángulo vectorscopio 112° (numpy). Conversión: `angulo = (270 - HUE) mod 360`. **La línea de piel 123° = HUEMED ≈ 147° en signalstats.**
3. **`cv2.VideoCapture` decodifica con otra matriz**: mismo fotograma, piel Y 146.3 / ángulo 108.3° (cv2) frente a 151.0 / 113.3° (ffmpeg con BT.709 tv). 5° de error en el ángulo = falso diagnóstico. Todo el medidor lee con ffmpeg (rawvideo rgb24 con `scale=in_range=tv:in_color_matrix=bt709`).
4. **Los clips traen superblancos/superneros**: YMAX=255 e YMIN=0 en ambos, y en aztec el 5,70 % de los píxeles está fuera de rango legal (BRNG). Pasar a RGB recorta esos valores sin aviso: se comprimen antes en YUV (paso 0).
5. **Tras x264 crf17 aparece sobreimpulso**: la cadena sale con YMAX 226 / YMIN 23 y **BRNG 0.0 %** antes de codificar, pero el MP4 medido da YMAX 238-245 y BRNG 0.05-1.3 % (anillos en bordes duros, p. ej. las persianas de raoul). Medir el legal range **antes** de x264 y dejar ~9 niveles de holgura (techo 0.95).
6. Rendimiento: cadena completa en `gbrp16le` ≈ 4,7 s de PC por segundo de vídeo (4 s de clip en 18,8 s; `gbrp10le` 12,2 s). Es lenta: se aplica una sola vez, en el render final (no en previews); `gbrp10le` para previews (banding sin evaluar).

## 1. Pipeline recomendado (8 pasos, ORDEN FIJO)

El denoise va **antes de todo** (ya está en `imagen.py`: hqdn3d) y la nitidez **al final**, fuera de este bloque. Dominio de trabajo: RGB codificado (gamma) de 16 bit, una sola conversión de entrada y una de salida.

| # | Paso | Filtro FFmpeg | Por qué en este orden |
|---|------|---------------|-----------------------|
| 0 | Entrada + superblancos | `lutyuv=y='if(gt(val,220),220+(val-220)*15/34,val)'`, `scale=in_range=tv:in_color_matrix=bt709:out_range=full:flags=accurate_rnd+full_chroma_int`, `format=gbrp16le` | Lo que pase de 235 muere al convertir a RGB: se comprime en YUV [220,254]→[220,235] antes. Matriz y rango explícitos: no depende de etiquetas |
| 1 | Exposición | `lutrgb=r=gammaval(g):g=gammaval(g):b=gammaval(g)` con g = ln(Yobj_n)/ln(Ypiel_n), acotado 0.72-1.25 | Gamma conserva 0 y 1 (no quema); si se hace tras el color, el balance de blancos se calcula sobre luces erróneas. Objetivo: piel Y=150 (≈61 IRE; piel oscura 100-125) |
| 2 | Balance de blancos (referencia neutra) | `colorchannelmixer` diagonal (gr, 1, gb) medida en camiseta/pared cerca de la cara, límite ±5 %, aplicada al 70 % | Antes que cualquier curva/saturación: un cast se amplifica con el contraste |
| 3 | Tono de piel | giro de croma hacia 123° (±8°, al 60 %) fundido en la **misma** matriz que el paso 2 (`colorchannelmixer` de 9 coeficientes) | Los neutros engañan en habitaciones de color; la piel es la referencia final. Una sola matriz = un solo redondeo |
| 4 | Contraste/curva | `curves=red=..:green=..:blue=..:interp=pchip` (suelo y techo por canal) | PCHIP es monótona: sin inversiones ni bandas. Suelo >0 y techo <1 = negros suaves y luces rodadas |
| 5 | Saturación/vibrance | `colorchannelmixer` de saturación (conserva luma) + `vibrance=intensity=0.06-0.10` | Después de la curva, que sube saturación implícitamente. Vibrance protege lo ya saturado (piel, silla naranja) |
| 6 | Look de marca | `colorbalance=rs..bh:pl=1` (sombras/medios/luces, preserva luminosidad) | Último paso creativo; tinte pequeño (≤0.03) |
| 7 | Salida legal | `scale=in_range=full:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int:sws_dither=ed`, `format=yuv420p`, `limiter=min=16:max=235:planes=1`, `limiter=min=16:max=240:planes=6`, `setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv` | Instagram/TikTok/Shorts/LinkedIn/YouTube re-codifican a H.264 BT.709 8 bit tv: lo que salga de rango se recorta (planos pastosos) y el full-range sin etiqueta se ve lavado. Dither `ed` evita bandas al bajar de 16 a 8 bit. Codificación: `-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv` |

HDR/HLG (iPhone «HDR»): hay que pasar a SDR **antes** del paso 0 (probado con HLG sintético, funciona): `zscale=t=linear:npl=100,format=gbrpf32le,tonemap=mobius:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p`.

Comando base (la cadena sale de `cadena_completa(perfil, look)`; ejemplo sin look, con los parámetros medidos de **aztec**: wb (0.986, 1, 1.004), giro +5.3°, gamma 1.0):

```
ffmpeg -i in.mp4 -vf "lutyuv=y='if(gt(val,220),220+(val-220)*15/34,val)',scale=in_range=tv:in_color_matrix=bt709:out_range=full:flags=accurate_rnd+full_chroma_int,format=gbrp16le,colorchannelmixer=rr=0.96618:rg=-0.05318:rb=0.07361:gr=0.01436:gg=1.00761:gb=-0.02227:br=-0.08389:bg=0.08119:bb=1.00817,<BLOQUE_LOOK>,scale=in_range=full:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int:sws_dither=ed,format=yuv420p,limiter=min=16:max=235:planes=1,limiter=min=16:max=240:planes=6,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv" -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv out.mp4
```
(raoul, para contrastar: gamma 0.9715, wb (0.954-ish vía matriz), giro +7.7°; los coeficientes los calcula `parametros_correccion`.)

Lo que **no** sirvió como palanca: `selectivecolor reds/yellows 0.12 cian` sobre la piel solo bajó el croma 31.3→30.9 (casi nada): para controlar el croma de piel usar la matriz de saturación (`sat_piel`). `colortemperature`, `colorcorrect`, `grayworld` ejecutan bien pero **no se midieron**; `grayworld` falla por diseño con fondos dominantes (madera, paredes de color).

## 2. Medición objetiva

Medidor: `medir_piel` (YuNet + máscara de piel Cb/Cr, mediana), `perfil_clip` (12 fotogramas en una pasada de ffmpeg), `delta_e2000` (validado contra `skimage.color.deltaE_ciede2000`: diferencia máxima 2.9e-14).

Validación cruzada del medidor contra `signalstats` en un parche de mejilla (mismo fotograma): YAVG 113.1 vs 112.0 numpy; UAVG 117.5 vs Cb 117.6; VAVG 153.2 vs Cr 153.6. Coinciden.

Comandos:
```
# estadísticas por fotograma (BRNG = % fuera de rango legal; hay que pedirlo con stat=brng)
ffmpeg -v error -i x.mp4 -vf "signalstats=stat=tout+vrep+brng,metadata=print:file=ss.txt" -f null -
# solo el parche de piel (w:h:x:y de la caja YuNet)
ffmpeg -v error -i x.mp4 -vf "crop=W:H:X:Y,signalstats,metadata=print:file=-" -f null -
# vectorscopio nativo (el hoja propia añade la línea de piel, que ffmpeg no dibuja)
ffmpeg -ss 10 -i x.mp4 -vf "vectorscope=mode=color2:colorspace=709:graticule=color:opacity=0.8:envelope=instant" -frames:v 1 vs.png
```

**Métricas de aceptación propuestas** (medidas sobre la mediana de ≥8 fotogramas y sobre el fichero **antes** de x264, salvo indicación):

| Métrica | Aceptar | Fallo duro |
|---|---|---|
| Piel Y (tv) | 150 ± 15 (clara/media); oscura 110 ± 15 | fuera de ± 30 |
| Piel ángulo vectorscopio | 123° ± 6 (signalstats HUEMED 147 ± 6) | ± 10°. Para igualar con otra cámara: ángulo de la referencia ± 3° |
| Piel croma (radio Cb/Cr) | 14-40 | <10 o >45 |
| Dispersión de piel entre fotogramas (ΔE00 p90) | ≤ 2.5 | >4 (parpadeo o mezcla de luces) |
| ΔE00 piel entre cortes/cámaras | ≤ 2.5 (JND ≈ 1) | >4 se nota |
| YMAX / YMIN (pre-codificación) | ≤ 235 / ≥ 16 | |
| BRNG % | 0 pre-codificación; ≤ 1.5 % tras x264 | >3 % |
| Cast global (UAVG-128, VAVG-128) | neutral ≤ 4 salvo look intencionado | |

Resultados (clips de 12 s, x264 crf17; piel en tv, ángulo en grados; BRNG tras codificar):

| clip / variante | YMAX | BRNG % | SATAVG | piel Y | piel ° | croma | disp ΔE p90 |
|---|---|---|---|---|---|---|---|
| aztec original | 255 | **5.702** | 4.03 | 149.6 | 114.1 | 31.0 | 1.65 |
| aztec corrección | 246 | 3.861 | 3.89 | 149.7 | 119.3 | 30.3 | 1.65 |
| aztec warm_black | 241 | 0.228 | 5.96 | 151.5 | 124.7 | 35.1 | 1.19 |
| aztec stone_light | 238 | 0.054 | 5.46 | 153.1 | 123.9 | 30.0 | 1.37 |
| aztec oro_editorial | 239 | 0.439 | 8.52 | 153.0 | 127.5 | 37.5 | 1.34 |
| aztec teal_sutil | 239 | 0.322 | 5.86 | 153.3 | 124.6 | 35.7 | 1.32 |
| raoul original | 255 | 0.005 | 18.11 | 147.5 | 112.4 | 32.0 | 1.60 |
| raoul corrección | 252 | 0.192 | 17.02 | 148.8 | 119.0 | 29.7 | 1.45 |
| raoul warm_black | 242 | 0.817 | 20.31 | 151.9 | 123.8 | 36.3 | 1.76 |
| raoul stone_light | 239 | 0.375 | 17.81 | 154.5 | 123.6 | 30.5 | 1.52 |
| raoul oro_editorial | 245 | 1.289 | 21.30 | 152.7 | 126.6 | 39.0 | 1.42 |
| raoul teal_sutil | 245 | 1.112 | 18.72 | 152.3 | 124.1 | 36.3 | 1.58 |

Lectura: la predicción del giro de piel se cumple (aztec: 114.1→119.3 con +5.3° pedidos; raoul 112.4→119.0 con +7.7°). El «BRNG 3.86 %» de aztec «corrección» (sin look) son negros bajo 16 que la cadena sin curva no levanta; con cualquier look el suelo >0 lo resuelve (0.05-0.44 %). Pre-codificación, warm_black y oro_editorial en ambos clips: **BRNG 0.0, YMAX 226, YMIN 23**.

Hojas antes/después (filas: original, corrección, 4 looks; 3 instantes): `_pruebas\color_lab\out\hoja_aztec.png`, `hoja_raoul.png`; vectorscopios con línea de piel: `hoja_vectorscopio.png`; nativo ffmpeg: `ffvs_aztec_orig.png`, `ffvs_aztec_warm_black.png`.

## 3. Consistencia entre cortes y cámaras

Reglas:
1. **Una cadena estática por cámara/toma**, calculada con la mediana de ≥12 fotogramas, nunca por fotograma (el auto-ajuste por fotograma parpadea). La dispersión interna de la piel medida ya es ΔE00 p90 1.2-1.8 (imperceptible): una cadena fija no añade nada.
2. **Mismo look, mismos números, para todas las cámaras**; la corrección primaria (pasos 1-3) es lo único que cambia por cámara.
3. **Dos modos de objetivo**: (a) absoluto = línea de piel 123° (cámara única), (b) **por referencia** = `objetivo_desde_referencia(perfil_ref)` para igualar a otra cámara o persona. No mezclar: forzar 123° sobre una cámara cuya piel real es 113° la aleja de la otra.
4. Entre personas distintas se iguala el **ángulo y la exposición relativa**, no el color absoluto de piel.

Prueba (raoul degradado a propósito: cast frío + ~0.8 EV de menos, piel Y 135.7 / 106.9°; se corrige con el perfil medido, sin conocer la degradación):

| Corrección | ΔE00 piel vs raoul sano |
|---|---|
| sin corregir | 5.24 |
| automática por línea 123° (parcial, valores por defecto) | 2.98 |
| forzando 123° al 100 % | 6.60 (peor: el objetivo no era la verdad) |
| **por referencia al clip sano** (`fuerza_wb=1, fuerza_piel=1, max_rot=16`) | **1.47** |

ΔE00 de piel aztec vs raoul (dos personas/cámaras): original 1.17; corrección 0.60; warm_black 1.0; stone_light 0.67; oro 0.87; teal 0.70 (todos ≤ 2.5: el look se aplica igual a ambos sin separarlos).

## 4. Cara subexpuesta con ventana detrás (máscara)

Solución implementada: `mascara_persona` = **silueta** (GrabCut a 0.35× inicializado con la caja YuNet: cabeza, cuello y hombros) con pluma gaussiana σ = 1.2 % del ancho; `grafo_exposicion_enmascarada` aplica el gamma solo bajo la máscara con `maskedmerge` en RGB 16 bit (una sola conversión, sin banding). Para vídeo: máscara por fotograma (YuNet cada fotograma + GrabCut cada 3-5 y EMA α≈0.2) como 2º input en gris.

Prueba **sintética** (la cara oscurecida −1.3 EV con una elipse independiente sobre aztec; piel Y 150.4 → 112.4; gamma pedido 0.72 por tope de seguridad):

| Método | Piel Y recuperada | Δ luma fondo (fuera de máscara) | Δ luma anillo 40 px fuera del borde |
|---|---|---|---|
| gamma global | 133.6 | **+25.1** (fondo se quema) | +26.2 |
| máscara elipse (como `_mascara_luz` actual) | 131.9 | 0.0 | +10.2 |
| **máscara silueta GrabCut** | 133.6 | 0.0 | **+4.9** |

Regla anti-«degradados raros»: (1) borde de la silueta, nunca elipse/viñeta; (2) solo luma/gamma por la máscara, **no** casts de color distintos dentro y fuera; (3) diferencial ≤ ~0.8 EV; (4) pluma 1-1.5 % del ancho; (5) prueba `halo_anillo` (Δ medio de luma en un anillo de 40 px): aceptar si ≤ 25 % de lo que se sube la cara (silueta 4.9/21 = 23 %; elipse 52 %). Con diferencial >1 EV el ruido de sombras se come la mejora: gamma tope 0.72 → la piel no llegó a 150 (queda 134): avisarlo, no forzarlo. Hoja: `out\hoja_mascara.png`.
Limitación honesta: la prueba es sintética y estática (1 fotograma); la estabilidad temporal de la máscara en movimiento (manos, giros) no se midió.

## 5. Looks de marca MacroWise (parámetros exactos)

Cadenas completas de cada look = pasos 0-3 de §1 + el bloque de abajo + paso 7. Suelo = negro cálido (RGB 0.036/0.034/0.027 ≈ Y 24, inspirado en #1A1A17 atenuado: un negro real a #1A1A17 daría Y 38, un velo lechoso); techo < 1 = luces rodadas. Ninguno usa glow, viñeta, degradado ni tinte de saturación alta.

**A. `warm_black`** (por defecto: estudio cálido, contraste de editorial)
```
curves=red='0/0.0360 0.1/0.0998 0.3/0.2874 0.5/0.5050 0.72/0.7426 0.9/0.8972 1/0.9560':green='0/0.0340 0.1/0.0974 0.3/0.2842 0.5/0.5010 0.72/0.7377 0.9/0.8916 1/0.9500':blue='0/0.0270 0.1/0.0893 0.3/0.2739 0.5/0.4885 0.72/0.7228 0.9/0.8747 1/0.9320':interp=pchip,colorbalance=rs=0.012:gs=0.004:bs=-0.016:rm=0.012:gm=0.004:bm=-0.012:rh=0.012:gh=0.004:bh=-0.016:pl=1,colorchannelmixer=rr=0.96063:rg=0.03576:rb=0.00361:gr=0.01063:gg=0.98576:gb=0.00361:br=0.01063:bg=0.03576:bb=0.95361,vibrance=intensity=0.100
```
(maestro 0→.030, .10→.094, .30→.282, .50→.500, .72→.738, .90→.893, 1→.952; saturación 0.95.)

**B. `stone_light`** (alta clave piedra #D6D1C8, contraste mínimo, aire)
```
curves=red='0/0.0540 0.12/0.1547 0.35/0.3761 0.55/0.5773 0.78/0.7987 0.92/0.9095 1/0.9450':green='0/0.0520 0.12/0.1518 0.35/0.3713 0.55/0.5709 0.78/0.7904 0.92/0.9002 1/0.9350':blue='0/0.0460 0.12/0.1441 0.35/0.3604 0.55/0.5572 0.78/0.7735 0.92/0.8813 1/0.9150':interp=pchip,colorbalance=rs=0.006:gs=0.003:bs=-0.008:rm=0.010:gm=0.006:bm=-0.010:rh=0.014:gh=0.008:bh=-0.014:pl=1,colorchannelmixer=rr=0.92126:rg=0.07152:rb=0.00722:gr=0.02126:gg=0.97152:gb=0.00722:br=0.02126:bg=0.07152:bb=0.90722,vibrance=intensity=0.060
```
(saturación 0.90.)

**C. `oro_editorial`** (luces hacia oro #C9A84C, piel cálida, sombras neutras para no verdear)
```
curves=red='0/0.0340 0.1/0.0946 0.3/0.2818 0.5/0.5050 0.72/0.7483 0.9/0.9044 1/0.9580':green='0/0.0320 0.1/0.0914 0.3/0.2762 0.5/0.4970 0.72/0.7377 0.9/0.8916 1/0.9440':blue='0/0.0280 0.1/0.0839 0.3/0.2617 0.5/0.4755 0.72/0.7085 0.9/0.8561 1/0.9050':interp=pchip,colorbalance=rs=0.006:gs=0.002:bs=-0.006:rm=0.016:gm=0.008:bm=-0.016:rh=0.028:gh=0.012:bh=-0.034:pl=1,colorchannelmixer=rr=0.95276:rg=0.04291:rb=0.00433:gr=0.01276:gg=0.98291:gb=0.00433:br=0.01276:bg=0.04291:bb=0.94433,vibrance=intensity=0.080
```
(saturación 0.94. Es el más cálido: ángulo de piel 126.6-127.5°, en el borde del margen ±6; BRNG post-x264 1.29 % en raoul, el mayor.)

**D. `teal_sutil`** (sombras hacia teal #50B5A2 ≈1 %, luces cálidas; separación de planos sin neón)
```
curves=red='0/0.0260 0.1/0.0892 0.3/0.2796 0.5/0.5020 0.72/0.7446 0.9/0.9018 1/0.9580':green='0/0.0360 0.1/0.0972 0.3/0.2836 0.5/0.5020 0.72/0.7402 0.9/0.8938 1/0.9480':blue='0/0.0360 0.1/0.0949 0.3/0.2767 0.5/0.4905 0.72/0.7237 0.9/0.8731 1/0.9250':interp=pchip,colorbalance=rs=-0.014:gs=0.004:bs=0.010:rm=0.006:bm=-0.006:rh=0.014:gh=0.006:bh=-0.018:pl=1,colorchannelmixer=rr=0.96850:rg=0.02861:rb=0.00289:gr=0.00850:gg=0.98861:gb=0.00289:br=0.00850:bg=0.02861:bb=0.96289,vibrance=intensity=0.080
```
(saturación 0.96.) El púrpura #73247D se reserva para gráficos/tarjetas: en etalonaje de la piel produce magenta; no se ofrece look con él.

Las cadenas completas de cada look para un clip concreto se generan con `a_vf(cadena_completa(perfil_clip(clip), "warm_black")[0])`; fuerza 0-1 en `fuerza_look` (0.6 si la cara queda muy tintada). Efecto medido sobre piel: Y +2 a +5, ángulo 123.6-127.5°, croma 30-39. Con tarjetas opacas del montaje (Warm Black/Dark): el suelo del look queda ~Y 24, más claro que la tarjeta opaca; esa diferencia es intencional (la cara no debe parecer pegada sobre un negro más profundo que el suyo).

## 6. LUTs libres (solo citadas, no descargadas)

| LUT / herramienta | Licencia | URL | Uso comercial |
|---|---|---|---|
| OpenColorIO-Config-ACES (transformaciones ACES, no LUT creativas) | BSD-3-Clause (leída en LICENSE del repo) | https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES | Sí |
| Khronos PBR Neutral tone mapper (curva neutra de luces; referencia para rodar luces sin virar color) | Apache-2.0 (leído en el repo) | https://github.com/KhronosGroup/ToneMapping | Sí |
| Jamie Fenn «free fenn x LUT» (1 .cube Rec.709) | licencia del vendedor: proyectos personales y comerciales (resumen de la ficha) | https://jamiefenn.sellfy.store/p/free-fenn-x-lut | Sí, **verificar el texto de licencia incluido en el zip** |
| FreeVisuals free LUTs | libres personal y comercial sin atribución (ficha) | https://www.freevisuals.net/free-luts | Sí, verificar |
| MARU Studio Log→Rec.709 gratis | personal y comercial; prohibido redistribuir | https://studiomaru.gumroad.com/l/tgvip | Sí (no redistribuir) |
| G'MIC Color Presets (CLUT Hald) | G'MIC es CeCILL; **las CLUT son de autores distintos sin licencia unificada** | https://gmic.eu/color_presets/ | **No claro: evitar** |
| Cinecom «free 10 look pack» | la descarga gratuita **no** permite comercial | https://cinecom.gumroad.com/l/LookPack | **No** |

Aviso: los datos de vendedores son resúmenes de sus fichas, no el texto legal; antes de usar una guardar copia de la licencia del zip (David monetiza). Recomendación práctica: **no depender de LUTs de terceros**: los 4 looks de arriba son propios (curvas + balance) y no tienen problema de licencia. Si se usa una `.cube`, aplicar `filtro_lut(ruta, 0.5)` (lut3d tetraédrico con intensidad; probado con una LUT identidad) **solo sobre material ya corregido y en espacio display Rec.709**; una LUT de log aplicada a Rec.709 destruye la imagen.

## 7. Lo que NO se puede arreglar

- **Altas luces quemadas** (Y=255 plano, p. ej. las persianas de raoul contra la ventana): sin información; la curva solo las baja a gris plano. Se reporta, no se finge.
- **Bitrate de origen bajo / macrobloques / banding de origen**: el color no lo repara y un contraste más fuerte los hace más visibles. Los looks suaves y el dither de salida no lo compensan.
- **Cast de luz mixta sobre la cara** (ventana fría a un lado, lámpara cálida al otro): un balance global no lo separa; solo la máscara por zonas y a mano.
- **Caras muy subexpuestas (>1 EV)**: la máscara las sube pero el ruido sube con ellas (prueba: tope 0.72 dejó la piel en 134 de 150).
- **Color real de piel**: se mide un valor relativo, no el absoluto; ΔE sin carta de color es solo comparativo.
- Compresión de redes sociales: Instagram/TikTok re-codifican y recortan; lo único que se controla es entregar BT.709 tv 8 bit limpio con holgura (techo 0.95).

## 8. Decisiones para revisar y pendientes

- Eliges tú: objetivo de piel Y=150 (clara/media; para otras pieles hay que bajarlo), el look por defecto (propongo `warm_black`), y si el giro a 123° se mantiene (por defecto al 60 %: ver tabla §3, el modo por referencia es más fiel).
- No probado: estabilidad temporal de la máscara en movimiento; banding real de `gbrp10le`; `colorcorrect`/`colortemperature`/`grayworld` como medidores; escenas con dos personas.
- Integración sugerida (no hecha): sustituir `imagen.py` (`eq`) y `render.py` (`_mascara_luz` elipse) por `cadena_completa` + `grafo_exposicion_enmascarada`; mantener denoise antes y unsharp ≤0.45 después de `filtros_salida`.
- Reproducir: `cd _pruebas\color_lab && python lab2.py` (renders y mediciones, ~15 min), `lab3_mask.py`, `lab4_hojas.py`, `lab5.py`, `lab6.py`.

Archivos: `docs\investigacion\color.md`, `docs\investigacion\color_propuesta.py`, `_pruebas\color_lab\` (frames, out, hojas, scripts).
