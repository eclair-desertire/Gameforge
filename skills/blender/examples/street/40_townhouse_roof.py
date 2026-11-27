"""Step 4: pitched tiled roof, brick gables, dormers, chimneys with pots, gutter and downpipe."""
import importlib, sys, os, math
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

W, D, T = 9.6, 10.0, 0.5
EAVE = 14.23            # cornice top
RIDGE_H = 3.4
x0, x1 = -W / 2, W / 2
yf, yb, yr = -0.35, D + 0.35, D / 2   # eaves front/back (overhang), ridge line
zr = EAVE + RIDGE_H
TH = 0.14               # roof build-up thickness

root = L.collection("GF_Townhouse", clear=False)
col = L.collection("GF_TH_Roof", root)
m_tile = L.pbr("GF_RoofTiles", "clay_roof_tiles_02", size=2.0, tint=(0.95, 0.85, 0.8, 1), color=(0.45, 0.2, 0.13, 1), rough=0.8, normal=1.2)
m_brick = bpy.data.materials["GF_Brick_Side"]
m_trim = bpy.data.materials["GF_Stone_Trim"]
m_zinc = L.simple("GF_Zinc", (0.42, 0.44, 0.45, 1), rough=0.35, metal=1.0)
m_pot = L.simple("GF_Terracotta", (0.55, 0.25, 0.14, 1), rough=0.8)
m_frame = bpy.data.materials["GF_Paint_White"]
m_glass = bpy.data.materials["GF_Glass"]
m_room = bpy.data.materials["GF_Room"]

slope = RIDGE_H / (yr - yf)
def z_front(y):  # top surface of the front slope at depth y
    return EAVE + (y - yf) * slope

# roof slopes (front and back) as thick slabs
L.prism_x("GF_TH_RoofFront", col, [(yf, EAVE), (yr, zr), (yr, zr + TH), (yf, EAVE + TH)], x0 - 0.12, x1 + 0.12, m_tile)
L.prism_x("GF_TH_RoofBack", col, [(yr, zr), (yb, EAVE), (yb, EAVE + TH), (yr, zr + TH)], x0 - 0.12, x1 + 0.12, m_tile)
# brick gables filling the roof triangle on both side walls
for sx, (a, b) in ((-1, (x0, x0 + T)), (1, (x1 - T, x1))):
    L.prism_x(f"GF_TH_Gable{'L' if sx < 0 else 'R'}", col, [(0.0, EAVE), (D, EAVE), (yr, zr - 0.05)], a, b, m_brick)
    # parapet coping on the gable edge
    L.prism_x("GF_TH_Coping", col, [(yf, EAVE + TH), (yr, zr + TH + 0.02), (yr, zr + TH + 0.12), (yf, EAVE + TH + 0.1)], a - 0.04, b + 0.04, m_trim)
    L.prism_x("GF_TH_Coping", col, [(yr, zr + TH + 0.02), (yb, EAVE + TH), (yb, EAVE + TH + 0.1), (yr, zr + TH + 0.12)], a - 0.04, b + 0.04, m_trim)
# ridge cap
L.cylinder("GF_TH_Ridge", col, (x0 - 0.1, yr, zr + TH - 0.02), 0.11, W + 0.2, m_tile, verts=12, axis="X")

# dormers on the front slope
for i, cx in enumerate((-2.6, 2.6)):
    w, h, dz = 1.5, 1.55, 0.0
    yfr = 0.9                          # dormer front plane depth
    zb = z_front(yfr) + TH             # where the dormer meets the roof
    top = zb + h
    # cheeks (side walls) follow the slope
    for sx in (-1, 1):
        xa = cx + sx * w / 2 - (0.1 if sx > 0 else 0)
        L.prism_x("GF_TH_DormerCheek", col, [(yfr, zb - 0.3), (yfr, top), ((top - EAVE - TH) / slope + yf, top)], xa, xa + 0.1, m_frame)
    # front: frame + glass + dark room
    L.box(f"GF_TH_DormerSill{i}", col, (cx - w / 2 - 0.05, yfr - 0.12, zb - 0.1), (cx + w / 2 + 0.05, yfr + 0.1, zb), m_zinc)
    parts = [L.box("df", col, (cx - w / 2, yfr, zb), (cx - w / 2 + 0.09, yfr + 0.08, top)),
             L.box("df", col, (cx + w / 2 - 0.09, yfr, zb), (cx + w / 2, yfr + 0.08, top)),
             L.box("df", col, (cx - w / 2, yfr, top - 0.09), (cx + w / 2, yfr + 0.08, top)),
             L.box("df", col, (cx - 0.03, yfr + 0.01, zb), (cx + 0.03, yfr + 0.07, top)),
             L.box("df", col, (cx - w / 2, yfr + 0.01, zb + (top - zb) * 0.55), (cx + w / 2, yfr + 0.07, zb + (top - zb) * 0.55 + 0.04))]
    fr = L.join(parts, f"GF_TH_DormerFrame{i}"); fr.data.materials.append(m_frame); L.add_bevel(fr, 0.006, 2)
    L.box(f"GF_TH_DormerGlass{i}", col, (cx - w / 2 + 0.05, yfr + 0.03, zb + 0.02), (cx + w / 2 - 0.05, yfr + 0.04, top - 0.02), m_glass)
    L.box(f"GF_TH_DormerRoom{i}", col, (cx - w / 2, yfr + 1.0, zb - 0.5), (cx + w / 2, yfr + 1.05, top), m_room)
    # small pitched dormer roof
    ry = (top + 0.55 - EAVE - TH) / slope + yf
    L.prism_x(f"GF_TH_DormerRoof{i}", col, [(yfr - 0.25, top), (ry, top + 0.55), (ry, top + 0.55 + 0.1), (yfr - 0.25, top + 0.1)], cx - w / 2 - 0.15, cx, m_tile)
    L.prism_x(f"GF_TH_DormerRoof{i}b", col, [(yfr - 0.25, top), (ry, top + 0.55), (ry, top + 0.55 + 0.1), (yfr - 0.25, top + 0.1)], cx, cx + w / 2 + 0.15, m_tile)
    # gabled front of the dormer roof (triangle) — simple: a pitched ridge over the dormer
    L.prism(f"GF_TH_DormerPediment{i}", col, [(cx - w / 2 - 0.15, top + 0.1), (cx + w / 2 + 0.15, top + 0.1), (cx, top + 0.62)], yfr - 0.25, ry, m_tile)

# chimneys on the gable walls with stone caps and terracotta pots
for sx in (-1, 1):
    cx = sx * (W / 2 - 0.45)
    L.box("GF_TH_Chimney", col, (cx - 0.4, yr + 0.3, EAVE), (cx + 0.4, yr + 1.3, zr + 1.3), m_brick, bevel=0.01)
    L.box("GF_TH_ChimneyCap", col, (cx - 0.48, yr + 0.22, zr + 1.3), (cx + 0.48, yr + 1.38, zr + 1.42), m_trim, bevel=0.01)
    for k, dx in enumerate((-0.18, 0.18)):
        L.cylinder("GF_TH_ChimneyPot", col, (cx + dx, yr + 0.8, zr + 1.42), 0.11, 0.38 + 0.08 * k, m_pot, verts=14, bevel=0.005)

# gutter along the front eave + downpipe at the right corner with brackets
L.cylinder("GF_TH_Gutter", col, (x0 - 0.12, yf - 0.02, EAVE - 0.02), 0.075, W + 0.24, m_zinc, verts=12, axis="X")
dx = x1 - 0.25
L.cylinder("GF_TH_Downpipe", col, (dx, -0.13, 0.15), 0.05, EAVE - 0.2, m_zinc, verts=12)
L.cylinder("GF_TH_DownpipeOffset", col, (dx, -0.13 - 0.0, EAVE - 0.25), 0.05, 0.3, m_zinc, verts=12, axis="Y")
for z in range(2, int(EAVE), 2):
    L.box("GF_TH_PipeBracket", col, (dx - 0.07, -0.2, z), (dx + 0.07, 0.0, z + 0.04), m_zinc)
L.box("GF_TH_PipeShoe", col, (dx - 0.07, -0.25, 0.1), (dx + 0.07, -0.05, 0.2), m_zinc)

L.view(target=(0, 2, 13), distance=22, yaw=-35, pitch=68)
result = {"step": "roof", **L.stats(col), "ridge_z": round(zr + TH, 2)}
