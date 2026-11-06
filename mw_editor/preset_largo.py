"""Preset «largo horizontal 16:9» derivado de MEDIR dos referencias reales (archivos, no solo captions):
UPSB «La tesis de Bitcoin…» (DR0pyraeIBU, 23:33) y Arte de Invertir «La gente no tiene ni idea…» (6-AzqY6KRWM, 23:12).
Cada cifra de RITMO viene de docs/investigacion/referencias_largo.md; los estilos se tradujeron a la paleta MacroWise
(no se copian marcas ni colores ajenos: el azul/amarillo de las referencias NO se usa)."""

RITMO = {
    # cambios visibles por minuto (cortes + gráficos que entran). Presentador solo se corta menos; los gráficos aportan el pulso.
    "cambios_por_min_objetivo": (4, 8),
    "plano_mediano_s": (4.5, 6.0),     # mediana de ambas referencias: 4,5 s y 5,9 s
    "plano_max_s": 45,                 # nadie se queda >45 s sin un cambio (gráfico, zoom o cambio de plano)
    "pico_de_apertura": "primer minuto con 8-12 cambios (gancho denso), luego cae a 1-3 y vuelve a subir al introducir cifras",
    "palabras_por_s": (3.1, 3.3),
    "pausas_largas_por_min": 0.5,      # casi no hay silencios: se recortan
    "cifras_por_min": (4, 12),
    "cta_max": 2,                      # patrocinio/suscripción: 1 a ~10 min y 1 al final, nunca en el gancho
}

TRANSICIONES = {
    "corte_seco": {"uso": "cambio de plano/ángulo del presentador y entrada de gráfico a pantalla completa", "peso": 0.8},
    "disolvencia_corta": {"dur_s": 0.15, "uso": "presentador → B-roll de rótulo (disolvencia con leve caída de luz)", "peso": 0.15},
    "pop_in_tarjeta": {"dur_s": 0.25, "uso": "tarjeta de gráfica sobre el hombro del presentador: escala 92→100 % + opacidad", "peso": 0.05},
    "regla": "una sola gramática de transición por video; prohibido whip, glitch, giro 3D, wipes de plantilla",
}

LETRAS_GRANDES = {
    "rotulo_b_roll": {"que": "frase corta (2-4 palabras) en mayúsculas sobre B-roll desenfocado + microetiqueta arriba", "fuente": "Geist Bold",
                      "tamano_pct_alto": 11, "entrada": "blur→nítido 0,35 s, sin rebote", "salida": "fundido 0,2 s", "dur_s": (2.0, 3.5)},
    "cifra_gigante": {"que": "cifra sola, grande, con etiqueta de 1 línea", "fuente": "Geist Mono Bold", "color": "gold #C9A84C (valor) / teal #50B5A2 (%)"},
    "limite": "máx. 1 rótulo grande cada ~25 s; sobre fondo Warm Black sólido o B-roll oscurecido (opaco), jamás glow ni neón",
}

SUBTITULOS_LARGO = {
    "estilo": "pildora_frase_clave",
    "que": "NO transcripción corrida. Frase de 2-4 palabras en píldora redondeada que apoya la idea; hasta 2 píldoras seguidas",
    "posicion": "tercio inferior, a la izquierda del presentador; no tapa cara ni manos; fuera de zona segura de interfaz",
    "fondo": "Warm Dark #232320 OPACO (las referencias usan azul traslúcido: no copiar, Premiere lo grisea)",
    "texto": "Stone Light #D6D1C8, Geist SemiBold, mayúsculas; palabra clave en lima #C6DD2E",
    "entrada": "deslizamiento 12 px + opacidad 0,2 s", "min_dur_s": 1.2,
    "master": "pista SRT/ASS editable aparte; las píldoras son capa gráfica (ProRes alfa) o ASS, nunca quemadas en el master",
}

GRAFICOS = {
    "tarjeta_hombro": "gráfica de línea en tarjeta oscura arriba-izquierda, ~35 % del ancho, con último valor resaltado (UPSB)",
    "pantalla_completa_oscura": "fondo casi negro, título arriba, 1 idea por pantalla, fuente al pie «Fuente: …, fecha» (ambas referencias)",
    "barras_comparativas": "dos barras que crecen en secuencia con cifra encima y descriptor al lado (Arte de Invertir)",
    "lista_numerada": "ítems 1…N con indicador de puntos y el ítem activo resaltado, resto atenuado (UPSB)",
    "linea_de_tiempo": "eje de fechas con marcador de hito (UPSB «El calendario»)",
    "termometro": "magnitud vs tope con 2 valores rotulados (UPSB techo de deuda)",
    "tinte_de_color": "tinte verde/rojo de todo el cuadro con velas animadas para subida/bajada (UPSB): usar teal/terracota de marca, mínimo 0,25 de opacidad",
    "regla": "cada gráfico rotula fuente y fecha; cifra sin fuente verificada = no sale (el motor ya lo exige)",
}

AUDIO = {"lufs": -14.0, "true_peak": -1.0,
         "nota": "Arte de Invertir sale a -12,3 LUFS con pico +0,3 dBTP (recorta); UPSB a -14,3. Nuestro objetivo -14/-1."}


def resumen():
    return {"ritmo": RITMO, "transiciones": TRANSICIONES, "letras_grandes": LETRAS_GRANDES, "subtitulos": SUBTITULOS_LARGO, "graficos": GRAFICOS, "audio": AUDIO}


def revisar_ritmo(tiempos_cambio, duracion):
    """Audita una lista de tiempos de cambio de plano de NUESTRO largo contra el preset. Devuelve avisos."""
    av = []
    t = sorted(tiempos_cambio)
    por_min = len(t) / (duracion / 60.0) if duracion else 0
    lo, hi = RITMO["cambios_por_min_objetivo"]
    if por_min < lo:
        av.append(f"ritmo bajo: {por_min:.1f} cambios/min (objetivo {lo}-{hi})")
    if por_min > hi * 1.6:
        av.append(f"ritmo excesivo: {por_min:.1f} cambios/min")
    huecos = [b - a for a, b in zip([0] + t, t + [duracion])]
    if huecos and max(huecos) > RITMO["plano_max_s"]:
        av.append(f"plano de {max(huecos):.0f} s sin cambio (máx {RITMO['plano_max_s']} s)")
    return av
