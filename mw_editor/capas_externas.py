"""Puente entre los CANDIDATOS de detectar.py y las herramientas externas (Electric Eye, Ride the Lightning).

Funciones puras (sin red, sin disco salvo `escribir_plan_capas`): convierten candidatos (lugares, activos, cifras) en PEDIDOS
estructurados que la skill/agente ejecuta con las herramientas reales, y escriben el plan 'clips'/'paneles' que
componer.py entiende (campos t, dur, archivo, caja en {full, panel, arriba}).

Reglas de la casa que se codifican aquí:
- Mapas SIEMPRE con Electric Eye; gráficas de series SIEMPRE con Ride the Lightning (RTL); datos con fuente y licencia.
- Yahoo y Coin Metrics NO sirven para contenido monetizado (marcados 'bloqueado').
- Una cifra rotulada es una afirmación de marca: el pedido nace 'sin_verificar' hasta que alguien la contraste con
  fuente oficial y rellene `verificacion`. Nada se inventa ni se omite en silencio (`avisos`).
Ver docs/investigacion/mapas_graficas_receta.md.
"""
import json
import re
from pathlib import Path

CANDIDATOS_VACIO = []

# --- mapas: qué receta de Electric Eye encaja con cada lugar ------------------------------------------------------
ESTRECHOS = {"Estrecho de Ormuz": "Ormuz", "Canal de Suez": "Suez", "Canal de Panamá": "Panamá", "Mar Rojo": "Bab el-Mandeb"}
PAISES = {"Estados Unidos", "China", "Japón", "Rusia", "Ucrania", "Alemania", "Francia", "España", "México", "Colombia", "Brasil", "Argentina",
          "Chile", "Perú", "Venezuela", "Panamá", "India", "Taiwán", "Corea", "Israel", "Irán", "Arabia Saudita", "Emiratos Árabes", "Turquía",
          "Reino Unido", "Suiza", "Singapur", "Canadá", "Australia"}
CIUDADES = {"Nueva York", "Londres", "Bogotá", "Silicon Valley"}

# --- gráficas: activo -> serie de RTL con licencia compatible o bloqueo explícito -----------------------------------
# estado: ok (dominio público / CC BY), revisar (editor privado o términos propios: confirmar antes de monetizar), bloqueado
SERIES_RTL = {
    "Petróleo": {"serie": "fred_wtisplc", "estado": "ok", "fuente": "FRED / EIA (WTI spot mensual)"},
    "Brent": {"serie": "fred_dcoilbrenteu", "estado": "ok", "fuente": "FRED / EIA (Brent spot diario)"},
    "Oro": {"serie": "bm_gold", "estado": "ok", "fuente": "Banco Mundial, Pink Sheet (CC BY 4.0)"},
    "Cobre": {"serie": "bm_copper", "estado": "ok", "fuente": "Banco Mundial, Pink Sheet (CC BY 4.0)"},
    "Inflación": {"serie": "fred_cpiaucsl", "estado": "ok", "fuente": "FRED / BLS (IPC EE. UU.)"},
    "Desempleo": {"serie": "fred_unrate", "estado": "ok", "fuente": "FRED / BLS (UNRATE)"},
    "Tasas Fed": {"serie": "fred_fedfunds", "estado": "ok", "fuente": "FRED / Junta de la Reserva Federal"},
    "Bonos del Tesoro": {"serie": "fred_dgs10", "estado": "ok", "fuente": "FRED / Junta de la Reserva Federal (10 años)"},
    "PIB": {"serie": "fred_gdp", "estado": "ok", "fuente": "FRED / BEA (PIB nominal EE. UU.)"},
    "Euro": {"serie": "fred_dexuseu", "estado": "ok", "fuente": "FRED / Junta de la Reserva Federal (US$ por euro)"},
    "Nasdaq": {"serie": "fred_nasdaqcom", "estado": "revisar", "fuente": "FRED (Nasdaq OMX Group: editor privado, confirmar términos)"},
    "S&P 500": {"serie": "sh_p", "estado": "revisar", "fuente": "Shiller (S&P Composite; citar a Shiller); yf_gspc está bloqueado"},
    "Dólar": {"serie": "fred_dexuseu", "estado": "revisar", "fuente": "No hay índice DXY libre; se propone US$ por euro"},
    "BTC": {"serie": None, "estado": "bloqueado", "fuente": "cm_btc_precio es CC BY-NC y yf_btc_usd es uso personal: no sirven para contenido monetizado"},
    "ETH": {"serie": None, "estado": "bloqueado", "fuente": "Sin serie libre verificada para uso comercial"},
}
EMPRESAS = {"NVIDIA", "Tesla", "Apple", "Microsoft", "Amazon", "Alphabet", "Meta"}  # trimestres: SEC por RTL (generar_trimestre), no series de precio

# Zona segura 'universal' (docs/investigacion/zonas_seguras.md): 14 % arriba, 35 % abajo, laterales 11,3 % / 22,4 %.
ZONA_UNIVERSAL = {"arriba": 0.14, "abajo": 0.35, "izquierda": 0.113, "derecha": 0.224}

# Qué caja de componer.py usa cada tipo de clip 9:16 (el clip llega a 1080x1920):
#   full  = el clip ya respeta la zona segura de origen (mapa EE con zona universal, cartela con alfa)
#   panel = el clip invade zonas (gráficas RTL de lienzo completo): componer lo encoge a la banda libre
CAJA_POR_TIPO = {"mapa": "full", "cartela": "full", "grafica": "panel"}
DURACION = {"mapa": 9.0, "grafica": 9.0, "cartela": 6.0}   # segundos por defecto; mapa 6-10, gráfica 8-12, cartela 5-8
PRESUPUESTO_MIN_SEPARACION = 0.4                            # hueco entre clips para que no se pisen


def _slug(txt):
    return re.sub(r"[^a-z0-9]+", "_", txt.lower().translate(str.maketrans("áéíóúñü", "aeiounu"))).strip("_")


def _agendar(items, dur_total=None, antelacion=0.4):
    """Asigna t/dur sin solapes. items: pedidos con 't_candidato' y 'dur'. Los que no caben se recortan (mín. 3 s) o se descartan con aviso."""
    avisos, out, libre = [], [], 0.0
    for it in sorted(items, key=lambda x: x["t_candidato"]):
        t = max(it["t_candidato"] - antelacion, libre)
        dur = it["dur"]
        if dur_total is not None:
            dur = min(dur, dur_total - t)
        if dur < 3.0:
            avisos.append(f"{it['id']}: sin hueco (empieza en {t:.1f} s, quedan {max(dur, 0):.1f} s): descartado")
            continue
        it = {**it, "t": round(t, 2), "dur": round(dur, 2)}
        out.append(it)
        libre = it["t"] + it["dur"] + PRESUPUESTO_MIN_SEPARACION
    return out, avisos


def pedidos_mapa(candidatos, formato="9:16", maximo=2):
    """Lugares -> pedidos para Electric Eye. Receta por tipo de lugar; un mapa por lugar distinto."""
    vistos, ped = set(), []
    for c in candidatos:
        if c.get("tipo") != "lugar" or c["texto"] in vistos:
            continue
        lugar = c["texto"]
        vistos.add(lugar)
        if lugar in ESTRECHOS:
            plantilla, objeto = "ruta-comercial", ESTRECHOS[lugar]
            texto = (f"Pieza de 10 s en vertical 9:16 (reel): {lugar}, cuello de botella. Rutas marítimas reales, el ancho con fuente (EIA, "
                     f"buscar_infraestructura) y un título corto. Revísalo y expórtalo.")
        elif lugar in CIUDADES:
            plantilla, objeto = "ciudad", lugar
            texto = f"Pieza de 8 s en 9:16: {lugar} en 3D (plano de ciudad), un pin y el título. Sin cifras."
        elif lugar in PAISES:
            plantilla, objeto = "perfil-pais", lugar
            texto = (f"Pieza de 9 s en 9:16: ficha de {lugar} (país resaltado, capital y vecinos). Cifras SOLO con dato_con_fuente "
                     f"(Banco Mundial / Wikidata) y su año.")
        else:
            plantilla, objeto = None, lugar
            texto = f"Pieza de 8 s en 9:16: mapa de {lugar} con buscar_lugar, un pin y el título."
        ped.append({
            "id": f"mapa_{_slug(lugar)}", "herramienta": "electric-eye", "tipo": "mapa", "lugar": lugar, "objeto": objeto,
            "plantilla": plantilla, "formato": formato, "zona_segura": "universal", "estilo_sugerido": "minimal",
            "pedido": texto, "pasos": ["escribir_plan", "nuevo_proyecto", "cambiar_formato(zonaSegura=universal)", "planos_de_camara",
                                       "anadir_elementos", "vista_previa", "revisar_proyecto", "exportar_video", "esperar_render", "revisar_video"],
            "dur": DURACION["mapa"], "t_candidato": c["t"], "caja": CAJA_POR_TIPO["mapa"],
            "cifras": "solo de buscar_infraestructura / dato_con_fuente; verificar contra la fuente antes de rotular",
            "salida_esperada": "MP4 H.264 (Electric Eye no exporta alfa; el mapa es opaco)",
        })
        if len(ped) >= maximo:
            break
    return ped


def pedidos_grafica(candidatos, formato="vertical", maximo=2):
    """Activos -> pedidos para Ride the Lightning con serie, licencia y estado. Los bloqueados no generan pedido ejecutable."""
    vistos, ped, avisos = set(), [], []
    for c in candidatos:
        if c.get("tipo") != "activo" or c["texto"] in vistos:
            continue
        act = c["texto"]
        vistos.add(act)
        if act in EMPRESAS:
            avisos.append(f"{act}: es una empresa; usa generar_trimestre de RTL (SEC) en vez de una serie de precio")
            continue
        info = SERIES_RTL.get(act)
        if not info:
            avisos.append(f"{act}: sin serie mapeada en SERIES_RTL; usa buscar_series de RTL y añade la entrada")
            continue
        if info["estado"] == "bloqueado":
            avisos.append(f"{act}: BLOQUEADO para contenido monetizado ({info['fuente']})")
            continue
        if info["estado"] == "revisar":
            avisos.append(f"{act}: licencia por revisar ({info['fuente']}); no publicar sin confirmarla")
        ped.append({
            "id": f"grafica_{_slug(act)}", "herramienta": "ride-the-lightning", "tipo": "grafica", "activo": act,
            "serie": info["serie"], "estado_licencia": info["estado"], "fuente": info["fuente"], "formato": formato,
            "plantilla": "historia", "camara": "dinamico", "momentos": ["max", "ultimo"], "tema": "oscuro",
            "pasos": ["buscar_series", "descargar_serie", "generar_pieza(historia, vertical, dinamico)", "compilar_spec",
                      "vista_previa", "verificar cada cifra contra la fuente oficial", "exportar_video (final + alfa)"],
            "dur": DURACION["grafica"], "t_candidato": c["t"], "caja": CAJA_POR_TIPO["grafica"],
            "salida_esperada": "MP4 + ProRes 4444 con alfa; el lienzo completo invade la zona segura, por eso caja=panel",
            "historia_completa": True,
        })
        if len(ped) >= maximo:
            break
    return ped, avisos


def pedidos_cartela(candidatos, maximo=2):
    """Cifras -> pedidos de cartela 'dato + fuente'. Nacen SIN VERIFICAR: nunca se rotula sin rellenar `verificacion`."""
    ped = []
    for c in candidatos:
        if c.get("tipo") != "cifra":
            continue
        ped.append({
            "id": f"cartela_{int(c['t'] * 10):05d}", "herramienta": "cartela_dato.py (Pillow+ffmpeg, ProRes 4444 alfa)", "tipo": "cartela",
            "contexto_hablado": c["texto"], "valor": None, "titulo": None, "periodo": None, "fuente": None,
            "estado": "sin_verificar",
            "verificacion": {"fuente_oficial": None, "url": None, "fecha_consulta": None, "valor_oficial": None},
            "accion": "Contrastar la cifra hablada con fuente oficial (API o web oficial); rellenar verificacion; si no se puede, preguntar a David",
            "dur": DURACION["cartela"], "t_candidato": c["t"], "caja": CAJA_POR_TIPO["cartela"],
        })
        if len(ped) >= maximo:
            break
    return ped


def pedidos_desde_candidatos(candidatos, dur_total=None, formato_ee="9:16", formato_rtl="vertical", maximo_por_tipo=2):
    """Entrada principal. Devuelve {'pedidos': [...agendados sin solape...], 'avisos': [...]}."""
    mapas = pedidos_mapa(candidatos, formato_ee, maximo_por_tipo)
    graficas, avisos = pedidos_grafica(candidatos, formato_rtl, maximo_por_tipo)
    cartelas = pedidos_cartela(candidatos, maximo_por_tipo)
    if not (mapas or graficas or cartelas):
        avisos.append("Sin candidatos aprovechables (lugares/activos/cifras): no se pide nada. Es un resultado válido, no un error.")
    agendados, av2 = _agendar(mapas + graficas + cartelas, dur_total)
    return {"pedidos": agendados, "avisos": avisos + av2}


def escribir_plan_capas(plan, listos, ruta=None, usar="clips"):
    """Devuelve (y opcionalmente escribe) el plan con los clips ya producidos.
    listos: [{'id'|'pedido'..., 'archivo': ruta, 't': s, 'dur': s, 'caja': 'full'|'panel'|'arriba'}]
    usar='clips'   -> plan['clips'] = [{t, dur, archivo, caja}] (componer los pone tal cual)
    usar='paneles' -> plan['paneles'] = [{t, dur, clip, caja}] (dentro de la cápsula Aztec Lab)
    Valida: archivo existente, dur > 0, caja válida, sin solapes entre clips. No toca otras claves del plan."""
    cajas_ok = {"full", "panel", "arriba"}
    plan = json.loads(json.dumps(plan))  # copia
    filas, avisos, fin_previo = [], [], -1.0
    for it in sorted(listos, key=lambda x: x["t"]):
        caja = it.get("caja", "panel")
        if caja not in cajas_ok:
            avisos.append(f"{it.get('id', it['archivo'])}: caja '{caja}' no válida; usa {sorted(cajas_ok)}")
            continue
        if it["dur"] <= 0 or not Path(it["archivo"]).exists():
            avisos.append(f"{it.get('id', it['archivo'])}: archivo inexistente o dur<=0; omitido")
            continue
        if it["t"] < fin_previo:
            avisos.append(f"{it.get('id', it['archivo'])}: se pisa con el clip anterior (t={it['t']} < {fin_previo}); omitido")
            continue
        fin_previo = it["t"] + it["dur"]
        if usar == "paneles":
            filas.append({"t": round(it["t"], 2), "dur": round(it["dur"], 2), "clip": str(it["archivo"]), "caja": caja})
        else:
            filas.append({"t": round(it["t"], 2), "dur": round(it["dur"], 2), "archivo": str(it["archivo"]), "caja": caja})
    plan["paneles" if usar == "paneles" else "clips"] = filas
    if ruta:
        Path(ruta).write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    return plan, avisos


def _prueba_rapida():
    cands = [
        {"t": 4.0, "tipo": "lugar", "texto": "Estrecho de Ormuz", "sugerencia": "mapa Electric Eye"},
        {"t": 6.0, "tipo": "activo", "texto": "Petróleo", "sugerencia": "gráfica"},
        {"t": 20.0, "tipo": "activo", "texto": "BTC", "sugerencia": "gráfica"},
        {"t": 22.0, "tipo": "cifra", "texto": "3 % de mi portafolio", "sugerencia": "tarjeta"},
        {"t": 40.0, "tipo": "lugar", "texto": "Taiwán", "sugerencia": "mapa"},
    ]
    r = pedidos_desde_candidatos(cands, dur_total=60)
    ids = [p["id"] for p in r["pedidos"]]
    assert "mapa_estrecho_de_ormuz" in ids and "grafica_petroleo" in ids and "cartela_00220" in ids, ids
    assert not any(p.get("activo") == "BTC" for p in r["pedidos"]), "BTC debe estar bloqueado"
    assert any("BLOQUEADO" in a for a in r["avisos"]), r["avisos"]
    ts = [(p["t"], p["t"] + p["dur"]) for p in r["pedidos"]]
    assert all(a[1] <= b[0] for a, b in zip(ts, ts[1:])), f"solapes: {ts}"
    ped_c = next(p for p in r["pedidos"] if p["tipo"] == "cartela")
    assert ped_c["estado"] == "sin_verificar"
    assert pedidos_desde_candidatos([])["pedidos"] == []
    f = Path(__file__)  # archivo que existe seguro
    plan, av = escribir_plan_capas({"cifras": []}, [{"id": "x", "archivo": str(f), "t": 1, "dur": 5, "caja": "full"},
                                                     {"id": "y", "archivo": str(f), "t": 3, "dur": 5, "caja": "panel"},
                                                     {"id": "z", "archivo": "no_existe.mp4", "t": 20, "dur": 5}])
    assert len(plan["clips"]) == 1 and len(av) == 2 and plan["cifras"] == [], (plan, av)
    print("capas_externas: prueba rapida OK", ids)


if __name__ == "__main__":
    _prueba_rapida()
