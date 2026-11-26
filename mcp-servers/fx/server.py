"""gameforge-fx — MCP server for game VFX flipbooks and 2D art post-processing.

Run: bash scripts/run-mcp.sh fx   (stdio). Logic lives in fxcore.py.
"""
from __future__ import annotations

import glob
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

import artlib  # noqa: E402
import fxcore as F  # noqa: E402
from mcpcompat import Image, Server, tool  # noqa: E402

INSTRUCTIONS = """2D VFX & art finishing. fx_effect renders HDR particle/shader flipbooks (explosion, fire,
smoke, magic, slash, hit, lightning, portal, heal, sparkle) as sprite sheet + GIF + JSON, smooth or
pixel-art (shared limited palette, hard alpha, outline). fx_post finishes any sprite or sheet
(outline, selective outline, shadow, glow, rim light, grading, quantize+dither, pixelate).
fx_normal_map makes normal maps for 2D lights. fx_palette builds hue-shifted ramps and .gpl palettes
for Aseprite/GIMP. ALWAYS look at the returned preview and iterate (seed, colors, intensity,
frames) before calling it done."""

mcp = Server("gameforge-fx", instructions=INSTRUCTIONS)


def _png(img) -> Image:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Image(data=buf.getvalue(), format="png")


def _j(d) -> str:
    return json.dumps(d, ensure_ascii=False, default=str)


def _frames_of(path: str, frame_w: int, frame_h: int):
    img = F.load_rgba(path)
    if frame_w and frame_h:
        count = 0
        p = artlib.resolve_path(path)
        for side in (p.with_suffix(".json"), p.with_name(p.stem.removesuffix("_sheet") + ".json")):
            if side.exists():  # our sheets record the real frame count
                try:
                    count = int(json.loads(side.read_text()).get("count", 0))
                except (ValueError, OSError):
                    pass
                break
        return F.split_sheet(img, frame_w, frame_h, count), True
    return [img], False


@tool(mcp)
def fx_effect(kind: str, out_dir: str, name: str = "", frames: int = 0, size: int = 128, fps: int = 0, seed: int = 1, colors: list[str] | None = None, intensity: float = 1.0, loop: bool | None = None, style: str = "smooth", pixel: int = 4, palette_size: int = 10, palette: str | list[str] | None = None, dither: str = "bayer4", outline: str = "", background: str = "transparent", bloom: float = 0.7, alpha_cut: float = 0.25, scale: int = 1, columns: int = 0, post: list[dict] | None = None) -> list:
    """Render a VFX flipbook. kind: explosion | fire | smoke | magic | slash | hit | lightning | portal | heal | sparkle.
    colors: main color(s) hex — one color builds a dark->base->hot ramp (magic/slash/hit/portal/heal/sparkle);
      several = explicit gradient cold->hot (explosion/fire).
    size: frame px (smooth). style='pixel': render at `size`, downscale by `pixel` (128/4 = 32px frames),
      shared `palette_size`-color palette (or `palette`: hex list | 'auto:N' | 'ramp:#hex:6' | .gpl path),
      `dither` none|bayer4|bayer8 on alpha edges and colors, `outline` '' | 'auto' (selective) | '#hex',
      `alpha_cut` 0.1-0.5: lower keeps faint fading frames visible.
    background 'black' = for additive blend materials; default transparent alpha.
    scale = nearest upscale of exported frames. post = fx_post ops applied to every frame.
    Writes <name>_sheet.png, <name>.gif, <name>.json into out_dir; returns a preview to review."""
    fr, meta = F.render_effect(kind, frames, size, seed, colors, intensity, loop, background, bloom)
    if fps:
        meta["fps"] = int(fps)
    if style == "pixel":
        pal = F.parse_palette(palette, None) if palette and not (isinstance(palette, str) and palette.startswith("auto")) else None
        if isinstance(palette, str) and palette.startswith("auto:"):
            palette_size = int(palette.split(":")[1])
        fr, pal = F.pixelize(fr, pixel, palette_size, pal, dither, alpha_cut, outline or None)
        meta["palette"] = [artlib.rgb_to_hex(c) for c in pal]
    if post:
        fr = [F.apply_ops(f, post) for f in fr]
    info = F.write_effect(fr, meta, artlib.resolve_path(out_dir), name or f"{kind}_{seed}", scale, columns)
    return [_png(F.preview(fr, 1024, "#14161b")), _j(info)]


@tool(mcp)
def fx_post(input: str, output: str, ops: list[dict], frame_w: int = 0, frame_h: int = 0) -> list:
    """Post-process a sprite or sprite sheet (per frame if frame_w/frame_h given). ops, applied in order:
    {"op":"outline","color":"#1a1420","thickness":1,"mode":"outer|inner","selective":true}
    {"op":"shadow","offset":[2,2],"color":"#000000","alpha":0.5,"blur":1.5}
    {"op":"glow","color":null|"#hex","radius":4,"strength":1,"threshold":0}
    {"op":"rim","angle":45,"color":"#fff1c4","width":1,"strength":0.8}   (light from angle: 0 right, 90 top)
    {"op":"grade","brightness":0,"contrast":1,"saturation":1,"temperature":0,"tint":0,"gamma":1}
    {"op":"vignette","strength":0.35} {"op":"hue","degrees":20}
    {"op":"quantize","palette":"auto:16"|"ramp:#hex:6"|[hex,...]|"path.gpl","dither":"none|bayer4|bayer8|floyd"}
    {"op":"pixelate","factor":2,"keep_size":false} {"op":"upscale","factor":4}"""
    frames, is_sheet = _frames_of(input, frame_w, frame_h)
    out = [F.apply_ops(f, ops) for f in frames]
    if is_sheet:
        sheet, meta = F.make_sheet(out, columns=F.load_rgba(input).shape[1] // frame_w)
    else:
        sheet, meta = out[0], {}
    p = artlib.ensure_parent(artlib.resolve_path(output))
    F.to_pil(sheet).save(p, optimize=True)
    return [_png(F.preview(out, 1024)), _j({"saved": str(p), **meta, "lint": F.lint(sheet)})]


@tool(mcp)
def fx_normal_map(input: str, output: str, strength: float = 2.0, bevel: int = 3, detail: float = 0.5, flip_y: bool = False, frame_w: int = 0, frame_h: int = 0) -> list:
    """Normal map for 2D lighting (Unity URP 2D Lights secondary texture _NormalMap, Godot CanvasTexture
    normal). Bevel from the sprite silhouette + luminance detail. flip_y for DirectX-style engines."""
    frames, is_sheet = _frames_of(input, frame_w, frame_h)
    out = [F.normal_map(f, strength, bevel, detail, flip_y) for f in frames]
    sheet = F.make_sheet(out, columns=F.load_rgba(input).shape[1] // frame_w)[0] if is_sheet else out[0]
    p = artlib.ensure_parent(artlib.resolve_path(output))
    F.to_pil(sheet).save(p)
    return [_png(F.preview(out, 768)), _j({"saved": str(p)})]


@tool(mcp)
def fx_palette(action: str = "ramp", base: str = "", steps: int = 6, hue_shift: float = 25.0, bases: list[str] | None = None, image: str = "", n: int = 16, colors: list[str] | None = None, out: str = "", name: str = "gameforge") -> list:
    """Palettes for consistent art.
    action='ramp': hue-shifted ramp(s) from `base` (or several `bases`) — shadows cool, highlights warm.
    action='extract': `n` representative colors from `image` (OKLab k-means).
    action='save': write `colors` to `out` (.gpl for Aseprite/GIMP/Krita, .hex, or .png swatch).
    Returns hex list + swatch image."""
    if action == "ramp":
        cols = []
        for b in bases or [base]:
            cols += artlib.hue_ramp(b, steps, hue_shift)
        cols = np.array(cols, np.float32)
    elif action == "extract":
        img = F.load_rgba(image)
        cols = artlib.kmeans_palette(img[..., :3][img[..., 3] > 0.5], n)
    elif action == "save":
        cols = np.array([artlib.hex_to_rgb(c) for c in colors or []], np.float32)
    else:
        raise ValueError("action: ramp | extract | save")
    hexes = [artlib.rgb_to_hex(c) for c in cols]
    saved = None
    if out:
        p = artlib.ensure_parent(artlib.resolve_path(out))
        if p.suffix.lower() == ".gpl":
            artlib.write_gpl(p, cols, name)
        elif p.suffix.lower() == ".hex":
            p.write_text("\n".join(h[1:] for h in hexes) + "\n")
        else:
            F.to_pil(np.dstack([cols[None], np.ones((1, len(cols)))])).save(p)
        saved = str(p)
    per_row = steps if action == "ramp" else min(16, len(cols))
    rows = int(np.ceil(len(cols) / per_row))
    sw = np.zeros((rows, per_row, 4), np.float32)
    for i, c in enumerate(cols):
        sw[i // per_row, i % per_row] = [*c, 1]
    return [_png(F.to_pil(F.upscale(sw, 32))), _j({"colors": hexes, "saved": saved})]


@tool(mcp)
def fx_sheet(action: str, out: str, inputs: str = "", input: str = "", frame_w: int = 0, frame_h: int = 0, columns: int = 0, fps: int = 12, padding: int = 0) -> list:
    """Sprite sheets. action='pack': frames matching glob `inputs` (sorted) -> sheet `out` + .json.
    action='unpack': sheet `input` (frame_w x frame_h) -> numbered PNGs in folder `out`.
    action='gif': sheet `input` -> animated GIF `out` at fps (for review / devlogs)."""
    if action == "pack":
        files = sorted(glob.glob(str(artlib.resolve_path(inputs))))
        if not files:
            raise ValueError(f"no files match {inputs}")
        frames = [F.load_rgba(f) for f in files]
        sheet, meta = F.make_sheet(frames, columns, padding)
        p = artlib.ensure_parent(artlib.resolve_path(out))
        F.to_pil(sheet).save(p, optimize=True)
        p.with_suffix(".json").write_text(json.dumps({**meta, "fps": fps, "files": [Path(f).name for f in files]}, indent=1))
        return [_png(F.preview(frames, 1024)), _j({"saved": str(p), **meta})]
    frames = F.split_sheet(F.load_rgba(input), frame_w, frame_h)
    if action == "unpack":
        d = artlib.resolve_path(out)
        d.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(frames):
            F.to_pil(f).save(d / f"frame_{i:03d}.png")
        return [_png(F.preview(frames, 1024)), _j({"frames": len(frames), "dir": str(d)})]
    if action == "gif":
        p = artlib.ensure_parent(artlib.resolve_path(out))
        F.save_gif(frames, p, fps, scale=max(1, 128 // frame_w))
        return [_png(F.preview(frames, 1024)), _j({"saved": str(p), "frames": len(frames)})]
    raise ValueError("action: pack | unpack | gif")


@tool(mcp)
def fx_view(input: str, frame_w: int = 0, frame_h: int = 0, max_px: int = 1024, background: str = "checker") -> list:
    """Look at any image or sheet (Aseprite/GIMP exports included): zoomed nearest-neighbour preview on a
    checker background + pixel-art lint (colors, semi-transparent px, orphan pixels, bbox, tips)."""
    frames, _ = _frames_of(input, frame_w, frame_h)
    return [_png(F.preview(frames, max_px, background)), _j({"frames": len(frames), "lint": F.lint(F.load_rgba(input))})]


if __name__ == "__main__":
    mcp.run()
