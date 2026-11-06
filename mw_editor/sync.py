"""Sincronización segura: carpeta PENDIENTE (C:) -> disco E: cuando esté montado.
Reglas: robocopy SIN /MIR ni /PURGE ni /MOV (nunca borra en origen ni en destino), /XO (no pisa lo más nuevo del destino),
/E (subcarpetas), reintentos cortos. El origen se queda intacto: se puede borrar a mano cuando David confirme.
`estado` compara por ruta relativa + tamaño y dice qué falta en E:."""
import json
import subprocess
import time
from pathlib import Path

from .common import log, RAIZ_E

PENDIENTE = Path(r"C:\Users\tante\Videos\MacroWise_pendiente_de_pasar_a_E")
# El pendiente replica la estructura de E:  <PENDIENTE>\Video con Ia editor\...  ->  E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\...
DESTINO = RAIZ_E.parent.parent   # E:\CARPETA OUTPUTS IA 2026


def e_montado(destino=None):
    d = Path(destino) if destino else DESTINO
    return d.parent.exists()      # existe E:\ (o la raíz equivalente)


def _archivos(raiz):
    raiz = Path(raiz)
    if not raiz.exists():
        return {}
    return {str(p.relative_to(raiz)): p.stat().st_size for p in raiz.rglob("*") if p.is_file() and not p.name.startswith(".sync_")}


def estado(origen=None, destino=None):
    origen, destino = Path(origen) if origen else PENDIENTE, Path(destino) if destino else DESTINO
    o = _archivos(origen)
    montado = e_montado(destino)
    d = _archivos(destino) if montado else {}
    faltan = {k: v for k, v in o.items() if d.get(k) != v}
    res = {"origen": str(origen), "destino": str(destino), "destino_montado": montado, "archivos_en_origen": len(o),
           "pendientes": len(faltan), "pendientes_gb": round(sum(faltan.values()) / 1e9, 3), "ejemplos": sorted(faltan)[:8]}
    if not o:
        res["resumen"] = "No hay nada pendiente: la carpeta de origen no existe o está vacía."
    elif not montado:
        res["resumen"] = f"E: NO está montado. Pendientes: {len(faltan)} archivos ({res['pendientes_gb']} GB). Conecta E: y corre `sync`."
    elif faltan:
        res["resumen"] = f"E: montado. Faltan {len(faltan)} archivos ({res['pendientes_gb']} GB) por copiar. Corre `sync`."
    else:
        res["resumen"] = "Todo lo pendiente ya está en E: (mismo tamaño). El origen se puede revisar y borrar a mano."
    return res


def sincronizar(origen=None, destino=None, simular=False):
    """Copia pendiente -> E:. Devuelve dict con código de robocopy y verificación posterior."""
    origen, destino = Path(origen) if origen else PENDIENTE, Path(destino) if destino else DESTINO
    if not origen.exists() or not any(origen.rglob("*")):
        return {"ok": True, "copiado": 0, "resumen": "Nada pendiente."}
    if not e_montado(destino):
        return {"ok": False, "resumen": "E: no está montado; no se copió nada."}
    destino.mkdir(parents=True, exist_ok=True)
    log_path = origen / ".sync_log.txt"
    # copia cada carpeta de primer nivel a su homónima en el destino; los archivos sueltos van a la raíz del destino
    hijos = [p for p in origen.iterdir() if not p.name.startswith(".sync_")]
    codigos = {}
    for h in hijos:
        if h.is_dir():
            cmd = ["robocopy", str(h), str(destino / h.name), "/E", "/XO", "/COPY:DAT", "/R:2", "/W:2", "/NP", "/NJH", "/NJS", "/NDL"]
        else:
            cmd = ["robocopy", str(origen), str(destino), h.name, "/XO", "/COPY:DAT", "/R:2", "/W:2", "/NP", "/NJH", "/NJS", "/NDL"]
        if simular:
            cmd.append("/L")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="cp850", errors="replace")
        codigos[h.name] = r.returncode          # robocopy: 0-7 éxito (bits: 1 copiado, 2 extra, 4 desajuste), >=8 error
    ok = all(c < 8 for c in codigos.values())
    ver = estado(origen, destino) if not simular else None
    res = {"ok": ok and (simular or ver["pendientes"] == 0), "codigos_robocopy": codigos, "verificacion": ver,
           "resumen": ("[SIMULACRO] " if simular else "") + ("Copia completa y verificada (ruta + tamaño). El origen NO se borró." if ok and ver and ver["pendientes"] == 0 else "Revisar: hay errores o archivos sin copiar.")}
    try:
        log_path.write_text(time.strftime("%Y-%m-%d %H:%M") + "\n" + json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return res
