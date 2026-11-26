"""GameForge FX core: HDR particle renderer for VFX flipbooks (explosion, fire, smoke, magic,
slash, hit, lightning, portal, heal, sparkle), pixel-art stylization, 2D post-processing
(outline, shadow, glow, rim light, grading, quantize+dither, pixelate), normal maps,
palettes and sprite sheets. Images are float RGBA in [0,1], shape (H, W, 4), straight alpha.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import artlib  # noqa: E402

# ============================================================ canvas


class Canvas:
    """Emission (additive HDR) + smoke (premultiplied, alpha-over) layers."""

    def __init__(self, w: int, h: int, tex: np.ndarray):
        self.w, self.h = w, h
        self.emit = np.zeros((h, w, 3), np.float32)
        self.sc = np.zeros((h, w, 3), np.float32)
        self.sa = np.zeros((h, w), np.float32)
        self.tex = tex
        self.yy, self.xx = np.mgrid[0:h, 0:w].astype(np.float32)

    def _win(self, x, y, r):
        R = max(1, int(math.ceil(r * 3)))
        x0, x1 = max(0, int(x) - R), min(self.w, int(x) + R + 2)
        y0, y1 = max(0, int(y) - R), min(self.h, int(y) + R + 2)
        if x0 >= x1 or y0 >= y1:
            return None
        return (slice(y0, y1), slice(x0, x1))

    def glow(self, x, y, r, rgb, intensity=1.0, textured=0.0, tex_off=0, stretch=1.0):
        sl = self._win(x, y, r * max(1.0, stretch))
        if sl is None or intensity <= 0:
            return
        dx = self.xx[sl] - x
        dy = self.yy[sl] - y
        g = np.exp(-(dx * dx + (dy / stretch) ** 2) / (2 * max(r, 0.4) ** 2))
        if textured:
            g = g * ((1 - textured) + textured * 1.6 * self._tex(dx, dy, r, tex_off))
        self.emit[sl] += g[..., None] * np.asarray(rgb, np.float32) * intensity

    def _tex(self, dx, dy, r, off):
        n = self.tex.shape[0]
        k = 18.0 / max(r, 1.0)
        ix = (dx * k + off * 37).astype(np.int64) % n
        iy = (dy * k + off * 53).astype(np.int64) % n
        return self.tex[iy, ix]

    def puff(self, x, y, r, rgb, alpha, tex_off=0, softness=0.55):
        """Alpha-over a soft noisy smoke puff on top of the smoke layer."""
        sl = self._win(x, y, r)
        if sl is None or alpha <= 0:
            return
        dx = self.xx[sl] - x
        dy = self.yy[sl] - y
        d = np.sqrt(dx * dx + dy * dy) / max(r, 0.5)
        n = self._tex(dx, dy, r, tex_off)
        a = np.clip((1.0 - d + (n - 0.5) * 0.9) / softness, 0, 1) * alpha
        self.sc[sl] = self.sc[sl] * (1 - a[..., None]) + np.asarray(rgb, np.float32) * a[..., None]
        self.sa[sl] = self.sa[sl] * (1 - a) + a

    def streak(self, x0, y0, x1, y1, width, rgb, intensity=1.0, taper=True):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(L / max(width * 0.6, 0.5)) + 1)
        for i in range(n):
            t = i / (n - 1)
            k = (0.25 + 0.75 * t) if taper else 1.0  # brighter toward the head (x1, y1)
            self.glow(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, width * (0.5 + 0.5 * k), rgb, intensity * k / max(1.0, n / 4))

    def ring(self, cx, cy, radius, thickness, rgb, intensity=1.0):
        d = np.abs(np.hypot(self.xx - cx, self.yy - cy) - radius)
        self.emit += (np.exp(-(d * d) / (2 * max(thickness, 0.5) ** 2)) * intensity)[..., None] * np.asarray(rgb, np.float32)

    def star(self, x, y, size, rgb, intensity=1.0, width=1.0, diagonals=0.5):
        self.streak(x - size, y, x, y, width, rgb, intensity, False)
        self.streak(x + size, y, x, y, width, rgb, intensity, False)
        self.streak(x, y - size, x, y, width, rgb, intensity, False)
        self.streak(x, y + size, x, y, width, rgb, intensity, False)
        if diagonals:
            s = size * 0.45
            for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                self.streak(x + sx * s, y + sy * s, x, y, width * 0.8, rgb, intensity * diagonals, False)
        self.glow(x, y, width * 2.2, rgb, intensity * 1.5)

    def finish(self, bloom_strength=0.7, exposure=1.0, background="transparent") -> np.ndarray:
        e = artlib.bloom(self.emit * exposure, threshold=0.6, strength=bloom_strength, radius=max(2.0, self.w / 40))
        et = artlib.tonemap_aces(e)
        if background == "black":  # for additive blend shaders
            rgb = self.sc * 1.0 + et
            return np.dstack([np.clip(rgb, 0, 1), np.ones((self.h, self.w), np.float32)])
        a_e = np.clip(artlib.luminance(et) * 1.35, 0, 1)
        A = np.clip(self.sa + a_e * (1 - self.sa * 0.35), 0, 1)
        C = self.sc + et
        rgb = np.clip(C / np.maximum(A, 1e-4)[..., None], 0, 1)
        return np.dstack([rgb, A])


# ============================================================ helpers


def ease_out(t):
    return 1 - (1 - np.clip(t, 0, 1)) ** 3


def ease_in(t):
    return np.clip(t, 0, 1) ** 2


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


FIRE = [(0.0, (0.25, 0.02, 0.01, 1)), (0.3, (0.75, 0.12, 0.02, 1)), (0.55, (1.0, 0.42, 0.06, 1)), (0.8, (1.0, 0.78, 0.3, 1)), (1.0, (1.0, 0.97, 0.85, 1))]


def color_stops(colors: list[str] | None, default):
    if not colors:
        return default
    rgb = [artlib.hex_to_rgb(c) for c in colors]
    if len(rgb) == 1:  # build a ramp: dark -> base -> white-hot
        base = rgb[0]
        dark = tuple(c * 0.25 for c in base)
        hot = tuple(min(1, c * 0.75 + 0.3) for c in base)
        rgb = [dark, base, hot, (1, 1, 1)]
    n = len(rgb)
    return [(i / (n - 1), (*c, 1)) for i, c in enumerate(rgb)]


def heat_color(stops, h):
    return artlib.gradient(stops, np.asarray(h, np.float32))[..., :3]


# ============================================================ effects
# Each maker returns draw(cv, t, frame_index) for t in [0,1).


def make_explosion(S, rng, colors, it):
    stops = color_stops(colors, FIRE)
    c = np.array([S / 2, S * 0.55])
    nf = 28
    fb = dict(ang=rng.uniform(0, 2 * np.pi, nf), spd=rng.uniform(0.12, 0.36, nf) * S, life=rng.uniform(0.35, 0.7, nf), r0=rng.uniform(0.05, 0.1, nf) * S)
    ns = 24
    sm = dict(ang=rng.uniform(0, 2 * np.pi, ns), spd=rng.uniform(0.08, 0.28, ns) * S, birth=rng.uniform(0.05, 0.22, ns), r0=rng.uniform(0.07, 0.11, ns) * S, shade=rng.uniform(0.14, 0.3, ns))
    nk = 34
    sp = dict(ang=rng.uniform(0, 2 * np.pi, nk), spd=rng.uniform(0.3, 0.62, nk) * S, life=rng.uniform(0.2, 0.55, nk))

    def draw(cv, t, fi):
        # smoke first (sits under the fire)
        for i in range(ns):
            age = (t - sm["birth"][i]) / (1 - sm["birth"][i])
            if age <= 0:
                continue
            d = sm["spd"][i] * (1 - math.exp(-3 * age)) / (1 - math.exp(-3))
            x = c[0] + math.cos(sm["ang"][i]) * d
            y = c[1] + math.sin(sm["ang"][i]) * d * 0.8 - S * 0.16 * age
            r = sm["r0"][i] * (1 + 2.6 * age**0.7)
            a = 0.9 * smooth(age / 0.12) * (1 - age) ** 1.4
            g = sm["shade"][i] + 0.12 * age
            tint = max(0.0, 1 - age * 3.0) * 0.7
            rgb = np.array([g, g * 0.95, g * 0.92]) * (1 - tint) + np.array([0.85, 0.32, 0.08]) * tint
            cv.puff(x, y, r, rgb, a, tex_off=i * 7 + fi)
        if t < 0.18:  # flash
            cv.glow(c[0], c[1], S * (0.07 + 0.35 * t), (1, 0.9, 0.7), 2.6 * it * (1 - t / 0.18) ** 2)
        if t < 0.45:  # shockwave
            cv.ring(c[0], c[1], S * 0.47 * float(ease_out(t / 0.45)), S * 0.012, (1, 0.8, 0.55), 0.9 * it * (1 - t / 0.45) ** 2)
        for i in range(nf):
            age = t / fb["life"][i]
            if age >= 1:
                continue
            d = fb["spd"][i] * (1 - math.exp(-4.5 * t)) / (1 - math.exp(-4.5))
            x = c[0] + math.cos(fb["ang"][i]) * d
            y = c[1] + math.sin(fb["ang"][i]) * d * 0.8 - S * 0.1 * t
            r = fb["r0"][i] * (1 + 1.8 * age**0.6)
            h = (1 - age) ** 1.2
            cv.glow(x, y, r * 0.8, heat_color(stops, 0.92 * h), 1.15 * it * h**1.3, textured=0.8, tex_off=i * 3 + fi)
        for i in range(nk):
            age = t / sp["life"][i]
            if age >= 1:
                continue
            k = 2.2
            d = sp["spd"][i] * (1 - math.exp(-k * t)) / k * 2
            vx, vy = math.cos(sp["ang"][i]), math.sin(sp["ang"][i])
            x, y = c[0] + vx * d, c[1] + vy * d + S * 0.35 * t * t
            sp_len = sp["spd"][i] * math.exp(-k * t) * 0.12
            cv.streak(x - vx * sp_len, y - vy * sp_len, x, y, max(0.6, S / 160), (1, 0.75, 0.35), 1.6 * it * (1 - age))

    return draw


def make_fire(S, rng, colors, it):
    """Shader-style flame: a noise field scrolled upward inside a tapered flame envelope.
    Seamless loop via cross-fading two noise phases."""
    stops = color_stops(colors, FIRE[:1] + [(0.35, (0.85, 0.15, 0.02, 1)), (0.6, (1.0, 0.45, 0.05, 1)), (0.85, (1.0, 0.75, 0.25, 1)), (1.0, (1.0, 0.92, 0.7, 1))])
    seed = int(rng.integers(0, 10000))
    ne = 10
    E = dict(b=rng.uniform(0, 1, ne), x=rng.normal(0, 0.1, ne) * S, ph=rng.uniform(0, 1, ne))
    base = np.array([S / 2, S * 0.92])
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    nx = (xx - base[0]) / (S * 0.5)
    ny = np.clip((base[1] - yy) / (S * 0.75), -0.2, 1.2)
    sc = S / 7.0
    D = 6.0  # noise units scrolled per loop

    def field(phase):
        pts = np.stack([xx / sc, (yy / sc) + phase * D], -1)
        return artlib.fbm(pts, seed, 4)

    def draw(cv, t, fi):
        n = (1 - t) * field(t) + t * field(t - 1)  # seamless loop
        n2 = (1 - t) * field(t * 2 + 0.37) + t * field(t * 2 - 1.63)
        width = 0.62 * np.clip(1 - ny, 0, 1) ** 0.5 + 0.02
        dx = (n2 - 0.5) * 0.55 * np.clip(ny, 0, 1)
        core = 1 - np.abs(nx + dx) / np.maximum(width, 1e-3)
        dens = np.clip(core * 1.2 - np.clip(ny, 0, 1) * 0.75 + (n - 0.5) * 2.1 * np.clip(ny + 0.2, 0, 1), 0, 1)
        dens *= np.clip(ny * 8 + 0.6, 0, 1)
        heat = dens**1.4
        col = heat_color(stops, np.clip(heat * 0.95, 0, 1))
        cv.emit += col * (heat * 1.1 * it)[..., None]
        flick = 1 + 0.1 * math.sin(2 * math.pi * 3 * t)
        cv.glow(base[0], base[1] - S * 0.08, S * 0.16, heat_color(stops, 0.45), 0.25 * it * flick)
        for i in range(ne):
            age = (t - E["b"][i]) % 1.0
            x = base[0] + E["x"][i] + math.sin(2 * math.pi * (age * 2 + E["ph"][i])) * S * 0.05
            y = base[1] - S * 0.2 - age * S * 0.75
            cv.glow(x, y, max(0.6, S / 140), (1, 0.6, 0.2), 1.8 * it * (1 - age) * smooth(age * 6))

    return draw


def make_smoke(S, rng, colors, it, loop):
    g = artlib.hex_to_rgb(colors[0]) if colors else (0.42, 0.42, 0.45)
    n = 22
    P = dict(b=rng.uniform(0, 1 if loop else 0.35, n), x=rng.normal(0, 0.07, n) * S, spd=rng.uniform(0.35, 0.6, n) * S, r=rng.uniform(0.06, 0.1, n) * S, sh=rng.uniform(0.75, 1.15, n), drift=rng.normal(0, 0.06, n) * S)
    base = np.array([S / 2, S * 0.85])

    def draw(cv, t, fi):
        for i in range(n):
            age = ((t - P["b"][i]) % 1.0) if loop else (t - P["b"][i]) / (1 - P["b"][i])
            if age <= 0 or age >= 1:
                continue
            x = base[0] + P["x"][i] + P["drift"][i] * age
            y = base[1] - P["spd"][i] * float(ease_out(age))
            r = P["r"][i] * (1 + 2.2 * age)
            a = 0.75 * smooth(age / 0.15) * (1 - age) ** 1.5 * min(1.0, it)
            cv.puff(x, y, r, np.array(g) * P["sh"][i] * (0.8 + 0.4 * age), a, tex_off=i * 5)

    return draw


def make_magic(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (0.55, 0.35, 1.0)
    stops = color_stops([artlib.rgb_to_hex(base)], None)
    core, mid, hot = heat_color(stops, 0.3), heat_color(stops, 0.45), heat_color(stops, 0.66)
    c = np.array([S / 2, S / 2])
    n_in, n_out = 18, 26
    A = dict(a=rng.uniform(0, 2 * np.pi, n_in), r=rng.uniform(0.3, 0.46, n_in) * S)
    B = dict(a=rng.uniform(0, 2 * np.pi, n_out), spd=rng.uniform(0.2, 0.46, n_out) * S, life=rng.uniform(0.45, 0.75, n_out), size=rng.uniform(0.02, 0.05, n_out) * S)
    T0 = 0.28

    def draw(cv, t, fi):
        if t < T0:  # anticipation: gather energy
            u = t / T0
            for i in range(n_in):
                rr = A["r"][i] * (1 - float(ease_in(u)))
                ang = A["a"][i] + u * 2.0
                cv.glow(c[0] + math.cos(ang) * rr, c[1] + math.sin(ang) * rr, max(0.8, S / 110), hot, 2.0 * it * (0.35 + 0.65 * u))
            cv.glow(c[0], c[1], S * (0.03 + 0.07 * u), mid, 2.5 * it * (0.3 + 0.7 * u))
            return
        u = (t - T0) / (1 - T0)
        if u < 0.15:
            cv.glow(c[0], c[1], S * 0.12, (1, 1, 1), 2.2 * it * (1 - u / 0.15) ** 2)
        cv.ring(c[0], c[1], S * 0.44 * float(ease_out(u / 0.6)), S * 0.014 * (1 + u), mid, 1.4 * it * max(0.0, 1 - u / 0.6) ** 1.5)
        if u < 0.35:
            for k in range(8):
                ang = k * math.pi / 4 + 0.2
                L = S * 0.42 * float(ease_out(u / 0.35))
                cv.streak(c[0], c[1], c[0] + math.cos(ang) * L, c[1] + math.sin(ang) * L, max(0.7, S / 150), hot, 1.6 * it * (1 - u / 0.35))
        for i in range(n_out):
            age = u / B["life"][i]
            if age >= 1:
                continue
            d = B["spd"][i] * float(ease_out(age))
            x, y = c[0] + math.cos(B["a"][i]) * d, c[1] + math.sin(B["a"][i]) * d
            tw = 0.6 + 0.4 * math.sin(fi * 2.1 + i)
            cv.star(x, y, B["size"][i] * (1 - age * 0.5), hot if i % 3 else (1, 1, 1), 1.8 * it * (1 - age) * tw, max(0.6, S / 170))
        cv.glow(c[0], c[1], S * 0.1 * (1 - u), core, 1.5 * it * (1 - u))

    return draw


def make_slash(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (0.55, 0.85, 1.0)
    stops = color_stops([artlib.rgb_to_hex(base)], None)
    edge = heat_color(stops, 0.7)
    c = np.array([S / 2, S / 2])
    R = S * 0.36
    a0, a1 = math.radians(-160), math.radians(25)
    Tsw = 0.35

    def draw(cv, t, fi):
        head = a0 + (a1 - a0) * float(ease_out(min(1.0, t / Tsw)))
        fade = 1.0 if t < Tsw else max(0.0, 1 - (t - Tsw) / (1 - Tsw)) ** 1.6
        trail = (a1 - a0) * (0.85 if t < Tsw else 0.85 * fade + 0.15)
        tail = max(a0, head - trail)
        dx, dy = cv.xx - c[0], cv.yy - c[1]
        r = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        u = np.clip((th - tail) / max(head - tail, 1e-3), 0, 1)
        inside = (th >= tail) & (th <= head)
        thick = S * 0.07 * np.sin(np.pi * np.clip(u * 0.92 + 0.04, 0, 1)) ** 0.8 * (0.4 + 0.6 * fade)
        d = np.abs(r - R) / np.maximum(thick, 0.3)
        body = np.clip(1 - d, 0, 1) * inside * (u**1.5)
        corev = np.clip(1 - d * 2.6, 0, 1) * inside * (u**2)
        cv.emit += (body * 1.6 * it * fade)[..., None] * np.asarray(heat_color(stops, 0.55), np.float32)
        cv.emit += (corev * 3.5 * it * fade)[..., None] * np.asarray(edge, np.float32)
        if t < Tsw + 0.2:
            hx, hy = c[0] + math.cos(head) * R, c[1] + math.sin(head) * R
            cv.glow(hx, hy, S * 0.03, (1, 1, 1), 3 * it * fade)
            for k in range(5):
                ang = head + rng.normal(0, 0.6) + math.pi / 2
                L = S * rng.uniform(0.04, 0.1)
                cv.streak(hx, hy, hx + math.cos(ang) * L, hy + math.sin(ang) * L, max(0.6, S / 180), edge, 1.2 * it * fade)

    return draw


def make_hit(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (1.0, 0.8, 0.35)
    stops = color_stops([artlib.rgb_to_hex(base)], None)
    hot = heat_color(stops, 0.66)
    c = np.array([S / 2, S / 2])
    n = 16
    P = dict(a=rng.uniform(0, 2 * np.pi, n), spd=rng.uniform(0.25, 0.48, n) * S, life=rng.uniform(0.7, 1.0, n))

    def draw(cv, t, fi):
        if t < 0.35:
            u = t / 0.35
            cv.star(c[0], c[1], S * 0.42 * (1 - u) ** 0.7, hot, 3.0 * it * (1 - u), max(0.8, S / 90), 0.6)
            cv.glow(c[0], c[1], S * 0.1, (1, 1, 1), 2.2 * it * (1 - u) ** 2)
        if t < 0.85:
            cv.ring(c[0], c[1], S * 0.32 * float(ease_out(t / 0.85)), S * 0.012, hot, 1.2 * it * (1 - t / 0.85) ** 0.8)
        for i in range(n):
            age = t / P["life"][i]
            if age >= 1:
                continue
            vx, vy = math.cos(P["a"][i]), math.sin(P["a"][i])
            d = P["spd"][i] * float(ease_out(age))
            L = P["spd"][i] * 0.25 * (1 - age) + S * 0.015
            x, y = c[0] + vx * d, c[1] + vy * d
            cv.streak(x - vx * L, y - vy * L, x, y, max(0.6, S / 170), hot, 2.2 * it * (1 - age) ** 0.7)

    return draw


def _bolt(rng, p0, p1, disp, depth):
    pts = [np.array(p0, float), np.array(p1, float)]
    for _ in range(depth):
        new = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            mid = (a + b) / 2
            nrm = np.array([-(b - a)[1], (b - a)[0]])
            nrm /= np.linalg.norm(nrm) + 1e-6
            new += [mid + nrm * rng.normal(0, disp), b]
        pts = new
        disp *= 0.55
    return pts


def make_lightning(S, rng, colors, it, frames):
    base = artlib.hex_to_rgb(colors[0]) if colors else (0.55, 0.7, 1.0)
    flick = [1.0, 0.35, 0.95, 0.6, 1.0, 0.25, 0.8, 0.5]
    s0 = int(rng.integers(0, 1 << 30))

    def draw(cv, t, fi):
        lr = np.random.default_rng(s0 + fi // 2)  # a new strike every 2 frames
        k = flick[fi % len(flick)] * (1.0 if t < 0.75 else (1 - t) / 0.25)
        main = _bolt(lr, (S / 2 + lr.normal(0, S * 0.08), S * 0.03), (S / 2 + lr.normal(0, S * 0.08), S * 0.97), S * 0.14, 6)
        bolts = [(main, 1.0)]
        for _ in range(3):
            j = int(lr.integers(4, len(main) - 8))
            a = main[j]
            end = a + np.array([lr.normal(0, S * 0.25), lr.uniform(0.15, 0.35) * S])
            bolts.append((_bolt(lr, a, end, S * 0.06, 4), 0.5))
        for pts, w in bolts:
            for a, b in zip(pts[:-1], pts[1:]):
                cv.streak(a[0], a[1], b[0], b[1], max(0.6, S / 200) * (1.3 if w == 1 else 0.9), (1, 1, 1), 2.2 * it * k * w, False)
                cv.streak(a[0], a[1], b[0], b[1], max(1.5, S / 60), base, 0.5 * it * k * w, False)
        cv.glow(S / 2, S * 0.97, S * 0.12, base, 1.2 * it * k)

    return draw


def make_portal(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (0.35, 0.85, 0.75)
    stops = color_stops([artlib.rgb_to_hex(base)], None)
    hot = heat_color(stops, 0.62)
    c = np.array([S / 2, S / 2])
    R = S * 0.34
    n = 110
    P = dict(a=rng.uniform(0, 2 * np.pi, n), b=rng.uniform(0, 1, n), arm=rng.integers(0, 3, n))

    def draw(cv, t, fi):
        dist = np.hypot(cv.xx - c[0], cv.yy - c[1]) / R
        dark = np.clip(1.15 - dist, 0, 1) ** 0.6
        swirl = cv.tex[(cv.yy.astype(int) + fi * 3) % cv.tex.shape[0], (cv.xx.astype(int) * 2) % cv.tex.shape[1]]
        a = dark * (0.8 + 0.2 * swirl)
        cv.sc[:] = cv.sc * (1 - a[..., None]) + a[..., None] * (np.asarray(base, np.float32) * 0.12)
        cv.sa[:] = cv.sa * (1 - a) + a
        pulse = 1 + 0.15 * math.sin(2 * math.pi * 2 * t)
        cv.ring(c[0], c[1], R, S * 0.02, hot, 1.6 * it * pulse)
        cv.ring(c[0], c[1], R * 1.04, S * 0.05, base, 0.5 * it * pulse)
        for i in range(n):
            u = (t + P["b"][i]) % 1.0
            rr = R * (1.15 - 1.0 * u)
            ang = P["a"][i] + 2 * math.pi * t + u * 2.5
            cv.glow(c[0] + math.cos(ang) * rr, c[1] + math.sin(ang) * rr * 0.98, max(0.6, S / 150) * (1.5 - u), hot, 1.6 * it * math.sin(math.pi * u))

    return draw


def make_heal(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (0.45, 1.0, 0.55)
    stops = color_stops([artlib.rgb_to_hex(base)], None)
    hot = heat_color(stops, 0.62)
    n = 26
    P = dict(b=rng.uniform(0, 1, n), x=rng.uniform(-0.3, 0.3, n) * S, r=rng.uniform(0.015, 0.035, n) * S, plus=rng.random(n) < 0.35, ph=rng.uniform(0, 1, n))
    by = S * 0.86

    def draw(cv, t, fi):
        pulse = 0.75 + 0.25 * math.sin(2 * math.pi * t)
        d = np.hypot((cv.xx - S / 2) / (S * 0.36), (cv.yy - by) / (S * 0.09))
        cv.emit += (np.exp(-((d - 1) ** 2) / 0.02) * 1.1 * it * pulse)[..., None] * np.asarray(base, np.float32)
        cv.glow(S / 2, by, S * 0.2, base, 0.5 * it * pulse)
        for i in range(n):
            u = (t + P["b"][i]) % 1.0
            x = S / 2 + P["x"][i] + math.sin(2 * math.pi * (u + P["ph"][i])) * S * 0.02
            y = by - u * S * 0.75
            k = math.sin(math.pi * u)
            if P["plus"][i]:
                s = P["r"][i] * 1.6
                cv.streak(x - s, y, x + s, y, max(0.7, S / 140), hot, 1.4 * it * k, False)
                cv.streak(x, y - s, x, y + s, max(0.7, S / 140), hot, 1.4 * it * k, False)
            else:
                cv.glow(x, y, P["r"][i], hot, 1.0 * it * k)

    return draw


def make_sparkle(S, rng, colors, it):
    base = artlib.hex_to_rgb(colors[0]) if colors else (1.0, 0.9, 0.5)
    n = 9
    P = dict(x=rng.uniform(0.15, 0.85, n) * S, y=rng.uniform(0.15, 0.85, n) * S, ph=rng.uniform(0, 1, n), s=rng.uniform(0.06, 0.16, n) * S, f=rng.integers(1, 3, n))

    def draw(cv, t, fi):
        for i in range(n):
            k = max(0.0, math.sin(2 * math.pi * (t * P["f"][i] + P["ph"][i]))) ** 3
            if k > 0.01:
                cv.star(P["x"][i], P["y"][i], P["s"][i] * (0.4 + 0.6 * k), base, 2.4 * it * k, max(0.6, S / 160), 0.4)

    return draw


EFFECTS = {
    "explosion": dict(loop=False, frames=16, fps=20),
    "fire": dict(loop=True, frames=16, fps=15),
    "smoke": dict(loop=False, frames=16, fps=15),
    "magic": dict(loop=False, frames=18, fps=20),
    "slash": dict(loop=False, frames=10, fps=24),
    "hit": dict(loop=False, frames=8, fps=24),
    "lightning": dict(loop=False, frames=10, fps=20),
    "portal": dict(loop=True, frames=24, fps=20),
    "heal": dict(loop=True, frames=20, fps=15),
    "sparkle": dict(loop=True, frames=16, fps=12),
}


def render_effect(kind: str, frames: int = 0, size: int = 128, seed: int = 1, colors: list[str] | None = None, intensity: float = 1.0, loop: bool | None = None, background: str = "transparent", bloom: float = 0.7) -> tuple[list[np.ndarray], dict]:
    if kind not in EFFECTS:
        raise ValueError(f"effect must be one of {list(EFFECTS)}")
    meta = dict(EFFECTS[kind])
    frames = int(frames or meta["frames"])
    if not 2 <= frames <= 128:
        raise ValueError("frames must be 2..128")
    size = int(size)
    if not 16 <= size <= 1024:
        raise ValueError("size must be 16..1024")
    loop = meta["loop"] if loop is None else loop
    rng = np.random.default_rng(seed)
    tex = artlib.fbm_image(128, 128, 14.0, seed, 4)
    tex = (tex - tex.min()) / max(1e-6, float(np.ptp(tex)))
    makers = {
        "explosion": lambda: make_explosion(size, rng, colors, intensity),
        "fire": lambda: make_fire(size, rng, colors, intensity),
        "smoke": lambda: make_smoke(size, rng, colors, intensity, loop),
        "magic": lambda: make_magic(size, rng, colors, intensity),
        "slash": lambda: make_slash(size, rng, colors, intensity),
        "hit": lambda: make_hit(size, rng, colors, intensity),
        "lightning": lambda: make_lightning(size, rng, colors, intensity, frames),
        "portal": lambda: make_portal(size, rng, colors, intensity),
        "heal": lambda: make_heal(size, rng, colors, intensity),
        "sparkle": lambda: make_sparkle(size, rng, colors, intensity),
    }
    draw = makers[kind]()
    out = []
    for fi in range(frames):
        t = fi / frames if loop else fi / max(1, frames - 1) * 0.9  # last frame = faint tail, not empty
        cv = Canvas(size, size, tex)
        draw(cv, t, fi)
        out.append(cv.finish(bloom, 1.0, background))
    meta.update(frames=frames, loop=loop, blend="additive" if background == "black" else "alpha")
    return out, meta


# ============================================================ pixel-art stylization


def downsample(img: np.ndarray, factor: int) -> np.ndarray:
    """Area-average downscale in premultiplied space (keeps edges clean)."""
    if factor <= 1:
        return img
    h, w = img.shape[:2]
    h2, w2 = h // factor, w // factor
    a = img[: h2 * factor, : w2 * factor]
    pm = np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1)
    pm = pm.reshape(h2, factor, w2, factor, 4).mean((1, 3))
    rgb = pm[..., :3] / np.maximum(pm[..., 3:4], 1e-4)
    return np.concatenate([np.clip(rgb, 0, 1), pm[..., 3:4]], -1)


def pixelize(frames: list[np.ndarray], pixel: int = 4, colors: int = 10, palette: np.ndarray | None = None, dither: str = "bayer4", alpha_cut: float = 0.5, outline: str | None = None) -> tuple[list[np.ndarray], np.ndarray]:
    """Turn smooth frames into crisp pixel art: downscale, shared limited palette across all
    frames (stable colors over the animation), dithered hard alpha, optional 1px outline."""
    small = [downsample(f, pixel) for f in frames]
    if palette is None:
        pts = np.concatenate([s[..., :3][s[..., 3] > 0.15] for s in small] or [np.zeros((1, 3), np.float32)])
        palette = artlib.kmeans_palette(pts, colors, seed=3)
    out = []
    for s in small:
        h, w = s.shape[:2]
        rgb = artlib.quantize(s[..., :3], palette, dither if dither != "none" else "none", 0.8)
        if dither in ("bayer4", "bayer8"):
            m = artlib.BAYER4 if dither == "bayer4" else artlib.bayer(8)
            thr = np.tile(m, (h // m.shape[0] + 1, w // m.shape[1] + 1))[:h, :w]
            a = (s[..., 3] > alpha_cut * 0.6 + thr * alpha_cut * 0.8).astype(np.float32)
        else:
            a = (s[..., 3] > alpha_cut).astype(np.float32)
        f = np.dstack([rgb, a])
        if outline:
            f = op_outline(f, color=outline, thickness=1, mode="outer", selective=(outline == "auto"))
        out.append(f)
    return out, palette


# ============================================================ post-processing ops


def _shift(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    out[yd, xd] = a[ys, xs]
    return out


def op_outline(img, color="#1a1420", thickness=1, mode="outer", selective=False):
    A = img[..., 3] > 0.5
    rgb = img[..., :3].copy()
    out = img.copy()
    if mode == "outer":
        grown = A.copy()
        src_col = np.zeros_like(rgb)
        for _ in range(int(thickness)):
            nxt = grown.copy()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                sh = _shift(grown, dx, dy)
                newp = sh & ~nxt
                if selective:
                    src_col[newp] = _shift(rgb, dx, dy)[newp]
                nxt |= sh
            grown = nxt
        ring = grown & ~A
        if selective:
            col = src_col[ring] * 0.35
            col[:, 2] = np.minimum(1, col[:, 2] + 0.03)  # slightly cool, not black
            out[ring, :3] = col
        else:
            out[ring, :3] = artlib.hex_to_rgb(color)
        out[ring, 3] = 1.0
    else:  # inner
        er = A.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            er &= _shift(A, dx, dy)
        edge = A & ~er
        out[edge, :3] = out[edge, :3] * 0.45 if selective or color == "auto" else artlib.hex_to_rgb(color)
    return out


def op_shadow(img, offset=(2, 2), color="#000000", alpha=0.5, blur=1.5):
    a = _shift(img[..., 3], int(offset[0]), int(offset[1]))
    a = np.clip(artlib.blur(a, blur), 0, 1) * alpha
    sh_rgb = np.broadcast_to(np.asarray(artlib.hex_to_rgb(color), np.float32), img[..., :3].shape)
    A = img[..., 3]
    outA = A + a * (1 - A)
    rgb = (img[..., :3] * A[..., None] + sh_rgb * (a * (1 - A))[..., None]) / np.maximum(outA, 1e-4)[..., None]
    return np.dstack([rgb, outA])


def op_glow(img, color=None, radius=4.0, strength=1.0, threshold=0.0):
    A = img[..., 3]
    src = img[..., :3] * A[..., None]
    if threshold > 0:
        src = src * (artlib.luminance(img[..., :3]) > threshold)[..., None]
    if color:
        src = A[..., None] * np.asarray(artlib.hex_to_rgb(color), np.float32)
    g = artlib.blur(src, radius) * strength
    ga = np.clip(artlib.luminance(g) * 1.5, 0, 1)
    outA = np.clip(A + ga * (1 - A), 0, 1)
    rgb = (img[..., :3] * A[..., None] + g) / np.maximum(outA, 1e-4)[..., None]
    return np.dstack([np.clip(rgb, 0, 1), outA])


def op_rim(img, angle=45.0, color="#fff1c4", width=1, strength=0.8):
    """Light the sprite edges facing a light direction (angle: 0 = from right, 90 = from top)."""
    A = img[..., 3] > 0.5
    dx = int(round(math.cos(math.radians(angle))))
    dy = -int(round(math.sin(math.radians(angle))))
    rim = np.zeros_like(A)
    for k in range(1, int(width) + 1):
        rim |= A & ~_shift(A, -dx * k, -dy * k)
    out = img.copy()
    c = np.asarray(artlib.hex_to_rgb(color), np.float32)
    out[rim, :3] = out[rim, :3] * (1 - strength) + c * strength
    return out


def op_grade(img, brightness=0.0, contrast=1.0, saturation=1.0, temperature=0.0, tint=0.0, gamma=1.0):
    rgb = img[..., :3]
    rgb = (rgb - 0.5) * contrast + 0.5 + brightness
    lum = artlib.luminance(rgb)[..., None]
    rgb = lum + (rgb - lum) * saturation
    rgb = rgb + np.array([temperature * 0.1, tint * 0.1, -temperature * 0.1], np.float32)
    rgb = np.clip(rgb, 0, 1) ** (1 / max(gamma, 0.05))
    return np.dstack([rgb, img[..., 3]])


def op_vignette(img, strength=0.35):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / math.sqrt(2)
    out = img.copy()
    out[..., :3] *= (1 - strength * d**2)[..., None]
    return out


def op_hue(img, degrees=0.0):
    import colorsys

    rgb = img[..., :3].reshape(-1, 3)
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in rgb])
    hsv[:, 0] = (hsv[:, 0] + degrees / 360.0) % 1.0
    back = np.array([colorsys.hsv_to_rgb(*p) for p in hsv], np.float32).reshape(img[..., :3].shape)
    return np.dstack([back, img[..., 3]])


def op_pixelate(img, factor=2, keep_size=False):
    s = downsample(img, int(factor))
    s[..., 3] = (s[..., 3] > 0.5).astype(np.float32)
    return upscale(s, int(factor)) if keep_size else s


def upscale(img, factor):
    return np.repeat(np.repeat(img, int(factor), 0), int(factor), 1)


def parse_palette(spec, img: np.ndarray | None = None) -> np.ndarray:
    """list of hex | 'auto:N' (from image) | 'ramp:#hex:steps' | path to .gpl/.hex/.png."""
    if isinstance(spec, list):
        return np.array([artlib.hex_to_rgb(c) for c in spec], np.float32)
    s = str(spec)
    if s.startswith("auto"):
        n = int(s.split(":")[1]) if ":" in s else 16
        if img is None:
            raise ValueError("auto palette needs an image")
        return artlib.kmeans_palette(img[..., :3][img[..., 3] > 0.5], n)
    if s.startswith("ramp:"):
        _, base, *rest = s.split(":")
        return np.array(artlib.hue_ramp(base, int(rest[0]) if rest else 6), np.float32)
    p = artlib.resolve_path(s)
    if p.suffix.lower() == ".gpl":
        cols = []
        for line in p.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and all(x.isdigit() for x in parts[:3]):
                cols.append([int(x) / 255 for x in parts[:3]])
        return np.array(cols, np.float32)
    if p.suffix.lower() == ".hex":
        return np.array([artlib.hex_to_rgb(x) for x in p.read_text().split() if x.strip()], np.float32)
    im = np.asarray(Image.open(p).convert("RGB")).reshape(-1, 3)
    return np.unique(im, axis=0).astype(np.float32)[:256] / 255.0


def op_quantize(img, palette="auto:16", dither="none", strength=1.0):
    pal = parse_palette(palette, img)
    rgb = artlib.quantize(img[..., :3], pal, dither, strength)
    return np.dstack([rgb, img[..., 3]])


OPS = {
    "outline": op_outline,
    "shadow": op_shadow,
    "glow": op_glow,
    "rim": op_rim,
    "grade": op_grade,
    "vignette": op_vignette,
    "hue": op_hue,
    "pixelate": op_pixelate,
    "upscale": upscale,
    "quantize": op_quantize,
}


def apply_ops(img: np.ndarray, ops: list[dict]) -> np.ndarray:
    for o in ops:
        o = dict(o)
        name = o.pop("op", None)
        if name not in OPS:
            raise ValueError(f"unknown op '{name}'. ops: {list(OPS)}")
        img = OPS[name](img, **o)
    return img


# ============================================================ normal map


def normal_map(img: np.ndarray, strength: float = 2.0, bevel: int = 3, detail: float = 0.5, flip_y: bool = False) -> np.ndarray:
    A = (img[..., 3] > 0.5).astype(np.float32)
    h = np.zeros_like(A)
    cur = A.copy()
    for _ in range(max(1, int(bevel))):  # distance-to-edge, capped at bevel
        h += cur
        er = cur.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            er = np.minimum(er, _shift(cur, dx, dy))
        cur = er
    h = h / max(1, bevel)
    h = artlib.blur(h, 0.8) + detail * artlib.luminance(img[..., :3]) * A
    gy, gx = np.gradient(h)
    nx, ny, nz = -gx * strength, (gy if not flip_y else -gy) * strength, np.ones_like(h)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rgb = n * 0.5 + 0.5
    return np.dstack([rgb, img[..., 3]])


# ============================================================ IO, sheets, preview


def load_rgba(path) -> np.ndarray:
    return np.asarray(Image.open(artlib.resolve_path(str(path))).convert("RGBA"), np.float32) / 255.0


def to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(np.round(img * 255), 0, 255).astype(np.uint8), "RGBA")


def split_sheet(img: np.ndarray, fw: int, fh: int, count: int = 0) -> list[np.ndarray]:
    rows, cols = img.shape[0] // fh, img.shape[1] // fw
    out = []
    for r in range(rows):
        for c in range(cols):
            f = img[r * fh : (r + 1) * fh, c * fw : (c + 1) * fw]
            out.append(f)
    return out[:count] if count else out


def make_sheet(frames: list[np.ndarray], columns: int = 0, padding: int = 0) -> tuple[np.ndarray, dict]:
    n = len(frames)
    h, w = frames[0].shape[:2]
    cols = columns or int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    sheet = np.zeros((rows * (h + padding), cols * (w + padding), 4), np.float32)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        sheet[r * (h + padding) : r * (h + padding) + h, c * (w + padding) : c * (w + padding) + w] = f
    return sheet, {"frame_w": w, "frame_h": h, "columns": cols, "rows": rows, "count": n, "padding": padding}


def save_gif(frames: list[np.ndarray], path: Path, fps: int, bg="#20242b", scale: int = 1) -> None:
    b = np.asarray(artlib.hex_to_rgb(bg), np.float32)
    ims = []
    for f in frames:
        rgb = f[..., :3] * f[..., 3:4] + b * (1 - f[..., 3:4])
        im = Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8), "RGB")
        if scale > 1:
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        ims.append(im)
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=int(1000 / max(1, fps)), loop=0)


def preview(frames: list[np.ndarray], max_w: int = 1024, bg="checker") -> Image.Image:
    """Contact sheet on a checker (or solid) background, nearest-upscaled for small pixel art."""
    sheet, meta = make_sheet(frames, padding=2)
    h, w = sheet.shape[:2]
    k = max(1, min(8, int(max_w / max(w, 1))))
    sheet = upscale(sheet, k)
    H, W = sheet.shape[:2]
    back = artlib.checker(H, W, max(4, 4 * k)) * 0.35 if bg == "checker" else np.broadcast_to(np.asarray(artlib.hex_to_rgb(bg), np.float32), (H, W, 3))
    rgb = sheet[..., :3] * sheet[..., 3:4] + back * (1 - sheet[..., 3:4])
    im = Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8), "RGB")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    return im


def lint(img: np.ndarray) -> dict:
    """Quick pixel-art health check."""
    A = img[..., 3]
    opaque = A > 0.5
    semi = int(((A > 0.02) & (A < 0.98)).sum())
    cols = img[..., :3][opaque]
    q = np.round(cols * 255).astype(np.int32)
    uniq = int(len(np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2]))) if len(q) else 0
    # orphan pixels: opaque pixel whose 4 neighbours all differ in color (noise)
    rgb8 = np.round(img[..., :3] * 255).astype(np.int32)
    key = rgb8[..., 0] * 65536 + rgb8[..., 1] * 256 + rgb8[..., 2]
    same = np.zeros_like(opaque)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        same |= (_shift(key, dx, dy) == key) & _shift(opaque, dx, dy)
    orphans = int((opaque & ~same).sum())
    ys, xs = np.nonzero(opaque)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    tips = []
    if semi and uniq <= 64:
        tips.append(f"{semi} semi-transparent px: pixel art usually wants hard alpha (0/255)")
    if uniq > 32:
        tips.append(f"{uniq} colors: consider a limited palette (quantize) for cohesion")
    if orphans > 0.03 * max(1, opaque.sum()):
        tips.append(f"{orphans} orphan pixels: noisy clusters, merge into readable shapes")
    return {"size": [img.shape[1], img.shape[0]], "opaque_px": int(opaque.sum()), "colors": uniq, "semi_transparent_px": semi, "orphan_px": orphans, "bbox": bbox, "tips": tips}


def write_effect(frames, meta, out_dir: Path, name: str, scale: int = 1, columns: int = 0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    fr = [upscale(f, scale) for f in frames] if scale > 1 else frames
    sheet, smeta = make_sheet(fr, columns)
    sp = out_dir / f"{name}_sheet.png"
    to_pil(sheet).save(sp, optimize=True)
    gp = out_dir / f"{name}.gif"
    save_gif(frames, gp, meta["fps"], scale=max(1, 128 // frames[0].shape[1]) if frames[0].shape[1] < 128 else 1)
    info = {**meta, **smeta, "sheet": str(sp), "gif": str(gp)}
    jp = out_dir / f"{name}.json"
    jp.write_text(json.dumps(info, indent=1))
    info["json"] = str(jp)
    return info
