"""Step 5: street (cobbles, pavement, kerb) and props that make the place feel lived-in: cast-iron
street lamp, bench, bistro tables and chairs, flower boxes, litter bin. Removes flat dormer
roof halves from step 4 (the gabled dormer roof stays)."""
import importlib, sys, os, math, random
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

rnd = random.Random(11)
for n in ("GF_TH_DormerRoof0", "GF_TH_DormerRoof0b", "GF_TH_DormerRoof1", "GF_TH_DormerRoof1b"):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

col = L.collection("GF_Street")
m_cobble = L.pbr("GF_Cobbles", "cobblestone_floor_04", size=2.5, color=(0.35, 0.33, 0.31, 1), rough=0.9, normal=1.3)
m_pave = L.pbr("GF_Pavement", "pavement_02", size=2.0, color=(0.55, 0.53, 0.5, 1), rough=0.85)
m_kerb = bpy.data.materials["GF_Stone_Plinth"]
m_iron = bpy.data.materials["GF_WroughtIron"]
m_wood = bpy.data.materials["GF_Door_Wood"]
m_lamp = L.simple("GF_LampGlow", (1.0, 0.85, 0.6, 1), rough=0.2, emission=((1.0, 0.8, 0.55, 1), 1.5))
m_marble = L.simple("GF_Marble", (0.85, 0.84, 0.8, 1), rough=0.15)
m_leaf = L.simple("GF_Leaf", (0.12, 0.3, 0.08, 1), rough=0.7)
m_flower = [L.simple("GF_FlowerRed", (0.7, 0.05, 0.08, 1), rough=0.6), L.simple("GF_FlowerPink", (0.85, 0.35, 0.55, 1), rough=0.6), L.simple("GF_FlowerWhite", (0.9, 0.9, 0.85, 1), rough=0.6)]
m_planter = L.simple("GF_PlanterZinc", (0.25, 0.26, 0.27, 1), rough=0.4, metal=0.8)

# ground
L.box("GF_ST_Road", col, (-16, -24, -0.12), (16, -3.0, 0.0), m_cobble)
L.box("GF_ST_Pavement", col, (-16, -3.0, -0.12), (16, 0.0, 0.14), m_pave)
L.box("GF_ST_Kerb", col, (-16, -3.12, -0.12), (16, -2.95, 0.16), m_kerb, bevel=0.02)
L.box("GF_ST_Gutter", col, (-16, -3.45, -0.02), (16, -3.12, 0.02), m_kerb)


def lamp(x, y):
    parts = [L.cylinder("lb", col, (x, y, 0.14), 0.24, 0.35, verts=8),
             L.cylinder("lb2", col, (x, y, 0.49), 0.17, 0.25, verts=8)]
    parts.append(L.cylinder("lp", col, (x, y, 0.74), 0.085, 3.2, verts=16, radius2=0.05))
    for z in (1.3, 2.6, 3.9):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.085, minor_radius=0.02, location=(x, y, z))
        t = bpy.context.active_object; L.link(t, col); parts.append(t)
    # lantern: frame, glass, roof, finial
    zc = 4.1
    parts.append(L.cylinder("lc", col, (x, y, zc - 0.05), 0.12, 0.1, verts=12))
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        parts.append(L.box("lf", col, (x + sx * 0.2 - 0.015, y + sy * 0.2 - 0.015, zc), (x + sx * 0.2 + 0.015, y + sy * 0.2 + 0.015, zc + 0.6)))
    parts.append(L.box("lfb", col, (x - 0.23, y - 0.23, zc), (x + 0.23, y + 0.23, zc + 0.04)))
    parts.append(L.cylinder("lr", col, (x, y, zc + 0.6), 0.34, 0.3, verts=8, radius2=0.03))
    parts.append(L.cylinder("lfin", col, (x, y, zc + 0.9), 0.03, 0.18, verts=8))
    for p in parts:
        if not p.data.materials:
            p.data.materials.append(m_iron)
    L.box("GF_ST_LampGlass", col, (x - 0.19, y - 0.19, zc + 0.04), (x + 0.19, y + 0.19, zc + 0.58), m_lamp)
    li = bpy.data.lights.new("GF_ST_LampLight", "POINT"); li.energy = 40; li.color = (1.0, 0.78, 0.5); li.shadow_soft_size = 0.15
    lo = bpy.data.objects.new("GF_ST_LampLight", li); lo.location = (x, y, zc + 0.3); col.objects.link(lo)
    for p in parts:
        p.name = "GF_ST_Lamp"


def bench(x, y, rot=0.0):
    objs = []
    for sx in (-0.75, 0.75):
        objs.append(L.prism("bs", col, [(x + sx - 0.03, 0.0), (x + sx + 0.03, 0.0), (x + sx + 0.03, 0.85), (x + sx - 0.03, 0.85)], y - 0.25, y + 0.25, m_iron))
        objs.append(L.box("bl", col, (x + sx - 0.03, y - 0.28, 0.0), (x + sx + 0.03, y + 0.28, 0.06), m_iron))
    for k in range(5):
        yy = y - 0.22 + k * 0.1
        objs.append(L.box("slat", col, (x - 0.95, yy, 0.42), (x + 0.95, yy + 0.08, 0.46), m_wood, bevel=0.008))
    for k in range(3):
        zz = 0.55 + k * 0.11
        objs.append(L.box("bslat", col, (x - 0.95, y + 0.22, zz), (x + 0.95, y + 0.26, zz + 0.08), m_wood, bevel=0.008))
    for o in objs:
        o.name = "GF_ST_Bench"


def bistro(x, y):
    L.cylinder("GF_ST_TableTop", col, (x, y, 0.74), 0.32, 0.03, m_marble, verts=24, bevel=0.005)
    L.cylinder("GF_ST_TablePost", col, (x, y, 0.14), 0.03, 0.6, m_iron, verts=10)
    L.cylinder("GF_ST_TableBase", col, (x, y, 0.14), 0.22, 0.03, m_iron, verts=16)
    for a in (0.6, 0.6 + math.pi):
        cx, cy = x + math.cos(a) * 0.55, y + math.sin(a) * 0.55
        L.cylinder("GF_ST_ChairSeat", col, (cx, cy, 0.58), 0.2, 0.035, m_wood, verts=20, bevel=0.004)
        for la in range(4):
            lx, ly = cx + math.cos(la * math.pi / 2 + 0.78) * 0.15, cy + math.sin(la * math.pi / 2 + 0.78) * 0.15
            L.cylinder("GF_ST_ChairLeg", col, (lx, ly, 0.14), 0.012, 0.44, m_iron, verts=6)
        bx, by = cx + math.cos(a) * 0.2, cy + math.sin(a) * 0.2
        bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.012, location=(bx, by, 0.85), rotation=(math.radians(90), 0, a + math.pi / 2))
        t = bpy.context.active_object; t.name = "GF_ST_ChairBack"; L.link(t, col); t.data.materials.append(m_iron)


def flower_box(cx, z, w=1.5):
    L.box("GF_ST_Planter", col, (cx - w / 2, -0.38, z), (cx + w / 2, -0.12, z + 0.2), m_planter, bevel=0.01)
    for k in range(14):
        x = cx - w / 2 + 0.08 + rnd.random() * (w - 0.16)
        y = -0.25 + rnd.uniform(-0.08, 0.08)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=rnd.uniform(0.07, 0.12), location=(x, y, z + 0.24))
        b = bpy.context.active_object; b.name = "GF_ST_Foliage"; L.link(b, col); b.data.materials.append(m_leaf)
        b.scale = (1.0, 0.8, rnd.uniform(0.8, 1.3))
        d = b.modifiers.new("Rough", "DISPLACE"); d.strength = 0.025
        tex = bpy.data.textures.get("GF_LeafNoise") or bpy.data.textures.new("GF_LeafNoise", "CLOUDS"); tex.noise_scale = 0.05; d.texture = tex
        if rnd.random() < 0.6:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.035, location=(x + rnd.uniform(-0.05, 0.05), y - 0.06, z + 0.3 + rnd.uniform(0, 0.08)))
            f = bpy.context.active_object; f.name = "GF_ST_Flower"; L.link(f, col); f.data.materials.append(rnd.choice(m_flower))


lamp(-6.6, -2.55)
bench(6.6, -1.0)
bistro(-2.6, -1.4)
bistro(2.0, -1.5)
for cx in (-3.0, 3.0):   # first-floor windows get flower boxes (sill top at GF_H+0.85)
    flower_box(cx, 4.0 + 0.85)
flower_box(0.0, 4.0 + 3.3 + 0.85)
# litter bin
L.cylinder("GF_ST_Bin", col, (5.2, -2.6, 0.14), 0.22, 0.8, m_iron, verts=20, bevel=0.01)
L.cylinder("GF_ST_BinLid", col, (5.2, -2.6, 0.94), 0.24, 0.05, m_iron, verts=20, bevel=0.01)

L.view(target=(0, -1, 3), distance=16, yaw=-25, pitch=78)
result = {"step": "street", **L.stats(col)}
