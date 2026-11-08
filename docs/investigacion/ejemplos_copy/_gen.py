import json, pathlib
D = pathlib.Path(__file__).parent
DISC = "Contenido educativo. No es asesoría de inversión."
NOTA = "Ejemplo de formato sobre material de terceros (clip de Aztec Lab). NO PUBLICAR."
reel = {
 "meta": {"pieza": "EJEMPLO REEL - IA y negocio en un fin de semana", "tipo": "reel", "tema": "IA que acorta el trabajo de montar un negocio",
          "invitado": "[PENDIENTE: nombre del orador]", "idioma": "es-CO", "duracion_s": 70, "no_publicar": True, "nota": NOTA},
 "cifras": [],
 "plataformas": {
  "instagram_reels": {"titulo": "", "hook": "Hace un año no habría podido hacerlo en un fin de semana. Ahora lo hizo con IA.",
    "cuerpo": "Ensambló un producto, desarrolló el software y montó la tienda web con pagos e inventario. Las medidas de la caja en 3D las generó ChatGPT.\n\nLo que más llama la atención: en ningún prompt usó lenguaje técnico. Escribió lo que necesitaba, como se lo contaría a una persona.",
    "cta": "¿Qué proyecto llevas aplazando porque no sabes cómo pedírselo a la IA? Cuéntalo en comentarios.",
    "hashtags": ["#InteligenciaArtificial", "#IAparaNegocios", "#Emprendimiento"], "texto_pantalla": ["Hace 1 año: imposible", "Software + tienda web + caja 3D", "Prompts en lenguaje natural"],
    "texto_portada": "No usó nada técnico", "enlaces": [], "disclaimer": ""},
  "tiktok": {"titulo": "", "hook": "Hace un año no habría podido. Ahora lo hizo en un fin de semana con IA.",
    "cuerpo": "Producto, software y tienda web con pagos, sin un solo prompt técnico.",
    "cta": "¿Qué proyecto tienes parado por miedo a pedírselo a la IA?", "hashtags": ["#InteligenciaArtificial", "#IAparaNegocios", "#Emprendimiento"],
    "texto_pantalla": ["Hace 1 año: imposible", "Prompts en lenguaje natural"], "texto_portada": "No usó nada técnico", "enlaces": [], "disclaimer": ""},
  "youtube_shorts": {"titulo": "Montó un negocio en un fin de semana con IA", "hook": "Hace un año no habría podido hacerlo en un fin de semana.",
    "cuerpo": "Producto, software y tienda web con pagos e inventario, y ningún prompt técnico. Así lo explica quien lo hizo.",
    "cta": "¿Qué proyecto llevas aplazando? Cuéntalo en comentarios.", "hashtags": ["#InteligenciaArtificial", "#Emprendimiento"],
    "texto_pantalla": ["Hace 1 año: imposible", "Prompts en lenguaje natural"], "texto_portada": "No usó nada técnico", "enlaces": [], "disclaimer": DISC},
  "linkedin": {"formato": "video", "titulo": "", "hook": "Hace un año no habría podido hacerlo en un fin de semana. Esta vez usó IA y no escribió nada técnico.",
    "cuerpo": "Ensambló un producto físico, desarrolló el software y montó una tienda web con pagos e inventario. Los planos de la caja en 3D los generó ChatGPT.\n\nEl detalle útil para equipos: los prompts fueron lenguaje natural, sin términos técnicos. La barrera que mucha gente se pone es mental.",
    "cta": "¿Qué tarea de tu equipo sigue pendiente solo por no saber cómo pedirla? Te leo.", "hashtags": ["#InteligenciaArtificial", "#Emprendimiento", "#Productividad"],
    "texto_pantalla": ["Hace 1 año: imposible"], "texto_portada": "No usó nada técnico", "enlaces": [], "disclaimer": DISC},
 }}
largo = {
 "meta": {"pieza": "EJEMPLO LARGO - Un negocio en un fin de semana con IA", "tipo": "largo", "tema": "Proceso completo de montar un producto con IA",
          "invitado": "[PENDIENTE: nombre del orador]", "idioma": "es-CO", "duracion_s": 1080,
          "no_publicar": True, "nota": NOTA + " Los capitulos y la duracion de 18 min son HIPOTETICOS: el clip real dura 70 s."},
 "cifras": [],
 "plataformas": {
  "youtube_largo": {"titulo": "Un negocio en un fin de semana con IA, sin código", "hook": "Hace un año no habría podido ensamblar esto en un fin de semana. Esta es la secuencia completa, paso a paso.",
    "cuerpo": "Producto físico, software, proveedores y tienda web con pagos e inventario, todo con ayuda de ChatGPT, Codex y Claude.\n\nVerás qué le pidió a cada herramienta y por qué ningún prompt necesitó lenguaje técnico.",
    "cta": "Cuéntanos en comentarios qué proyecto tienes parado y qué te frena.",
    "hashtags": ["#InteligenciaArtificial", "#Emprendimiento", "#ChatGPT"],
    "capitulos": [{"t": "00:00", "titulo": "Intro: lo que verás"}, {"t": "01:30", "titulo": "El producto: una caja que no existía"},
                  {"t": "04:10", "titulo": "Proveedores y proceso comercial"}, {"t": "07:20", "titulo": "Software y tienda web con pagos"},
                  {"t": "11:00", "titulo": "Los planos 3D que generó ChatGPT"}, {"t": "14:30", "titulo": "Los prompts: lenguaje natural"}, {"t": "17:00", "titulo": "Cierre: pierde el miedo"}],
    "texto_pantalla": ["Hace 1 año: imposible"], "texto_portada": "Sin código, en 2 días",
    "enlaces": [{"etiqueta": "Newsletter", "url": "[PENDIENTE: URL newsletter]"}], "disclaimer": DISC},
  "linkedin": {"formato": "video", "titulo": "", "hook": "Un producto, su software y su tienda web con pagos, en un fin de semana. Sin escribir un prompt técnico.",
    "cuerpo": "Dejamos la conversación completa en YouTube: 7 capítulos, del producto a la tienda web.\n\nLo útil para quien dirige un equipo: la IA recortó el proceso comercial y el desarrollo, pero la decisión de qué construir siguió siendo humana.",
    "cta": "¿Qué parte de tu proceso comercial automatizarías primero?", "hashtags": ["#InteligenciaArtificial", "#Emprendimiento", "#Productividad"],
    "texto_pantalla": [], "texto_portada": "Sin código, en 2 días", "enlaces": [{"etiqueta": "Video completo", "url": "[PENDIENTE: URL YouTube]"}], "disclaimer": DISC},
 }}
(D/"reel.json").write_text(json.dumps(reel, ensure_ascii=False, indent=1), encoding="utf-8")
(D/"largo.json").write_text(json.dumps(largo, ensure_ascii=False, indent=1), encoding="utf-8")
