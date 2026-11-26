"""Shared art helpers for GameForge MCP servers (voxel, fx).

Pure numpy + Pillow, no MCP dependency, so everything here is unit-testable.
Colors are float RGB in [0, 1] unless a function says otherwise.
"""
from __future__ import annotations

import colorsys
import os
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- paths


def resolve_path(p: str) -> Path:
    """Relative paths are resolved against the project dir (if Claude Code passed it) or cwd."""
    path = Path(os.path.expanduser(p))
    if not path.is_absolute():
        base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        path = Path(base) / path
    return path


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- color


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8):
        raise ValueError(f"bad hex color: #{h}")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    r, g, b = (int(round(max(0.0, min(1.0, c)) * 255)) for c in rgb[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _rotate_hue_toward(h: float, target: float, amount: float) -> float:
    """Rotate hue h (0..1) toward target along the shortest arc by at most `amount` (fraction of a turn)."""
    d = ((target - h + 0.5) % 1.0) - 0.5
    step = (1 if d >= 0 else -1) * min(abs(d), amount)
    return (h + step) % 1.0


def hue_ramp(base, steps: int = 6, hue_shift: float = 25.0, contrast: float = 1.0) -> list[tuple[float, float, float]]:
    """Pixel-art style color ramp, dark -> light, with hue shifting.

    Shadows rotate toward cool blue/purple and gain saturation, highlights rotate toward
    warm yellow and lose saturation (no "pillow" grey shading). `hue_shift` is degrees at
    the ends of the ramp. The base color sits in the middle of the ramp.
    """
    if isinstance(base, str):
        base = hex_to_rgb(base)
    steps = max(2, int(steps))
    h, s, v = colorsys.rgb_to_hsv(*base)
    out = []
    for k in range(steps):
        t = (k / (steps - 1)) * 2.0 - 1.0  # -1 darkest .. +1 lightest
        t *= contrast
        t = max(-1.0, min(1.0, t))
        if t < 0:
            hh = _rotate_hue_toward(h, 0.68, abs(t) * hue_shift / 360.0)  # toward blue-violet
            ss = min(1.0, s + 0.12 * abs(t) * (1 - s) + 0.06 * abs(t))
            vv = v * (1.0 + 0.68 * t)
        else:
            hh = _rotate_hue_toward(h, 0.15, t * hue_shift / 360.0)  # toward warm yellow
            ss = max(0.0, s * (1.0 - 0.3 * t))
            vv = min(1.0, v * (1.0 + 0.45 * t) + 0.05 * t)
        out.append(colorsys.hsv_to_rgb(hh, max(0, min(1, ss)), max(0, min(1, vv))))
    return out


def gradient(stops: list[tuple[float, tuple[float, float, float, float]]], t: np.ndarray) -> np.ndarray:
    """Piecewise-linear RGBA gradient. stops: [(pos, (r,g,b,a)), ...] sorted by pos."""
    t = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0)
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.array([c for _, c in stops], dtype=np.float32)
    out = np.empty(t.shape + (cols.shape[1],), dtype=np.float32)
    for ch in range(cols.shape[1]):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


# OKLab for perceptual color distance (quantize, palette extraction)


def _srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    lin = _srgb_to_linear(rgb)
    m1 = np.array(
        [[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]],
        dtype=np.float32,
    )
    lms = np.cbrt(np.maximum(lin @ m1.T, 0))
    m2 = np.array(
        [[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]],
        dtype=np.float32,
    )
    return lms @ m2.T


# ---------------------------------------------------------------- noise

_LATTICE_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _lattice(seed: int, dims: int, n: int = 64) -> np.ndarray:
    key = (seed, dims)
    if key not in _LATTICE_CACHE:
        rng = np.random.default_rng(seed)
        _LATTICE_CACHE[key] = rng.random((n,) * dims, dtype=np.float32)
    return _LATTICE_CACHE[key]


def _fade(t):
    return t * t * (3 - 2 * t)


def value_noise(points: np.ndarray, seed: int = 0) -> np.ndarray:
    """Smooth value noise in [0,1] at float points of shape (..., D), D in {2,3}. Period 64."""
    pts = np.asarray(points, dtype=np.float32)
    d = pts.shape[-1]
    lat = _lattice(seed, d)
    n = lat.shape[0]
    i0 = np.floor(pts).astype(np.int64)
    f = _fade(pts - i0)
    i0 %= n
    i1 = (i0 + 1) % n
    if d == 2:
        x0, y0 = i0[..., 0], i0[..., 1]
        x1, y1 = i1[..., 0], i1[..., 1]
        fx, fy = f[..., 0], f[..., 1]
        a = lat[x0, y0] * (1 - fx) + lat[x1, y0] * fx
        b = lat[x0, y1] * (1 - fx) + lat[x1, y1] * fx
        return a * (1 - fy) + b * fy
    x0, y0, z0 = i0[..., 0], i0[..., 1], i0[..., 2]
    x1, y1, z1 = i1[..., 0], i1[..., 1], i1[..., 2]
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]

    def lerp(a, b, t):
        return a + (b - a) * t

    c00 = lerp(lat[x0, y0, z0], lat[x1, y0, z0], fx)
    c10 = lerp(lat[x0, y1, z0], lat[x1, y1, z0], fx)
    c01 = lerp(lat[x0, y0, z1], lat[x1, y0, z1], fx)
    c11 = lerp(lat[x0, y1, z1], lat[x1, y1, z1], fx)
    return lerp(lerp(c00, c10, fy), lerp(c01, c11, fy), fz)


def fbm(points: np.ndarray, seed: int = 0, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5) -> np.ndarray:
    """Fractal value noise in ~[0,1]."""
    pts = np.asarray(points, dtype=np.float32)
    total = np.zeros(pts.shape[:-1], dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, 1.0
    for o in range(octaves):
        total += amp * value_noise(pts * freq + o * 17.31, seed + o * 101)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def fbm_image(h: int, w: int, scale: float, seed: int = 0, octaves: int = 4) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return fbm(np.stack([xx / scale, yy / scale], axis=-1), seed, octaves)


# ---------------------------------------------------------------- image filters


def box_blur(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    if r <= 0:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode="constant")
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(img: np.ndarray, sigma: float) -> np.ndarray:
    """Approximate gaussian blur (3 box passes) over the first two axes of HxW[xC] float arrays."""
    if sigma <= 0.3:
        return img.astype(np.float32)
    # box radius for 3 passes approximating sigma
    r = max(1, int(round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    out = img.astype(np.float32)
    for _ in range(3):
        out = box_blur(out, r, 0)
        out = box_blur(out, r, 1)
    return out


def tonemap_aces(x: np.ndarray) -> np.ndarray:
    """Narkowicz ACES filmic fit: HDR (>=0) -> [0,1]."""
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    x = np.maximum(x, 0)
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def bloom(hdr: np.ndarray, threshold: float = 0.8, strength: float = 0.6, radius: float = 6.0) -> np.ndarray:
    """Add multi-scale glow from pixels brighter than threshold. hdr: HxWx3 float."""
    lum = luminance(hdr)
    bright = hdr * (np.clip(lum - threshold, 0, None) / np.maximum(lum, 1e-6))[..., None]
    glow = np.zeros_like(hdr)
    for k, w in ((1.0, 0.5), (2.5, 0.3), (6.0, 0.2)):
        glow += w * blur(bright, radius * k / 2.5)
    return hdr + glow * strength


# ---------------------------------------------------------------- quantize & dither

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) + 0.5) / 16.0


def bayer(n: int) -> np.ndarray:
    m = np.array([[0]], dtype=np.float32)
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / (m.size)


def nearest_palette(rgb: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Index of the perceptually nearest palette color (OKLab). rgb: (...,3), palette: (N,3)."""
    lab = rgb_to_oklab(rgb.reshape(-1, 3))
    plab = rgb_to_oklab(palette)
    best = np.zeros(lab.shape[0], dtype=np.int32)
    bestd = np.full(lab.shape[0], np.inf, dtype=np.float32)
    for i, p in enumerate(plab):
        d = np.sum((lab - p) ** 2, axis=1)
        m = d < bestd
        best[m] = i
        bestd[m] = d[m]
    return best.reshape(rgb.shape[:-1])


def quantize(rgb: np.ndarray, palette: np.ndarray, dither: str = "none", strength: float = 1.0) -> np.ndarray:
    """Map HxWx3 floats to palette colors. dither: none | bayer4 | bayer8 | floyd."""
    palette = np.asarray(palette, dtype=np.float32)
    if dither in ("bayer4", "bayer8"):
        m = BAYER4 if dither == "bayer4" else bayer(8)
        h, w = rgb.shape[:2]
        tile = np.tile(m, (h // m.shape[0] + 1, w // m.shape[1] + 1))[:h, :w]
        # spread ~ typical distance between neighbouring palette colors
        spread = 0.12 * strength
        idx = nearest_palette(np.clip(rgb + (tile[..., None] - 0.5) * spread, 0, 1), palette)
        return palette[idx]
    if dither == "floyd":
        img = rgb.astype(np.float32).copy()
        h, w = img.shape[:2]
        if h * w > 512 * 512:
            raise ValueError("floyd dithering is limited to 512x512 px; use bayer4/bayer8 for bigger images")
        plab = rgb_to_oklab(palette)
        out = np.zeros_like(img)
        for y in range(h):
            for x in range(w):
                old = np.clip(img[y, x], 0, 1)
                i = int(np.argmin(((rgb_to_oklab(old[None])[0] - plab) ** 2).sum(1)))
                new = palette[i]
                out[y, x] = new
                err = (old - new) * strength
                if x + 1 < w:
                    img[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        img[y + 1, x - 1] += err * 3 / 16
                    img[y + 1, x] += err * 5 / 16
                    if x + 1 < w:
                        img[y + 1, x + 1] += err * 1 / 16
        return out
    return palette[nearest_palette(rgb, palette)]


def kmeans_palette(rgb: np.ndarray, n: int, seed: int = 0, iters: int = 12) -> np.ndarray:
    """Extract n representative colors (OKLab k-means). rgb: (N,3) floats."""
    pts = rgb.reshape(-1, 3).astype(np.float32)
    if len(pts) == 0:
        return np.zeros((0, 3), np.float32)
    rng = np.random.default_rng(seed)
    if len(pts) > 20000:
        pts = pts[rng.choice(len(pts), 20000, replace=False)]
    lab = rgb_to_oklab(pts)
    n = min(n, len(np.unique(pts, axis=0)))
    centers = lab[rng.choice(len(lab), n, replace=False)]
    for _ in range(iters):
        d = ((lab[:, None, :] - centers[None]) ** 2).sum(-1)
        lbl = d.argmin(1)
        for k in range(n):
            m = lbl == k
            if m.any():
                centers[k] = lab[m].mean(0)
    d = ((lab[:, None, :] - centers[None]) ** 2).sum(-1)
    lbl = d.argmin(1)
    out = np.array([pts[lbl == k].mean(0) if (lbl == k).any() else pts[0] for k in range(n)], dtype=np.float32)
    # sort dark -> light
    return out[np.argsort(luminance(out))]


# ---------------------------------------------------------------- palette files


def write_gpl(path: Path, colors, name: str = "GameForge") -> None:
    lines = ["GIMP Palette", f"Name: {name}", "Columns: 8", "#"]
    for i, c in enumerate(colors):
        r, g, b = (int(round(max(0, min(1, v)) * 255)) for v in c[:3])
        lines.append(f"{r:3d} {g:3d} {b:3d}\t{name}-{i}")
    ensure_parent(path).write_text("\n".join(lines) + "\n")


def checker(h: int, w: int, cell: int = 8) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((yy // cell + xx // cell) % 2).astype(np.float32)
    v = 0.78 + 0.1 * m
    return np.stack([v, v, v], -1)
