"""F3 Imagen: la cadena se decide por lo medido. ORDEN FIJO: denoise -> etalonaje (exposicion/color, mw_editor.color) -> (estabilizar) -> (upscale) -> nitidez suave.
Nunca afilar antes de limpiar. Altas luces quemadas y bitrate bajo de origen no se arreglan: se reportan.

El etalonaje (antes un `eq` de 8 bit) es ahora el pipeline de 8 pasos de color.py, con look de marca (warm_black por defecto) y dos niveles:
'calidad' (16 bit, origen <= 3 min) y 'rapido' (LUT 3D 33^3 horneada, origen largo). Parametros por camara en 00_DOCS/color.json."""
import os
from pathlib import Path


def _denoise(info):
    bitrate = (info or {}).get("bitrate", 0)
    fuerte = bool(bitrate and bitrate < 3_000_000)
    return ("hqdn3d=2.0:1.5:4:3" if fuerte else "hqdn3d=1.2:1.0:3:2.5"), \
        "denoise hqdn3d " + ("fuerte (bitrate de origen bajo)" if fuerte else "suave") + " - primero, antes de afilar"


def cadena(analisis_video, info, look=None, modo=None, ruta=None, proyecto=None, forzar=False, referencia=None, fuerza_look=1.0):
    """Devuelve (lista de filtros ffmpeg, lista de decisiones). El unsharp final sigue siendo el ULTIMO elemento (render.py lo separa como chain_post).
    look: warm_black (defecto) | stone_light | oro_editorial | teal_sutil | ninguno (o env MW_COLOR_LOOK).
    modo: 'calidad' | 'rapido' | None (auto por duracion; o env MW_COLOR_MODO).
    ruta/proyecto: origen y carpeta del proyecto; si no se pasan se toman de las variables `src`/`docs` de quien llama (cmd_editar)."""
    f, dec = [], []
    # 1) Denoise primero. Mas fuerte si el origen viene comprimido/ruidoso.
    d, txt = _denoise(info)
    f.append(d)
    dec.append(txt)
    # 2) Etalonaje (exposicion + color + look + salida legal). Cualquier fallo cae a la cadena minima, nunca rompe el render.
    from . import color
    docs = None
    if ruta is None:
        ruta, docs = color.contexto_del_llamador()
    if proyecto is not None:
        docs = Path(proyecto) / "00_DOCS"
    try:
        if ruta is None:
            raise RuntimeError("origen desconocido (cadena() llamada sin ruta ni contexto)")
        r = color.plan_color(ruta, docs=docs, duracion=(info or {}).get("duracion"), look=look, modo=modo,
                             fuerza_look=fuerza_look, referencia=referencia, forzar=forzar)
        f += r["filtros"]
        dec += r["decisiones"]
    except Exception as e:  # no rompe el render: look con parametros neutros, sin medicion
        dec.append(f"AVISO: etalonaje medido no disponible ({type(e).__name__}: {str(e)[:120]}); se aplica solo el look con parametros neutros")
        try:
            lk = look or os.environ.get("MW_COLOR_LOOK") or color.LOOK_DEFECTO
            prm = {"gamma": 1.0, "wb": [1.0, 1.0, 1.0], "rot_deg": 0.0, "sat_piel": 1.0}
            f += color.filtros_entrada() + color.nucleo(prm, None if lk == "ninguno" else lk) + color.filtros_salida()
        except Exception as e2:
            dec.append(f"AVISO: tampoco el look neutro ({e2}); sin etalonaje")
    # 3) Nitidez al final y suave (unsharp <= 0.6 para no crear halos)
    f.append("unsharp=5:5:0.45:5:5:0.0")
    dec.append("nitidez unsharp luma 0.45 (suave, sin halos)")
    return f, dec
