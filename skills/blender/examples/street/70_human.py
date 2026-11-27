"""Step 7: realistic human with MPFB2 (MakeHuman CC0 system assets).
Passport: café owner, man ~38, ~1.80 m, average build, casual clothes, short hair; stands by the
entrance, turned toward the street. Body from macro sliders, SSS skin, eyes/brows/lashes/teeth,
hair, clothes and shoes fitted to the body, game-engine rig, relaxed standing pose."""
import importlib, sys, os, math
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

BASE = "bl_ext.user_default.mpfb"
HS = importlib.import_module(BASE + ".services.humanservice").HumanService
AS = importlib.import_module(BASE + ".services.assetservice").AssetService
LS = importlib.import_module(BASE + ".services.locationservice").LocationService
AS.update_all_asset_lists()
DATA = LS.get_user_data()


def asset(sub, name, ext):
    d = os.path.join(DATA, sub, name)
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if f.endswith(ext):
                return os.path.join(root, f)
    raise FileNotFoundError(f"{sub}/{name}/*{ext}")


col = L.collection("GF_People")
lc = bpy.context.view_layer.layer_collection.children.get(col.name)
if lc:
    bpy.context.view_layer.active_layer_collection = lc
bpy.context.scene.cursor.location = (0, 0, 0)


def z_range(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = 1e9, -1e9
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            z = (ev.matrix_world @ v.co).z
            lo, hi = min(lo, z), max(hi, z)
        ev.to_mesh_clear()
    return lo, hi


def calibrated_body(macro, target_m, tol=0.015, slope=1.3):
    """MPFB height is non-linear and race-dependent: measure the NAKED body (before clothes add
    Mask modifiers that hide the feet), correct `height`, recreate until within tolerance."""
    macro = dict(macro)
    for _ in range(6):
        body = HS.create_human(macro_detail_dict=macro, feet_on_ground=True, scale=0.1)
        lo, hi = z_range([body])
        h = hi - lo
        if target_m is None or abs(h - target_m) <= tol:
            return body, round(h, 3), macro["height"]
        macro["height"] = max(0.0, min(1.0, macro["height"] + (target_m - h) / slope))
        me = body.data
        bpy.data.objects.remove(body, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return body, round(h, 3), macro["height"]


def person(name, macro, skin, equip, loc, rot_z, head_turn=0.0, target_m=None, subdiv=1):
    """Order matters: body -> rig -> skin -> fitted assets (so clothes get the armature).
    subdiv: 1 for renders, 0 for game characters."""
    before = set(bpy.data.objects)
    body, naked_h, height_param = calibrated_body(macro, target_m)
    body.name = f"GF_Human_{name}"
    rig = HS.add_builtin_rig(body, "game_engine")
    rig.name = f"GF_Human_{name}_Rig"
    HS.set_character_skin(asset("skins", skin, ".mhmat"), body, skin_type="ENHANCED_SSS")
    added = []
    for sub, an, typ in equip:
        try:
            HS.add_mhclo_asset(asset(sub, an, ".mhclo"), body, asset_type=typ, subdiv_levels=subdiv, material_type="MAKESKIN")
            added.append(f"{sub}/{an or '*'}")
        except Exception as e:
            added.append(f"FAILED {sub}/{an}: {e}")
    pb = rig.pose.bones
    from mathutils import Matrix

    def rot_arm_space(bone, axis, deg):
        """Rotate a pose bone around an ARMATURE-space axis (independent of the bone's roll)."""
        b = pb.get(bone)
        if not b:
            return None
        M = rig.data.bones[bone].matrix_local
        R = Matrix.Rotation(math.radians(deg), 4, axis)
        b.rotation_mode = "QUATERNION"
        b.rotation_quaternion = (M.inverted() @ R @ M).to_quaternion()
        return deg

    for side, sgn in (("l", 1), ("r", -1)):
        bone_ = rig.data.bones[f"upperarm_{side}"]
        v = (bone_.tail_local - bone_.head_local).normalized()   # armature space (Bone.vector is parent-relative!)
        below = math.degrees(math.asin(max(-1.0, min(1.0, -v.z))))    # current angle below horizontal
        rot_arm_space(f"upperarm_{side}", "Y", sgn * (87 - below))      # arms hang almost vertical
        rot_arm_space(f"lowerarm_{side}", "X", -8)                     # soft elbow, forearm slightly forward
        hb = pb.get(f"lowerarm_{side}")                                # twist forearm so palms face the thighs
        if hb:
            from mathutils import Quaternion
            hb.rotation_quaternion = hb.rotation_quaternion @ Quaternion((0, 1, 0), math.radians(sgn * 40))
    # relaxed fingers: curl every phalanx a little around its local X axis (thumb less)
    from mathutils import Quaternion as _Q
    for b_ in pb:
        n_ = b_.name
        if any(k in n_ for k in ("index_", "middle_", "ring_", "pinky_", "thumb_")):
            b_.rotation_mode = "QUATERNION"
            seg = int(n_.split("_")[1]) if n_.split("_")[1].isdigit() else 1
            ang = (10 if "thumb" in n_ else 18 + 6 * seg)
            b_.rotation_quaternion = b_.rotation_quaternion @ _Q((1, 0, 0), math.radians(ang))
    rot_arm_space("head", "Z", head_turn)
    rot_arm_space("spine_03", "Z", head_turn * 0.3)
    rot_arm_space("thigh_r", "Y", -3)
    for ob in set(bpy.data.objects) - before:
        L.link(ob, col)
    rig.location = loc
    rig.rotation_euler = (0, 0, math.radians(rot_z))
    bpy.context.view_layer.update()
    # final check: shoe sole -> top of the head (all rigged meshes except hair)
    parts = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig]
    sole, _ = z_range(parts)
    _, top = z_range([body])
    return {"assets": added, "naked_body_m": naked_h, "height_param": round(height_param, 3),
            "sole_to_head_m": round(top - sole, 3)}


def years(a):
    return 0.5 + (a - 25) / 65 * 0.5


owner = person("CafeOwner",
               {"gender": 1.0, "age": years(38), "muscle": 0.56, "weight": 0.55, "proportions": 0.65, "height": 0.55,
                "cupsize": 0.5, "firmness": 0.5, "race": {"caucasian": 0.8, "african": 0.08, "asian": 0.12}},
               "middleage_caucasian_male",
               [("eyes", "high-poly", "Eyes"), ("eyebrows", "eyebrow001", "Eyebrows"), ("eyelashes", "eyelashes01", "Eyelashes"),
                ("teeth", "", "Teeth"), ("tongue", "", "Tongue"), ("hair", "short02", "Hair"),
                ("clothes", "male_casualsuit03", "Clothes"), ("clothes", "shoes02", "Clothes")],
               (-1.35, -1.25, 0.14), -28, head_turn=8, target_m=1.80)
walker = person("Passerby",
                {"gender": 0.0, "age": years(30), "muscle": 0.5, "weight": 0.45, "proportions": 0.7, "height": 0.55,
                 "cupsize": 0.5, "firmness": 0.55, "race": {"asian": 0.75, "caucasian": 0.2, "african": 0.05}},
                "young_asian_female",
                [("eyes", "high-poly", "Eyes"), ("eyebrows", "eyebrow010", "Eyebrows"), ("eyelashes", "eyelashes02", "Eyelashes"),
                 ("teeth", "", "Teeth"), ("tongue", "", "Tongue"), ("hair", "ponytail01", "Hair"),
                 ("clothes", "female_elegantsuit01", "Clothes"), ("clothes", "shoes06", "Clothes")],
                (4.3, -1.7, 0.14), 62, head_turn=-15, target_m=1.65)

L.view(target=(1.5, -1.5, 1.1), distance=8.5, yaw=-15, pitch=86, shading="MATERIAL", lens=50)
result = {"owner": owner, "passerby": walker, "objects": len(col.all_objects)}
