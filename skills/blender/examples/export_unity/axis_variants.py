import bpy, os, sys
OUT = sys.argv[sys.argv.index("--") + 1]
vl = bpy.context.view_layer
def exp(objs, path, **kw):
    for o in vl.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    vl.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH","ARMATURE","EMPTY"},
        apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True, use_mesh_modifiers=True,
        add_leaf_bones=False, bake_anim=False, path_mode="STRIP", **kw)
lamp = [bpy.data.objects["SM_StreetLamp"]]
rig = bpy.data.objects["SK_CafeOwner"]; hum = [rig] + [o for o in bpy.data.objects if o.parent == rig]
os.makedirs(OUT, exist_ok=True)
for tag, kw in {"C_applyT": dict(axis_forward="-Z", axis_up="Y", bake_space_transform=True),
                "E_default": dict(axis_forward="-Z", axis_up="Y", bake_space_transform=False)}.items():
    exp(lamp, os.path.join(OUT, f"lamp_{tag}.fbx"), **kw)
    exp(hum, os.path.join(OUT, f"human_{tag}.fbx"), **kw)
