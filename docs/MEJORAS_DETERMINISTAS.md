# Mejoras deterministas del motor (lecciones del Arca, 2026-11-08)

Principio: una corrección que David hizo a mano no se "recuerda"; se convierte en una **regla medible que corre sola en cada video**.
Estado: ✅ ya es código · 🔧 código parcial · ⏳ pendiente (con el paso exacto).

| # | Lección (qué falló en el Arca) | Regla determinista | Dónde vive | Estado |
|---|---|---|---|---|
| 1 | E: llegó a 0 GB y ffmpeg dejó un MP4 sin `moov` | Antes de producir: espacio libre ≥ 3 × (duración × bitrate) o ≥ 5 GB; si no, se detiene | `gates.preflight` (enganchada en `produce`) | ✅ |
| 2 | Versiones v1–v3 apiladas llenaron el disco | Se **propone** (nunca se borra) la lista de versiones viejas con MB | `gates.versiones_apiladas` | ✅ |
| 3 | 01_RAW intocable era solo una frase | Sello (tamaño + hash de extremos) al empezar y verificación al terminar; FAIL si cambia | `gates.sellar_raw / verificar_raw` (enganchada en `produce`) | ✅ |
| 4 | Infografías y títulos sobre la cara | Cada capa se mide contra la cara (YuNet) en el fotograma final; solape > 1 % = FAIL | `revisar_colisiones` + `gates.colisiones`; reubicación previa en `evitar_cara` | ✅ (falta engancharla en `produce` tras `componer`) |
| 5 | Sonoridad de la mezcla con música | −14 ±1,5 LUFS y pico ≤ −1 dBTP sobre el MP4 entregado, no sobre el stem | `gates.audio` | ✅ |
| 6 | Música: licencia verificada "por sitio", no por pista | Pista sin `licencia` permitida + `atribucion` = FAIL; sin `verificada_por_pista` = WARN visible; el crédito sale del catálogo | `gates.licencias` | 🔧 (hay que verificar las 4 pistas una a una y marcar `verificada_por_pista`) |
| 7 | El mensaje final cambia cada vez | `ENTREGA.md` siempre con: qué hice · rutas completas (con existencia y MB) · decisiones a revisar · qué quedó fuera | `gates.entrega` | ✅ |
| 8 | Las 3 variantes de color se veían iguales | Una variante solo cuenta si cambia ΔE medio ≥ umbral frente al original; si no, se declara "sin cambio perceptible" | `gates.delta_color` (ΔE76 del Lab medio, 10 fotogramas, umbral 2,3). Medido en el Arca: **ΔE 2,8** (L 44→42) = apenas por encima de lo perceptible; es estadístico (los cortes cambian el tiempo y las gráficas cuentan) | 🔧 |
| 16 | Contraste de tarjetas "a ojo" | Cada acento de marca sobre Warm Black/Dark ≥ 4,5:1 (WCAG). Medido: los 8 pares pasan (6,4–17,4:1) | `gates.paleta_legible`, `contraste_wcag` | ✅ |
| 9 | Encuadre: poco aire sobre la cabeza, cara enorme en reels | Medir `aire_sobre_cabeza` y `ancho_cara/ancho_cuadro` con YuNet; si cae fuera de [0,10–0,18] y [0,18–0,32] se recompone (zoom/relleno) o se avisa que la fuente no da más | `gates.encuadre` (mediana de 8 fotogramas, YuNet). Medido: largo 24 % aire / cara 14 % = PASS; reel tiempo_libre cara 47 % = WARN. Rangos ESTIMADOS (confianza media). **Salvedad:** los fotogramas con panel a pantalla completa distorsionan la mediana (reel anos_libertad); falta excluirlos con `plan.paneles` | 🔧 |
| 10 | Franja oscura abajo en reels | Detectar filas casi negras en el borde inferior > 6 % de la altura = WARN y rellenar con Warm Black sólido o subir el encuadre | `gates.encuadre` (filas oscuras **y** uniformes, luma < 34). Medido: tiempo_libre 7 % WARN; anos_libertad 27 % WARN (probable panel, mismo caso de la salvedad) | 🔧 |
| 11 | Subtítulos píldora existían pero no quedaron en el largo final | Si hay `*_subtitulos.ass` y el entregable es largo sin REFERENCIA, la píldora se quema o se declara "SRT aparte" en `ENTREGA.md` | ⏳ `componer.referencia` ya acepta ASS; falta decisión por defecto | ⏳ |
| 12 | Cifras del Arca eran "ejemplo del autor" | Toda cifra rotulada necesita `fuente` o la marca `ejemplo del autor`; si no, no se renderiza | `plan_auto` (ya rechaza sin verificar) | ✅ |
| 13 | Línea gráfica oficial (lima solo en miniaturas) | Paleta cerrada: oro/teal/púrpura/rojo coste; "lima" se mapea a oro salvo en miniatura | `subs._cm`, `color_marca` | ✅ |
| 14 | Procesos solapados rompen `.mov` | Candado de exportación por proyecto (`06_EXPORT/.exportando`); segundo proceso espera o aborta | `gates.candado`, enganchado en `exportar()`: un solo exportador por proyecto; candado huérfano caduca a las 6 h (no usa `os.kill(pid,0)`, que en Windows mata el proceso). Probado: el 2.º intento aborta y el candado se libera al salir | ✅ |
| 15 | Resultados que "se ven bien" sin medirse | Todo fix visual se prueba en fotogramas reales de ≥ 3 tipos de ropa/fondo | ⏳ banco de fotogramas de prueba en `_pruebas/banco/` | ⏳ |

## Orden de implementación esta noche
1. Enganchar 4 (colisiones) a `produce` y 7 (entrega) al final de `produce`.
2. 9 y 10 como puertas medibles (WARN si la fuente no da más).
3. 8 (ΔE de color) para dejar de entregar variantes idénticas.
4. 14 (candado de exportación).
5. 6: verificar las 4 pistas y marcarlas en `catalogo.json`.

## Uso
```
python -m mw_editor.gates preflight --destino "E:\..." --dur-min 11
python -m mw_editor.gates raw --proyecto P --sellar      # al empezar
python -m mw_editor.gates raw --proyecto P               # al terminar
python -m mw_editor.gates audio --video final.mp4
python -m mw_editor.gates colisiones --base base.mp4 --final final.mp4 --plan plan.json
python -m mw_editor.gates licencias --pistas windswept,easy_lemon
python -m mw_editor.gates versiones --proyecto P         # propuesta, no borra
```
