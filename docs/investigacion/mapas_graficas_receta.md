# Receta: mapas (Electric Eye), gráficas (Ride the Lightning) y cartelas de dato para el motor de reels

Fecha: 2026-11-05. Probado de punta a punta con tres clips reales en `_pruebas\agentes\mapas_graficas\clips\`.

## 1. Estado real HOY (qué funciona y qué falla)

| Pieza | Estado | Detalle |
|---|---|---|
| Electric Eye (EE) vive en | `C:\electric-eye` (no en D:) | El MCP `electric-eye` apunta a `C:\electric-eye\servidor\mcp.mjs`. D: no está montado: EE avisa "D no disponible" y guarda en `C:\electric-eye\salidas`. |
| Puente MCP (5175) | Activo | Lo sirve el MCP. Sin el editor abierto todas las herramientas responden "El editor de Electric Eye no está abierto". |
| Editor web (5174) | Hay que arrancarlo | `cd C:\electric-eye; set EE_SIN_NAVEGADOR=1; node servidor\iniciar.mjs` (equivale a `npm run iniciar` sin abrir el navegador). Comprobado que 5174 estaba libre. Tarda ~10 s. |
| Pestaña del editor | OBLIGATORIA, y en la pestaña "Editor del mapa" | Con la pestaña en "Escenarios" `ver_estado` sigue fallando. Si la pestaña navega a otra cosa (p. ej. un PNG local) se desconecta: abrir `http://127.0.0.1:5174/` y pulsar "Editor del mapa". Se hizo con el panel de navegador de la app (`mcp__Claude_Browser__navigate`). |
| Ride the Lightning (RTL) | Funciona por CLI; su MCP NO estaba expuesto en esta sesión | Se usa `node servidor\cli.mjs buscar\|bajar\|compilar\|vista\|render` desde `C:\Users\tante\Projects\Ride-the-Lightning`. Equivale al MCP. Datos de FRED bajan en ~4 s. |
| Entregables de EE | Solo MP4 H.264 (sin alfa) | Es un mapa opaco: no necesita alfa. |
| Entregables de RTL | MP4 + ProRes 4444 alfa (yuva444p12le) | `render` genera ambos (2 min 27 s para 9,6 s en final). |

Bugs de EE observados:
1. `configurar_estilo({estilo:"atlas"})` desde otro estilo => `Maximum call stack size exceeded` y la vista previa siguiente se cuelga 10 min ("el editor está ocupado"). Solución: recargar la pestaña, pulsar "Editor del mapa" (el proyecto persiste) y usar otro estilo (`minimal` funcionó). No se pudo volver a `atlas` en esa sesión.
2. El estilo `noche` sale casi negro, sin contraste: ilegible en reel. `minimal` y `atlas` leen bien. EE no ofrece la paleta MacroWise (fondo claro): el mapa es un plano de contexto, no una pieza de marca.
3. `anadir_elementos` pin: la etiqueta sale en la ficha del proyecto como `etiqueta` pero en la vista previa solo se veía el punto rojo hasta la 3.ª revisión; el rótulo de agua del pin chocó con un `texto` propio ("se pisan"). No duplicar rótulos.
4. La capa `rutas-maritimas` mete una leyenda ("Ruta principal / Ruta secundaria") a la izquierda que tapa nombres de ciudades (Abu Dabi). Se ocultó el rótulo con `ocultarRotulos`; mejor no usar la capa si la leyenda no aporta.
5. La línea "Fuentes: Natural Earth y otras" de EE cae a ~7 % del alto, DENTRO de la franja superior prohibida del perfil universal. No se puede mover; es texto tenue. Si se quiere limpio, tapar con el título o recortar al componer.

## 2. Mapa con Electric Eye (probado: Estrecho de Ormuz, 9:16, 10,8 s)

Pasos exactos (orden que EE obliga; `escribir_plan` es obligatorio antes de `nuevo_proyecto`):
1. Arrancar el editor (sección 1) y abrir `http://127.0.0.1:5174/` > pestaña "Editor del mapa". Comprobar con `ver_estado`.
2. `buscar_lugar` (nunca coordenadas de memoria). Ormuz: centro [56.45, 26.55].
3. `buscar_infraestructura({tipo:"estrechos", consulta:"Ormuz"})`: 34 km, fuente EIA (dominio público). Verificado contra eia.gov/todayinenergy/detail.php?id=32352: "At its narrowest point, the Strait of Hormuz is 21 miles wide" (21 mi = 33,8 km, redondeo a 34).
4. `escribir_plan` (4-6 líneas), `nuevo_proyecto({formato:"9:16", duracion, estilo, fuente, idioma:"es"})`; la `fuente` va en el proyecto, no en el rótulo.
5. `cambiar_formato({formato:"9:16", zonaSegura:"universal"})`.
6. `planos_de_camara` con `sujeto:["Estrecho de Ormuz"]` en cada plano: así EE centra el sujeto en y=760 de 1920 (40 %), dentro de la banda libre. Planos de 3-4 s (más largos: "pártelo").
7. `anadir_elementos` (titulo, pin, texto) y `anadir_capa`. Cada plano debe estrenar algo en su primer segundo.
8. `vista_previa({tiempos:[...]})` (un mapa para varios segundos) y mirar la imagen.
9. `revisar_proyecto` hasta "Sin fallos". Reglas que más tiempo costaron: lectura mínima 3 s en pantalla por texto (`fundido: 0.1` en `editar_elemento` lo arregla cuando los fundidos de 0,4 s se comen la lectura), ningún texto cruza un corte salvo `cruza:true`, sujeto en x 540±60 / y 760±80 (se arregla solo re-llamando `cambiar_formato`), un rótulo de agua no puede caer 19 % en tierra.
10. `estimar_render`, `exportar_video`, `esperar_render` (61 s reales con RTX 4050, GPU activa, estimado 56 s), `revisar_video` (1 página, 324 fotogramas) y `revisar_video({problemas:[...]})` (obligatorio para cerrar). Nota 10/10, saltos 0, hervor 0,31.

Tiempos medidos: puesta en marcha 12 s; construcción y revisión del proyecto ~25 llamadas (la parte lenta, por las reglas de lectura); render 61 s.

Salida: `C:\electric-eye\salidas\2026-11-05 · mw_prueba_mapa_ormuz\mw_prueba_mapa_ormuz · versión 1.mp4`.

Cifra rotulada: "34 km de ancho" con fuente EIA en la línea de fuentes del proyecto. Verificada.

### Plantilla de pedido EE (reutilizable)
```
Pieza de {8-10} s en vertical 9:16 (reel): {LUGAR}. {Receta de plantillas_de_pedido: ruta-comercial | ciudad | perfil-pais}.
Zona segura universal. Un título de 1-2 palabras, un pin en {LUGAR}, UNA cifra solo si viene de buscar_infraestructura o
dato_con_fuente (con su año). Fuente en nuevo_proyecto.fuente. Planos de 3-4 s con sujeto centrado. Revísalo y expórtalo.
```

## 3. Gráfica con Ride the Lightning (probado: desempleo EE. UU., vertical, 9,6 s)

Pasos exactos (CLI; el MCP hace lo mismo):
1. `node servidor\cli.mjs buscar desempleo` (o petroleo, inflacion...). Elegir serie con fuente y licencia compatibles (sección 5).
2. `node servidor\cli.mjs bajar fred_unrate` (944 filas, 1948-01 a 2026-09, ~2 s). Historia COMPLETA siempre.
3. Spec: `node _pruebas\agentes\mapas_graficas\gen_spec_rtl.mjs fred_unrate mw_prueba_unrate_v vertical "Desempleo en EE. UU." max,ultimo` (usa `generar` de RTL, plantilla "historia", cámara "dinamico"). Escribe `Ride-the-Lightning\specs\<nombre>.json`. La plantilla dinámica dura 16 s; para un clip de 9-10 s se escalaron por 0,6 todos los `t` y `mov` de la spec (RTL no lo marca como error).
4. `node servidor\cli.mjs compilar specs\mw_prueba_unrate_v.json`: lista cada cifra con serie, fecha y fila (14,80 % @ 2020-04, 4,20 % @ 2026-09).
5. `node servidor\cli.mjs vista specs\mw_prueba_unrate_v.json 0.8,3,5,7,9 --completa` (9 s): mirar los PNG.
6. `node servidor\cli.mjs render specs\mw_prueba_unrate_v.json` (final + alfa, 2 min 27 s). Salidas en `Ride-the-Lightning\salidas\mw_prueba_unrate_v\`.

Verificación de la cifra contra fuente oficial: API de BLS `https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000` => abril 2020 = 14,8; septiembre 2026 = 4,2. Coinciden con RTL (FRED UNRATE republica la serie del BLS).

Límites medidos: el lienzo vertical de RTL usa 6-97 % del alto (título a 6 %, fuente a 96 %): INVADE las zonas seguras. Por eso al componer va en `caja: "panel"` (se encoge a la banda libre). La spec admite `caja:[x,y,w,h]` por gráfica si se quiere un lienzo ya seguro. Con `fred_fedfunds` salta la escala logarítmica automática (variación 382x) y se ve peor: preferir series acotadas.

### Plantilla de pedido RTL
```
serie: {id del catálogo, estado de licencia ok}   plantilla: historia   formato: vertical   cámara: dinamico
momentos: max, ultimo   título: {nombre corto}   historia completa (sin recorte)
Comprobar: compilar_spec sin errores; cada cifra contra fuente oficial; vista previa de 5 instantes; render final + alfa.
```

## 4. Cartela "dato + fuente" (probado: 14,8 % desempleo, 8 s)

EE no hace cartelas sueltas y RTL solo con gráfica; las tarjetas de dato se hacen con `_pruebas\agentes\mapas_graficas\cartela_dato.py` (Pillow + ffmpeg, Geist, tarjeta opaca Warm Dark, oro, fuente en teal):
`python cartela_dato.py clips\cartela_X "14,8 %" "Desempleo en EE. UU." "abril de 2020 · máximo desde 1948" "Fuente: BLS · LNS14000000 · cons. 2026-11-05" 8` (24 s). Salida: ProRes 4444 con alfa (verificado con PIL: alfa 0-255, bbox x 11-78 %, y 26-44 %, dentro del perfil universal) + MP4 de referencia sobre Warm Black. Pendiente: pasarla a HyperFrames si se quiere la animación de marca.

## 5. Límites: licencias, series y qué NO hace cada herramienta

- Yahoo (`yf_*`) y Coin Metrics (`cm_*`, CC BY-NC): NO para contenido monetizado. BTC/ETH quedan sin serie libre (se marcan `bloqueado`).
- Licencia FRED = "ver términos de la serie": las de agencias de EE. UU. (BLS, BEA, Fed, EIA) son seguras; las de editores privados (Nasdaq, VIX) quedan `revisar`. Banco Mundial (Pink Sheet) = CC BY 4.0, con atribución. FMI: no automatizar sin permiso escrito.
- Series de país `pais_<ISO3>_*`: mostrar siempre el AÑO junto a la cifra.
- EE no calcula cifras: solo `dato_con_fuente` (Banco Mundial, Wikidata, EIA, R4V, ACNUR). Cualquier otra cifra la verifica el humano/agente y va en el pedido. La capa "Shipping lanes" exige crédito CC BY 4.0 (EE lo añade a la línea de fuentes).
- EE: sin alfa, sin paleta oscura MacroWise utilizable, un editor web que debe estar abierto; el modelo de "texto sin solapes" es estricto y exige iterar. RTL: sin mapas, sin cartela suelta, un render final de 2-3 min.
- Ninguna de las dos herramientas hace subtítulos: van aparte como pista editable.
- Los candidatos de detectar.py son pocos (`LUGARES`, `ACTIVOS` fijos): en `clip_raoul_75s.mp4` NO se detectó ningún lugar (habla de gestión de riesgo y del "data center de Real Vision"), y la transcripción del `clip_aztec_70s.mp4` no llegó a completarse (CPU, > 10 min). El mapa de prueba usa por tanto "Ormuz", que sí está en `LUGARES`, como candidato simulado; no es un lugar mencionado en esos clips.

## 6. Cómo componer con `python -m mw_editor componer`

`capas_externas.escribir_plan_capas(plan, listos, ruta, usar="clips"|"paneles")` escribe el plan; `componer.py` lee `plan["clips"]` (`t`, `dur`, `archivo`, `caja`) y `plan["paneles"]` (`t`, `dur`, `clip`, `caja`; dentro de la cápsula). Cajas (9:16): `full` 1080x1920; `panel` 864x960 centrada en y 25-75 %; `arriba` 864x691 desde 15 %. El clip se ajusta con `force_original_aspect_ratio=decrease`, así que un 9:16 en `panel` queda de 540x960: legible pero pequeño (se vio tapando la cara en la prueba).
Reglas: mapa y cartela => `full`; gráfica RTL => `panel`; no solapar clips (el módulo los descarta con aviso); la cartela ya viene con alfa (el MP4 de referencia la compone sobre el vídeo).
Prueba hecha: `python -m mw_editor componer --out _pruebas\agentes\mapas_graficas\proj_comp --plan _pruebas\agentes\mapas_graficas\plan_capas_prueba.json --formato vertical` (96 s para 30 s de base). Salida `proj_comp\06_EXPORT\prueba_vertical_v1_REFERENCIA.mp4` (subtítulos solo como ASS/SRT/ALFA aparte).

Flujo completo: `detectar.candidatos` => `capas_externas.pedidos_desde_candidatos(candidatos, dur_total)` => ejecutar cada pedido con su herramienta (sección 2/3/4) => `escribir_plan_capas(plan, listos, ruta)` => `componer`. Las cifras de las cartelas nacen `sin_verificar` y NO se ejecutan hasta rellenar `verificacion`.
