"""Close-up camera for checking the people (face, skin, clothes). Restores the main camera after."""
import bpy, math, os
sc = bpy.data.scenes["GF_Examples"]
cam = bpy.data.objects.get("GF_PortraitCam")
if cam is None:
    cam = bpy.data.objects.new("GF_PortraitCam", bpy.data.cameras.new("GF_PortraitCam")); sc.collection.objects.link(cam)
tgt = bpy.data.objects.get("GF_PortraitTarget") or bpy.data.objects.new("GF_PortraitTarget", None)
if tgt.name not in sc.collection.objects:
    sc.collection.objects.link(tgt)
WHO = globals().get("WHO", "owner")
if WHO == "owner":
    cam.location = (-2.55, -3.45, 1.62); tgt.location = (-1.35, -1.25, 1.42); cam.data.lens = 55
else:
    cam.location = (2.4, -3.6, 1.5); tgt.location = (4.3, -1.7, 1.28); cam.data.lens = 55
c = cam.constraints.get("Track") or cam.constraints.new("TRACK_TO")
c.name = "Track"; c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
cam.data.dof.use_dof = True; cam.data.dof.focus_object = tgt; cam.data.dof.aperture_fstop = 2.8
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 1000, 1250
result = {"camera": cam.name, "who": WHO}
