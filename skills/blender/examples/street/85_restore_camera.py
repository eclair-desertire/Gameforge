import bpy
sc = bpy.data.scenes["GF_Examples"]
sc.camera = bpy.data.objects["GF_Camera"]
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
result = {"camera": sc.camera.name}
