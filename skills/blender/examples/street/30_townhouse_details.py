"""Step 3: string course, main cornice with dentils and modillions, corner quoins, French
balcony with wrought-iron railing, shop fascia with lettering."""
import importlib, sys, os, math
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

W, T = 9.6, 0.5
GF_H, UF_H, N_UP = 4.0, 3.3, 3
TOP = GF_H + UF_H * N_UP
x0, x1 = -W / 2, W / 2

root = L.collection("GF_Townhouse", clear=False)
col = L.collection("GF_TH_Details", root)
m_trim = bpy.data.materials["GF_Stone_Trim"]
m_iron = L.simple("GF_WroughtIron", (0.03, 0.03, 0.032, 1), rough=0.45, metal=0.85)
m_stone = bpy.data.materials["GF_Stone_Plinth"]
m_shop = bpy.data.materials["GF_Paint_BottleGreen"]
m_gold = L.simple("GF_GildedLetters", (0.85, 0.65, 0.28, 1), rough=0.3, metal=1.0)


def band(name, z, layers, x_ext=0.0, ret=True):
    """Stacked moulding: layers = [(height, projection)] from bottom to top; returns around corners."""
    parts, zz = [], z
    for h, p in layers:
        parts.append(L.box(f"{name}_l", col, (x0 - p - x_ext, -p, zz), (x1 + p + x_ext, T if ret else 0.02, zz + h)))
        zz += h
    ob = L.join(parts, name)
    ob.data.materials.append(m_trim)
    L.add_bevel(ob, 0.006, 2)
    return ob, zz


# string course over the shop floor (doubles as the fascia cornice)
band("GF_TH_StringCourse", GF_H - 0.12, [(0.06, 0.05), (0.08, 0.11), (0.06, 0.16), (0.04, 0.12)])
# sill course under first-floor windows
band("GF_TH_SillCourse", GF_H + 0.6, [(0.06, 0.04), (0.05, 0.07)])

# main cornice: architrave, frieze, dentils, modillions, corona, cyma
_, z = band("GF_TH_Architrave", TOP - 0.62, [(0.08, 0.04), (0.06, 0.07)])
_, z = band("GF_TH_Frieze", z, [(0.26, 0.02)])
dent = []
n = int(W / 0.16)
for i in range(n + 1):
    x = x0 - 0.05 + i * (W + 0.1) / n
    dent.append(L.box("dent", col, (x - 0.04, -0.13, z), (x + 0.04, 0.0, z + 0.1)))
d = L.join(dent, "GF_TH_Dentils"); d.data.materials.append(m_trim)
z += 0.1
_, z = band("GF_TH_CorniceBed", z, [(0.05, 0.16)])
mods = []
for i in range(14):
    x = x0 + 0.25 + i * (W - 0.5) / 13
    mods.append(L.prism("mod", col, [(x - 0.07, z), (x + 0.07, z), (x + 0.07, z + 0.16), (x - 0.07, z + 0.16)], -0.42, 0.0))
    mods.append(L.box("modc", col, (x - 0.07, -0.42, z - 0.06), (x + 0.07, -0.3, z)))
m = L.join(mods, "GF_TH_Modillions"); m.data.materials.append(m_trim); L.add_bevel(m, 0.01, 2)
_, z = band("GF_TH_Corona", z + 0.16, [(0.14, 0.5), (0.05, 0.54), (0.05, 0.58)])
CORNICE_TOP = z

# rusticated quoins on the upper floors (alternating long/short blocks)
q = []
zz, k = GF_H + 0.05, 0
while zz < TOP - 0.7:
    h = 0.42
    long = k % 2 == 0
    for sx in (-1, 1):
        xe = x0 if sx < 0 else x1
        L_ = 0.62 if long else 0.38
        xa, xb = (xe, xe + L_) if sx < 0 else (xe - L_, xe)
        q.append(L.box("q", col, (xa - (0.04 if sx < 0 else 0), -0.04, zz), (xb + (0.04 if sx > 0 else 0), 0.3 if long else 0.2, zz + h - 0.04)))
    zz += h
    k += 1
qo = L.join(q, "GF_TH_Quoins"); qo.data.materials.append(m_trim); L.add_bevel(qo, 0.02, 3)

# French balcony on the first floor, centre bay: stone slab on consoles + wrought iron railing
bz = GF_H + 0.62
L.box("GF_TH_BalconySlab", col, (-1.05, -0.62, bz - 0.12), (1.05, 0.02, bz), m_stone, bevel=0.015)
cons = [L.prism("bc", col, [(-0.9, bz - 0.12), (-0.78, bz - 0.12), (-0.78, bz - 0.55)], -0.58, 0.0),
        L.prism("bc", col, [(0.78, bz - 0.12), (0.9, bz - 0.12), (0.78, bz - 0.55)], -0.58, 0.0)]
for c in cons:
    c.data.materials.append(m_trim)
rail = []
for i in range(23):
    x = -0.98 + i * (1.96 / 22)
    rail.append(L.box("bal", col, (x - 0.008, -0.56, bz), (x + 0.008, -0.544, bz + 0.95)))
for zr in (bz + 0.06, bz + 0.86):
    rail.append(L.box("rh", col, (-1.0, -0.57, zr), (1.0, -0.53, zr + 0.025)))
rail.append(L.box("top", col, (-1.02, -0.585, bz + 0.95), (1.02, -0.515, bz + 0.99)))
for sx in (-1, 1):
    rail.append(L.box("rs", col, (sx * 1.0 - 0.012, -0.57, bz + 0.95), (sx * 1.0 + 0.012, 0.0, bz + 0.98)))
r = L.join(rail, "GF_TH_BalconyRailing"); r.data.materials.append(m_iron)
# decorative rings in the railing
for i in range(6):
    x = -0.82 + i * 0.328
    bpy.ops.mesh.primitive_torus_add(major_radius=0.11, minor_radius=0.008, location=(x, -0.552, bz + 0.46), rotation=(math.radians(90), 0, 0))
    t = bpy.context.active_object; t.name = "GF_TH_RailRing"; L.link(t, col); t.data.materials.append(m_iron)

# shop fascia with gilded lettering
L.box("GF_TH_Fascia", col, (x0 + 0.3, -0.06, 3.58), (x1 - 0.3, 0.02, 3.86), m_shop, bevel=0.01)
bpy.ops.object.text_add(location=(0, -0.075, 3.64))
txt = bpy.context.active_object
txt.name = "GF_TH_SignText"
L.link(txt, col)
txt.data.body = "BAKERY  &  CAFE"
txt.data.align_x = "CENTER"
txt.data.size = 0.2
txt.data.extrude = 0.008
txt.data.bevel_depth = 0.002
txt.rotation_euler = (math.radians(90), 0, 0)
txt.data.materials.append(m_gold)

L.view(target=(0, 0, 9), distance=20, yaw=-30, pitch=78)
result = {"step": "details", **L.stats(col), "cornice_top": round(CORNICE_TOP, 3)}
