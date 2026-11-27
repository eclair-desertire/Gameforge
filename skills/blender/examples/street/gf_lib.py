"""GameForge example helpers for Blender (run through Blender MCP execute_blender_code).

Real-world meters, Z up, front facade faces -Y. Every object gets the GF_ prefix and lives in
a named collection so steps can be re-run: each step first deletes its own collection.
"""
import math
import os

import bmesh
import bpy

ROOT = os.path.expanduser(os.environ.get("GF_EXAMPLES_ROOT", "~/Documents/GameForge-examples"))
TEX = os.path.join(ROOT, "textures")


# ------------------------------------------------------------------ scene / collections

def scene():
    sc = bpy.data.scenes.get("GF_Examples")
    if sc is None:
        sc = bpy.data.scenes.new("GF_Examples")
        sc.unit_settings.system = "METRIC"
        sc.unit_settings.scale_length = 1.0
    bpy.context.window.scene = sc
    return sc


def collection(name, parent=None, clear=True):
    sc = scene()
    col = bpy.data.collections.get(name)
    if col and clear:
        for ob in list(col.all_objects):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and getattr(data, "users", 1) == 0:
                for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
                    if data.name in coll and coll[data.name] == data:
                        coll.remove(data)
                        break
        for ch in list(col.children):
            bpy.data.collections.remove(ch)
    if col is None:
        col = bpy.data.collections.new(name)
    par = parent or sc.collection
    if col.name not in par.children:
        par.children.link(col)
    return col


def link(ob, col):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


# ------------------------------------------------------------------ mesh primitives

def box(name, col, lo, hi, mat=None, bevel=0.0, segments=2):
    """Axis-aligned box between corners lo and hi (meters)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = lo[0] if v.co.x < 0 else hi[0]
        v.co.y = lo[1] if v.co.y < 0 else hi[1]
        v.co.z = lo[2] if v.co.z < 0 else hi[2]
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if bevel > 0:
        add_bevel(ob, bevel, segments)
    return ob


def prism(name, col, pts_xz, y0, y1, mat=None, bevel=0.0):
    """Extrude a polygon given in the XZ plane between y0 and y1 (pediments, profiles)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    front = [bm.verts.new((x, y0, z)) for x, z in pts_xz]
    back = [bm.verts.new((x, y1, z)) for x, z in pts_xz]
    n = len(pts_xz)
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if bevel > 0:
        add_bevel(ob, bevel, 2)
    return ob


def cylinder(name, col, base, radius, depth, mat=None, verts=16, axis="Z", bevel=0.0, radius2=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=radius, radius2=radius if radius2 is None else radius2, depth=depth)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, depth / 2))
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.radians(90), 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.radians(-90), 3, "X"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=base)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if bevel > 0:
        add_bevel(ob, bevel, 2)
    return ob


def add_bevel(ob, width, segments=2):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(40)
    m.harden_normals = True
    try:
        ob.data.shade_smooth()
    except Exception:
        pass
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    return m


def boolean_cut(target, cutters_col, apply=True):
    m = target.modifiers.new("Openings", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.operand_type = "COLLECTION"
    m.collection = cutters_col
    m.solver = "EXACT"
    if apply:
        with bpy.context.temp_override(object=target, active_object=target, selected_objects=[target]):
            bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)
            bpy.ops.object.modifier_apply(modifier=m.name)
    return m


def join(objs, name):
    objs = [o for o in objs if o]
    if not objs:
        return None
    main = objs[0]
    with bpy.context.temp_override(active_object=main, selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    main.name = name
    main.data.name = name
    return main


# ------------------------------------------------------------------ materials

def _img(path, non_color=False):
    if not os.path.exists(path):
        return None
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def _find(folder, key):
    d = os.path.join(TEX, folder)
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        if key in f and os.path.getsize(os.path.join(d, f)) > 10000:
            return os.path.join(d, f)
    return None


def pbr(name, folder=None, size=2.0, tint=(1, 1, 1, 1), color=(0.7, 0.7, 0.7, 1), rough=0.8, metal=0.0, normal=1.0, noise=0.15):
    """PBR material with Poly Haven textures (box-projected in object space, `size` meters per
    tile), tinted. Falls back to a procedural noise material if textures are missing."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    import json as _json
    mat["gf_pbr"] = _json.dumps({"folder": folder, "size": size, "tint": list(tint), "color": list(color), "rough": rough, "metal": metal, "normal": normal, "noise": noise})
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Metallic"].default_value = metal
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-700, 0)
    mp.inputs["Scale"].default_value = (1 / size, 1 / size, 1 / size)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    diff = _find(folder, "_diff") if folder else None
    if diff:
        def tex(path, nc, y):
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = _img(path, nc)
            n.projection = "BOX"
            n.projection_blend = 0.25
            n.location = (-400, y)
            nt.links.new(mp.outputs[0], n.inputs[0])
            return n
        d = tex(diff, False, 300)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.location = (100, 300)
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(d.outputs["Color"], mix.inputs[6])
        mix.inputs[7].default_value = tint
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        r = _find(folder, "_rough")
        if r:
            rt = tex(r, True, 0)
            nt.links.new(rt.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            bsdf.inputs["Roughness"].default_value = rough
        nrm = _find(folder, "_nor_gl")
        if nrm:
            nt_ = tex(nrm, True, -300)
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.location = (300, -300)
            nm.inputs["Strength"].default_value = normal
            nt.links.new(nt_.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    else:
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.location = (-400, 200)
        nz.inputs["Scale"].default_value = 3.0 / size * 4
        nz.inputs["Detail"].default_value = 8
        nt.links.new(mp.outputs[0], nz.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.location = (-150, 200)
        c0 = [max(0, c * (1 - noise)) for c in color[:3]] + [1]
        c1 = [min(1, c * (1 + noise)) for c in color[:3]] + [1]
        ramp.color_ramp.elements[0].color = c0
        ramp.color_ramp.elements[1].color = c1
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = rough
        bump = nt.nodes.new("ShaderNodeBump")
        bump.location = (300, -250)
        bump.inputs["Strength"].default_value = 0.15 * normal
        nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def simple(name, color, rough=0.5, metal=0.0, transmission=0.0, ior=1.45, emission=None, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    if emission:
        b.inputs["Emission Color"].default_value = emission[0]
        b.inputs["Emission Strength"].default_value = emission[1]
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return mat


def stats(col):
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in col.all_objects:
        if ob.type == "MESH":
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            tris += sum(len(p.vertices) - 2 for p in me.polygons)
            ev.to_mesh_clear()
    return {"objects": len(col.all_objects), "tris": tris}


# ------------------------------------------------------------------ viewport

def view(target=(0, 0, 6), distance=30, yaw=-35, pitch=72, shading="SOLID", lens=50):
    """Point the 3D viewport at target from a yaw/pitch (degrees). pitch 90 = horizontal."""
    from mathutils import Euler
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = shading
        if shading == "SOLID":
            sp.shading.light = "STUDIO"
            sp.shading.color_type = "MATERIAL"
            sp.shading.show_cavity = True
        sp.lens = lens
        sp.overlay.show_overlays = False
        r3 = sp.region_3d
        r3.view_perspective = "PERSP"
        r3.view_location = target
        r3.view_distance = distance
        r3.view_rotation = Euler((math.radians(pitch), 0, math.radians(yaw)), "XYZ").to_quaternion()
    return True


def prism_x(name, col, pts_yz, x0, x1, mat=None, bevel=0.0):
    """Extrude a polygon given in the YZ plane between x0 and x1 (roof slopes, gables, dormers)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in pts_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in pts_yz]
    n = len(pts_yz)
    bm.faces.new(a)
    bm.faces.new(b[::-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if bevel > 0:
        add_bevel(ob, bevel, 2)
    return ob


def refresh_pbr():
    """Rebuild every GameForge PBR material (picks up textures that finished downloading)."""
    import json as _json
    out = []
    for m in bpy.data.materials:
        if "gf_pbr" in m.keys():
            a = _json.loads(m["gf_pbr"])
            pbr(m.name, a["folder"], a["size"], tuple(a["tint"]), tuple(a["color"]), a["rough"], a["metal"], a["normal"], a["noise"])
            out.append((m.name, bool(a["folder"] and _find(a["folder"], "_diff"))))
    return out


def room(name, col, lo, hi, wall, floor=None, ceil=None):
    """Open-front interior box (floor, ceiling, back and side walls, normals inward). Front (-Y) open."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    v = {k: bm.verts.new(p) for k, p in {
        "a": (x0, y0, z0), "b": (x1, y0, z0), "c": (x1, y1, z0), "d": (x0, y1, z0),
        "e": (x0, y0, z1), "f": (x1, y0, z1), "g": (x1, y1, z1), "h": (x0, y1, z1)}.items()}
    faces = {"floor": ("a", "b", "c", "d"), "ceil": ("e", "h", "g", "f"), "back": ("d", "c", "g", "h"),
             "left": ("a", "d", "h", "e"), "right": ("b", "f", "g", "c")}
    mats = [wall, floor or wall, ceil or wall]
    idx = {"floor": 1, "ceil": 2, "back": 0, "left": 0, "right": 0}
    for k, f in faces.items():
        face = bm.faces.new([v[n] for n in f])
        face.material_index = idx[k]
    bm.to_mesh(me)
    bm.free()
    me.flip_normals()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    for m in mats:
        me.materials.append(m)
    return ob
