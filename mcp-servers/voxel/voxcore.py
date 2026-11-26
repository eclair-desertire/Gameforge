"""GameForge voxel core: scenes, hue-shifted ramps, SDF-style shapes, procedural generators,
baked AO/edge shading, software preview renderer and MagicaVoxel .vox / OBJ / GLB IO.

Coordinates: x right, y depth, z up (MagicaVoxel convention). Characters face -y.
Each model is a dense uint8 grid of palette indices (0 = empty), at most 256 per axis.
"""
from __future__ import annotations

import io
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import artlib  # noqa: E402

MAX_DIM = 256
MAX_SHIFT = 4

# ============================================================ palette


class Palette:
    def __init__(self) -> None:
        self.colors = np.zeros((256, 3), dtype=np.float32)
        self.next = 1
        self.ramps: dict[str, list[int]] = {}
        self.singles: dict[str, int] = {}
        self.materials: dict[int, dict[str, str]] = {}
        self._lut: np.ndarray | None = None

    # ---- allocation
    def _alloc(self, n: int) -> list[int]:
        if self.next + n > 256:
            raise ValueError(f"palette full: {self.next - 1}/255 colors used; reuse ramps or use fewer steps")
        idx = list(range(self.next, self.next + n))
        self.next += n
        return idx

    def add_ramp(self, name: str, base: str | None = None, steps: int = 6, hue_shift: float = 25.0, colors: list[str] | None = None, contrast: float = 1.0) -> list[int]:
        if colors:
            rgb = [artlib.hex_to_rgb(c) for c in colors]
        else:
            if base is None:
                raise ValueError("add_ramp needs base or colors")
            rgb = artlib.hue_ramp(base, steps, hue_shift, contrast)
        if name in self.ramps and len(self.ramps[name]) == len(rgb):
            idx = self.ramps[name]
        else:
            idx = self._alloc(len(rgb))
        for i, c in zip(idx, rgb):
            self.colors[i] = c
        self.ramps[name] = idx
        self._lut = None
        return idx

    def ensure_ramp(self, name: str, base: str, steps: int = 6, hue_shift: float = 25.0) -> list[int]:
        """Use existing ramp `name`, or create it. If `base` is itself a ramp name, alias it."""
        if name in self.ramps:
            return self.ramps[name]
        if base in self.ramps:
            self.ramps[name] = self.ramps[base]
            self._lut = None
            return self.ramps[name]
        return self.add_ramp(name, base, steps, hue_shift)

    def single(self, hexcolor: str) -> int:
        key = artlib.rgb_to_hex(artlib.hex_to_rgb(hexcolor))
        if key not in self.singles:
            i = self._alloc(1)[0]
            self.colors[i] = artlib.hex_to_rgb(key)
            self.singles[key] = i
        return self.singles[key]

    def resolve(self, ref) -> int:
        """int index | '#hex' | 'ramp' (middle shade) | 'ramp:k' (k from 0 = darkest, negative from end)."""
        if isinstance(ref, (int, np.integer)):
            if not 1 <= int(ref) <= 255:
                raise ValueError("palette index must be 1..255")
            return int(ref)
        ref = str(ref).strip()
        if ref.isdigit():
            return self.resolve(int(ref))
        if ref.startswith("#"):
            return self.single(ref)
        name, _, k = ref.partition(":")
        if name not in self.ramps:
            raise ValueError(f"unknown ramp '{name}'. Known: {sorted(self.ramps)}; or pass '#rrggbb'")
        r = self.ramps[name]
        pos = len(r) // 2 if k == "" else int(k)
        return r[max(-len(r), min(len(r) - 1, pos))]

    def set_material(self, ref, kind: str, **props) -> list[int]:
        """kind: diffuse | metal | glass | emit. Applies to one index or a whole ramp (ref = ramp name)."""
        kinds = {"diffuse": "_diffuse", "metal": "_metal", "glass": "_glass", "emit": "_emit"}
        if kind not in kinds:
            raise ValueError(f"material kind must be one of {list(kinds)}")
        targets = self.ramps[ref] if isinstance(ref, str) and ref in self.ramps else [self.resolve(ref)]
        for i in targets:
            d = {"_type": kinds[kind]}
            if kind == "metal":
                d.update({"_metal": str(props.get("metal", 0.8)), "_rough": str(props.get("rough", 0.3))})
            elif kind == "glass":
                d.update({"_trans": str(props.get("trans", 0.5)), "_rough": str(props.get("rough", 0.05)), "_ior": str(props.get("ior", 1.5))})
            elif kind == "emit":
                d.update({"_emit": str(props.get("emit", 1.0)), "_flux": str(props.get("flux", 1)), "_ldr": "0"})
            self.materials[i] = d
        return targets

    # ---- ramp-aware shading
    def shift_lut(self) -> np.ndarray:
        """lut[d + MAX_SHIFT, idx] -> index shifted by d shades inside its ramp (unchanged if not in a ramp)."""
        if self._lut is None:
            lut = np.tile(np.arange(256, dtype=np.uint8), (2 * MAX_SHIFT + 1, 1))
            for r in self.ramps.values():
                for p, i in enumerate(r):
                    for d in range(-MAX_SHIFT, MAX_SHIFT + 1):
                        lut[d + MAX_SHIFT, i] = r[max(0, min(len(r) - 1, p + d))]
            self._lut = lut
        return self._lut

    def ramp_mask(self, vox: np.ndarray, name: str) -> np.ndarray:
        return np.isin(vox, np.array(self.ramps[name], dtype=np.uint8))

    def emissive_indices(self) -> set[int]:
        return {i for i, m in self.materials.items() if m.get("_type") == "_emit"}

    def to_json(self) -> dict:
        return {
            "colors": {str(i): artlib.rgb_to_hex(self.colors[i]) for i in range(1, self.next)},
            "next": self.next,
            "ramps": self.ramps,
            "singles": self.singles,
            "materials": {str(k): v for k, v in self.materials.items()},
        }

    def load_json(self, d: dict) -> None:
        for k, v in d.get("colors", {}).items():
            self.colors[int(k)] = artlib.hex_to_rgb(v)
        self.next = int(d.get("next", self.next))
        self.ramps = {k: [int(i) for i in v] for k, v in d.get("ramps", {}).items()}
        self.singles = {k: int(v) for k, v in d.get("singles", {}).items()}
        self.materials = {int(k): v for k, v in d.get("materials", {}).items()}
        self._lut = None


# ============================================================ scene


class Model:
    def __init__(self, name: str, size, pos=(0, 0, 0)) -> None:
        sx, sy, sz = (int(v) for v in size)
        if not all(1 <= v <= MAX_DIM for v in (sx, sy, sz)):
            raise ValueError(f"model size must be 1..{MAX_DIM} per axis (MagicaVoxel limit); split big scenes into several models")
        self.name = name
        self.vox = np.zeros((sx, sy, sz), dtype=np.uint8)
        self.pos = [int(v) for v in pos]
        self._history: list[np.ndarray] = []

    def snapshot(self) -> None:
        self._history.append(self.vox.copy())
        if len(self._history) > 6:
            self._history.pop(0)

    def undo(self) -> bool:
        if not self._history:
            return False
        self.vox = self._history.pop()
        return True

    @property
    def size(self):
        return list(self.vox.shape)

    def info(self) -> dict:
        nz = np.argwhere(self.vox)
        bbox = None if len(nz) == 0 else [nz.min(0).tolist(), nz.max(0).tolist()]
        return {"name": self.name, "size": self.size, "pos": self.pos, "voxels": int(len(nz)), "bbox": bbox}


class Scene:
    def __init__(self, name: str) -> None:
        self.name = name
        self.palette = Palette()
        self.models: dict[str, Model] = {}

    def model(self, name: str) -> Model:
        if name not in self.models:
            raise ValueError(f"no model '{name}' in scene '{self.name}'. Models: {list(self.models)}")
        return self.models[name]

    def add_model(self, name: str, size, pos=(0, 0, 0)) -> Model:
        m = Model(name, size, pos)
        self.models[name] = m
        return m

    def info(self) -> dict:
        p = self.palette
        return {
            "scene": self.name,
            "models": [m.info() for m in self.models.values()],
            "palette_used": p.next - 1,
            "ramps": {k: [artlib.rgb_to_hex(p.colors[i]) for i in v] for k, v in p.ramps.items()},
            "materials": {str(k): v["_type"] for k, v in p.materials.items()},
        }

    def composite(self, names: list[str] | None = None):
        """Merge models into one world grid. Returns (grid, world_origin)."""
        ms = [self.model(n) for n in names] if names else list(self.models.values())
        if not ms:
            raise ValueError("scene has no models")
        lo = np.min([m.pos for m in ms], axis=0)
        hi = np.max([np.add(m.pos, m.size) for m in ms], axis=0)
        dims = hi - lo
        if np.prod(dims) > 600_000_000:
            raise ValueError("world too large to composite; render/export fewer models")
        grid = np.zeros(tuple(int(d) for d in dims), dtype=np.uint8)
        for m in ms:
            o = np.subtract(m.pos, lo)
            view = grid[o[0] : o[0] + m.size[0], o[1] : o[1] + m.size[1], o[2] : o[2] + m.size[2]]
            np.copyto(view, m.vox, where=m.vox > 0)
        return grid, lo


# ============================================================ shapes


def _bbox(m: Model, lo, hi):
    lo = np.maximum(np.floor(np.asarray(lo, dtype=np.float64)).astype(int), 0)
    hi = np.minimum(np.ceil(np.asarray(hi, dtype=np.float64)).astype(int) + 1, m.size)
    if np.any(hi <= lo):
        return None
    sl = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
    g = np.meshgrid(*[np.arange(a, b, dtype=np.float32) for a, b in zip(lo, hi)], indexing="ij")
    return sl, g


def _apply(m: Model, sl, mask: np.ndarray, mode: str, idx: int) -> int:
    sub = m.vox[sl]
    if mode == "add":
        sub[mask] = idx
    elif mode == "subtract":
        mask = mask & (sub > 0)
        sub[mask] = 0
    elif mode == "paint":
        mask = mask & (sub > 0)
        sub[mask] = idx
    elif mode == "fill_empty":
        mask = mask & (sub == 0)
        sub[mask] = idx
    else:
        raise ValueError("mode must be add | subtract | paint | fill_empty")
    return int(mask.sum())


def _rough(g, scale: float, roughness: float, seed: int):
    if roughness <= 0:
        return 0.0
    pts = np.stack(g, -1) / max(scale, 1e-3)
    return (artlib.fbm(pts, seed, 3) - 0.5) * 2.0 * roughness


def shape_box(m: Model, lo, hi, idx: int, mode="add", hollow: int = 0) -> int:
    r = _bbox(m, lo, np.asarray(hi))
    if r is None:
        return 0
    sl, g = r
    mask = np.ones(g[0].shape, dtype=bool)
    lo_i, hi_i = np.asarray(lo), np.asarray(hi)
    mask &= (g[0] >= lo_i[0]) & (g[0] <= hi_i[0]) & (g[1] >= lo_i[1]) & (g[1] <= hi_i[1]) & (g[2] >= lo_i[2]) & (g[2] <= hi_i[2])
    if hollow > 0:
        inner = (
            (g[0] >= lo_i[0] + hollow) & (g[0] <= hi_i[0] - hollow) & (g[1] >= lo_i[1] + hollow) & (g[1] <= hi_i[1] - hollow) & (g[2] >= lo_i[2] + hollow) & (g[2] <= hi_i[2] - hollow)
        )
        mask &= ~inner
    return _apply(m, sl, mask, mode, idx)


def shape_ellipsoid(m: Model, center, radii, idx: int, mode="add", roughness=0.0, seed=0, power=2.0) -> int:
    c, r = np.asarray(center, float), np.maximum(np.asarray(radii, float), 0.5)
    res = _bbox(m, c - r * (1 + roughness) - 1, c + r * (1 + roughness) + 1)
    if res is None:
        return 0
    sl, g = res
    d = sum(np.abs((g[i] - c[i]) / r[i]) ** power for i in range(3)) ** (1.0 / power)
    d = d + _rough(g, float(np.mean(r)) * 0.6, roughness, seed)
    return _apply(m, sl, d <= 1.0, mode, idx)


def shape_capsule(m: Model, p0, p1, r0: float, r1: float, idx: int, mode="add", roughness=0.0, seed=0) -> int:
    a, b = np.asarray(p0, float), np.asarray(p1, float)
    rmax = max(r0, r1) * (1 + roughness) + 1
    res = _bbox(m, np.minimum(a, b) - rmax, np.maximum(a, b) + rmax)
    if res is None:
        return 0
    sl, g = res
    ab = b - a
    L2 = float(ab @ ab) or 1e-6
    t = np.clip(((g[0] - a[0]) * ab[0] + (g[1] - a[1]) * ab[1] + (g[2] - a[2]) * ab[2]) / L2, 0, 1)
    dist = np.sqrt(sum((g[i] - (a[i] + t * ab[i])) ** 2 for i in range(3)))
    rad = r0 + (r1 - r0) * t
    dist = dist / np.maximum(rad, 0.5) + _rough(g, max(r0, r1, 1.0), roughness, seed)
    return _apply(m, sl, dist <= 1.0, mode, idx)


def shape_cylinder(m: Model, base, radius: float, height: float, idx: int, mode="add", radius_top: float | None = None, axis="z", roughness=0.0, seed=0) -> int:
    ax = "xyz".index(axis)
    b = np.asarray(base, float)
    rt = radius if radius_top is None else radius_top
    rmax = max(radius, rt) * (1 + roughness) + 1
    lo, hi = b - rmax, b + rmax
    lo[ax], hi[ax] = b[ax], b[ax] + height - 1
    res = _bbox(m, lo, hi)
    if res is None:
        return 0
    sl, g = res
    others = [i for i in range(3) if i != ax]
    t = np.clip((g[ax] - b[ax]) / max(height - 1, 1), 0, 1)
    rad = np.maximum(radius + (rt - radius) * t, 0.35)
    d = np.sqrt(sum((g[i] - b[i]) ** 2 for i in others)) / rad + _rough(g, max(radius, 1.0), roughness, seed)
    mask = (d <= 1.0) & (g[ax] >= b[ax]) & (g[ax] <= b[ax] + height - 1)
    return _apply(m, sl, mask, mode, idx)


# ============================================================ detail & shading


def _surface(vox: np.ndarray) -> np.ndarray:
    filled = vox > 0
    p = np.pad(filled, 1, constant_values=False)
    empty_nb = np.zeros_like(filled)
    for ax in range(3):
        for s in (1, -1):
            empty_nb |= ~np.roll(p, s, axis=ax)[1:-1, 1:-1, 1:-1]
    return filled & empty_nb


def noise_shade(scene: Scene, m: Model, ramp: str = "*", scale: float = 4.0, strength: float = 1.0, seed: int = 0) -> int:
    """Vary shades inside ramps with 3D fbm noise (stone, bark, foliage, plaster)."""
    pal = scene.palette
    mask = (m.vox > 0) if ramp == "*" else pal.ramp_mask(m.vox, ramp)
    pts = np.argwhere(mask)
    if len(pts) == 0:
        return 0
    n = artlib.fbm(pts.astype(np.float32) / max(scale, 0.5), seed, 3)
    delta = np.clip(np.round((n - 0.5) * 2.5 * strength), -MAX_SHIFT, MAX_SHIFT).astype(int)
    lut = pal.shift_lut()
    cur = m.vox[mask]
    m.vox[mask] = lut[delta + MAX_SHIFT, cur]
    return int(len(pts))


def erode(m: Model, amount: float = 0.25, scale: float = 2.0, seed: int = 0, iterations: int = 1, only_idx: np.ndarray | None = None) -> int:
    """Chip random surface voxels for a weathered / organic silhouette."""
    removed = 0
    for it in range(max(1, iterations)):
        surf = _surface(m.vox)
        if only_idx is not None:
            surf &= np.isin(m.vox, only_idx)
        pts = np.argwhere(surf)
        if len(pts) == 0:
            break
        n = artlib.fbm(pts.astype(np.float32) / max(scale, 0.5), seed + it * 7, 2)
        kill = pts[n < amount]
        m.vox[tuple(kill.T)] = 0
        removed += len(kill)
    return removed


def scatter(scene: Scene, m: Model, color: str, density: float = 0.3, on: str = "top", scale: float = 3.0, height: int = 1, seed: int = 0) -> int:
    """Grow moss/grass/snow/debris onto exposed faces. color may be a ramp name (random light shades)."""
    pal = scene.palette
    filled = m.vox > 0
    rng = np.random.default_rng(seed)
    if on == "top":
        below = np.zeros_like(filled)
        below[:, :, 1:] = filled[:, :, :-1]
        cand = ~filled & below
    elif on == "sides":
        nb = np.zeros_like(filled)
        nb[1:] |= filled[:-1]
        nb[:-1] |= filled[1:]
        nb[:, 1:] |= filled[:, :-1]
        nb[:, :-1] |= filled[:, 1:]
        cand = ~filled & nb
    else:
        raise ValueError("on must be top | sides")
    pts = np.argwhere(cand)
    if len(pts) == 0:
        return 0
    n = artlib.fbm(pts.astype(np.float32) / max(scale, 0.5), seed, 3)
    keep = pts[(n > 1.0 - density) | (rng.random(len(pts)) < density * 0.08)]
    name = color.partition(":")[0]
    shades = pal.ramps[name][len(pal.ramps[name]) // 2 :] if name in pal.ramps and ":" not in color else [pal.resolve(color)]
    placed = 0
    for x, y, z in keep:
        h = 1 + (rng.integers(0, height) if height > 1 else 0)
        for k in range(h):
            zz = z + k
            if zz >= m.size[2] or m.vox[x, y, zz]:
                break
            m.vox[x, y, zz] = shades[rng.integers(0, len(shades))]
            placed += 1
    return placed


def shade(scene: Scene, m: Model, ao: float = 1.0, edges: float = 1.0, top: float = 0.0, radius: int = 2) -> int:
    """Bake ambient occlusion (darker crevices), edge highlights (lighter convex edges) and
    optional sky light into ramp shades. Run once, after geometry is final."""
    filled = (m.vox > 0).astype(np.float32)
    occ = filled
    for ax in range(3):
        occ = artlib.box_blur(occ, radius, ax)
    surf = _surface(m.vox)
    pts = surf
    f = occ[pts]  # fraction of filled neighbourhood
    delta = np.zeros(f.shape, dtype=np.int32)
    delta -= np.round(ao * np.clip((f - 0.6) / 0.14, 0, 2.5)).astype(np.int32)
    delta += (edges > 0) * np.round(edges * (f < 0.34)).astype(np.int32)
    if top:
        above_empty = np.ones_like(m.vox, dtype=bool)
        above_empty[:, :, :-1] = m.vox[:, :, 1:] == 0
        delta += np.round(top * above_empty[pts]).astype(np.int32)
    delta = np.clip(delta, -MAX_SHIFT, MAX_SHIFT)
    lut = scene.palette.shift_lut()
    m.vox[pts] = lut[delta + MAX_SHIFT, m.vox[pts]]
    return int(pts.sum())


def mirror(m: Model, axis: str = "x", keep: str = "low") -> None:
    ax = "xyz".index(axis)
    v = np.moveaxis(m.vox, ax, 0)
    n = v.shape[0]
    half = n // 2
    if keep == "low":
        v[n - half :] = v[:half][::-1]
    else:
        v[:half] = v[n - half :][::-1]


def stamp(src: Model, dst: Model, offset, rotate: int = 0, flip_x: bool = False, overwrite: bool = True) -> int:
    a = src.vox
    if flip_x:
        a = a[::-1]
    a = np.rot90(a, k=rotate % 4, axes=(0, 1))
    o = np.asarray(offset, int)
    lo = np.maximum(o, 0)
    hi = np.minimum(o + a.shape, dst.size)
    if np.any(hi <= lo):
        return 0
    s_lo, s_hi = lo - o, hi - o
    srcv = a[s_lo[0] : s_hi[0], s_lo[1] : s_hi[1], s_lo[2] : s_hi[2]]
    dv = dst.vox[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
    where = srcv > 0 if overwrite else (srcv > 0) & (dv == 0)
    np.copyto(dv, srcv, where=where)
    return int(where.sum())


# ============================================================ generators


def _ramp(pal: Palette, role: str, color: str, steps: int = 6, hue_shift: float = 25.0) -> list[int]:
    """Ramp for a role. `color` may be an existing ramp name or a hex color; each distinct hex
    gets its own ramp (role_rrggbb), so several characters/buildings keep their own colors."""
    if color in pal.ramps:
        return pal.ramps[color]
    name = f"{role}_{artlib.rgb_to_hex(artlib.hex_to_rgb(color))[1:]}"
    return pal.ensure_ramp(name, color, steps, hue_shift)


def _rname(pal: Palette, idx: list[int]) -> str:
    return next(k for k, v in pal.ramps.items() if v is idx or v == idx)

STYLE_COLORS = {
    "brick": {"wall": "#9a4a37", "trim": "#d8cbb0", "roof": "#5a3b34"},
    "plaster": {"wall": "#d9c7a0", "trim": "#f0ead8", "roof": "#8a4b3a"},
    "concrete": {"wall": "#9c9a94", "trim": "#c9c6bd", "roof": "#4f5257"},
    "wood": {"wall": "#8a5a36", "trim": "#cdb48a", "roof": "#3f4a3a"},
    "stone": {"wall": "#8d8576", "trim": "#bdb3a0", "roof": "#454b55"},
}


def gen_building(scene: Scene, m: Model, origin=(0, 0, 0), width=20, depth=14, floors=3, floor_h=7, style="brick", roof="gable", seed=0, window_w=3, window_h=4, window_gap=3, balconies=0.3, shop=False, lit=0.0, wall=None, trim=None, roof_color=None, glass="#5d7f99", details=True, person_height=None) -> dict:
    """Detailed modular building: plinth, string courses, quoins, recessed windows with frames,
    sills and lintels, door with steps, balconies, cornice, gable/hip/flat roof with chimney or roof
    equipment. Footprint is width x depth walls plus 1 voxel margin for protrusions."""
    if person_height:  # match the scale of characters made with gen_character(height=person_height)
        ph = float(person_height)
        floor_h = max(6, round(ph * 1.25))
        window_w = max(2, round(ph * 0.28))
        window_h = max(3, round(ph * 0.5))
        window_gap = max(2, round(ph * 0.3))
    rng = np.random.default_rng(seed)
    pal = scene.palette
    sc = STYLE_COLORS.get(style, STYLE_COLORS["brick"])
    R = {
        "wall": _ramp(pal, "wall", wall or sc["wall"], 6),
        "trim": _ramp(pal, "trim", trim or sc["trim"], 5, 15),
        "roof": _ramp(pal, "roof", roof_color or sc["roof"], 6),
        "glass": _ramp(pal, "glass", glass, 4, 30),
        "frame": pal.ensure_ramp("frame_dark", "#3b3530", 4),
        "door": pal.ensure_ramp("door_wood", "#5e3d26", 5),
        "metal": pal.ensure_ramp("metal", "#6f7680", 5, 10),
    }
    pal.set_material(_rname(pal, R["glass"]), "glass", trans=0.35)
    if lit > 0:
        R["lit"] = pal.ensure_ramp("glass_lit", "#ffcf7a", 3, 15)
        pal.set_material("glass_lit", "emit", emit=0.8)
    ox, oy, oz = (int(v) for v in origin)
    W, D, F, FH = int(width), int(depth), int(floors), int(floor_h)
    H = F * FH + 1
    x0, x1, y0, y1 = ox + 1, ox + W, oy + 1, oy + D  # wall outer faces (inclusive)
    need = (ox + W + 2, oy + D + 2, oz + H + (min(W, D) // 2 + 4 if roof != "flat" else 12))
    if any(n > s for n, s in zip(need, m.size)):
        raise ValueError(f"model too small for this building: need at least {list(need)}, have {m.size}")
    wall_mid = R["wall"][len(R["wall"]) // 2]
    trim_mid = R["trim"][len(R["trim"]) // 2]
    # shell (2 thick) + floor slabs
    shape_box(m, (x0, y0, oz), (x1, y1, oz + H - 1), wall_mid, hollow=2)
    for f in range(F + 1):
        shape_box(m, (x0 + 2, y0 + 2, oz + f * FH), (x1 - 2, y1 - 2, oz + f * FH), R["trim"][0])
    # brick / plank texture
    shell = m.vox == wall_mid
    pts = np.argwhere(shell)
    if style == "brick":
        u = pts[:, 0] + pts[:, 1]
        brick = (u + (pts[:, 2] % 2) * 2) // 4 + pts[:, 2] * 131
        d = np.array([-1, 0, 0, 1, 0, -1, 1, 0])[(brick * 2654435761 % 2**32) % 8]
    elif style == "wood":
        d = np.where(pts[:, 2] % 3 == 0, -1, 0) + np.array([0, 0, 1, 0, -1])[(pts[:, 0] * 7 + pts[:, 1] * 13 + pts[:, 2] // 3 * 5) % 5]
    else:
        d = np.round((artlib.fbm(pts.astype(np.float32) / 3.0, seed, 3) - 0.5) * 2.2).astype(int)
    m.vox[tuple(pts.T)] = pal.shift_lut()[np.clip(d, -2, 2) + MAX_SHIFT, wall_mid]
    # plinth
    shape_box(m, (x0 - 1, y0 - 1, oz), (x1 + 1, y1 + 1, oz + 1), R["trim"][1])
    shape_box(m, (x0 + 1, y0 + 1, oz), (x1 - 1, y1 - 1, oz + 1), R["trim"][1], mode="paint")
    # string courses between floors
    for f in range(1, F):
        z = oz + f * FH
        shape_box(m, (x0 - 1, y0 - 1, z), (x1 + 1, y1 + 1, z), trim_mid)
        shape_box(m, (x0, y0, z), (x1, y1, z), trim_mid)
    # quoins
    if details and style in ("brick", "stone", "plaster"):
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            for z in range(oz + 2, oz + H - 1, 2):
                if (z - oz) % FH == 0:
                    continue
                L = 2 if ((z - oz) // 2) % 2 == 0 else 1
                sx = 1 if cx == x0 else -1
                sy = 1 if cy == y0 else -1
                shape_box(m, (min(cx, cx + sx * L), cy, z), (max(cx, cx + sx * L), cy, z), R["trim"][-2])
                shape_box(m, (cx, min(cy, cy + sy * L), z), (cx, max(cy, cy + sy * L), z), R["trim"][-2])

    facades = [  # (axis along, fixed coord, outward normal sign, axis normal)
        ("x", y0, -1, "y"),  # front (-y)
        ("x", y1, 1, "y"),  # back
        ("y", x0, -1, "x"),  # left
        ("y", x1, 1, "x"),  # right
    ]
    windows = 0
    for fi, (along, fixed, sign, nrm) in enumerate(facades):
        a0, a1 = (x0, x1) if along == "x" else (y0, y1)
        span = a1 - a0 + 1 - 4
        n = max(0, (span + window_gap) // (window_w + window_gap))
        if n == 0:
            continue
        used = n * window_w + (n - 1) * window_gap
        start = a0 + 2 + (span - used) // 2
        for f in range(F):
            zb = oz + f * FH + 2
            is_ground_front = f == 0 and fi == 0
            slots = list(range(n))
            door_slot = n // 2 if is_ground_front else None
            for k in slots:
                a = start + k * (window_w + window_gap)
                if k == door_slot:
                    _door(m, R, along, fixed, sign, a, window_w, oz + 1, FH - 2, shop)
                    continue
                ww, wh = window_w, window_h
                if is_ground_front and shop:
                    ww, wh = window_w + window_gap - 1, FH - 3
                    a -= (window_gap - 1) // 2
                glass_idx = R["glass"]
                if lit > 0 and rng.random() < lit:
                    glass_idx = R["lit"]
                _window(m, R, along, fixed, sign, nrm, a, zb, ww, wh, glass_idx, rng, details)
                windows += 1
                if details and f >= 1 and fi == 0 and rng.random() < balconies:
                    _balcony(m, R, along, fixed, sign, a - 1, a + ww, zb - 1)
        if fi == 0 and shop:
            # awning over the ground floor shop front
            z = oz + FH - 1
            stripe = pal.ensure_ramp("awning", "#b8413a", 4)
            for k in range(3):
                for aa in range(a0, a1 + 1):
                    col = stripe[2] if (aa // 2) % 2 == 0 else R["trim"][-1]
                    p = _fpt(along, aa, fixed + sign * (k + 1), z - k)
                    if _inside(m, p):
                        m.vox[p] = col

    # cornice
    zt = oz + H - 1
    shape_box(m, (x0 - 1, y0 - 1, zt), (x1 + 1, y1 + 1, zt), trim_mid)
    shape_box(m, (x0 - 1, y0 - 1, zt - 1), (x1 + 1, y1 + 1, zt - 1), R["trim"][1], mode="fill_empty")
    shape_box(m, (x0, y0, zt - 1), (x1, y1, zt - 1), R["trim"][1], mode="paint")
    _roof(scene, m, R, roof, x0, x1, y0, y1, zt + 1, rng, details)
    return {"footprint": [x0, y0, x1, y1], "height": H, "windows": windows, "ramps": list(R)}


def _fpt(along, a, n, z):
    return (a, n, z) if along == "x" else (n, a, z)


def _inside(m: Model, p) -> bool:
    return all(0 <= p[i] < m.size[i] for i in range(3))


def _set(m: Model, p, idx) -> None:
    if _inside(m, p):
        m.vox[p] = idx


def _window(m, R, along, fixed, sign, nrm, a, zb, ww, wh, glass, rng, details):
    inward = -sign
    for da in range(ww):
        for dz in range(wh):
            _set(m, _fpt(along, a + da, fixed, zb + dz), 0)  # carve outer layer
            n = len(glass)
            g = glass[min(1, n - 1)] if dz >= wh - 1 else glass[min(n - 1, 2 if (da + dz) % 3 else 3)]
            _set(m, _fpt(along, a + da, fixed + inward, zb + dz), g)  # recessed glass
    if ww >= 3:
        for dz in range(wh):
            _set(m, _fpt(along, a + ww // 2, fixed + inward, zb + dz), R["frame"][1])  # mullion
    if wh >= 4:
        for da in range(ww):
            _set(m, _fpt(along, a + da, fixed + inward, zb + wh // 2), R["frame"][1])  # transom
    for da in range(-1, ww + 1):
        _set(m, _fpt(along, a + da, fixed + sign, zb - 1), R["trim"][2])  # sill
        _set(m, _fpt(along, a + da, fixed, zb + wh), R["trim"][-2])  # lintel
    if details:
        for dz in range(wh):  # side frames, every other window gets shutters
            _set(m, _fpt(along, a - 1, fixed, zb + dz), R["trim"][-2])
            _set(m, _fpt(along, a + ww, fixed, zb + dz), R["trim"][-2])


def _door(m, R, along, fixed, sign, a, w, zb, h, shop):
    inward = -sign
    w = max(2, w)
    h = max(3, h - h // 5)
    for da in range(w):
        for dz in range(h):
            _set(m, _fpt(along, a + da, fixed, zb + dz), 0)
            panel = R["door"][1 if (dz % 3 == 0) else 2]
            _set(m, _fpt(along, a + da, fixed + inward, zb + dz), R["glass"][2] if (shop and dz > 1) else panel)
    _set(m, _fpt(along, a + w - 1, fixed + inward, zb + h // 2), R["metal"][-1])  # handle
    for da in range(-1, w + 1):
        _set(m, _fpt(along, a + da, fixed, zb + h), R["trim"][-1])
        _set(m, _fpt(along, a + da, fixed + sign, zb - 1), R["trim"][2])  # step
    for dz in range(h + 1):
        _set(m, _fpt(along, a - 1, fixed + sign, zb + dz), R["trim"][-2])
        _set(m, _fpt(along, a + w, fixed + sign, zb + dz), R["trim"][-2])


def _balcony(m, R, along, fixed, sign, a0, a1, z):
    for da in range(a0, a1 + 1):
        for k in (1, 2):
            _set(m, _fpt(along, da, fixed + sign * k, z), R["trim"][1])
        if (da - a0) % 2 == 0 or da == a1:
            for dz in (1, 2):
                _set(m, _fpt(along, da, fixed + sign * 2, z + dz), R["metal"][1])
        _set(m, _fpt(along, da, fixed + sign * 2, z + 3), R["metal"][2])
    for dz in (1, 2, 3):
        _set(m, _fpt(along, a0, fixed + sign, z + dz), R["metal"][1])
        _set(m, _fpt(along, a1, fixed + sign, z + dz), R["metal"][1])


def _roof(scene, m, R, kind, x0, x1, y0, y1, z, rng, details):
    roof = R["roof"]
    if kind == "flat":
        shape_box(m, (x0, y0, z), (x1, y1, z), R["trim"][1], hollow=0)
        shape_box(m, (x0, y0, z + 1), (x1, y1, z + 1), R["trim"][2], hollow=1)
        shape_box(m, (x0 + 1, y0 + 1, z), (x1 - 1, y1 - 1, z), roof[1])
        if details:
            cx, cy = x0 + (x1 - x0) // 3, y0 + (y1 - y0) // 2
            for lx in (-1, 1):
                for ly in (-1, 1):
                    shape_box(m, (cx + lx * 2, cy + ly * 2, z + 1), (cx + lx * 2, cy + ly * 2, z + 3), R["metal"][0])
            shape_cylinder(m, (cx, cy, z + 4), 3.2, 5, R["door"][2])
            shape_box(m, (cx - 3, cy, z + 9), (cx + 3, cy, z + 9), R["door"][1], mode="fill_empty")
            for _ in range(2):
                vx = int(rng.integers(x0 + 2, x1 - 3))
                vy = int(rng.integers(y0 + 2, y1 - 3))
                shape_box(m, (vx, vy, z + 1), (vx + 2, vy + 1, z + 2), R["metal"][2])
                _set(m, (vx + 1, vy, z + 2), R["metal"][0])
        return
    ridge_x = (x1 - x0) >= (y1 - y0)
    lo_a, hi_a = (y0 - 1, y1 + 1) if ridge_x else (x0 - 1, x1 + 1)
    lo_b, hi_b = (x0 - 1, x1 + 1) if ridge_x else (y0 - 1, y1 + 1)
    k = 0
    while lo_a + k <= hi_a - k:
        a0, a1 = lo_a + k, hi_a - k
        b0, b1 = (lo_b + k, hi_b - k) if kind == "hip" else (lo_b, hi_b)
        if b0 > b1:
            break
        col = roof[1 + (k % 2)] if a1 - a0 > 1 else roof[-2]
        if ridge_x:
            shape_box(m, (b0, a0, z + k), (b1, a1, z + k), col)
        else:
            shape_box(m, (a0, b0, z + k), (a1, b1, z + k), col)
        if kind == "gable":  # gable walls under the roof
            if ridge_x:
                shape_box(m, (x0, a0 + 1, z + k), (x0, a1 - 1, z + k), R["wall"][2])
                shape_box(m, (x1, a0 + 1, z + k), (x1, a1 - 1, z + k), R["wall"][2])
            else:
                shape_box(m, (a0 + 1, y0, z + k), (a1 - 1, y0, z + k), R["wall"][2])
                shape_box(m, (a0 + 1, y1, z + k), (a1 - 1, y1, z + k), R["wall"][2])
        k += 1
    # hollow the roof interior a bit so it stays a shell (lighter files, clean AO)
    if details:
        cx = x0 + (x1 - x0) * 3 // 4
        cy = y0 + (y1 - y0) // 3
        shape_box(m, (cx, cy, z), (cx + 1, cy + 1, z + k + 1), R["wall"][1])
        shape_box(m, (cx - 1, cy - 1, z + k + 1), (cx + 2, cy + 2, z + k + 1), R["trim"][1])


def gen_tree(scene: Scene, m: Model, base=(16, 16, 0), kind="oak", height=28, seed=0, trunk=None, leaves=None) -> dict:
    """Organic tree: tapered trunk with root flare, recursive branches and noisy foliage clusters.
    kind: oak | pine | birch | dead."""
    rng = np.random.default_rng(seed)
    pal = scene.palette
    bark = _ramp(pal, "bark", trunk or {"birch": "#d8d2c4"}.get(kind, "#5b4030"), 5)
    leaf = _ramp(pal, "leaves", leaves or {"pine": "#2f5d3a", "birch": "#8fb34d"}.get(kind, "#4f7f35"), 6, 30)
    bark_n, leaf_n = _rname(pal, bark), _rname(pal, leaf)
    bx, by, bz = (float(v) for v in base)
    H = float(height)
    r0 = max(1.0, H / 14)
    top = np.array([bx + rng.normal(0, H * 0.04), by + rng.normal(0, H * 0.04), bz + H * (0.9 if kind == "pine" else 0.6)])
    shape_capsule(m, (bx, by, bz), top, r0, r0 * 0.45, bark[2], roughness=0.15, seed=seed)
    for i in range(4):  # root flare
        ang = i * math.pi / 2 + rng.uniform(-0.4, 0.4)
        shape_capsule(m, (bx, by, bz + r0), (bx + math.cos(ang) * r0 * 2.4, by + math.sin(ang) * r0 * 2.4, bz), r0 * 0.6, 0.6, bark[1])
    tips = []
    if kind == "pine":
        layers = max(4, int(H / 4))
        for i in range(layers):
            t = i / layers
            z = bz + H * (0.22 + 0.72 * t)
            rad = (1 - t) * H * 0.3 + 1.2
            shape_cylinder(m, (bx, by, z), rad, max(2, H * 0.16), leaf[2], radius_top=rad * 0.25, roughness=0.25, seed=seed + i)
        shape_cylinder(m, (top[0], top[1], bz + H * 0.9), 1.4, H * 0.14, leaf[3], radius_top=0.3)
    else:

        def branch(p, d, length, rad, depth):
            end = p + d * length
            shape_capsule(m, p, end, rad, max(0.5, rad * 0.6), bark[2])
            if depth == 0:
                tips.append(end)
                return
            for _ in range(2 if depth > 1 else 3):
                nd = d + rng.normal(0, 0.55, 3)
                nd[2] = abs(nd[2]) + 0.35
                nd /= np.linalg.norm(nd)
                branch(end, nd, length * 0.68, max(0.5, rad * 0.62), depth - 1)

        nb = 4 if kind != "birch" else 3
        for i in range(nb):
            ang = i * 2 * math.pi / nb + rng.uniform(-0.5, 0.5)
            start = np.array([bx, by, bz]) + (top - np.array([bx, by, bz])) * rng.uniform(0.55, 0.95)
            d = np.array([math.cos(ang), math.sin(ang), rng.uniform(0.5, 1.1)])
            d /= np.linalg.norm(d)
            branch(start, d, H * 0.26, r0 * 0.6, 2 if kind != "dead" else 3)
        tips.append(top)
        if kind != "dead":
            cr = H * (0.17 if kind == "oak" else 0.12)
            for j, tp in enumerate(tips):
                rr = cr * rng.uniform(0.7, 1.15)
                shape_ellipsoid(m, tp + np.array([0, 0, rr * 0.25]), (rr, rr, rr * 0.75), leaf[2], roughness=0.35, seed=seed + j * 3)
    if kind == "birch":  # dark birch markings
        pts = np.argwhere(pal.ramp_mask(m.vox, bark_n))
        if len(pts):
            n = artlib.value_noise(pts[:, [0, 2]].astype(np.float32) * np.array([0.9, 0.45], np.float32), seed)
            dark = pts[n > 0.72]
            m.vox[tuple(dark.T)] = pal.resolve("#2b2622")
    if kind != "dead":
        erode(m, 0.3, 1.5, seed, 1, only_idx=np.array(leaf, dtype=np.uint8))
        noise_shade(scene, m, leaf_n, 3.0, 1.0, seed)
    noise_shade(scene, m, bark_n, 2.0, 0.8, seed + 1)
    return {"tips": len(tips), "ramps": [bark_n, leaf_n]}


def gen_rock(scene: Scene, m: Model, center=(8, 8, 0), size=8.0, seed=0, color="#7d7a72", moss: float = 0.0) -> dict:
    pal = scene.palette
    stone = _ramp(pal, "rock", color, 6, 18)
    rng = np.random.default_rng(seed)
    c = np.asarray(center, float)
    r = np.array([size, size * rng.uniform(0.65, 0.95), size * rng.uniform(0.5, 0.75)])
    n = shape_ellipsoid(m, c + np.array([0, 0, r[2] * 0.35]), r, stone[2], roughness=0.32, seed=seed, power=2.4)
    for i in range(2):  # sharp facets: slice off a corner of the boulder
        p = c + np.array([rng.choice([-1, 1]) * size * 0.8, rng.choice([-1, 1]) * size * 0.6, r[2] * 0.9])
        shape_ellipsoid(m, p, (size * 0.5, size * 0.5, size * 0.35), 0, mode="subtract")
    noise_shade(scene, m, _rname(pal, stone), 2.5, 1.0, seed)
    if moss > 0:
        pal.ensure_ramp("moss", "#5c7a32", 5, 25)
        scatter(scene, m, "moss", density=moss, on="top", scale=2.5, seed=seed)
    return {"voxels": n}


def gen_terrain(scene: Scene, m: Model, seed=0, base=4, amplitude=None, scale=None, water_level=None, snow_line=None, trees=0, rocks=0) -> dict:
    """Heightmap terrain: grass/dirt/stone layers, sand beaches, water (glass), cliffs, snow,
    optional scattered trees and rocks."""
    pal = scene.palette
    X, Y, Z = m.size
    amplitude = amplitude if amplitude is not None else Z * 0.45
    scale = scale or max(X, Y) / 3.0
    R = {
        "grass": pal.ensure_ramp("grass", "#5d8c3a", 6, 30),
        "dirt": pal.ensure_ramp("dirt", "#7a5638", 5),
        "stone": pal.ensure_ramp("rock", "#7d7a72", 6, 18),
        "sand": pal.ensure_ramp("sand", "#d9c58f", 5, 15),
        "water": pal.ensure_ramp("water", "#3f78a8", 4, 20),
        "snow": pal.ensure_ramp("snow", "#e9eef4", 4, 20),
    }
    pal.set_material("water", "glass", trans=0.45)
    yy, xx = np.mgrid[0:Y, 0:X]
    pts = np.stack([xx / scale, yy / scale], -1).astype(np.float32)
    h = base + artlib.fbm(pts, seed, 3) ** 1.35 * amplitude * 1.6
    h = np.clip(h, 1, Z - 2).T  # (X, Y)
    hi = np.round(h).astype(int)
    gx, gy = np.gradient(h)
    slope = np.hypot(gx, gy)
    wl = water_level if water_level is not None else int(base + amplitude * 0.28)
    sl_ = snow_line if snow_line is not None else int(base + amplitude * 0.95)
    z = np.arange(Z)[None, None, :]
    top = hi[..., None]
    solid = z <= top
    depth = top - z
    vox = np.zeros((X, Y, Z), np.uint8)
    vox[solid] = R["stone"][2]
    dirt = solid & (depth >= 1) & (depth <= 3)
    vox[dirt] = R["dirt"][2]
    surf = solid & (depth == 0)
    vox[surf] = R["grass"][2]
    cliff = (slope > 1.4)[..., None] & solid & (depth <= 3)
    vox[cliff] = R["stone"][3]
    beach = (np.abs(hi - wl) <= 1)[..., None] & solid & (depth <= 2)
    vox[beach] = R["sand"][2]
    snow = (hi >= sl_)[..., None] & surf
    vox[snow] = R["snow"][2]
    water = (z > top) & (z <= wl)
    vox[water] = R["water"][2]
    m.vox[:] = vox
    noise_shade(scene, m, "grass", 5.0, 0.6, seed)
    noise_shade(scene, m, "rock", 2.5, 0.8, seed + 1)
    noise_shade(scene, m, "dirt", 2.5, 0.6, seed + 2)
    rng = np.random.default_rng(seed + 5)
    placed_t = placed_r = 0
    for _ in range(int(trees) * 8):
        if placed_t >= trees:
            break
        x, y = int(rng.integers(4, X - 4)), int(rng.integers(4, Y - 4))
        if hi[x, y] <= wl + 1 or slope[x, y] > 1.0 or hi[x, y] >= sl_:
            continue
        th = int(rng.integers(10, max(12, min(26, Z - hi[x, y] - 2))))
        gen_tree(scene, m, (x, y, hi[x, y] + 1), "pine" if hi[x, y] > wl + amplitude * 0.5 else "oak", th, seed + placed_t)
        placed_t += 1
    for _ in range(int(rocks) * 8):
        if placed_r >= rocks:
            break
        x, y = int(rng.integers(3, X - 3)), int(rng.integers(3, Y - 3))
        if hi[x, y] <= wl:
            continue
        gen_rock(scene, m, (x, y, hi[x, y]), float(rng.uniform(1.5, 3.5)), seed + 50 + placed_r, moss=0.3)
        placed_r += 1
    return {"water_level": wl, "snow_line": sl_, "trees": placed_t, "rocks": placed_r}


def gen_character(scene: Scene, m: Model, origin=None, height=32, style="stylized", body="neutral", pose="a", skin="#d9a27c", hair="#3b2a20", hair_style="short", eyes="#2a3a55", top="#4a6fa5", bottom="#3b3f4a", shoes="#2b2622", sleeves="long", jacket=None, belt=True, hat="none", seed=0) -> dict:
    """Voxel humanoid with real proportions: style realistic (7.5 heads) | stylized (5.2) | chibi (3).
    body: male | female | neutral. pose: a | t | idle. Faces -y. Built from capsules and
    superellipsoids, then face features, hair, clothing details."""
    pal = scene.palette
    R = {
        "skin": _ramp(pal, "skin", skin, 6, 18),
        "hair": _ramp(pal, "hair", hair, 5, 20),
        "top": _ramp(pal, "cloth", top, 5, 20),
        "bottom": _ramp(pal, "cloth", bottom, 5, 20),
        "shoes": _ramp(pal, "shoes", shoes, 4),
        "eyes": _ramp(pal, "eyes", eyes, 3, 10),
        "belt": pal.ensure_ramp("leather", "#4a3324", 4),
        "metal": pal.ensure_ramp("metal", "#6f7680", 5, 10),
    }
    if jacket:
        R["jacket"] = _ramp(pal, "cloth", jacket, 5, 20)
    heads = {"realistic": 7.5, "stylized": 5.2, "chibi": 3.0}.get(style, 5.2)
    H = float(height)
    hh = H / heads  # head height
    hw = hh * (0.78 if style != "chibi" else 0.92)  # head width
    X, Y, Z = m.size
    if origin is None:
        origin = (X // 2, Y // 2, 0)
    cx, cy, z0 = (float(v) for v in origin)
    sh_w = hw * {"male": 2.05, "female": 1.72, "neutral": 1.9}.get(body, 1.9) * (0.62 if style == "chibi" else 1.0)
    hip_w = hw * {"male": 1.5, "female": 1.75, "neutral": 1.6}.get(body, 1.6) * (0.7 if style == "chibi" else 1.0)
    waist_w = hip_w * (0.82 if body == "female" else 0.92)
    tdepth = hw * (0.95 if style != "chibi" else 0.8)
    leg_len = (H - hh) * (0.53 if style != "chibi" else 0.38)
    torso_len = H - hh - leg_len - hh * 0.18
    hip_z = z0 + leg_len
    sh_z = hip_z + torso_len
    neck_z = sh_z
    head_c = np.array([cx, cy, sh_z + hh * 0.18 + hh / 2])
    limb = max(1.0, hw * 0.2)
    # legs
    for s in (-1, 1):
        lx = cx + s * hip_w * 0.26
        knee = (lx, cy - 0.3, z0 + leg_len * 0.5)
        shape_capsule(m, (lx, cy, hip_z), knee, limb * 1.35, limb * 1.05, R["bottom"][2])
        shape_capsule(m, knee, (lx, cy, z0 + limb * 1.2), limb * 1.05, limb * 0.85, R["bottom"][2])
        shoe_h = max(1.5, H * 0.045)
        shape_ellipsoid(m, (lx, cy - limb * 0.8, z0 + shoe_h / 2), (limb * 1.1, limb * 2.0, shoe_h), R["shoes"][2], power=2.6)
        shape_box(m, (lx - limb * 1.1, cy - limb * 2.6, z0), (lx + limb * 1.1, cy + limb * 1.4, z0), R["shoes"][0], mode="paint")
    # pelvis + torso (stacked ellipses)
    shape_ellipsoid(m, (cx, cy, hip_z), (hip_w / 2, tdepth / 2 * 1.05, hh * 0.32), R["bottom"][2])
    nz = max(2, int(round(torso_len)))
    for i in range(nz + 1):
        t = i / nz
        w = waist_w + (sh_w - waist_w) * (t**1.6)
        if body == "female":
            w = waist_w * (1.0 + 0.12 * (1 - t)) + (sh_w - waist_w) * (t**1.6)
        dpt = tdepth * (1.0 + 0.18 * math.sin(math.pi * min(1, t * 1.2)))
        z = hip_z + t * torso_len
        top_idx = R["top"][2]
        shape_ellipsoid(m, (cx, cy, z), (w / 2, dpt / 2, 0.75), top_idx, power=2.4)
    shape_ellipsoid(m, (cx, cy, sh_z - 0.5), (sh_w / 2, tdepth / 2, hh * 0.22), R["top"][2], power=2.2)  # shoulders
    if body == "female" and style != "chibi":
        shape_ellipsoid(m, (cx, cy - tdepth * 0.28, hip_z + torso_len * 0.68), (sh_w * 0.34, tdepth * 0.32, hh * 0.22), R["top"][2])
    # neck + head
    shape_cylinder(m, (cx, cy, neck_z - 1), max(1.0, hw * 0.2), hh * 0.4, R["skin"][2])
    shape_ellipsoid(m, head_c, (hw / 2, hw / 2 * 1.02, hh / 2), R["skin"][3], power=2.8)
    front_y = int(round(head_c[1] - hw / 2 * 1.02))
    eye_z = int(round(head_c[2] - hh * 0.02))
    # ears
    for s in (-1, 1):
        shape_ellipsoid(m, (head_c[0] + s * hw / 2, head_c[1] + 0.5, eye_z), (0.8, 0.9, max(1.0, hh * 0.12)), R["skin"][2])
    # face: find actual front surface per column so features sit on the skin
    def face_set(x, z, idx, depth=0):
        x, z = int(round(x)), int(round(z))
        if not (0 <= x < X and 0 <= z < Z):
            return
        col = np.nonzero(m.vox[x, :, z])[0]
        if len(col):
            m.vox[x, col[0] + depth, z] = idx

    ex = max(1, int(round(hw * 0.2)))
    big = hh >= 6
    for s in (-1, 1):
        x = head_c[0] + s * ex
        if big:
            face_set(x - s * 0.5, eye_z, R["skin"][-1])
            face_set(x + s * 0.5, eye_z, R["eyes"][1])
            face_set(x - s * 0.5, eye_z + 2, R["hair"][1])
            face_set(x + s * 0.5, eye_z + 2, R["hair"][1])
        else:
            face_set(x, eye_z, R["eyes"][0])
    nose_x = int(round(head_c[0]))
    col = np.nonzero(m.vox[nose_x, :, eye_z - 1])[0]
    if len(col) and col[0] > 0 and big:
        m.vox[nose_x, col[0] - 1, eye_z - 1] = R["skin"][2]
    mouth_z = int(round(head_c[2] - hh * 0.27))
    for dx in ((-0.5, 0.5) if big else (0,)):
        face_set(head_c[0] + dx, mouth_z, R["skin"][1])
    # hair
    if hair_style != "bald":
        hidx = R["hair"][2]
        sc = 1.14
        hair_c = head_c + np.array([0, 0.35, 0.25])
        tmp = np.zeros_like(m.vox)
        mm = Model("_tmp", m.size)
        mm.vox = tmp
        shape_ellipsoid(mm, hair_c, (hw / 2 * sc, hw / 2 * sc, hh / 2 * sc), hidx, power=2.6, roughness=0.08, seed=seed)
        g = np.indices(m.size)
        fringe_z = eye_z + (3 if big else 2)
        keep = (g[2] >= fringe_z) | (g[1] >= head_c[1] + hw * 0.05)
        if hair_style in ("short", "bun", "ponytail"):
            keep &= g[2] >= head_c[2] - hh * 0.38
        elif hair_style == "long":
            keep &= g[2] >= head_c[2] - hh * 0.9
        tmp[~keep] = 0
        np.copyto(m.vox, tmp, where=(tmp > 0) & (m.vox == 0) | ((tmp > 0) & (g[2] >= fringe_z) & (m.vox == R["skin"][3])))
        if hair_style == "long":
            shape_capsule(m, head_c + np.array([0, hw * 0.3, -hh * 0.2]), head_c + np.array([0, hw * 0.35, -hh * 1.1]), hw * 0.45, hw * 0.35, hidx)
        if hair_style == "ponytail":
            shape_capsule(m, head_c + np.array([0, hw * 0.55, hh * 0.15]), head_c + np.array([0, hw * 0.75, -hh * 0.9]), hw * 0.2, hw * 0.12, hidx)
        if hair_style == "bun":
            shape_ellipsoid(m, head_c + np.array([0, hw * 0.35, hh * 0.55]), (hw * 0.25,) * 3, hidx)
        noise_shade(scene, m, _rname(pal, R["hair"]), 1.2, 0.9, seed)
    if hat == "cap":
        shape_ellipsoid(m, head_c + np.array([0, 0.3, hh * 0.22]), (hw / 2 * 1.18, hw / 2 * 1.18, hh * 0.38), R["top"][1], mode="add", power=2.6)
        shape_box(m, (head_c[0] - hw * 0.45, front_y - hw * 0.45, head_c[2] + hh * 0.12), (head_c[0] + hw * 0.45, front_y, head_c[2] + hh * 0.12), R["top"][1])
    elif hat == "helmet":
        shape_ellipsoid(m, head_c + np.array([0, 0.2, hh * 0.12]), (hw / 2 * 1.2, hw / 2 * 1.2, hh / 2 * 1.1), R["metal"][2], power=2.4)
        g = np.indices(m.size)
        face_cut = (g[1] < head_c[1]) & (g[2] < eye_z + 2) & (g[2] > mouth_z - 2) & (np.abs(g[0] - head_c[0]) < hw * 0.42) & (m.vox == R["metal"][2])
        m.vox[face_cut] = 0
    # arms
    ang = {"a": 28, "t": 88, "idle": 9}.get(pose, 28)
    arm_len = H * (0.36 if style != "chibi" else 0.27)
    for s in (-1, 1):
        sh = np.array([cx + s * (sh_w / 2 - limb * 0.6), cy, sh_z - limb * 0.9])
        dirv = np.array([s * math.sin(math.radians(ang)), 0, -math.cos(math.radians(ang))])
        elbow = sh + dirv * arm_len * 0.5 + np.array([0, 0.2, 0])
        wrist = sh + dirv * arm_len * 0.93
        upper = R["top"][2] if not jacket else R["jacket"][2]
        fore = upper if sleeves == "long" else R["skin"][2]
        shape_capsule(m, sh, elbow, limb * 1.05, limb * 0.9, upper)
        shape_capsule(m, elbow, wrist, limb * 0.9, limb * 0.75, fore)
        if sleeves == "long":
            shape_capsule(m, wrist - dirv * 0.6, wrist, limb * 0.95, limb * 0.95, R["top"][1] if not jacket else R["jacket"][1])
        shape_ellipsoid(m, wrist + dirv * limb * 1.1, (limb * 0.85, limb * 0.75, limb * 1.15), R["skin"][2])
    # jacket: open front showing the shirt
    if jacket:
        torso = (m.vox == R["top"][2]) | (m.vox == R["top"][1])
        g = np.indices(m.size)
        opening = (np.abs(g[0] - cx) <= max(0.6, sh_w * 0.12)) & (g[1] < cy)
        jm = torso & ~opening & (g[2] < sh_z + 1)
        m.vox[jm] = R["jacket"][2]
        collar = torso & (g[2] >= sh_z - 1) & (np.abs(g[0] - cx) <= sh_w * 0.3)
        m.vox[collar & (m.vox > 0)] = R["jacket"][3]
    if belt:
        bz = int(round(hip_z + 0.5))
        layer = m.vox[:, :, bz]
        cloth = (layer > 0) & ~np.isin(layer, np.array(R["skin"], np.uint8))
        g2 = np.indices(layer.shape)
        cloth &= np.hypot((g2[0] - cx) / (hip_w / 2 + 1), (g2[1] - cy) / (tdepth / 2 + 1)) < 1.2
        layer[cloth] = R["belt"][1]
        col = np.nonzero(layer[int(round(cx)), :] == R["belt"][1])[0]
        if len(col):
            layer[int(round(cx)), col[0]] = R["metal"][-1]
    noise_shade(scene, m, _rname(pal, R["top"]), 2.0, 0.5, seed)
    noise_shade(scene, m, _rname(pal, R["bottom"]), 2.0, 0.5, seed + 1)
    return {"head_height": round(hh, 2), "eye_z": eye_z, "facing": "-y", "heads_tall": heads}


# ============================================================ rendering

FACE_LIGHT = {"top": 1.0, "front": 0.84, "side": 0.68}


def _rgb8(pal: Palette, idx: int, k: float) -> tuple[int, int, int, int]:
    c = pal.colors[idx] * k
    return (int(min(255, c[0] * 255)), int(min(255, c[1] * 255)), int(min(255, c[2] * 255)), 255)


def render_iso(pal: Palette, grid: np.ndarray, scale: int = 0, rotate: int = 0, max_px: int = 1024) -> Image.Image:
    """2:1 isometric preview: visible faces -y (front), +x (right), +z (top), painter-sorted."""
    g = np.rot90(grid, k=rotate % 4, axes=(0, 1))
    X, Y, Z = g.shape
    if not scale:
        scale = max(1, int(max_px / max(1, (X + Y) * 2)))
        scale = min(scale, max(1, int(max_px / max(1, (X + Y) * 0.5 + Z))))
    s = scale

    def P(x, y, z):
        return ((x + y) * s, (x - y) * s / 2 - z * s)

    corners = np.array([P(x, y, z) for x in (0, X) for y in (0, Y) for z in (0, Z)])
    minx, miny = corners.min(0)
    maxx, maxy = corners.max(0)
    W, Hh = int(maxx - minx) + 2, int(maxy - miny) + 2
    img = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    filled = g > 0
    pad = np.pad(filled, 1)
    top_vis = ~pad[1:-1, 1:-1, 2:]
    front_vis = ~pad[1:-1, :-2, 1:-1]
    side_vis = ~pad[2:, 1:-1, 1:-1]
    vis = filled & (top_vis | front_vis | side_vis)
    pts = np.argwhere(vis)
    order = np.argsort(pts[:, 0] - pts[:, 1] + pts[:, 2], kind="stable")
    ox, oy = -minx + 1, -miny + 1
    for x, y, z in pts[order]:
        idx = int(g[x, y, z])

        def poly(cs):
            return [(px + ox, py + oy) for px, py in (P(*c) for c in cs)]

        if top_vis[x, y, z]:
            c = _rgb8(pal, idx, FACE_LIGHT["top"])
            dr.polygon(poly([(x, y, z + 1), (x + 1, y, z + 1), (x + 1, y + 1, z + 1), (x, y + 1, z + 1)]), fill=c, outline=c)
        if front_vis[x, y, z]:
            c = _rgb8(pal, idx, FACE_LIGHT["front"])
            dr.polygon(poly([(x, y, z), (x + 1, y, z), (x + 1, y, z + 1), (x, y, z + 1)]), fill=c, outline=c)
        if side_vis[x, y, z]:
            c = _rgb8(pal, idx, FACE_LIGHT["side"])
            dr.polygon(poly([(x + 1, y, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x + 1, y, z + 1)]), fill=c, outline=c)
    return img


def render_ortho(pal: Palette, grid: np.ndarray, view: str = "front", scale: int = 0, max_px: int = 768) -> Image.Image:
    views = {
        # (array transform producing (cols, depth, rows-from-bottom))
        "front": lambda g: g,  # look along +y, cols=x
        "back": lambda g: g[::-1, ::-1, :],
        "left": lambda g: np.transpose(g, (1, 0, 2))[::-1, :, :],  # look along +x from -x side
        "right": lambda g: np.transpose(g, (1, 0, 2))[:, ::-1, :],
        "top": lambda g: np.transpose(g, (0, 2, 1))[:, ::-1, ::-1],  # look down -z, rows = y
    }
    if view not in views:
        raise ValueError(f"view must be one of {list(views)} or iso/turnaround")
    a = views[view](grid)
    C, D, Rr = a.shape
    filled = a > 0
    any_ = filled.any(1)
    first = np.argmax(filled, axis=1)
    idx = np.take_along_axis(a, first[:, None, :], 1)[:, 0, :]
    rgb = pal.colors[idx] * (1.0 - 0.45 * (first / max(D - 1, 1)))[..., None]
    img = np.zeros((C, Rr, 4), np.uint8)
    img[..., :3] = np.clip(rgb * 255, 0, 255)
    img[..., 3] = any_ * 255
    img = np.transpose(img, (1, 0, 2))[::-1]  # rows top->bottom
    if not scale:
        scale = max(1, int(max_px / max(C, Rr)))
    return Image.fromarray(img, "RGBA").resize((C * scale, Rr * scale), Image.NEAREST)


def render(scene: Scene, names=None, view="iso", scale=0, rotate=0, background="#20242b") -> Image.Image:
    grid, _ = scene.composite(names)
    pal = scene.palette
    if view == "iso":
        img = render_iso(pal, grid, scale, rotate)
    elif view == "turnaround":
        ims = [render_iso(pal, grid, scale, r, max_px=640) for r in range(4)]
        w, h = max(i.width for i in ims), max(i.height for i in ims)
        img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        for k, im in enumerate(ims):
            img.paste(im, ((k % 2) * w, (k // 2) * h), im)
    elif view == "sheet":
        ims = [render_iso(pal, grid, 0, 0, 640)] + [render_ortho(pal, grid, v, 0, 320) for v in ("front", "right", "back", "top")]
        w = ims[0].width + max(i.width for i in ims[1:3]) + max(i.width for i in ims[3:]) + 16
        h = max(ims[0].height, ims[1].height + ims[2].height + 8, ims[3].height + ims[4].height + 8)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.paste(ims[0], (0, 0), ims[0])
        x = ims[0].width + 8
        img.paste(ims[1], (x, 0), ims[1])
        img.paste(ims[2], (x, ims[1].height + 8), ims[2])
        x += max(ims[1].width, ims[2].width) + 8
        img.paste(ims[3], (x, 0), ims[3])
        img.paste(ims[4], (x, ims[3].height + 8), ims[4])
    else:
        img = render_ortho(pal, grid, view, scale)
    if background and background != "transparent":
        bg = Image.new("RGBA", img.size, tuple(int(c * 255) for c in artlib.hex_to_rgb(background)) + (255,))
        bg.alpha_composite(img)
        img = bg
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ============================================================ .vox IO


def _chunk(cid: bytes, content: bytes = b"", children: bytes = b"") -> bytes:
    return cid + struct.pack("<ii", len(content), len(children)) + content + children


def _vstr(s: str) -> bytes:
    b = s.encode()
    return struct.pack("<i", len(b)) + b


def _vdict(d: dict) -> bytes:
    return struct.pack("<i", len(d)) + b"".join(_vstr(k) + _vstr(str(v)) for k, v in d.items())


def save_vox(scene: Scene, path: Path) -> dict:
    ms = list(scene.models.values())
    if not ms:
        raise ValueError("scene has no models")
    body = b""
    for m in ms:
        X, Y, Z = m.size
        pts = np.argwhere(m.vox)
        cols = m.vox[m.vox > 0]
        data = np.column_stack([pts.astype(np.uint8), cols.astype(np.uint8)]).tobytes()
        body += _chunk(b"SIZE", struct.pack("<iii", X, Y, Z))
        body += _chunk(b"XYZI", struct.pack("<i", len(pts)) + data)
    # scene graph: root transform -> group -> (transform -> shape) per model
    n = len(ms)
    body += _chunk(b"nTRN", struct.pack("<i", 0) + _vdict({}) + struct.pack("<iiii", 1, -1, -1, 1) + _vdict({}))
    body += _chunk(b"nGRP", struct.pack("<i", 1) + _vdict({}) + struct.pack("<i", n) + struct.pack(f"<{n}i", *[2 + 2 * i for i in range(n)]))
    for i, m in enumerate(ms):
        t = np.add(m.pos, np.array(m.size) // 2)
        body += _chunk(b"nTRN", struct.pack("<i", 2 + 2 * i) + _vdict({"_name": m.name}) + struct.pack("<iiii", 3 + 2 * i, -1, 0, 1) + _vdict({"_t": f"{t[0]} {t[1]} {t[2]}"}))
        body += _chunk(b"nSHP", struct.pack("<i", 3 + 2 * i) + _vdict({}) + struct.pack("<i", 1) + struct.pack("<i", i) + _vdict({}))
    body += _chunk(b"LAYR", struct.pack("<i", 0) + _vdict({"_name": "0"}) + struct.pack("<i", -1))
    rgba = np.zeros((256, 4), np.uint8)
    rgba[:255, :3] = np.clip(scene.palette.colors[1:256] * 255, 0, 255).round()
    rgba[:255, 3] = 255
    body += _chunk(b"RGBA", rgba.tobytes())
    for idx, mat in sorted(scene.palette.materials.items()):
        body += _chunk(b"MATL", struct.pack("<i", idx) + _vdict(mat))
    data = b"VOX " + struct.pack("<i", 150) + _chunk(b"MAIN", b"", body)
    artlib.ensure_parent(path).write_bytes(data)
    side = path.with_suffix(path.suffix + ".json")
    side.write_text(json.dumps({"scene": scene.name, "palette": scene.palette.to_json(), "models": [{"name": m.name, "pos": m.pos} for m in ms]}, indent=1))
    return {"path": str(path), "bytes": len(data), "models": n, "sidecar": str(side)}


def load_vox(path: Path, name: str | None = None) -> Scene:
    data = path.read_bytes()
    if data[:4] != b"VOX ":
        raise ValueError("not a MagicaVoxel .vox file")
    scene = Scene(name or path.stem)
    sizes, voxels, nodes = [], [], {}
    palette = None
    materials = {}

    def rd_str(b, o):
        (n,) = struct.unpack_from("<i", b, o)
        return b[o + 4 : o + 4 + n].decode(errors="replace"), o + 4 + n

    def rd_dict(b, o):
        (n,) = struct.unpack_from("<i", b, o)
        o += 4
        d = {}
        for _ in range(n):
            k, o = rd_str(b, o)
            v, o = rd_str(b, o)
            d[k] = v
        return d, o

    o = 8
    cid = data[o : o + 4]
    nc, nch = struct.unpack_from("<ii", data, o + 4)
    o += 12 + nc
    end = o + nch
    while o < end:
        cid = data[o : o + 4]
        nc, nch = struct.unpack_from("<ii", data, o + 4)
        c = data[o + 12 : o + 12 + nc]
        o += 12 + nc + nch
        if cid == b"SIZE":
            sizes.append(struct.unpack_from("<iii", c))
        elif cid == b"XYZI":
            (n,) = struct.unpack_from("<i", c)
            voxels.append(np.frombuffer(c, np.uint8, n * 4, 4).reshape(-1, 4))
        elif cid == b"RGBA":
            palette = np.frombuffer(c, np.uint8).reshape(256, 4)
        elif cid == b"MATL":
            (mid,) = struct.unpack_from("<i", c)
            materials[mid], _ = rd_dict(c, 4)
        elif cid == b"nTRN":
            (nid,) = struct.unpack_from("<i", c)
            attrs, p = rd_dict(c, 4)
            child, _r, _l, nf = struct.unpack_from("<iiii", c, p)
            p += 16
            fr = {}
            if nf:
                fr, p = rd_dict(c, p)
            nodes[nid] = ("T", child, attrs.get("_name"), fr.get("_t"))
        elif cid == b"nSHP":
            (nid,) = struct.unpack_from("<i", c)
            _a, p = rd_dict(c, 4)
            (nm,) = struct.unpack_from("<i", c, p)
            (mid,) = struct.unpack_from("<i", c, p + 4)
            nodes[nid] = ("S", mid)
    pal = scene.palette
    if palette is not None:
        pal.colors[1:256] = palette[:255, :3] / 255.0
    else:  # default palette approximation: greys
        pal.colors[1:256] = np.linspace(0.1, 1, 255)[:, None]
    pal.next = 256
    pal.materials = {k: v for k, v in materials.items() if v.get("_type", "_diffuse") != "_diffuse"}
    place = {}
    for nid, nd in nodes.items():
        if nd[0] == "T" and nodes.get(nd[1], ("",))[0] == "S":
            place[nodes[nd[1]][1]] = (nd[2], nd[3])
    for i, ((X, Y, Z), v) in enumerate(zip(sizes, voxels)):
        nm, t = place.get(i, (None, None))
        nm = nm or f"model{i}"
        while nm in scene.models:
            nm += "_"
        m = scene.add_model(nm, (X, Y, Z))
        m.vox[v[:, 0], v[:, 1], v[:, 2]] = v[:, 3]
        if t:
            tt = [int(float(s)) for s in t.split()]
            m.pos = list(np.subtract(tt, np.array([X, Y, Z]) // 2))
    side = path.with_suffix(path.suffix + ".json")
    if side.exists():
        try:
            pal.load_json(json.loads(side.read_text())["palette"])
        except Exception:  # sidecar is optional
            pass
    return scene


# ============================================================ mesh export

_DIRS = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]


def _runs_2d(face: np.ndarray):
    """Merge equal-colored cells into rectangles: row runs, then identical runs across rows."""
    rects = []
    active: dict[tuple[int, int, int], int] = {}
    for r in range(face.shape[0]):
        row = face[r]
        cur = {}
        if row.any():
            change = np.flatnonzero(np.diff(np.concatenate([[0], row, [0]]).astype(np.int32)) != 0)
            for a, b in zip(change[:-1], change[1:]):
                c = int(row[a])
                if c:
                    cur[(int(a), int(b), c)] = active.get((int(a), int(b), c), r)
        for k, r0 in active.items():
            if k not in cur:
                rects.append((r0, r, k[0], k[1], k[2]))
        active = cur
    for k, r0 in active.items():
        rects.append((r0, face.shape[0], k[0], k[1], k[2]))
    return rects  # (row0, row1, col0, col1, color) half-open


def build_mesh(grid: np.ndarray):
    """Greedy-ish face merging. Returns verts (N,3) float (z-up voxel units), normals, colors per quad."""
    filled = grid > 0
    pad = np.pad(filled, 1)
    quads, normals, colors = [], [], []
    for ax, s in _DIRS:
        sl = [slice(1, -1)] * 3
        sl[ax] = slice(1 + s, pad.shape[ax] - 1 + s)
        nb = pad[tuple(sl)]
        vis = filled & ~nb
        faces = np.where(vis, grid, 0)
        u, v = [a for a in range(3) if a != ax]
        for i in range(grid.shape[ax]):
            f2 = np.take(faces, i, axis=ax)  # dims (u, v)
            if not f2.any():
                continue
            plane = i + (1 if s > 0 else 0)
            for r0, r1, c0, c1, col in _runs_2d(f2):
                cs = []
                for uu, vv in ((r0, c0), (r1, c0), (r1, c1), (r0, c1)):
                    p = [0.0, 0.0, 0.0]
                    p[ax], p[u], p[v] = plane, uu, vv
                    cs.append(p)
                cs = np.array(cs, dtype=np.float32)
                n = np.zeros(3, np.float32)
                n[ax] = s
                if np.dot(np.cross(cs[1] - cs[0], cs[2] - cs[0]), n) < 0:
                    cs = cs[::-1]
                quads.append(cs)
                normals.append(n)
                colors.append(col)
    if not quads:
        raise ValueError("nothing to export: models are empty")
    return np.array(quads), np.array(normals), np.array(colors, np.int32)


def _to_yup(p: np.ndarray) -> np.ndarray:
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)


def export_mesh(scene: Scene, path: Path, names=None, voxel_size: float = 0.1, pivot: str = "bottom_center") -> dict:
    grid, _ = scene.composite(names)
    quads, normals, colors = build_mesh(grid)
    X, Y, Z = grid.shape
    off = np.array([X / 2, Y / 2, 0], np.float32) if pivot == "bottom_center" else np.zeros(3, np.float32)
    verts = _to_yup((quads - off) * voxel_size)  # (Q,4,3)
    nrm = _to_yup(normals)
    pal = scene.palette
    tex = np.zeros((1, 256, 3), np.uint8)
    tex[0] = np.clip(pal.colors * 255, 0, 255).round()
    emis_idx = pal.emissive_indices()
    etex = np.zeros_like(tex)
    for i in emis_idx:
        etex[0, i] = tex[0, i]
    uv = np.stack([(colors + 0.5) / 256.0, np.full(len(colors), 0.5)], -1).astype(np.float32)
    ext = path.suffix.lower()
    artlib.ensure_parent(path)
    if ext == ".obj":
        png = path.with_name(path.stem + "_palette.png")
        Image.fromarray(tex, "RGB").save(png)
        mtl = path.with_suffix(".mtl")
        mtl.write_text(f"newmtl voxel\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\nmap_Kd {png.name}\n")
        lines = [f"mtllib {mtl.name}", "o voxel", "usemtl voxel"]
        lines += [f"v {a:.5f} {b:.5f} {c:.5f}" for a, b, c in verts.reshape(-1, 3)]
        lines += [f"vt {a:.6f} {b:.6f}" for a, b in uv]
        lines += [f"vn {a:.0f} {b:.0f} {c:.0f}" for a, b, c in nrm]
        for q in range(len(quads)):
            b = q * 4 + 1
            lines.append(f"f {b}/{q + 1}/{q + 1} {b + 1}/{q + 1}/{q + 1} {b + 2}/{q + 1}/{q + 1} {b + 3}/{q + 1}/{q + 1}")
        path.write_text("\n".join(lines) + "\n")
        files = [str(path), str(mtl), str(png)]
    elif ext in (".glb", ".gltf"):
        path = path.with_suffix(".glb")
        _write_glb(path, verts, nrm, uv, tex, etex if emis_idx else None)
        files = [str(path)]
    else:
        raise ValueError("export format: .obj or .glb")
    size = np.ptp(verts.reshape(-1, 3), axis=0)
    return {"files": files, "quads": int(len(quads)), "triangles": int(len(quads) * 2), "size_m": [round(float(v), 3) for v in size], "up": "Y", "forward": "+Z (model -y)"}


def _write_glb(path: Path, verts, nrm, uv, tex, etex) -> None:
    Q = len(verts)
    pos = verts.reshape(-1, 3).astype(np.float32)
    nor = np.repeat(nrm, 4, axis=0).astype(np.float32)
    uvs = np.repeat(uv, 4, axis=0).astype(np.float32)
    base = (np.arange(Q, dtype=np.uint32) * 4)[:, None]
    idx = (base + np.array([0, 1, 2, 0, 2, 3], np.uint32)).reshape(-1)
    png = png_bytes(Image.fromarray(tex, "RGB"))
    epng = png_bytes(Image.fromarray(etex, "RGB")) if etex is not None else None
    blobs = [pos.tobytes(), nor.tobytes(), uvs.tobytes(), idx.tobytes(), png] + ([epng] if epng else [])
    views, binbuf = [], b""
    for b in blobs:
        while len(binbuf) % 4:
            binbuf += b"\0"
        views.append({"buffer": 0, "byteOffset": len(binbuf), "byteLength": len(b)})
        binbuf += b
    while len(binbuf) % 4:
        binbuf += b"\0"
    for i in range(3):
        views[i]["target"] = 34962
    views[3]["target"] = 34963
    n = len(pos)
    gltf = {
        "asset": {"version": "2.0", "generator": "gameforge-voxel"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": path.stem}],
        "meshes": [{"name": path.stem, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3", "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": n, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": len(binbuf)}],
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"bufferView": 4, "mimeType": "image/png"}] + ([{"bufferView": 5, "mimeType": "image/png"}] if epng else []),
        "textures": [{"sampler": 0, "source": 0}] + ([{"sampler": 0, "source": 1}] if epng else []),
        "materials": [
            {
                "name": "voxel_palette",
                "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 0.9},
                **({"emissiveTexture": {"index": 1}, "emissiveFactor": [1.0, 1.0, 1.0]} if epng else {}),
            }
        ],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binbuf))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(binbuf), 0x004E4942) + binbuf
    path.write_bytes(out)
