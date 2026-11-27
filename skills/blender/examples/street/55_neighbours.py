"""Step 5b: row-house context — neighbours left/right reuse the townhouse geometry (linked mesh
data, cheap) with different plaster colours; longer street."""
import importlib, sys, os
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

col = L.collection("GF_Neighbours")
variants = {
    -9.6: L.pbr("GF_Plaster_Grey", "painted_plaster_wall", size=3.0, tint=(0.78, 0.8, 0.8, 1), color=(0.7, 0.72, 0.72, 1), rough=0.85),
    9.6: L.pbr("GF_Plaster_Rose", "painted_plaster_wall", size=3.0, tint=(0.9, 0.72, 0.66, 1), color=(0.8, 0.62, 0.56, 1), rough=0.85),
}
skip = ("Sign", "Fascia", "Balcony", "RailRing", "Downpipe", "PipeBracket", "PipeShoe", "Counter", "Gable", "Coping")
src = [o for o in bpy.data.collections["GF_Townhouse"].all_objects if o.type == "MESH" and not o.name.startswith("GF_cut_") and not any(k in o.name for k in skip)]
for dx, plaster in variants.items():
    for o in src:
        c = o.copy()           # linked mesh data, own transform/materials
        c.location.x += dx
        col.objects.link(c)
        for i, slot in enumerate(c.material_slots):
            if slot.material and slot.material.name in ("GF_Plaster_Ochre", "GF_Plaster_Rustic"):
                slot.link = "OBJECT"
                slot.material = plaster
# neighbours' shops are closed for the day: dim interiors instead of the lit café
dim = L.simple("GF_Shop_Closed", (0.05, 0.045, 0.04, 1), rough=0.9)
for o in col.objects:
    if "_Room" in o.name and "Shop" in o.name:
        o.material_slots[0].link = "OBJECT"
        o.material_slots[0].material = dim
# extend the street
for n in ("GF_ST_Road", "GF_ST_Pavement", "GF_ST_Kerb", "GF_ST_Gutter"):
    ob = bpy.data.objects.get(n)
    if ob:
        ob.scale.x = 2.6
result = {"neighbours": len(col.objects)}
