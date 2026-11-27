"""Step 2: windows (frames, sashes, glass, dim rooms behind), stone surrounds, sills, pediments,
hoods; shopfront and entrance door with transom and steps."""
import importlib, sys, os, random
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

W, D, T = 9.6, 10.0, 0.5
GF_H, UF_H, N_UP, PLINTH = 4.0, 3.3, 3, 0.9
BAYS = (-3.0, 0.0, 3.0)
rnd = random.Random(7)

root = L.collection("GF_Townhouse", clear=False)
col = L.collection("GF_TH_Windows", root)

m_frame = L.simple("GF_Paint_White", (0.86, 0.85, 0.80, 1), rough=0.35)
m_glass = L.simple("GF_Glass", (0.015, 0.017, 0.018, 1), rough=0.08, metal=0.0, ior=1.52)
m_glass.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.5
m_glass.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.28   # see rooms/curtains behind
try:
    m_glass.surface_render_method = "DITHERED"
except Exception:
    m_glass.blend_method = "HASHED"
m_trim = L.pbr("GF_Stone_Trim", "painted_plaster_wall", size=1.5, tint=(0.97, 0.94, 0.86, 1), color=(0.88, 0.85, 0.78, 1), rough=0.75, normal=0.6)
m_room = L.simple("GF_Room", (0.11, 0.085, 0.065, 1), rough=0.9)
m_walls = [L.simple("GF_Wall_Cream", (0.55, 0.48, 0.38, 1), rough=0.9), L.simple("GF_Wall_Sage", (0.32, 0.38, 0.30, 1), rough=0.9),
           L.simple("GF_Wall_Blue", (0.28, 0.33, 0.40, 1), rough=0.9), L.simple("GF_Wall_Rose", (0.50, 0.36, 0.33, 1), rough=0.9)]
m_floor = L.simple("GF_Floor_Parquet", (0.25, 0.15, 0.08, 1), rough=0.6)
m_ceil = L.simple("GF_Ceiling", (0.6, 0.58, 0.55, 1), rough=0.9)
m_curtain = [L.simple("GF_Curtain_Cream", (0.75, 0.68, 0.55, 1), rough=0.9), L.simple("GF_Curtain_Red", (0.42, 0.12, 0.10, 1), rough=0.9)]
m_shop = L.simple("GF_Paint_BottleGreen", (0.04, 0.16, 0.11, 1), rough=0.4)
m_wood = L.pbr("GF_Door_Wood", "wood_planks_grey", size=1.0, tint=(0.45, 0.28, 0.16, 1), color=(0.30, 0.18, 0.10, 1), rough=0.55)
m_brass = L.simple("GF_Brass", (0.78, 0.6, 0.3, 1), rough=0.25, metal=1.0)
m_bread = L.simple("GF_Bread", (0.62, 0.36, 0.14, 1), rough=0.7)
m_bulb = L.simple("GF_Bulb", (1, 0.85, 0.6, 1), rough=0.3, emission=((1.0, 0.75, 0.45, 1), 8.0))
m_iron_dark = L.simple("GF_IronDark", (0.03, 0.03, 0.03, 1), rough=0.5, metal=0.8)
m_stone = bpy_stone = L.pbr("GF_Stone_Plinth", "stone_brick_wall_001", size=2.0, tint=(0.85, 0.82, 0.76, 1), color=(0.55, 0.52, 0.48, 1), rough=0.9)


def window(tag, cx, z0, w, h, recess=0.16, transom=True, sashes=2, frame=0.075, bar=0.05):
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = recess - 0.04, recess + 0.05
    parts = []
    # outer frame
    parts += [L.box(f"{tag}_fL", col, (x0, y0, z0), (x0 + frame, y1, z0 + h)),
              L.box(f"{tag}_fR", col, (x1 - frame, y0, z0), (x1, y1, z0 + h)),
              L.box(f"{tag}_fB", col, (x0, y0 - 0.02, z0), (x1, y1, z0 + frame * 1.3)),
              L.box(f"{tag}_fT", col, (x0, y0, z0 + h - frame), (x1, y1, z0 + h))]
    tz = z0 + h * 0.74 if transom else None
    if transom:
        parts.append(L.box(f"{tag}_tr", col, (x0, y0, tz - bar / 2), (x1, y1, tz + bar / 2)))
    top = (tz - bar / 2) if transom else z0 + h - frame
    if sashes == 2:
        parts.append(L.box(f"{tag}_mu", col, (cx - bar * 0.7, y0, z0), (cx + bar * 0.7, y1, top)))
    # sash glazing bars (each casement split into 3 panes)
    for sx in ((x0 + frame, cx - bar * 0.7), (cx + bar * 0.7, x1 - frame)) if sashes == 2 else ((x0 + frame, x1 - frame),):
        for k in (1, 2):
            z = z0 + frame + (top - z0 - frame) * k / 3
            parts.append(L.box(f"{tag}_gb", col, (sx[0], y0 + 0.02, z - 0.012), (sx[1], y1 - 0.02, z + 0.012)))
    fr = L.join(parts, f"GF_TH_{tag}_Frame")
    fr.data.materials.append(m_frame)
    L.add_bevel(fr, 0.006, 2)
    L.box(f"GF_TH_{tag}_Glass", col, (x0 + 0.01, recess, z0 + 0.01), (x1 - 0.01, recess + 0.008, z0 + h - 0.01), m_glass)
    # dim room behind + sometimes a curtain
    L.room(f"GF_TH_{tag}_Room", col, (x0 - 1.0, T, z0 - 0.85), (x1 + 1.0, T + 3.2, z0 + h + 0.35), rnd.choice(m_walls), m_floor, m_ceil)
    if rnd.random() < 0.55:
        side = rnd.choice((-1, 1))
        cw = w * rnd.uniform(0.25, 0.45)
        cx0 = x0 + 0.05 if side < 0 else x1 - 0.05 - cw
        cur = L.box(f"GF_TH_{tag}_Curtain", col, (cx0, recess + 0.25, z0 + 0.05), (cx0 + cw, recess + 0.27, z0 + h - 0.05), rnd.choice(m_curtain))
        sol = cur.modifiers.new("Wave", "WAVE")
        sol.use_x, sol.use_y, sol.height, sol.width, sol.narrowness = True, False, 0.03, 0.12, 1.5
    return fr


def surround(tag, cx, z0, w, h, kind):
    x0, x1 = cx - w / 2, cx + w / 2
    b, p = 0.15, 0.05  # band width, projection
    parts = [L.box(f"{tag}_sL", col, (x0 - b, -p, z0), (x0, 0.01, z0 + h + b)),
             L.box(f"{tag}_sR", col, (x1, -p, z0), (x1 + b, 0.01, z0 + h + b)),
             L.box(f"{tag}_sT", col, (x0 - b, -p, z0 + h), (x1 + b, 0.01, z0 + h + b))]
    # sill with drip and two small consoles
    parts.append(L.box(f"{tag}_sill", col, (x0 - b - 0.06, -0.13, z0 - 0.09), (x1 + b + 0.06, 0.16, z0)))
    for sx in (x0 - b + 0.02, x1 + b - 0.12):
        parts.append(L.box(f"{tag}_con", col, (sx, -0.09, z0 - 0.32), (sx + 0.1, 0.01, z0 - 0.09)))
    if kind == "pediment":
        zt = z0 + h + b
        parts.append(L.box(f"{tag}_frz", col, (x0 - b, -p, zt), (x1 + b, 0.01, zt + 0.22)))
        parts.append(L.box(f"{tag}_cor", col, (x0 - b - 0.08, -p - 0.08, zt + 0.22), (x1 + b + 0.08, 0.01, zt + 0.3)))
        parts.append(L.prism(f"{tag}_ped", col, [(x0 - b - 0.08, zt + 0.3), (x1 + b + 0.08, zt + 0.3), (cx, zt + 0.72)], -p - 0.08, 0.01))
    elif kind == "hood":
        zt = z0 + h + b
        parts.append(L.box(f"{tag}_frz", col, (x0 - b, -p, zt), (x1 + b, 0.01, zt + 0.16)))
        parts.append(L.box(f"{tag}_cor", col, (x0 - b - 0.1, -p - 0.12, zt + 0.16), (x1 + b + 0.1, 0.01, zt + 0.26)))
        for sx in (x0 - b - 0.02, x1 + b - 0.08):
            parts.append(L.box(f"{tag}_brk", col, (sx, -p - 0.1, zt - 0.25), (sx + 0.1, 0.0, zt + 0.16)))
    s = L.join(parts, f"GF_TH_{tag}_Surround")
    s.data.materials.append(m_trim)
    L.add_bevel(s, 0.008, 2)
    return s


for f in range(N_UP):
    base = GF_H + f * UF_H
    h = 2.1 if f < N_UP - 1 else 1.85
    kind = ("pediment", "hood", "plain")[f]
    for i, cx in enumerate(BAYS):
        window(f"W{f}{i}", cx, base + 0.85, 1.3, h)
        surround(f"W{f}{i}", cx, base + 0.85, 1.3, h, kind)

# ---- shopfront: painted timber frames, big glass, stall riser is the stone plinth
for i, cx in enumerate((-3.0, 3.0)):
    tag = f"Shop{i}"
    x0, x1, z0, z1 = cx - 1.15, cx + 1.15, PLINTH, 3.55
    parts = [L.box(f"{tag}_a", col, (x0, 0.2, z0), (x0 + 0.1, 0.32, z1)),
             L.box(f"{tag}_b", col, (x1 - 0.1, 0.2, z0), (x1, 0.32, z1)),
             L.box(f"{tag}_c", col, (x0, 0.18, z0), (x1, 0.34, z0 + 0.12)),
             L.box(f"{tag}_d", col, (x0, 0.2, z1 - 0.1), (x1, 0.32, z1)),
             L.box(f"{tag}_e", col, (x0, 0.2, 2.75), (x1, 0.32, 2.83)),
             L.box(f"{tag}_f", col, (cx - 0.04, 0.2, z0), (cx + 0.04, 0.32, 2.75))]
    for k in range(1, 4):
        xx = x0 + (x1 - x0) * k / 4
        parts.append(L.box(f"{tag}_g", col, (xx - 0.02, 0.21, 2.83), (xx + 0.02, 0.31, z1 - 0.1)))
    fr = L.join(parts, f"GF_TH_{tag}_Frame")
    fr.data.materials.append(m_shop)
    L.add_bevel(fr, 0.008, 2)
    L.box(f"GF_TH_{tag}_Glass", col, (x0 + 0.05, 0.255, z0 + 0.1), (x1 - 0.05, 0.265, z1 - 0.05), m_glass)
    shop_wall = L.simple("GF_Shop_Wall", (0.42, 0.30, 0.20, 1), rough=0.8)
    L.room(f"GF_TH_{tag}_Room", col, (x0 - 0.4, T, 0.14), (x1 + 0.4, 4.2, 3.9), shop_wall, m_floor, m_ceil)
    L.box(f"GF_TH_{tag}_Counter", col, (x0 + 0.3, 2.2, 0.14), (x1 - 0.3, 2.75, 1.05), m_wood, bevel=0.01)
    L.box(f"GF_TH_{tag}_CounterTop", col, (x0 + 0.25, 2.15, 1.05), (x1 - 0.25, 2.8, 1.1), L.simple("GF_Marble", (0.85, 0.84, 0.8, 1), rough=0.15))
    for k, zs in enumerate((1.3, 1.75, 2.2)):
        L.box(f"GF_TH_{tag}_Shelf", col, (x0 - 0.3, 3.85, zs), (x1 + 0.3, 4.15, zs + 0.04), m_wood)
        for j in range(9):
            bx = x0 - 0.2 + j * ((x1 - x0 + 0.4) / 9) + rnd.uniform(0, 0.08)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.09, location=(bx, 4.0, zs + 0.09))
            b = bpy.context.active_object; b.scale = (1.6, 0.9, 0.7); b.name = "GF_TH_Bread"; L.link(b, col)
            b.data.materials.append(m_bread)
    for k in (0.3, 0.7):
        lx = x0 + (x1 - x0) * k
        L.cylinder("GF_TH_PendantCord", col, (lx, 1.6, 3.0), 0.006, 0.9, m_iron_dark)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.12, location=(lx, 1.6, 2.95))
        g_ = bpy.context.active_object; g_.name = "GF_TH_PendantBulb"; L.link(g_, col); g_.data.materials.append(m_bulb)
        li = bpy.data.lights.new("GF_TH_ShopLight", "POINT"); li.energy = 60; li.color = (1.0, 0.75, 0.45); li.shadow_soft_size = 0.2
        lo = bpy.data.objects.new("GF_TH_ShopLight", li); lo.location = (lx, 1.6, 2.8); col.objects.link(lo)

# ---- entrance: panelled double door, glazed transom, stone steps
parts = []
for side, (dx0, dx1) in enumerate(((-0.72, -0.01), (0.01, 0.72))):
    leaf = L.box(f"Door{side}", col, (dx0, 0.30, 0.3), (dx1, 0.36, 2.6))
    parts.append(leaf)
    for pz0, pz1 in ((0.45, 1.25), (1.4, 2.45)):
        parts.append(L.box(f"Pan{side}", col, (dx0 + 0.1, 0.27, pz0), (dx1 - 0.1, 0.30, pz1)))
door = L.join(parts, "GF_TH_Door")
door.data.materials.append(m_wood)
L.add_bevel(door, 0.006, 2)
dfr = L.join([L.box("dfa", col, (-0.75, 0.25, 0.3), (-0.72, 0.4, 3.55)), L.box("dfb", col, (0.72, 0.25, 0.3), (0.75, 0.4, 3.55)),
              L.box("dfc", col, (-0.75, 0.25, 2.6), (0.75, 0.4, 2.72)), L.box("dfd", col, (-0.75, 0.25, 3.45), (0.75, 0.4, 3.55)),
              L.box("dfe", col, (-0.02, 0.26, 2.72), (0.02, 0.39, 3.45))], "GF_TH_DoorFrame")
dfr.data.materials.append(m_shop)
L.box("GF_TH_DoorTransomGlass", col, (-0.72, 0.32, 2.72), (0.72, 0.33, 3.45), m_glass)
for hx in (-0.12, 0.12):
    L.cylinder("GF_TH_DoorKnob", col, (hx, 0.24, 1.35), 0.03, 0.06, m_brass, axis="Y")
L.box("GF_TH_Step1", col, (-1.05, -0.62, 0.0), (1.05, 0.3, 0.15), m_stone, bevel=0.015)
L.box("GF_TH_Step2", col, (-0.95, -0.3, 0.15), (0.95, 0.3, 0.3), m_stone, bevel=0.015)

L.view(target=(0, 0, 6.5), distance=24, yaw=-22, pitch=82)
result = {"step": "windows", **L.stats(col)}
