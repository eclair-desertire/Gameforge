"""Step 6: refresh materials, HDRI sky + sun (or procedural sky fallback), street-level camera,
EEVEE ray-traced render settings. Rendering itself is a separate call (render tool)."""
import importlib, sys, os, math
sys.path.insert(0, os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts")))
import bpy
import gf_lib as L; importlib.reload(L)

sc = L.scene()
for im in bpy.data.images:  # re-read any image that failed to load (e.g. finished downloading later)
    if im.source == "FILE" and im.size[0] == 0:
        im.reload()
mats = L.refresh_pbr()

# world
w = bpy.data.worlds.get("GF_World") or bpy.data.worlds.new("GF_World")
sc.world = w
w.use_nodes = True
nt = w.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
bg = nt.nodes.new("ShaderNodeBackground")
nt.links.new(bg.outputs[0], out.inputs[0])
hdr = os.path.join(L.TEX, "hdri", "kloofendal_48d_partly_cloudy_puresky_1k.hdr")
if os.path.exists(hdr) and os.path.getsize(hdr) > 100000:
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdr, check_existing=True)
    env.image.reload()  # the file may have been partial when first loaded
    mp = nt.nodes.new("ShaderNodeMapping"); tc = nt.nodes.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value[2] = math.radians(150)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], env.inputs[0])
    nt.links.new(env.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.9
    sky = "hdri"
else:
    skyn = nt.nodes.new("ShaderNodeTexSky")
    items = [i.identifier for i in bpy.types.ShaderNodeTexSky.bl_rna.properties["sky_type"].enum_items]
    for pref in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE"):
        if pref in items:
            skyn.sky_type = pref; break
    if hasattr(skyn, "sun_elevation"):
        skyn.sun_elevation = math.radians(38); skyn.sun_rotation = math.radians(205)
    nt.links.new(skyn.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.35
    sky = "procedural:" + skyn.sky_type

# sun
sun = bpy.data.objects.get("GF_Sun")
if sun is None:
    ld = bpy.data.lights.new("GF_Sun", "SUN"); sun = bpy.data.objects.new("GF_Sun", ld); sc.collection.objects.link(sun)
sun.data.energy = 3.2
sun.data.angle = math.radians(1.2)
sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(52), 0, math.radians(-38))

# camera at pedestrian height, 3/4 view across the street
cam = bpy.data.objects.get("GF_Camera")
if cam is None:
    cd = bpy.data.cameras.new("GF_Camera"); cam = bpy.data.objects.new("GF_Camera", cd); sc.collection.objects.link(cam)
cam.data.lens = 30
cam.data.sensor_width = 36
cam.location = (-7.5, -19.0, 1.65)
tgt = bpy.data.objects.get("GF_CamTarget") or bpy.data.objects.new("GF_CamTarget", None)
if tgt.name not in sc.collection.objects:
    sc.collection.objects.link(tgt)
tgt.location = (0.6, 2.0, 7.0)
con = cam.constraints.get("Track") or cam.constraints.new("TRACK_TO")
con.name = "Track"; con.target = tgt; con.track_axis = "TRACK_NEGATIVE_Z"; con.up_axis = "UP_Y"
cam.data.shift_y = 0.0
sc.camera = cam

# render settings
eng = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in eng else ("BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in eng else eng[0])
ee = sc.eevee
for attr, val in (("use_raytracing", True), ("taa_render_samples", 64), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_fast_gi", True)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1600, 1000, 100
vt = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items]
sc.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
os.makedirs(os.path.join(L.ROOT, "renders"), exist_ok=True)

result = {"sky": sky, "engine": sc.render.engine, "textured_materials": [m for m, t in mats if t], "procedural_materials": [m for m, t in mats if not t]}
