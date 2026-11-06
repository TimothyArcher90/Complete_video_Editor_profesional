"""Variantes de ENTREGA por plataforma: 07_PUBLICAR\\<plataforma>\\ con códec/bitrate/fps/audio según docs/investigacion/plataformas_metricas.md
y zonas_seguras.md. Cada pieza lleva su portada y su ficha_publicacion.json (título/descripción/hashtags/cta vacíos: los rellena el copy).

SEPARACIÓN CLARA:
  06_EXPORT   = MASTER EDITABLE (ProRes 4444 con alfa de subtítulos/gráficos + SRT + base + referencia). Aquí los subtítulos son pista.
  07_PUBLICAR = ENTREGA. Para Instagram, TikTok, Shorts y LinkedIn los subtítulos van INCRUSTADOS (esas redes no importan SRT).
                YouTube largo y LinkedIn horizontal llevan el SRT al lado y NO quemados.
Nada se sobrescribe: v1, v2, v3 ... Si se pide un formato que aún no existe (4:5, 1:1), se renderiza bajo demanda."""
import datetime as _dt
import json
import re
import shutil
import time
from argparse import Namespace
from pathlib import Path

from .common import BRAND, FFMPEG, log, probe, run

# fuente: docs/investigacion/plataformas_metricas.md (sec. 2, 4, 5, 6) y zonas_seguras.md (sec. 2). "conf" = confianza de la cifra.
PERFILES = {
    "instagram-reels": dict(formato="vertical", w=1080, h=1920, tipo="corto", fps_max=30, mbps=8, abr=192, incrustar=True, max_dur=180,
                            max_mb=4000, conf="terceros", nota="Instagram recodifica siempre; 1080x1920, 30 fps, H.264/AAC 48 kHz. Reels hasta 3 min (verificar en la app: blogs citan 20 min)."),
    "tiktok": dict(formato="vertical", w=1080, h=1920, tipo="corto", fps_max=30, mbps=8, abr=192, incrustar=True, max_dur=600,
                   max_mb=500, conf="terceros", nota="TikTok recomprime; 1080x1920, H.264/AAC, 30 fps. Sin importación de SRT: subtítulos incrustados. Tope de duración en app por verificar."),
    "youtube-shorts": dict(formato="vertical", w=1080, h=1920, tipo="corto", fps_max=30, mbps=8, abr=384, incrustar=True, max_dur=180,
                           max_mb=4000, conf="oficial (codificación) / terceros (duración)", cgop=True, nota="YouTube: H.264 High, GOP cerrado = fps/2, 2 B-frames, AAC-LC 48 kHz 384 kbps. Short <= 3 min (vertical 9:16)."),
    "linkedin-vertical": dict(formato="4x5", w=1080, h=1350, tipo="ambos", fps_max=29.97, mbps=8, abr=192, incrustar=True, max_dur=600,
                              max_mb=500, conf="oficial (relaciones/peso/fps) / estimado (bitrate)", nota="LinkedIn: 4:5 es su relación vertical recomendada (máx. 1080x1350), <30 fps, MP4 H.264, 500 MB, no acepta ProRes. 9:16 es solo móvil."),
    "linkedin-cuadrado": dict(formato="cuadrado", w=1080, h=1080, tipo="ambos", fps_max=29.97, mbps=8, abr=192, incrustar=True, max_dur=600,
                              max_mb=500, conf="oficial (relaciones/peso/fps) / estimado (bitrate)", nota="LinkedIn 1:1 hasta 1920x1920; se entrega 1080x1080, <30 fps, MP4 H.264."),
    "youtube-largo": dict(formato="horizontal", w=1920, h=1080, tipo="largo", fps_max=60, mbps=8, abr=384, incrustar=False, max_dur=43200,
                          max_mb=256000, conf="oficial", cgop=True, capitulos=True, srt=True, nota="Ajustes de codificación de YouTube (Help 1722171): 1080p SDR 8 Mbps (<=30 fps) / 12 Mbps (>30), GOP cerrado fps/2, BT.709, faststart. SRT aparte; capítulos en la descripción y en el MP4."),
    "linkedin-horizontal": dict(formato="horizontal", w=1920, h=1080, tipo="largo", fps_max=29.97, mbps=8, abr=192, incrustar=False, max_dur=1800,
                                max_mb=500, conf="oficial (relaciones/peso/fps) / estimado (bitrate)", srt=True, nota="LinkedIn 16:9 1920x1080, <30 fps, MP4 H.264, 500 MB, hasta 30 min. SRT aparte (verificar en la app; algunos recomiendan quemar para autoplay mudo: usar --incrustar)."),
}
POR_TIPO = {"corto": ["instagram-reels", "tiktok", "youtube-shorts"], "largo": ["youtube-largo", "linkedin-horizontal"]}
TAMS = {"vertical": (1080, 1920), "4x5": (1080, 1350), "cuadrado": (1080, 1080), "horizontal": (1920, 1080)}


def _fecha_y_nombre(proj):
    proj = Path(proj)
    f = proj.parent.name if re.fullmatch(r"\d{2}-\d{2}-\d{4}", proj.parent.name) else _dt.date.today().strftime("%d-%m-%Y")
    return f, proj.name


def _mejor_base(exp, fm):
    bases = sorted(exp.glob(f"*_{fm}_v*_base.mp4"), key=lambda p: int(re.search(r"_v(\d+)_base", p.name).group(1)))
    if not bases:
        return None, None
    return bases[-1], int(re.search(r"_v(\d+)_base", bases[-1].name).group(1))


def ns_editar(video, out, nombre, formato, idioma="auto", rapido=True, estilo="visual", plan=None, preview=False, modelo="medium", rehacer=False, zoom=1.12):
    return Namespace(video=str(video), out=str(out), nombre=nombre, formato=formato, idioma=idioma, modelo=modelo, plan=plan, sin_cortes=False,
                     pausa_max=0.45, toma=3.6, zoom=zoom, luz=1.0, sin_luz=False, estilo=estilo, rehacer=rehacer, preview=preview, progreso=False, rapido=rapido, zona="universal")


def asegurar_formato(proj, fm, rapido=True, estilo="visual", idioma="auto"):
    """Devuelve (base, n) del formato; si no existe lo renderiza reusando análisis y transcripción (cmd_editar)."""
    proj = Path(proj)
    exp = proj / "06_EXPORT"
    base, n = _mejor_base(exp, fm)
    if base:
        return base, n
    from .__main__ import cmd_editar
    raws = sorted((proj / "01_RAW").glob("*"))
    raws = [r for r in raws if r.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v", ".webm")]
    if not raws:
        raise RuntimeError(f"{proj}: no hay video en 01_RAW para renderizar el formato {fm}")
    plan = next((str(p) for p in (proj / "05_PROJECT" / "plan.json", proj / "05_PROJECT" / "plan_auto.json") if p.exists()), None)
    log(f"exportar: renderizando formato {fm} bajo demanda ...")
    cmd_editar(ns_editar(raws[0], proj, proj.name, fm, idioma=idioma, rapido=rapido, estilo=estilo, plan=plan))
    return _mejor_base(exp, fm)


# ---------- portada ----------
def portada(proj, fm, titulo=None, tema="lima", etiqueta="MACROWISE"):
    """Portada del formato. Con titular -> miniatura de marca (miniatura.py); sin titular -> mejor fotograma limpio, marcado como PENDIENTE de titular."""
    import cv2
    proj = Path(proj)
    exp = proj / "06_EXPORT"
    th = exp / "THUMBNAILS"
    th.mkdir(parents=True, exist_ok=True)
    W, H = TAMS[fm]
    if titulo and fm in ("vertical", "horizontal"):
        destino = th / f"thumb_A_impacto_{fm}.jpg"
        if not destino.exists():
            from . import miniatura as mi
            raw = next(r for r in sorted((proj / "01_RAW").glob("*")) if r.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v", ".webm"))
            l = (titulo.split("|") + [""])[:2]
            try:
                mi.generar(video=str(raw), titulo=(l[0].strip(), l[1].strip()), tema=tema, etiqueta=etiqueta, carpeta=th, dur=probe(str(raw))["duracion"])
            except Exception as e:  # noqa: BLE001
                log("AVISO: miniatura con titular falló:", str(e)[:120])
        if destino.exists():
            return destino, False
    destino = th / f"thumb_portada_sin_titular_{fm}.jpg"
    if destino.exists():
        return destino, True
    base, _ = _mejor_base(exp, fm)
    if base is None:
        return None, True
    dur = probe(str(base))["duracion"]
    from . import miniatura as mi
    try:
        _, img, _ = mi.elegir_frame(base, dur, n=24)
    except Exception:  # noqa: BLE001
        from .miniatura import _frame
        img = _frame(base, dur / 2, W)
    if img is None:
        return None, True
    h0, w0 = img.shape[:2]
    esc = max(W / w0, H / h0)
    img = cv2.resize(img, (int(w0 * esc) + 1, int(h0 * esc) + 1), interpolation=cv2.INTER_LANCZOS4)
    y0, x0 = (img.shape[0] - H) // 2, (img.shape[1] - W) // 2
    cv2.imwrite(str(destino), img[y0:y0 + H, x0:x0 + W], [cv2.IMWRITE_JPEG_QUALITY, 95])
    return destino, True


# ---------- codificación ----------
def _fps_destino(fps_src, fps_max):
    if fps_src <= fps_max + 0.01:
        return fps_src
    return fps_max if fps_max != 29.97 else 30000 / 1001


def _verificar(ruta, perfil):
    from .qc import _lufs
    i = probe(str(ruta))
    lufs, tp = _lufs(ruta)
    mb = Path(ruta).stat().st_size / 1e6
    kbps = round(mb * 8000 / max(i["duracion"], 0.1))
    av = []
    if (i.get("ancho"), i.get("alto")) != (perfil["w"], perfil["h"]):
        av.append(f"resolución {i.get('ancho')}x{i.get('alto')} ≠ {perfil['w']}x{perfil['h']}")
    if i["duracion"] > perfil["max_dur"]:
        av.append(f"dura {i['duracion']:.0f} s y el máximo de la plataforma es {perfil['max_dur']} s")
    if mb > perfil["max_mb"]:
        av.append(f"pesa {mb:.0f} MB y el máximo es {perfil['max_mb']} MB")
    if perfil["fps_max"] < 30 and i["fps"] >= 30.0:
        av.append(f"{i['fps']} fps: LinkedIn pide menos de 30")
    if lufs is not None and abs(lufs + 14) > 1.5:
        av.append(f"loudness {lufs:.1f} LUFS fuera de -14±1.5")
    return {"codec": i.get("codec"), "ancho": i.get("ancho"), "alto": i.get("alto"), "fps": i.get("fps"), "duracion": round(i["duracion"], 2),
            "bitrate_total_kbps": kbps, "tamano_mb": round(mb, 1), "audio_codec": i.get("audio_codec"), "audio_hz": i.get("audio_hz"),
            "lufs": None if lufs is None else round(lufs, 1), "true_peak_dbtp": None if tp is None else round(tp, 1)}, av


def _codificar(entrada, salida, perfil, fps_src, rapido, ffmeta=None):
    fps = _fps_destino(fps_src, perfil["fps_max"])
    fps_txt = "30000/1001" if abs(fps - 29.97) < 0.01 else (f"{fps:g}")
    gop = max(1, int(round(fps / 2))) if perfil.get("cgop") else int(round(fps * 2))
    br = perfil["mbps"] * (1.5 if fps > 30.5 else 1.0)
    cmd = [FFMPEG, "-hide_banner", "-y", "-v", "error", "-i", str(entrada)]
    if ffmeta:
        cmd += ["-i", str(ffmeta)]
    cmd += ["-map", "0:v:0", "-map", "0:a:0?", "-vf", f"scale={perfil['w']}:{perfil['h']}:flags=lanczos,fps={fps_txt},format=yuv420p,setsar=1",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "veryfast" if rapido else "slow", "-b:v", f"{br:g}M", "-maxrate", f"{br * 1.5:g}M", "-bufsize", f"{br * 2:g}M",
            "-g", str(gop), "-bf", "2", "-sc_threshold", "0"]
    if perfil.get("cgop"):
        cmd += ["-flags", "+cgop"]
    cmd += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-c:a", "aac", "-b:a", f"{perfil['abr']}k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]
    if ffmeta:
        cmd += ["-map_metadata", "1", "-map_chapters", "1"]
    cmd += [str(salida)]
    run(cmd)
    return fps


def _intermedio(proj, fm, n, base, quemar, tmp):
    """Base + gráficos/paneles/clips del plan (+ subtítulos quemados si `quemar`). Si no hace falta nada, es la propia base."""
    from . import componer as co
    exp = Path(proj) / "06_EXPORT"
    ass = next(iter(sorted(exp.glob(f"*_{fm}_v{n}_subtitulos.ass"))), None)
    graf = next(iter(sorted(exp.glob(f"*_{fm}_v{n}_graficos_ALFA.mov"))), None)
    plan_p = next((p for p in (Path(proj) / "05_PROJECT" / "plan.json", Path(proj) / "05_PROJECT" / "plan_auto.json") if p.exists()), None)
    plan = json.loads(plan_p.read_text(encoding="utf-8-sig")) if plan_p else {}
    hay_capas = bool(graf) or bool(plan.get("paneles")) or bool(plan.get("clips"))
    if not quemar and not hay_capas:
        return base, False
    if quemar and not ass:
        log("AVISO: no hay .ass para incrustar; se entrega sin subtítulos")
        quemar = False
        if not hay_capas:
            return base, False
    out = Path(tmp) / f"inter_{fm}_v{n}_{'subs' if quemar else 'capas'}.mp4"
    tmp.mkdir(parents=True, exist_ok=True)
    co.referencia(str(base), dict(plan), fm, None, str(graf) if graf else None, None, str(out), tmp, preview_burned_ass=str(ass) if quemar else None)
    return out, quemar


def _manifiesto_ia(proj):
    proj = Path(proj)
    rep = proj / "00_DOCS" / "reparacion.json"
    dec_img, dec_aud = [], []
    if rep.exists():
        try:
            j = json.loads(rep.read_text(encoding="utf-8-sig"))
            dec_img = j.get("imagen") or []
            dec_aud = (j.get("audio") or {}).get("decisiones") or []
        except Exception:  # noqa: BLE001
            pass
    txt = " ".join(map(str, dec_img + dec_aud)).lower()
    return {
        "mejora_de_imagen_propia": {"aplicada": bool(dec_img), "decisiones": dec_img, "upscaling": "upscal" in txt or "escal" in txt},
        "mejora_de_audio_propia": {"aplicada": bool(dec_aud), "decisiones": dec_aud},
        "restauracion_facial": False, "ia_generativa_video_o_imagen": False, "voz_sintetica_o_clonada": False, "persona_alterada_o_sintetica": False,
        "transcripcion_automatica": "Whisper local (faster-whisper); solo para subtítulos y búsqueda de ganchos",
        "luz_de_estudio": "máscara elíptica fija + corrección de exposición (no generativa)",
        "requiere_declaracion_ia": False,
        "base": "docs/investigacion/plataformas_metricas.md sec. 7: YouTube exime sharpening, upscaling, reparación de audio/video, color, subtítulos; la declaración aplica a personas/hechos realistas alterados o sintéticos. Revisar si se añade IA generativa después.",
    }


def exportar(proj, plataformas=None, rapido=True, quemar_largos=False, titulo=None, tema="lima", etiqueta="MACROWISE", estilo="visual", cta="", idioma="auto", tipo=None):
    """Genera 07_PUBLICAR\\<plataforma>\\ para el proyecto. Devuelve la lista de fichas escritas."""
    proj = Path(proj).resolve()
    exp = proj / "06_EXPORT"
    pub = proj / "07_PUBLICAR"
    pub.mkdir(exist_ok=True)
    fecha, nombre = _fecha_y_nombre(proj)
    if not plataformas:
        plataformas = POR_TIPO[tipo or "corto"]
    caps = None
    cj = proj / "00_DOCS" / "capitulos.json"
    if cj.exists():
        caps = json.loads(cj.read_text(encoding="utf-8"))
    hechos = []
    for pl in plataformas:
        if pl not in PERFILES:
            log(f"AVISO: plataforma desconocida '{pl}' (usa {', '.join(PERFILES)})")
            continue
        perf = PERFILES[pl]
        t0 = time.time()
        fm = perf["formato"]
        base, n = asegurar_formato(proj, fm, rapido=rapido, estilo=estilo, idioma=idioma)
        if base is None:
            log(f"AVISO: sin base {fm}; se omite {pl}")
            continue
        incr = perf["incrustar"] or (quemar_largos and perf["tipo"] == "largo")
        carpeta = pub / pl
        carpeta.mkdir(exist_ok=True)
        v = 1
        while (carpeta / f"{fecha}_{nombre}_{pl}_v{v}.mp4").exists():
            v += 1
        stem = f"{fecha}_{nombre}_{pl}_v{v}"
        tmp = pub / "_tmp"
        inter, quemado = _intermedio(proj, fm, n, base, incr, tmp)
        ffmeta = None
        if perf.get("capitulos") and caps and caps.get("capitulos") and caps.get("cumple_youtube"):
            ffmeta = proj / "00_DOCS" / "capitulos.ffmetadata"
        salida = carpeta / f"{stem}.mp4"
        fps_src = probe(str(base))["fps"]
        fps = _codificar(inter, salida, perf, fps_src, rapido, ffmeta=ffmeta if ffmeta and ffmeta.exists() else None)
        ver, avisos = _verificar(salida, perf)
        srt_dest = None
        if perf.get("srt") and not quemado:
            srt = next(iter(sorted(exp.glob("*_subtitulos.srt"), key=lambda p: p.stat().st_mtime, reverse=True)), None)
            if srt:
                srt_dest = carpeta / f"{stem}.srt"
                shutil.copy2(srt, srt_dest)
        pj, sin_titular = portada(proj, fm, titulo=titulo, tema=tema, etiqueta=etiqueta)
        pj_dest = None
        if pj:
            pj_dest = carpeta / f"{stem}_portada{'_SIN-TITULAR' if sin_titular else ''}.jpg"
            shutil.copy2(pj, pj_dest)
        if perf.get("capitulos") and caps:
            shutil.copy2(proj / "00_DOCS" / "capitulos_youtube.txt", carpeta / f"{stem}_capitulos_para_descripcion.txt")
        # zona segura usada
        zona = {"perfil": "universal" if fm == "vertical" else "provisional (ver zonas_seguras.md)", "formato": fm}
        try:
            from . import zonas
            x0, y0, x1, y1 = zonas.caja_segura_px(fm)
            zona.update({"caja_segura_px": [round(x0), round(y0), round(x1), round(y1)], "preset": zonas.preset() if fm == "vertical" else None})
        except Exception as e:  # noqa: BLE001
            zona["aviso"] = f"no se pudo leer zonas.py: {str(e)[:60]}"
        # cifras sin fuente (regla de marca)
        plan_p = next((p for p in (proj / "05_PROJECT" / "plan.json", proj / "05_PROJECT" / "plan_auto.json") if p.exists()), None)
        cifras = (json.loads(plan_p.read_text(encoding="utf-8-sig")).get("cifras") or []) if plan_p else []
        sin_fuente = [c for c in cifras if not (c.get("fuente") and c.get("verificada"))]
        if sin_fuente:
            avisos.append(f"{len(sin_fuente)} cifra(s) rotulada(s) sin fuente verificada: no publicar hasta verificar")
        qcj = proj / "00_DOCS" / "qc.json"
        if qcj.exists():
            try:
                q = json.loads(qcj.read_text(encoding="utf-8-sig"))
                fallos = [f"QC FAIL {k}: {c['check']}" for k, v in q.items() for c in v if c.get("estado") == "FAIL" and k in (fm, "proyecto")]
                avisos += fallos
            except Exception:  # noqa: BLE001
                pass
        masters = sorted(str(p) for p in exp.glob("*_ALFA.mov")) + sorted(str(p) for p in exp.glob("*_subtitulos.srt"))
        ficha = {
            "pieza": nombre, "fecha": fecha, "plataforma": pl, "version": v, "estado": "pendiente_de_copy",
            "titulo": "", "descripcion": "", "hashtags": [], "cta": cta or "",
            "archivo_publicar": str(salida), "portada": str(pj_dest) if pj_dest else None, "portada_pendiente_titular": bool(sin_titular),
            "duracion_s": ver["duracion"], "formato": {"relacion": fm, "ancho": ver["ancho"], "alto": ver["alto"], "fps": ver["fps"], "codec": ver["codec"],
                                                       "bitrate_total_kbps": ver["bitrate_total_kbps"], "tamano_mb": ver["tamano_mb"]},
            "audio": {"codec": ver["audio_codec"], "hz": ver["audio_hz"], "lufs": ver["lufs"], "true_peak_dbtp": ver["true_peak_dbtp"]},
            "subtitulos": {"incrustados": bool(quemado), "srt_aparte": str(srt_dest) if srt_dest else None,
                           "nota": "VARIANTE DE ENTREGA con subtítulos quemados; el master editable (pista) está en 06_EXPORT" if quemado else "Subtítulos como pista SRT aparte (no quemados)"},
            "capitulos": (caps or {}).get("capitulos") if perf.get("capitulos") else None,
            "capitulos_en_mp4": bool(ffmeta),
            "zona_segura_usada": zona,
            "manifiesto_ia": _manifiesto_ia(proj),
            "master_editable": masters,
            "fuente_especificaciones": {"documento": "docs/investigacion/plataformas_metricas.md + zonas_seguras.md", "confianza": perf["conf"], "nota": perf["nota"]},
            "origen_clip": (json.loads((proj / "00_DOCS" / "clip.json").read_text(encoding="utf-8")) if (proj / "00_DOCS" / "clip.json").exists() else None),
            "avisos": avisos,
            "segundos_de_exportacion": round(time.time() - t0, 1),
        }
        fp = carpeta / "ficha_publicacion.json"
        if fp.exists():
            try:
                ant = json.loads(fp.read_text(encoding="utf-8"))
                shutil.move(str(fp), str(carpeta / f"ficha_publicacion_v{ant.get('version', v - 1)}.json"))
            except Exception:  # noqa: BLE001
                pass
        fp.write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
        hechos.append(ficha)
        log(f"PUBLICAR {pl}: {salida.name} · {ver['ancho']}x{ver['alto']} {ver['fps']:.2f}fps {ver['tamano_mb']} MB {ver['lufs']} LUFS" + (f" · AVISOS: {'; '.join(avisos)}" if avisos else ""))
    shutil.rmtree(pub / "_tmp", ignore_errors=True)
    (pub / "LEEME_PUBLICAR.txt").write_text(
        "07_PUBLICAR = ENTREGA por plataforma (lista para subir; falta rellenar ficha_publicacion.json con el copy).\n"
        "Instagram, TikTok, Shorts y LinkedIn vertical/cuadrado llevan los subtitulos INCRUSTADOS (esas redes no importan SRT).\n"
        "YouTube largo y LinkedIn horizontal llevan el SRT al lado (no quemados) y las marcas de capitulos.\n"
        "El MASTER EDITABLE (ProRes 4444 con alfa + SRT + base) esta en ..\\06_EXPORT. No se publica desde alli.\n"
        "Nada se sobrescribe: v1, v2, v3.\n", encoding="utf-8")
    return hechos
