import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\tante\Projects\macrowise-video-editor")
from mw_editor import componer as co
from mw_editor.musica import aplicar_musica
P = Path(r"E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados\06-11-2026\Arca_14ene2026_editado")
OUT = Path(r"C:\Users\tante\Videos\Arca_14ene2026_FINAL"); OUT.mkdir(parents=True, exist_ok=True)
tmp = OUT / "_tmp"; tmp.mkdir(exist_ok=True)
exp = P / "06_EXPORT"
base = exp / "Arca_14ene2026_editado_horizontal_v2_base.mp4"
ass = exp / "Arca_14ene2026_editado_horizontal_v2_graficos.ass"
plan = json.loads((P / "05_PROJECT" / "plan.json").read_text(encoding="utf-8-sig"))
inter = OUT / "inter_capas.mp4"
co.referencia(str(base), dict(plan), "horizontal", None, None, None, str(inter), tmp, graficos_ass=str(ass))
final = OUT / "Arca_14ene2026_largo_FINAL_con_musica.mp4"
aplicar_musica(inter, exp / "Arca_14ene2026_editado_horizontal_v2_MUSICA_stem.wav", final)
inter.unlink()
print("FINAL:", final)
