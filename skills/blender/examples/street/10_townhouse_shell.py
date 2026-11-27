"""Step 1: townhouse shell — walls with real openings (reveals), rusticated ground floor, plinth."""
import importlib, sys, os
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import gf_lib as L; importlib.reload(L)

W, D, T = 9.6, 10.0, 0.5          # width (x), depth (y), wall thickness
GF_H, UF_H, N_UP = 4.0, 3.3, 3    # ground floor height, upper floor height, upper floors
PLINTH = 0.9
TOP = GF_H + UF_H * N_UP          # 13.9
BAYS = (-3.0, 0.0, 3.0)
x0, x1 = -W / 2, W / 2

root = L.collection("GF_Townhouse")
shell = L.collection("GF_TH_Shell", root)
cut = L.collection("GF_TH_Cutters", root)
cut.hide_render = True
cut.hide_viewport = True

m_plaster = L.pbr("GF_Plaster_Ochre", "painted_plaster_wall", size=3.0, tint=(0.93, 0.80, 0.60, 1), color=(0.82, 0.70, 0.52, 1), rough=0.85)
m_stone = L.pbr("GF_Stone_Plinth", "stone_brick_wall_001", size=2.0, tint=(0.85, 0.82, 0.76, 1), color=(0.55, 0.52, 0.48, 1), rough=0.9)
m_brick = L.pbr("GF_Brick_Side", "red_brick_03", size=2.0, color=(0.45, 0.22, 0.16, 1), rough=0.9)
m_rust = L.pbr("GF_Plaster_Rustic", "painted_plaster_wall", size=2.0, tint=(0.88, 0.84, 0.76, 1), color=(0.80, 0.76, 0.68, 1), rough=0.85)

def opening(name, cx, w, z0, z1):
    return L.box(name, cut, (cx - w / 2, -0.3, z0), (cx + w / 2, T + 0.3, z1))

# openings — upper floors: tall 19th-century windows, top floor slightly lower
for f in range(N_UP):
    base = GF_H + f * UF_H
    h = 2.1 if f < N_UP - 1 else 1.85
    for i, cx in enumerate(BAYS):
        opening(f"GF_cut_w{f}_{i}", cx, 1.3, base + 0.85, base + 0.85 + h)
# ground floor: two shop windows and a central door with transom
for i, cx in enumerate((-3.0, 3.0)):
    opening(f"GF_cut_shop{i}", cx, 2.3, PLINTH, 3.55)
opening("GF_cut_door", 0.0, 1.5, 0.3, 3.55)

# rusticated ground floor: horizontal V-joints every 0.45 m on the front face
for k, z in enumerate([PLINTH + 0.45 * j for j in range(1, 7)]):
    if z < GF_H - 0.2:
        L.box(f"GF_cut_rust{k}", cut, (x0 - 0.1, -0.2, z - 0.018), (x1 + 0.1, 0.025, z + 0.018))

front_upper = L.box("GF_TH_FrontWall", shell, (x0, 0, GF_H), (x1, T, TOP), m_plaster)
front_ground = L.box("GF_TH_GroundWall", shell, (x0, 0, PLINTH), (x1, T, GF_H), m_rust)
plinth = L.box("GF_TH_Plinth", shell, (x0 - 0.06, -0.06, 0), (x1 + 0.06, T, PLINTH), m_stone)
for ob in (front_upper, front_ground, plinth):
    L.boolean_cut(ob, cut)
    L.add_bevel(ob, 0.01, 2)

# side and back walls (brick, as if the neighbour was demolished), stone plinth continues
L.box("GF_TH_SideL", shell, (x0, T, 0), (x0 + T, D, TOP), m_brick, bevel=0.01)
L.box("GF_TH_SideR", shell, (x1 - T, T, 0), (x1, D, TOP), m_brick, bevel=0.01)
L.box("GF_TH_Back", shell, (x0, D - T, 0), (x1, D, TOP), m_brick, bevel=0.01)
# floor slabs inside (seen through windows)
dark = L.simple("GF_Interior_Dark", (0.06, 0.05, 0.045, 1), rough=0.9)
for f in range(N_UP + 1):
    z = PLINTH if f == 0 else GF_H + (f - 1) * UF_H
    L.box(f"GF_TH_Slab{f}", shell, (x0 + T, T, z - 0.25), (x1 - T, D - T, z), dark)

L.view(target=(0, 0, 7), distance=34, yaw=-28, pitch=80)
result = {"step": "shell", **L.stats(shell), "top": TOP}
