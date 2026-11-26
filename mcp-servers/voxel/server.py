"""gameforge-voxel — MCP server for detailed voxel art (MagicaVoxel-compatible).

Run: bash scripts/run-mcp.sh voxel   (stdio). Logic lives in voxcore.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import artlib  # noqa: E402
from mcpcompat import Image, Server, tool  # noqa: E402
import voxcore as V  # noqa: E402

INSTRUCTIONS = """Voxel art studio (z is up, characters face -y, max 256 per model axis).
Quality workflow: 1) vox_scene new -> 2) vox_palette ramp for every material (hue-shifted ramps,
5-6 shades) -> 3) block out big forms with vox_shape / vox_generate -> 4) details: vox_shape
subtract for recesses, vox_detail noise/erode/scatter -> 5) vox_detail shade ONCE at the end
(baked AO + edge light) -> 6) vox_render view=sheet or turnaround and LOOK at it, fix, repeat ->
7) vox_save (.vox for MagicaVoxel/Goxel) and vox_export (.glb/.obj for Unity/Godot/Unreal/Blender).
Colors: '#rrggbb', ramp name (middle shade) or 'ramp:k' (0 = darkest, -1 = lightest).
Scenes live in memory: save often."""

mcp = Server("gameforge-voxel", instructions=INSTRUCTIONS)
SCENES: dict[str, V.Scene] = {}


def _scene(name: str) -> V.Scene:
    if name not in SCENES:
        raise ValueError(f"no scene '{name}'. Open scenes: {list(SCENES)}. Create with vox_scene(action='new') or vox_load.")
    return SCENES[name]


def _j(d: Any) -> str:
    return json.dumps(d, ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


@tool(mcp)
def vox_scene(action: str = "list", scene: str = "main") -> str:
    """Manage scenes. action: new | info | list | delete."""
    if action == "new":
        SCENES[scene] = V.Scene(scene)
        return _j({"created": scene})
    if action == "info":
        return _j(_scene(scene).info())
    if action == "delete":
        SCENES.pop(scene, None)
        return _j({"deleted": scene})
    return _j({"scenes": {k: list(v.models) for k, v in SCENES.items()}})


@tool(mcp)
def vox_model(scene: str, name: str, size: list[int], pos: list[int] | None = None, action: str = "add") -> str:
    """Add (or with action='move' reposition, 'delete' remove) a model. size [x,y,z] <= 256 each;
    pos = world position of the model's (0,0,0) corner, used for layout, render and export."""
    sc = _scene(scene)
    if action == "delete":
        sc.models.pop(name, None)
        return _j({"deleted": name})
    if action == "move":
        sc.model(name).pos = [int(v) for v in (pos or [0, 0, 0])]
        return _j(sc.model(name).info())
    m = sc.add_model(name, size, pos or [0, 0, 0])
    return _j(m.info())


@tool(mcp)
def vox_palette(scene: str, action: str = "list", name: str = "", base: str = "", steps: int = 6, hue_shift: float = 25.0, colors: list[str] | None = None, ref: str = "", kind: str = "diffuse", contrast: float = 1.0) -> str:
    """Palette & materials.
    action='ramp': create ramp `name` from `base` hex (dark->light, hue-shifted shadows/highlights,
      `steps` shades) or from explicit `colors`. Use one ramp per material (brick, skin, leaves...).
    action='material': kind diffuse|metal|glass|emit for `ref` (ramp name or color) — exported to .vox MATL
      and to the GLB emissive texture (emit).
    action='list': ramps and materials."""
    pal = _scene(scene).palette
    if action == "ramp":
        idx = pal.add_ramp(name, base or None, steps, hue_shift, colors, contrast)
        return _j({"ramp": name, "indices": idx, "colors": [artlib.rgb_to_hex(pal.colors[i]) for i in idx]})
    if action == "material":
        return _j({"material": kind, "indices": pal.set_material(ref, kind)})
    return _j({"used": pal.next - 1, "ramps": {k: [artlib.rgb_to_hex(pal.colors[i]) for i in v] for k, v in pal.ramps.items()}, "materials": {str(k): v for k, v in pal.materials.items()}})


@tool(mcp)
def vox_shape(scene: str, model: str, shape: str, color: str = "", mode: str = "add", lo: list[float] | None = None, hi: list[float] | None = None, center: list[float] | None = None, radii: list[float] | None = None, p0: list[float] | None = None, p1: list[float] | None = None, radius: float = 2.0, radius_end: float | None = None, height: float = 4.0, axis: str = "z", hollow: int = 0, roughness: float = 0.0, power: float = 2.0, seed: int = 0) -> str:
    """Draw a shape in model-local coords. mode: add | subtract (carve) | paint (recolor existing) | fill_empty.
    shape='box' lo,hi (inclusive corners), hollow=wall thickness;
    'ellipsoid' center, radii, power (2 round, 3-4 boxy/rounded-cube);
    'cylinder' center=base point, radius, height, axis x|y|z, radius_end for taper ('cone' = radius_end 0);
    'capsule' p0, p1, radius, radius_end (limbs, branches, pipes, cables).
    roughness 0..0.5 adds fbm noise to the surface (rocks, foliage, ruins)."""
    sc = _scene(scene)
    m = sc.model(model)
    idx = sc.palette.resolve(color) if mode != "subtract" else 0
    m.snapshot()
    if shape == "box":
        n = V.shape_box(m, lo, hi, idx, mode, hollow)
    elif shape == "ellipsoid":
        n = V.shape_ellipsoid(m, center, radii, idx, mode, roughness, seed, power)
    elif shape in ("cylinder", "cone"):
        rt = 0.0 if shape == "cone" and radius_end is None else radius_end
        n = V.shape_cylinder(m, center, radius, height, idx, mode, rt, axis, roughness, seed)
    elif shape == "capsule":
        n = V.shape_capsule(m, p0, p1, radius, radius if radius_end is None else radius_end, idx, mode, roughness, seed)
    else:
        raise ValueError("shape: box | ellipsoid | cylinder | cone | capsule")
    return _j({"changed": n, **m.info()})


@tool(mcp)
def vox_detail(scene: str, model: str, op: str, ramp: str = "*", color: str = "", to: str = "", amount: float = 0.25, scale: float = 3.0, strength: float = 1.0, density: float = 0.3, on: str = "top", height: int = 1, axis: str = "x", keep: str = "low", ao: float = 1.0, edges: float = 1.0, top: float = 0.0, radius: int = 2, iterations: int = 1, seed: int = 0) -> str:
    """Detail passes.
    op='noise': vary shades inside `ramp` ('*' = all ramps) with 3D noise (scale, strength) — stone, bark, cloth.
    op='erode': chip surface voxels (amount 0.1-0.4, scale, iterations) — weathering, ruins, foliage.
    op='scatter': grow `color` (ramp name or hex) on='top'|'sides' with density, height — moss, grass, snow, rubble.
    op='replace': recolor every `color` voxel to `to`.
    op='mirror': copy half across `axis`, keep='low'|'high' — symmetric props/characters.
    op='shade': bake AO (ao), convex edge highlight (edges), sky light (top). Run ONCE at the end."""
    sc = _scene(scene)
    m = sc.model(model)
    pal = sc.palette
    m.snapshot()
    if op == "noise":
        n = V.noise_shade(sc, m, ramp, scale, strength, seed)
    elif op == "erode":
        n = V.erode(m, amount, scale, seed, iterations)
    elif op == "scatter":
        n = V.scatter(sc, m, color, density, on, scale, height, seed)
    elif op == "replace":
        a, b = pal.resolve(color), pal.resolve(to)
        n = int((m.vox == a).sum())
        m.vox[m.vox == a] = b
    elif op == "mirror":
        V.mirror(m, axis, keep)
        n = int((m.vox > 0).sum())
    elif op == "shade":
        n = V.shade(sc, m, ao, edges, top, radius)
    else:
        raise ValueError("op: noise | erode | scatter | replace | mirror | shade")
    return _j({"op": op, "affected": n, **m.info()})


@tool(mcp)
def vox_generate(scene: str, model: str, kind: str, params: dict | None = None, size: list[int] | None = None, pos: list[int] | None = None) -> str:
    """Procedural generators (creates the model if `size` is given). kind and main params:
    building: width, depth, floors, floor_h(7), style brick|plaster|concrete|wood|stone, roof gable|hip|flat,
      window_w, window_h, window_gap, balconies 0..1, shop bool, lit 0..1 (emissive night windows),
      wall/trim/roof_color/glass hex, seed, person_height (= character height in the same scene: sets
      floor_h ~1.25x, windows and door to match people). Default floor_h 7 suits ~6-voxel figures.
      Model >= (width+2, depth+2, floors*floor_h + roof); width >= 3 windows wide.
    character: height (32-48 good), style realistic|stylized|chibi, body male|female|neutral, pose a|t|idle,
      skin, hair, hair_style short|long|ponytail|bun|bald, eyes, top, bottom, shoes, sleeves long|short,
      jacket hex|null, belt, hat none|cap|helmet, seed. Faces -y. Model ~ (height*0.6, height*0.4, height+2).
    tree: base [x,y,z], kind oak|pine|birch|dead, height, trunk, leaves, seed.
    rock: center, size, color, moss 0..1, seed.
    terrain: seed, base, amplitude, scale, water_level, snow_line, trees, rocks (fills the whole model).
    Then add your own details and finish with vox_detail op='shade'."""
    sc = _scene(scene)
    if size:
        sc.add_model(model, size, pos or [0, 0, 0])
    m = sc.model(model)
    p = dict(params or {})
    m.snapshot()
    gens = {"building": V.gen_building, "character": V.gen_character, "tree": V.gen_tree, "rock": V.gen_rock, "terrain": V.gen_terrain}
    if kind not in gens:
        raise ValueError(f"kind: {list(gens)}")
    try:
        out = gens[kind](sc, m, **p)
    except Exception:
        if size:  # do not leave a half-made model behind
            sc.models.pop(model, None)
        raise
    return _j({"kind": kind, "result": out, **m.info()})


@tool(mcp)
def vox_stamp(scene: str, src: str, dst: str, offset: list[int], rotate: int = 0, flip_x: bool = False, overwrite: bool = True) -> str:
    """Copy model `src` into `dst` at offset (prefab-style kits: windows, lamps, props).
    rotate = quarter turns around z."""
    sc = _scene(scene)
    d = sc.model(dst)
    d.snapshot()
    n = V.stamp(sc.model(src), d, offset, rotate, flip_x, overwrite)
    return _j({"stamped": n, **d.info()})


@tool(mcp)
def vox_render(scene: str, models: list[str] | None = None, view: str = "sheet", rotate: int = 0, scale: int = 0, out: str = "", background: str = "#20242b") -> list:
    """Render a preview and return it as an image so you can check the result.
    view: sheet (iso + front/right/back/top — best for review) | turnaround (4 iso angles) | iso |
    front | back | left | right | top. out: optional PNG path to save."""
    sc = _scene(scene)
    img = V.render(sc, models, view, scale, rotate, background)
    note = {"view": view, "px": list(img.size)}
    if out:
        p = artlib.ensure_parent(artlib.resolve_path(out))
        img.save(p)
        note["saved"] = str(p)
    return [Image(data=V.png_bytes(img), format="png"), _j(note)]


@tool(mcp)
def vox_save(scene: str, path: str) -> str:
    """Save scene as MagicaVoxel .vox (models, positions, palette, materials) + .vox.json sidecar with ramps."""
    return _j(V.save_vox(_scene(scene), artlib.resolve_path(path)))


@tool(mcp)
def vox_load(path: str, scene: str = "") -> str:
    """Load a .vox file (MagicaVoxel/Goxel/our own) into a scene for editing."""
    p = artlib.resolve_path(path)
    sc = V.load_vox(p, scene or p.stem)
    SCENES[sc.name] = sc
    return _j(sc.info())


@tool(mcp)
def vox_export(scene: str, path: str, models: list[str] | None = None, voxel_size: float = 0.1, pivot: str = "bottom_center") -> str:
    """Export a merged, face-optimized mesh: .glb (recommended: Unity glTFast, Godot, Unreal, Blender;
    emissive palette kept) or .obj (+ .mtl + palette PNG). Y-up, model front (-y) -> +Z.
    voxel_size in meters (0.1 = 10 voxels per meter; a 32-voxel human at 0.056 = 1.8 m).
    Use point/nearest filtering for the palette texture in the engine."""
    return _j(V.export_mesh(_scene(scene), artlib.resolve_path(path), models, voxel_size, pivot))


@tool(mcp)
def vox_undo(scene: str, model: str) -> str:
    """Undo the last change to a model (up to 6 steps)."""
    m = _scene(scene).model(model)
    return _j({"undone": m.undo(), **m.info()})


if __name__ == "__main__":
    mcp.run()
