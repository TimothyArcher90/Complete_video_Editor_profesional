"""Producción masiva: de UN master (una persona / entrevista, 5-60 min) a un paquete publicable.

  master ──► proyecto LARGO (01_RAW copia) ─ editar horizontal ─► capítulos ─► miniatura 16:9 ─► 07_PUBLICAR youtube-largo / linkedin-horizontal
        └──► clips.puntuar (top-N ventanas) ─► N proyectos REEL (copia recortada en su 01_RAW) ─ editar 9:16 ─► portada 9:16 ─► 07_PUBLICAR instagram-reels / tiktok / youtube-shorts
  + 00_DOCS\\SIGUIENTE_PASO.md (lo que queda para Claude: copy, capas, mapas Electric Eye, gráficas Ride the Lightning)
El master NUNCA se modifica. Nada se publica ni se envía."""
import argparse
import json
import re
import shutil
import time
import traceback
from pathlib import Path

from . import clips as cl, capitulos as ca, exportar as ex
from .common import crear_proyecto, log, probe

EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}


def parse_brief(ruta):
    """brief.txt: líneas 'clave: valor'. Claves: titulo ('Línea 1|Línea 2'), tema, etiqueta, idioma, cta, nombre (persona, para el lower third),
    rol (cargo en el lower third), proyecto (nombre de la carpeta de salida), plataformas (lista separada por comas)."""
    d = {}
    if ruta and Path(ruta).exists():
        for ln in Path(ruta).read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if ":" in ln and not ln.strip().startswith("#"):
                k, v = ln.split(":", 1)
                d[k.strip().lower()] = v.strip()
    return d


def _slug(s):
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:40] or "pieza"


def _lista(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _plataformas(brief, cli):
    elegidas = cli or _lista(brief.get("plataformas"))
    if not elegidas:
        return list(ex.POR_TIPO["corto"]), list(ex.POR_TIPO["largo"])
    corto = [p for p in elegidas if p in ex.PERFILES and ex.PERFILES[p]["tipo"] in ("corto", "ambos")]
    largo = [p for p in elegidas if p in ex.PERFILES and ex.PERFILES[p]["tipo"] in ("largo", "ambos")]
    desconocidas = [p for p in elegidas if p not in ex.PERFILES]
    if desconocidas:
        log("AVISO: plataformas desconocidas ignoradas:", ", ".join(desconocidas))
    return corto, largo


def _cifras_detectadas(palabras, max_n=15):
    """Cifras dichas en el discurso (para verificar contra fuente oficial ANTES de rotularlas)."""
    out = []
    for i, w in enumerate(palabras):
        if re.search(r"\d", w["w"]) and not re.fullmatch(r"\W*\d{1,2}\W*", w["w"]):
            ctx = " ".join(x["w"] for x in palabras[max(0, i - 4):i + 5])
            out.append({"t": round(w["s"], 1), "contexto": ctx})
    return out[:max_n]


def crear_reel(master, c, k, nombre, raiz, palabras, brief, rapido, idioma, plataformas, estilo="visual"):
    """Un clip -> proyecto propio (copia recortada en 01_RAW) -> editar 9:16 -> QC -> exportar."""
    from .__main__ import cmd_editar
    from .qc import qc_proyecto, resumen_estado
    t0 = time.time()
    nom = f"{nombre}_reel{k:02d}"
    rp = crear_proyecto(nom, raiz=raiz)
    raw = rp / "01_RAW" / f"{nom}.mp4"
    cl.extraer(master, c["ini"], c["fin"], raw)
    trn = rp / "03_TRANSCRIPT"
    trn.mkdir(exist_ok=True)
    pc = cl.palabras_de_clip(palabras, c["ini"], c["fin"])
    (trn / "words.json").write_text(json.dumps(pc, ensure_ascii=False, indent=1), encoding="utf-8")
    (rp / "00_DOCS" / "clip.json").write_text(json.dumps({"master": str(master), "ini_en_master": c["ini"], "fin_en_master": c["fin"], "puntuacion": c["puntuacion"],
                                                          "componentes": c["componentes"], "motivo": c["motivo"], "gancho": c["gancho"], "texto": c["texto"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    cmd_editar(ex.ns_editar(raw, rp, nom, "vertical", idioma=idioma, rapido=rapido, estilo=estilo))
    try:
        qc = qc_proyecto(rp)
        estado = resumen_estado(qc)
    except Exception as e:  # noqa: BLE001
        estado = f"QC no corrió: {str(e)[:60]}"
    t_edit = time.time() - t0
    fichas = ex.exportar(rp, plataformas, rapido=rapido, cta=brief.get("cta", ""), idioma=idioma, tipo="corto") if plataformas else []
    return {"proyecto": str(rp), "reel": k, "ini": c["ini"], "fin": c["fin"], "dur": c["dur"], "puntuacion": c["puntuacion"], "gancho": c["gancho"], "qc": estado,
            "segundos_edicion": round(t_edit, 1), "segundos_total": round(time.time() - t0, 1), "publicar": [f["archivo_publicar"] for f in fichas]}


def produce(master, raiz=None, brief_path=None, nombre=None, n_reels=5, min_clip=20.0, max_clip=90.0, plataformas=None, rapido=True,
            idioma=None, sin_largo=False, sin_reels=False, min_cap=60.0):
    from .__main__ import cmd_editar
    from .qc import qc_proyecto, resumen_estado
    T = {}
    t_ini = time.time()
    raiz = str(Path(raiz).resolve()) if raiz else None
    master = Path(master).resolve()
    brief = parse_brief(brief_path)
    idioma = idioma or brief.get("idioma", "auto")
    nombre = nombre or brief.get("proyecto") or _slug(master.stem)
    corto, largo = _plataformas(brief, plataformas)
    proj = crear_proyecto(nombre, raiz=raiz)
    raw = proj / "01_RAW" / master.name
    if not raw.exists():
        shutil.copy2(master, raw)                     # el master queda intacto; 01_RAW tiene la copia
    info = probe(str(raw))
    log(f"produce: {master.name} ({info['duracion'] / 60:.1f} min) -> {proj}")
    manifiesto = {"master": str(master), "proyecto_largo": str(proj), "brief": brief, "plataformas_corto": corto, "plataformas_largo": largo,
                  "reels": [], "avisos": [], "tiempos_s": T}
    # ---- plan: lower third si el brief trae nombre ----
    plan_p = None
    if brief.get("nombre"):
        plan = {"lower_thirds": [{"t": 1.5, "dur": 5.0, "nombre": brief["nombre"], "rol": brief.get("rol", "")}]}
        plan_p = proj / "05_PROJECT" / "plan_auto.json"
        plan_p.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    # ---- (a) VIDEO LARGO ----
    t0 = time.time()
    trn = proj / "03_TRANSCRIPT"
    if not sin_largo:
        cmd_editar(ex.ns_editar(raw, proj, nombre, "horizontal", idioma=idioma, rapido=rapido, estilo="pildora", plan=str(plan_p) if plan_p else None))
        T["largo_editar_s"] = round(time.time() - t0, 1)
        try:                                       # rótulos grandes cada ~25 s (preset_largo); las cifras sin verificar las rechaza el motor
            from argparse import Namespace
            from . import plan_auto as pa
            from .__main__ import cmd_componer
            pal_f = json.loads((trn / "words_final.json").read_text(encoding="utf-8-sig"))
            b2 = dict(brief)
            b2.update({"sep_min": 25.0, "max_por_min": 3, "cifras_por_min": 4})
            pl_auto = pa.componer_plan(pal_f, "horizontal", b2)
            plan_p = proj / "05_PROJECT" / "plan_auto.json"
            plan_p.write_text(json.dumps(pl_auto, ensure_ascii=False, indent=1), encoding="utf-8")
            cmd_componer(Namespace(out=str(proj), plan=str(plan_p), formato="horizontal", version=str(ex._mejor_base(proj / "06_EXPORT", "horizontal")[1]), preview=False, estilo="pildora"))
            manifiesto["avisos"].append(f"largo: {len(pl_auto['titulos_grandes'])} rótulos grandes propuestos (revisar tono) y {len(pl_auto['cifras'])} cifras candidatas SIN verificar (no salen en pantalla)")
        except Exception as e:  # noqa: BLE001
            manifiesto["avisos"].append(f"plan automático del largo no corrió: {str(e)[:80]}")
    elif not sin_reels and not (trn / "words.json").exists():
        from . import transcribir as tr
        trn.mkdir(exist_ok=True)
        tr.transcribir(str(raw), trn / "words.json", idioma=idioma, modelo="small" if rapido else "medium")
        T["transcribir_s"] = round(time.time() - t0, 1)
    palabras = json.loads((trn / "words.json").read_text(encoding="utf-8-sig")) if (trn / "words.json").exists() else []
    if not sin_largo:
        t0 = time.time()
        base, n = ex._mejor_base(proj / "06_EXPORT", "horizontal")
        dur_f = probe(str(base))["duracion"]
        capj = ca.generar(trn / "words_final.json", dur_f, proj / "00_DOCS", min_cap=min_cap)
        manifiesto["capitulos"] = [f"{c['marca']} {c['titulo']}" for c in capj["capitulos"]]
        manifiesto["avisos"] += capj["avisos"]
        T["capitulos_s"] = round(time.time() - t0, 1)
        try:
            manifiesto["qc_largo"] = resumen_estado(qc_proyecto(proj))
        except Exception as e:  # noqa: BLE001
            manifiesto["qc_largo"] = f"QC no corrió: {str(e)[:60]}"
        t0 = time.time()
        fichas = ex.exportar(proj, largo, rapido=rapido, titulo=brief.get("titulo"), tema=brief.get("tema", "lima"), etiqueta=brief.get("etiqueta", "MACROWISE"),
                             cta=brief.get("cta", ""), idioma=idioma, estilo="minimo")
        manifiesto["publicar_largo"] = [f["archivo_publicar"] for f in fichas]
        T["largo_exportar_s"] = round(time.time() - t0, 1)
    # ---- (b) REELS ----
    if not sin_reels and palabras:
        t0 = time.time()
        sel = cl.puntuar(palabras, str(raw), dur=info["duracion"], n=n_reels, min_s=min_clip, max_s=max_clip)
        cl.guardar(sel, proj / "00_DOCS" / "clips.json")
        T["clips_seleccion_s"] = round(time.time() - t0, 1)
        if len(sel) < n_reels:
            manifiesto["avisos"].append(f"solo se encontraron {len(sel)} ventanas válidas de {min_clip:.0f}-{max_clip:.0f} s (pedidas {n_reels})")
        for k, c in enumerate(sel, 1):
            log(f"reel {k}/{len(sel)}: {c['ini']:.1f}-{c['fin']:.1f}s  puntuación {c['puntuacion']}")
            try:
                r = crear_reel(raw, c, k, nombre, raiz, palabras, brief, rapido, idioma, corto)
            except Exception:  # noqa: BLE001
                err = traceback.format_exc(limit=4)
                log(f"ERROR en reel {k}: {err.splitlines()[-1]}")
                r = {"reel": k, "error": err}
            manifiesto["reels"].append(r)
        T["reels_total_s"] = round(time.time() - t0, 1)
    elif not palabras and not sin_reels:
        manifiesto["avisos"].append("sin transcripción (¿sin audio?): no se pueden elegir reels")
    T["total_s"] = round(time.time() - t_ini, 1)
    (proj / "00_DOCS" / "produccion.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")
    _siguiente_paso(proj, nombre, brief, manifiesto, palabras)
    log(f"PRODUCCIÓN LISTA en {T['total_s'] / 60:.1f} min -> {proj}")
    return manifiesto


def _siguiente_paso(proj, nombre, brief, m, palabras):
    L = [f"# {nombre} — lo que queda (lo hace Claude)", "",
         f"Master: `{m['master']}` (intacto). Largo: `{m['proyecto_largo']}`.", ""]
    if m.get("avisos"):
        L += ["## Avisos de la producción"] + [f"- {a}" for a in m["avisos"]] + [""]
    L += ["## 1. Copy (rellenar `ficha_publicacion.json` de cada pieza)",
          "- Título, descripción, hashtags y cta en cada `07_PUBLICAR\\<plataforma>\\ficha_publicacion.json` (campos vacíos a propósito).",
          f"- CTA del brief: {brief.get('cta') or '(no hay: definir)'}",
          "- Reescribir los títulos provisionales de capítulos (`00_DOCS\\capitulos.json` + `capitulos_youtube.txt`): ahora son palabras clave del tramo."]
    if "capitulos" in m:
        L += ["", "Capítulos detectados:"] + [f"  - {c}" for c in m["capitulos"]]
    L += ["", "## 2. Miniaturas",
          ("- Largo: miniatura con el titular del brief ya generada." if brief.get("titulo") else "- Falta titular (brief sin `titulo`): las portadas salieron SIN TITULAR (`*_SIN-TITULAR.jpg`). Con el titular: `python -m mw_editor miniatura --video ... --titulo \"L1|L2\" --out ...\\06_EXPORT\\THUMBNAILS`."),
          "- Reels: portada 9:16 sin titular; poner un titular de ≤5 palabras por reel (gancho en `00_DOCS\\clip.json`).", ""]
    L += ["## 3. Plan de capas (skill macrowise-editor)",
          "- Leer `03_TRANSCRIPT\\transcript_final.txt` y `candidatos.json` de cada proyecto y escribir `05_PROJECT\\plan.json` (títulos, cifras con fuente, mapas, gráficas).",
          "- Luego `python -m mw_editor componer --out <proyecto> --plan <plan.json>` y re-exportar (`exportar`) para que el plan entre en 07_PUBLICAR.",
          "- **Mapas**: Electric Eye (geografía/rutas/frentes). **Gráficas animadas**: Ride the Lightning (series históricas, datos vivos). Tarjetas opacas, no semitransparentes.", ""]
    cif = _cifras_detectadas(palabras)
    if cif:
        L += ["## 4. Cifras dichas en el video (verificar contra fuente oficial ANTES de rotularlas)"]
        L += [f"- {c['t']} s: «{c['contexto']}»" for c in cif] + [""]
    L += ["## 5. Reels generados"]
    for r in m.get("reels", []):
        if r.get("error"):
            L.append(f"- Reel {r['reel']}: FALLÓ (ver produccion.json)")
        else:
            L.append(f"- Reel {r['reel']} ({r['ini']:.0f}-{r['fin']:.0f} s del master, puntuación {r['puntuacion']}, QC {r['qc']}): `{r['proyecto']}` — gancho: «{r['gancho'][:80]}»")
    L += ["", "## 6. Antes de publicar",
          "- Revisar ficha: `avisos` (cifras sin fuente, duración fuera de rango, LUFS). Nada se publicó ni se envió desde este flujo.",
          "- El master editable (ProRes 4444 alfa + SRT) está en `06_EXPORT`; `07_PUBLICAR` es solo entrega (subtítulos incrustados en IG/TikTok/Shorts/LinkedIn).",
          "- Si E: no estaba montado: `python -m mw_editor sync --estado` y luego `python -m mw_editor sync`."]
    (proj / "00_DOCS" / "SIGUIENTE_PASO.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------- CLI ----------
def registrar(sp):
    """Añade los subcomandos produce | clips | exportar | sync al parser de __main__."""
    p = sp.add_parser("produce", help="un master largo -> video largo + reels + 07_PUBLICAR")
    p.add_argument("master")
    p.add_argument("--raiz", help="raíz de salidas (por defecto E: o la carpeta pendiente)")
    p.add_argument("--brief", help="brief.txt: titulo, tema, etiqueta, idioma, cta, nombre, rol, proyecto, plataformas")
    p.add_argument("--nombre")
    p.add_argument("--reels", type=int, default=5)
    p.add_argument("--min-clip", type=float, default=20.0)
    p.add_argument("--max-clip", type=float, default=90.0)
    p.add_argument("--min-cap", type=float, default=60.0, help="duración mínima de un capítulo (s)")
    p.add_argument("--plataformas", help="lista separada por comas: " + ", ".join(ex.PERFILES))
    p.add_argument("--idioma")
    p.add_argument("--sin-largo", action="store_true")
    p.add_argument("--sin-reels", action="store_true")
    p.add_argument("--lento", action="store_true", help="calidad final (preset slow, Whisper medium)")
    c = sp.add_parser("clips", help="puntúa ventanas y devuelve el top-N (no renderiza salvo --procesar)")
    c.add_argument("master")
    c.add_argument("--out", required=True, help="carpeta donde escribir clips.json")
    c.add_argument("--words", help="words.json del master (si no, lo transcribe)")
    c.add_argument("--n", type=int, default=5)
    c.add_argument("--min", dest="min_s", type=float, default=20.0)
    c.add_argument("--max", dest="max_s", type=float, default=90.0)
    c.add_argument("--procesar", action="store_true", help="además crea un proyecto reel por clip (requiere --raiz)")
    c.add_argument("--raiz")
    c.add_argument("--nombre")
    c.add_argument("--idioma", default="auto")
    c.add_argument("--lento", action="store_true")
    e = sp.add_parser("exportar", help="genera 07_PUBLICAR\\<plataforma>\\ de un proyecto ya editado")
    e.add_argument("proyecto")
    e.add_argument("--plataformas")
    e.add_argument("--tipo", choices=["corto", "largo"], default="corto")
    e.add_argument("--titulo")
    e.add_argument("--tema", default="lima")
    e.add_argument("--etiqueta", default="MACROWISE")
    e.add_argument("--cta", default="")
    e.add_argument("--incrustar", action="store_true", help="quemar subtítulos también en las variantes largas")
    e.add_argument("--lento", action="store_true")
    s = sp.add_parser("sync", help="copia segura (sin borrar) de la carpeta pendiente a E:")
    s.add_argument("--estado", action="store_true", help="solo informa qué hay pendiente")
    s.add_argument("--simular", action="store_true")
    s.add_argument("--origen")
    s.add_argument("--destino")


def despachar(a):
    """Devuelve True si el comando era de producción."""
    if a.cmd == "produce":
        produce(a.master, raiz=a.raiz, brief_path=a.brief, nombre=a.nombre, n_reels=a.reels, min_clip=a.min_clip, max_clip=a.max_clip,
                plataformas=_lista(a.plataformas), rapido=not a.lento, idioma=a.idioma, sin_largo=a.sin_largo, sin_reels=a.sin_reels, min_cap=a.min_cap)
    elif a.cmd == "clips":
        from . import transcribir as tr
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        wp = Path(a.words) if a.words else out / "words.json"
        if not wp.exists():
            tr.transcribir(a.master, wp, idioma=a.idioma, modelo="medium" if a.lento else "small")
        palabras = json.loads(wp.read_text(encoding="utf-8-sig"))
        sel = cl.puntuar(palabras, a.master, dur=probe(a.master)["duracion"], n=a.n, min_s=a.min_s, max_s=a.max_s)
        cl.guardar(sel, out / "clips.json")
        for c in sel:
            log(f"#{c['rank']} {c['ini']:.1f}-{c['fin']:.1f}s ({c['dur']:.0f}s) {c['puntuacion']} — {c['motivo']}")
        if a.procesar:
            if not a.raiz:
                raise SystemExit("--procesar necesita --raiz")
            nombre = a.nombre or _slug(Path(a.master).stem)
            for k, c in enumerate(sel, 1):
                crear_reel(Path(a.master), c, k, nombre, a.raiz, palabras, {}, not a.lento, a.idioma, list(ex.POR_TIPO["corto"]))
    elif a.cmd == "exportar":
        ex.exportar(a.proyecto, _lista(a.plataformas) or None, rapido=not a.lento, quemar_largos=a.incrustar, titulo=a.titulo, tema=a.tema, etiqueta=a.etiqueta, cta=a.cta, tipo=a.tipo)
    elif a.cmd == "sync":
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
        from . import sync as sy
        if a.estado:
            r = sy.estado(a.origen, a.destino)
        else:
            r = sy.sincronizar(a.origen, a.destino, simular=a.simular)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        return False
    return True
