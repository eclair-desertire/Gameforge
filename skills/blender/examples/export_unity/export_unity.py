"""GameForge export test: Townhouse, StreetLamp, CafeOwner -> FBX for Unity (URP).
Run: Blender -b export_test.blend --python export_unity.py -- <UnityAssetsOutDir>
Works only on the copy (export_test.blend); builds GF_EXPORT_* collections, saves the copy."""
import bpy, bmesh, json, os, sys, shutil, math
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/gf_export"
assert bpy.data.filepath.endswith("export_test.blend"), "refusing to touch the original file"
sc = bpy.data.scenes["GF_Examples"]
assert bpy.context.scene.name == "GF_Examples", bpy.context.scene.name
vl = bpy.context.view_layer
report = {}

def coll(name):
    c = bpy.data.collections.get(name)
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    else:
        c = bpy.data.collections.new(name); sc.collection.children.link(c)
    return c

def pbr_info(mat):
    return json.loads(mat["gf_pbr"]) if mat and "gf_pbr" in mat else None

def box_uv(bm, me_mats):
    """UV = box projection in object space / tile size (same as the gf_lib Box-projected material)."""
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        m = me_mats[f.material_index] if f.material_index < len(me_mats) else None
        info = pbr_info(m)
        size = info["size"] if info else 1.0
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            if ax == 0:   u, v = (c.y if n.x > 0 else -c.y), c.z
            elif ax == 1: u, v = (-c.x if n.y > 0 else c.x), c.z
            else:         u, v = c.x, (c.y if n.z > 0 else -c.y)
            l[uv].uv = (u / size, v / size)

def bake(objs, name, col, pivot=Vector((0, 0, 0)), disable=("NONE",), make_uv=True):
    """Evaluated copy (modifiers applied, fonts -> mesh), world space minus pivot, joined into one object."""
    saved = []
    for o in objs:
        for m in o.modifiers:
            if m.type in disable and m.show_viewport:
                m.show_viewport = False; saved.append(m)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bm_all = bmesh.new(); mats = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        bm = bmesh.new(); bm.from_mesh(me)
        omats = [s.material for s in o.material_slots] or [None]
        if make_uv:
            box_uv(bm, omats)
        # remap material indices into the joined slot list
        remap = []
        for m in omats:
            if m not in mats: mats.append(m)
            remap.append(mats.index(m))
        for f in bm.faces:
            f.material_index = remap[min(f.material_index, len(remap) - 1)]
        mw = Matrix.Translation(-pivot) @ o.matrix_world
        bm.transform(mw)
        if mw.determinant() < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        tmp = bpy.data.meshes.new("tmp"); bm.to_mesh(tmp); bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp); bpy.data.meshes.remove(me)
    for m in saved: m.show_viewport = True
    # drop empty slots: faces on None go to the first real material
    real = [m for m in mats if m is not None]
    for f in bm_all.faces:
        m = mats[f.material_index] if f.material_index < len(mats) else None
        f.material_index = real.index(m) if m in real else 0
    me = bpy.data.meshes.new(name); bm_all.to_mesh(me); bm_all.free()
    for m in real: me.materials.append(m)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob

def hull(points, name, col):
    bm = bmesh.new()
    for p in points: bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); col.objects.link(ob); return ob

def world_pts(objs, pivot, pred=lambda p: True):
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        pts += [p for p in ((o.matrix_world @ v.co) - pivot for v in me.vertices) if pred(p)]
        ev.to_mesh_clear()
    return pts

def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)

def export(objs, path, armature=False):
    for o in vl.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    vl.objects.active = objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True,
        object_types={"MESH", "ARMATURE", "EMPTY"},
        apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
        use_mesh_modifiers=True, mesh_smooth_type="OFF", use_tspace=False,
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        bake_anim=False, path_mode="STRIP", embed_textures=False,
        # static: Apply Transform -> clean (0,0,0) root in Unity; rigs: keep off (experimental for armatures)
        bake_space_transform=not armature)

# ------------------------------------------------------------------ (a) Townhouse
TH = ["GF_TH_Shell", "GF_TH_Windows", "GF_TH_Details", "GF_TH_Roof"]  # GF_TH_Cutters excluded
all_th = [o for c in TH for o in bpy.data.collections[c].objects if o.type in ("MESH", "FONT")]
SMALL = ("GF_TH_Bread", "GF_TH_DoorKnob", "GF_TH_PendantCord", "GF_TH_PendantBulb", "GF_TH_RailRing",
         "GF_TH_Dentils", "GF_TH_Modillions", "GF_TH_PipeBracket", "GF_TH_PipeShoe", "GF_TH_Shop0_Shelf",
         "GF_TH_Shop1_Shelf", "bc")
LOD2_KEEP = ("GF_TH_FrontWall", "GF_TH_GroundWall", "GF_TH_Plinth", "GF_TH_SideL", "GF_TH_SideR", "GF_TH_Back",
             "GF_TH_RoofFront", "GF_TH_RoofBack", "GF_TH_GableL", "GF_TH_GableR", "GF_TH_Ridge", "GF_TH_Chimney",
             "GF_TH_Corona", "GF_TH_Door")
base = lambda o: o.name.rsplit(".", 1)[0]
lod1_objs = [o for o in all_th if base(o) not in SMALL]
lod2_objs = [o for o in all_th if base(o) in LOD2_KEEP or "_Glass" in o.name]
c = coll("GF_EXPORT_Townhouse")
root = bpy.data.objects.new("SM_Townhouse", None); c.objects.link(root)
l0 = bake(all_th, "SM_Townhouse_LOD0", c)
l1 = bake(lod1_objs, "SM_Townhouse_LOD1", c, disable=("BEVEL", "WAVE"))
l2 = bake(lod2_objs, "SM_Townhouse_LOD2", c, disable=("BEVEL", "WAVE"))
shell = [o for o in bpy.data.collections["GF_TH_Shell"].objects if base(o) != "GF_TH_Plinth"]
roof = [bpy.data.objects[n] for n in ("GF_TH_RoofFront", "GF_TH_RoofBack", "GF_TH_GableL", "GF_TH_GableR", "GF_TH_Ridge")]
steps = [o for o in all_th if base(o) in ("GF_TH_Step1", "GF_TH_Step2", "GF_TH_Plinth")]
u0 = hull(world_pts(shell, Vector()), "UCX_SM_Townhouse_00", c)
u1 = hull(world_pts(roof, Vector()), "UCX_SM_Townhouse_01", c)
u2 = hull(world_pts(steps, Vector()), "UCX_SM_Townhouse_02", c)
for o in (l0, l1, l2, u0, u1, u2): o.parent = root
report["Townhouse"] = {"LOD0": tris(l0), "LOD1": tris(l1), "LOD2": tris(l2), "materials": len(l0.data.materials),
                       "UCX": [tris(u) for u in (u0, u1, u2)], "dims": list(l0.dimensions)}
export([root, l0, l1, l2, u0, u1, u2], os.path.join(OUT, "Townhouse", "SM_Townhouse.fbx"))

# ------------------------------------------------------------------ (b) Street lamp
lamp = [o for o in sc.objects if o.name.startswith("GF_ST_Lamp") and o.type == "MESH"]  # includes LampGlass
piv = Vector((-6.6, -2.55, 0.14))
c = coll("GF_EXPORT_StreetLamp")
lm = bake(lamp, "SM_StreetLamp", c, pivot=piv)
parts_post = [o for o in lamp if base(o) == "GF_ST_Lamp" and o.name in ("GF_ST_Lamp", "GF_ST_Lamp.001", "GF_ST_Lamp.002")]
parts_head = [o for o in lamp if o not in parts_post and o.name not in ("GF_ST_Lamp.003", "GF_ST_Lamp.004", "GF_ST_Lamp.005")]
lu0 = hull(world_pts(parts_post, piv), "UCX_SM_StreetLamp_00", c)
lu1 = hull(world_pts(parts_head, piv), "UCX_SM_StreetLamp_01", c)
lu0.parent = lm; lu1.parent = lm
report["StreetLamp"] = {"tris": tris(lm), "materials": [m.name for m in lm.data.materials], "dims": list(lm.dimensions)}
export([lm, lu0, lu1], os.path.join(OUT, "StreetLamp", "SM_StreetLamp.fbx"))

# ------------------------------------------------------------------ (c) CafeOwner (MPFB)
rig = bpy.data.objects["GF_Human_CafeOwner_Rig"]
parts = [o for o in bpy.data.objects if o.parent == rig and o.type == "MESH"]
rig.data.pose_position = "REST"          # bind pose = MPFB T-pose -> Unity Humanoid
rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
rig.name = "SK_CafeOwner"; rig.data.name = "SK_CafeOwner_Skeleton"
NAMES = {"short02": "Hair", "male_casualsuit03": "Suit", "high-poly": "Eyes", "tongue01": "Tongue",
         "eyebrow001": "Eyebrows", "eyelashes01": "Eyelashes", "shoes02": "Shoes", "teeth_shape02": "Teeth"}
bpy.context.view_layer.update()
for o in parts:
    # 1) shape keys = MPFB macro targets -> bake current mix (blocks modifier apply otherwise)
    if o.data.shape_keys:
        vl.objects.active = o
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    # 2) drop SUBSURF (game budget), apply MASK by deleting verts
    for m in list(o.modifiers):
        if m.type == "SUBSURF": o.modifiers.remove(m)
    masks = [m for m in o.modifiers if m.type == "MASK"]
    if masks:
        bm = bmesh.new(); bm.from_mesh(o.data); dl = bm.verts.layers.deform.verify()
        kill = []
        for v in bm.verts:
            for m in masks:
                gi = o.vertex_groups[m.vertex_group].index
                inside = v[dl].get(gi, 0.0) > 0.0
                if inside == m.invert_vertex_group: kill.append(v); break
        bmesh.ops.delete(bm, geom=kill, context="VERTS"); bm.to_mesh(o.data); bm.free()
        for m in masks: o.modifiers.remove(m)
    # drop helper/delete vertex groups (not bones)
    for g in list(o.vertex_groups):
        if g.name not in rig.data.bones: o.vertex_groups.remove(g)
    suf = o.name.split(".", 1)[1] if "." in o.name else "body"
    o.name = "SK_CafeOwner_" + NAMES.get(suf, "Body")
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
zs = []
for o in parts:
    ev = o.evaluated_get(dg); me = ev.to_mesh(); zs += [(o.matrix_world @ v.co).z for v in me.vertices]; ev.to_mesh_clear()
report["CafeOwner"] = {"tris": {o.name: tris(o) for o in parts}, "total_tris": sum(tris(o) for o in parts),
                       "height_sole_to_top": round(max(zs) - min(zs), 3), "bones": len(rig.data.bones)}
export([rig] + parts, os.path.join(OUT, "CafeOwner", "SK_CafeOwner.fbx"), armature=True)

# ------------------------------------------------------------------ material manifest for Unity (URP Lit)
def imgs(nt):
    out = []
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeTexImage" and n.image: out.append(n)
        if n.bl_idname == "ShaderNodeGroup" and n.node_tree: out += imgs(n.node_tree)
    return out

def copy_tex(img, dst_dir):
    src = bpy.path.abspath(img.filepath); os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(src) and not os.path.exists(dst): shutil.copy2(src, dst)
    return os.path.basename(src)

def ms_from_rough(img, metal, dst_dir):
    """URP Lit: R = metallic, A = smoothness (1 - roughness)."""
    name = os.path.splitext(os.path.basename(img.filepath))[0].replace("_rough", "_MS") + ".png"
    dst = os.path.join(dst_dir, name)
    if not os.path.exists(dst):
        import numpy as np
        w, h = img.size; px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
        px = px.reshape(-1, 4); out = np.zeros_like(px)
        out[:, 0] = metal; out[:, 1] = metal; out[:, 2] = metal; out[:, 3] = 1.0 - px[:, 0]
        im = bpy.data.images.new("GF_tmp_ms", w, h, alpha=True, float_buffer=False)
        im.colorspace_settings.name = "Non-Color"; im.pixels.foreach_set(out.ravel())
        im.filepath_raw = dst; im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
    return name

manifest = {}
for asset, obs in (("Townhouse", [l0, l1, l2]), ("StreetLamp", [lm]), ("CafeOwner", parts)):
    tdir = os.path.join(OUT, asset, "Textures")
    for ob in obs:
        for m in ob.data.materials:
            if m is None or (asset + "/" + m.name) in manifest: continue
            key = asset + "/" + m.name
            e = {"asset": asset, "smoothness": 0.5, "metallic": 0.0, "color": [1, 1, 1, 1]}
            info = pbr_info(m)
            bsdf = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
            ims = imgs(m.node_tree)
            if info:
                e["metallic"] = info["metal"]; e["smoothness"] = 1 - info["rough"]
                diff = next((n.image for n in ims if "_diff" in n.image.name), None)
                if diff:
                    e["baseMap"] = copy_tex(diff, tdir); e["color"] = info["tint"]
                    nrm = next((n.image for n in ims if "_nor_gl" in n.image.name), None)
                    if nrm: e["normalMap"] = copy_tex(nrm, tdir); e["normalScale"] = info["normal"]
                    r = next((n.image for n in ims if "_rough" in n.image.name), None)
                    if r: e["metallicGlossMap"] = ms_from_rough(r, info["metal"], tdir)
                else:
                    e["color"] = info["color"]          # procedural fallback -> flat color
            elif bsdf and not bsdf.inputs["Base Color"].is_linked:
                e["color"] = list(bsdf.inputs["Base Color"].default_value)
                e["metallic"] = bsdf.inputs["Metallic"].default_value
                e["smoothness"] = 1 - bsdf.inputs["Roughness"].default_value
                a = bsdf.inputs["Alpha"].default_value
                if a < 1: e["transparent"] = True; e["color"][3] = a
                es = bsdf.inputs["Emission Strength"].default_value
                if es > 0: e["emission"] = [c * es for c in bsdf.inputs["Emission Color"].default_value[:3]]
            else:   # MPFB: diffuse image (+ normal), alpha clip for hair cards / lashes / brows
                diff = next((n.image for n in ims if n.image.colorspace_settings.name == "sRGB"
                             and "sss" not in n.image.name), None)
                if diff: e["baseMap"] = copy_tex(diff, tdir)
                nrm = next((n.image for n in ims if "normal" in n.image.name), None)
                if nrm: e["normalMap"] = copy_tex(nrm, tdir); e["normalScale"] = 1.0
                if bsdf and bsdf.inputs["Alpha"].is_linked:      # MPFB: alpha from diffuse (cornea, hair cards, lashes)
                    e["alphaClip"] = 0.5
                if any(k in m.name for k in ("short02", "eyebrow", "eyelashes")):
                    e["doubleSided"] = True
                e["smoothness"] = 0.35 if "body" in m.name or "ears" in m.name else 0.3
                if "high-poly" in m.name or "teeth" in m.name: e["smoothness"] = 0.8
            e["name"] = m.name
            manifest[key] = e
with open(os.path.join(OUT, "gf_materials.json"), "w") as f:
    json.dump({"materials": list(manifest.values())}, f, indent=1)
report["materials_total"] = len(manifest)
bpy.ops.wm.save_mainfile()
print("GF_REPORT " + json.dumps(report))
