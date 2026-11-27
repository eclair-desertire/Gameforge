"""Built-in synthesizer for gameforge-music (numpy only, no external audio libs).

* patches: subtractive (band-limited saw/pulse, supersaw, sub, noise) through a resonant 24 dB
  low-pass with its own envelope / LFO wobble, FM (bells, e-piano), additive organ, chip waves;
* drum kits: 808, 909, chip, lofi, taiko, acoustic (fallback for GM kits without a SoundFont);
* effects: resonant filter sweeps, drive, chorus, tempo delay, bitcrush, sidechain ducking,
  gated snare reverb, algorithmic reverbs (room/plate/hall/cathedral/space), lo-fi tape, stereo width.
Every patch also names a General MIDI program so the MIDI file stays playable in any DAW.
"""
from __future__ import annotations

import math

import numpy as np

SR = 48000


def mtof(p):
    return 440.0 * 2 ** ((np.asarray(p, float) - 69) / 12)


# ============================================================ oscillators

def _phase(freq: np.ndarray, sr: int, phase0: float = 0.0):
    dt = np.asarray(freq, float) / sr
    ph = (phase0 + np.concatenate([[0.0], np.cumsum(dt[:-1])])) % 1.0
    return ph, dt


def _blep(t, dt):
    y = np.zeros_like(t)
    a = t < dt
    if np.any(a):
        x = t[a] / dt[a]
        y[a] = x + x - x * x - 1
    b = t > 1 - dt
    if np.any(b):
        x = (t[b] - 1) / dt[b]
        y[b] = x * x + x + x + 1
    return y


def osc_saw(freq, sr, phase0=0.0):
    ph, dt = _phase(freq, sr, phase0)
    return 2 * ph - 1 - _blep(ph, dt)


def osc_pulse(freq, sr, width=0.5, phase0=0.0):
    ph, dt = _phase(freq, sr, phase0)
    ph2 = (ph + width) % 1.0
    s1 = 2 * ph - 1 - _blep(ph, dt)
    s2 = 2 * ph2 - 1 - _blep(ph2, dt)
    return 0.5 * (s1 - s2)


def osc_tri(freq, sr, phase0=0.0):
    ph, _ = _phase(freq, sr, phase0)
    return 1 - 4 * np.abs(ph - 0.5)


def osc_sine(freq, sr, phase0=0.0):
    ph, _ = _phase(freq, sr, phase0)
    return np.sin(2 * np.pi * ph)


# ============================================================ filters

def _lp_h(fr, fc, q):
    w = fr / fc
    h1 = 1.0 / (1 - w * w + 1j * w / q)          # resonant 2-pole
    h2 = 1.0 / (1 - w * w + 1j * w / 0.6)        # + plain 2-pole = 24 dB/oct
    return h1 * h2


def sweep_lp(x: np.ndarray, fc: np.ndarray | float, q: float, sr: int, bank: int = 8) -> np.ndarray:
    """Time-varying resonant low-pass: the signal is filtered at `bank` cutoffs (log-spaced) in the
    frequency domain and the outputs are cross-faded by the cutoff curve — vectorized and stable."""
    if x.ndim == 2:
        return np.stack([sweep_lp(x[:, c], fc, q, sr, bank) for c in range(x.shape[1])], 1)
    N = len(x)
    nfft = 1 << int(math.ceil(math.log2(N + 4096)))
    X = np.fft.rfft(x, nfft)
    fr = np.fft.rfftfreq(nfft, 1 / sr)
    fc = np.broadcast_to(np.asarray(fc, float), (N,)) if np.ndim(fc) else np.full(N, float(fc))
    fc = np.clip(fc, 25, sr * 0.45)
    lo, hi = float(fc.min()), float(fc.max())
    if hi / lo < 1.04:
        return np.fft.irfft(X * _lp_h(fr, (lo + hi) / 2, q), nfft)[:N]
    cuts = np.geomspace(lo, hi, bank)
    Y = np.stack([np.fft.irfft(X * _lp_h(fr, c, q), nfft)[:N] for c in cuts])
    pos = np.interp(np.log(fc), np.log(cuts), np.arange(bank))
    i0 = np.clip(np.floor(pos).astype(int), 0, bank - 2)
    fr_ = pos - i0
    idx = np.arange(N)
    return Y[i0, idx] * (1 - fr_) + Y[i0 + 1, idx] * fr_


def convolve(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Overlap-add FFT convolution (memory-safe for long tracks). x (N,C), h (M,C) or (M,)."""
    if x.ndim == 1:
        x = x[:, None]
    if h.ndim == 1:
        h = np.repeat(h[:, None], x.shape[1], 1)
    N, M = len(x), len(h)
    nfft = 1 << int(math.ceil(math.log2(2 * M + 1)))
    nfft = max(nfft, 1 << 16)
    block = nfft - M + 1
    H = np.fft.rfft(h, nfft, axis=0)
    out = np.zeros((N + M - 1, x.shape[1]), np.float64)
    for i in range(0, N, block):
        seg = x[i:i + block]
        y = np.fft.irfft(np.fft.rfft(seg, nfft, axis=0) * H, nfft, axis=0)[: len(seg) + M - 1]
        out[i:i + len(y)] += y
    return out


def fir(kind: str, cutoff: float, sr: int, taps: int = 1023, q: float = 0.707) -> np.ndarray:
    """Linear-phase FIR: lowpass | highpass at `cutoff` Hz."""
    n = 4096
    fr = np.fft.rfftfreq(n, 1 / sr)
    w = fr / cutoff
    mag = np.abs(1.0 / (1 - w * w + 1j * w / q)) if kind == "lowpass" else np.abs((w * w) / (1 - w * w + 1j * w / q))
    h = np.fft.irfft(mag, n)
    h = np.roll(h, taps // 2)[:taps] * np.hanning(taps)
    return h


def filt(x: np.ndarray, kind: str, cutoff: float, sr: int) -> np.ndarray:
    h = fir(kind, cutoff, sr)
    y = convolve(x if x.ndim == 2 else x[:, None], h)
    d = len(h) // 2
    y = y[d:d + len(x)]
    return y if x.ndim == 2 else y[:, 0]


# ============================================================ envelopes

def adsr(N: int, held: int, sr: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    t = np.arange(N) / sr
    a = max(a, 0.002)
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-3)))
    if held < N:
        lvl = e[max(0, held - 1)]
        e[held:] = lvl * np.exp(-np.arange(N - held) / (max(r, 0.004) * sr))
    f = min(N, int(0.004 * sr))
    e[-f:] *= np.linspace(1, 0, f)
    return e


# ============================================================ patches

def P(**kw):
    base = dict(osc="saw", adsr=(0.005, 0.2, 0.7, 0.15), gain=0.5, gm=81)
    base.update(kw)
    return base


PATCHES = {
    # leads
    "saw_lead": P(osc="saw", adsr=(0.005, 0.25, 0.75, 0.12), filter=dict(cut=2200, env=3500, fa=0.005, fd=0.25, q=1.1, key=0.5), vib=(0.12, 5.5, 0.25), glide=0.03, gm=81),
    "square_lead": P(osc="pulse", width=0.5, adsr=(0.004, 0.2, 0.75, 0.1), filter=dict(cut=2600, env=2500, fa=0.003, fd=0.2, q=0.9, key=0.5), vib=(0.1, 5.5, 0.3), gm=80),
    "pluck_lead": P(osc="pulse", width=0.3, adsr=(0.002, 0.35, 0.25, 0.25), filter=dict(cut=900, env=5500, fa=0.001, fd=0.18, q=1.3, key=0.6), gm=84, fx=dict(delay=0.75)),
    "glass_lead": P(osc="fm", ratio=3.0, index=1.6, idecay=1.2, adsr=(0.02, 0.8, 0.5, 0.6), vib=(0.08, 4.5, 0.4), gm=98, gain=0.45),
    "flute_synth": P(osc="sine", noise=0.05, adsr=(0.05, 0.3, 0.85, 0.15), vib=(0.15, 5.0, 0.3), gm=73, gain=0.55),
    "reed": P(osc="pulse", width=0.35, adsr=(0.03, 0.3, 0.8, 0.1), filter=dict(cut=1600, env=600, fa=0.03, fd=0.3, q=1.4, key=0.8), vib=(0.12, 5.2, 0.35), gm=68),
    "brass_synth": P(osc="saw", adsr=(0.04, 0.3, 0.8, 0.15), filter=dict(cut=700, env=3200, fa=0.06, fd=0.35, q=0.9, key=0.6), gm=62, gain=0.45),
    "dist_guitar": P(osc="saw", sub=0.3, adsr=(0.003, 0.5, 0.7, 0.12), filter=dict(cut=2600, env=1500, fa=0.002, fd=0.3, q=0.9, key=0.3), drive=4.0, gm=30, gain=0.35),
    # plucks / keys / mallets
    "pluck": P(osc="saw", adsr=(0.002, 0.25, 0.0, 0.2), filter=dict(cut=500, env=5000, fa=0.001, fd=0.12, q=1.6, key=0.6), gm=84, gain=0.5),
    "fm_bell": P(osc="fm", ratio=3.5, index=3.0, idecay=0.6, adsr=(0.002, 1.2, 0.0, 1.0), gm=14, gain=0.45),
    "fm_epiano": P(osc="fm", ratio=1.0, index=1.8, idecay=0.4, adsr=(0.002, 1.0, 0.25, 0.3), gm=4, gain=0.5, fx=dict(chorus=0.3)),
    "bell_keys": P(osc="fm", ratio=2.0, index=2.2, idecay=0.35, adsr=(0.002, 0.7, 0.15, 0.4), gm=11, gain=0.45),
    "mallet": P(osc="fm", ratio=4.0, index=2.5, idecay=0.08, adsr=(0.001, 0.35, 0.0, 0.25), gm=12, gain=0.55),
    "keys": P(osc="tri", sub=0.0, adsr=(0.002, 0.8, 0.2, 0.3), filter=dict(cut=1800, env=2500, fa=0.001, fd=0.3, q=0.8, key=0.7), gm=0, gain=0.6),
    "organ": P(osc="organ", drawbars=(0.8, 1.0, 0.6, 0.4, 0.3, 0.2), adsr=(0.006, 0.1, 0.9, 0.06), gm=16, gain=0.35, fx=dict(chorus=0.4)),
    # pads
    "supersaw": P(osc="supersaw", voices=7, detune=0.25, adsr=(0.01, 0.3, 0.8, 0.3), filter=dict(cut=4500, env=0, q=0.8), gm=81, gain=0.33),
    "synth_pad": P(osc="supersaw", voices=5, detune=0.15, adsr=(0.5, 1.0, 0.8, 1.2), filter=dict(cut=1600, env=900, fa=0.8, fd=2.0, q=0.9, key=0.3), gm=89, gain=0.3, fx=dict(chorus=0.3)),
    "atmosphere_pad": P(osc="supersaw", voices=5, detune=0.1, noise=0.03, adsr=(1.5, 2.0, 0.85, 2.5), filter=dict(cut=900, env=1400, fa=2.0, fd=3.0, q=1.2, key=0.2), gm=99, gain=0.3, fx=dict(chorus=0.5)),
    "dark_pad": P(osc="supersaw", voices=4, detune=0.08, adsr=(1.0, 2.0, 0.9, 2.0), filter=dict(cut=420, env=300, fa=2.0, fd=3.0, q=1.3, key=0.1), gm=95, gain=0.4),
    "string_pad": P(osc="supersaw", voices=5, detune=0.12, adsr=(0.25, 0.8, 0.85, 0.6), filter=dict(cut=2400, env=800, fa=0.3, fd=1.0, q=0.7, key=0.5), vib=(0.06, 5.0, 0.4), gm=50, gain=0.3),
    "choir_pad": P(osc="pulse", width=0.4, adsr=(0.35, 0.8, 0.85, 0.8), filter=dict(cut=1100, env=400, fa=0.4, fd=1.0, q=2.2, key=0.5), vib=(0.1, 4.8, 0.3), gm=52, gain=0.4, fx=dict(chorus=0.5)),
    # basses
    "sub_bass": P(osc="sine", adsr=(0.004, 0.2, 0.9, 0.06), drive=1.3, gm=38, gain=0.7),
    "analog_bass": P(osc="saw", sub=0.5, adsr=(0.003, 0.25, 0.6, 0.08), filter=dict(cut=280, env=1800, fa=0.002, fd=0.15, q=1.2, key=0.5), gm=38, gain=0.55),
    "acid_bass": P(osc="saw", adsr=(0.002, 0.2, 0.55, 0.06), filter=dict(cut=320, env=3200, fa=0.002, fd=0.16, q=4.0, key=0.4), drive=2.0, glide=0.05, gm=39, gain=0.45),
    "reese_bass": P(osc="supersaw", voices=2, detune=0.09, sub=0.6, adsr=(0.01, 0.4, 0.85, 0.1), filter=dict(cut=520, env=400, fa=0.01, fd=0.4, q=1.1, key=0.3), drive=1.6, gm=38, gain=0.45),
    "wobble_bass": P(osc="saw", sub=0.6, adsr=(0.005, 0.3, 0.9, 0.08), filter=dict(cut=180, env=2600, q=3.0, wobble=0.5), drive=2.4, gm=39, gain=0.45),
    "808_bass": P(osc="sine", adsr=(0.002, 1.2, 0.35, 0.25), pitch_env=(7, 0.03), drive=1.8, glide=0.04, gm=38, gain=0.75),
    "round_bass": P(osc="tri", sub=0.3, adsr=(0.003, 0.35, 0.6, 0.08), filter=dict(cut=500, env=800, fa=0.002, fd=0.1, q=0.8, key=0.6), gm=33, gain=0.7),
}

# loudness-matched gains (measured: lead/pluck/pad/bass reach the same RMS per voice at velocity 100)
LEVEL = {'saw_lead': 0.338, 'square_lead': 0.397, 'pluck_lead': 0.566, 'glass_lead': 0.268, 'flute_synth': 0.254, 'reed': 0.391,
         'brass_synth': 0.338, 'dist_guitar': 0.163, 'pluck': 0.529, 'fm_bell': 0.243, 'fm_epiano': 0.287, 'bell_keys': 0.223,
         'mallet': 0.362, 'keys': 0.307, 'organ': 0.217, 'supersaw': 0.539, 'synth_pad': 0.457, 'atmosphere_pad': 0.442,
         'dark_pad': 0.495, 'string_pad': 0.459, 'choir_pad': 0.236, 'sub_bass': 0.259, 'analog_bass': 0.462, 'acid_bass': 0.314,
         'reese_bass': 0.429, 'wobble_bass': 0.24, '808_bass': 0.245, 'round_bass': 0.452}
for _k, _g in LEVEL.items():
    PATCHES[_k]["gain"] = _g


# General MIDI program -> built-in patch (used when there is no SoundFont, or synth='synth')
def gm_fallback(program: int) -> str:
    p = int(program)
    if p in (4, 5):
        return "fm_epiano"
    if p < 8:
        return "keys"
    if p < 16:
        return "fm_bell" if p in (8, 9, 10, 14) else "mallet"
    if p < 24:
        return "organ"
    if p < 32:
        return "dist_guitar" if p >= 29 else "pluck"
    if p < 40:
        return "analog_bass" if p >= 38 else "round_bass"
    if p in (45, 46):
        return "pluck"
    if p == 47:
        return "sub_bass"
    if p < 52:
        return "string_pad"
    if p < 55:
        return "choir_pad"
    if p < 64:
        return "brass_synth"
    if p < 72:
        return "reed"
    if p < 80:
        return "flute_synth"
    if p < 88:
        return "saw_lead" if p in (81, 87) else "square_lead"
    if p < 96:
        return "synth_pad"
    if p < 104:
        return "atmosphere_pad"
    if p < 112:
        return "pluck"
    if p < 120:
        return "mallet"
    return "pluck"


# ============================================================ note rendering

def render_note(P: dict, pitch: int, dur_s: float, vel: int, sr: int, rng: np.random.Generator,
                spb: float = 0.5, prev_pitch: int | None = None, params: dict | None = None) -> np.ndarray:
    if params:
        P = {**P, **{k: v for k, v in params.items() if k in P or k in ("cut", "q", "drive", "detune")}}
    a, d, s, r = P["adsr"]
    held = max(16, int(dur_s * sr))
    N = held + int(max(r, 0.005) * 4.5 * sr)
    t = np.arange(N) / sr
    f0 = float(mtof(pitch + 12 * P.get("octave", 0)))
    freq = np.full(N, f0)
    if P.get("glide") and prev_pitch is not None and prev_pitch != pitch:
        fp = float(mtof(prev_pitch + 12 * P.get("octave", 0)))
        freq = f0 * (fp / f0) ** np.exp(-t / P["glide"])
    if P.get("pitch_env"):
        semi, tc = P["pitch_env"]
        freq = freq * 2 ** (semi / 12 * np.exp(-t / tc))
    if P.get("vib"):
        dep, rate, dly = P["vib"]
        freq = freq * 2 ** (dep / 12 * np.sin(2 * np.pi * rate * t) * np.clip((t - dly) / 0.25, 0, 1))
    o = P["osc"]
    ph0 = float(rng.uniform(0, 1))
    if o == "saw":
        y = osc_saw(freq, sr, ph0)
    elif o == "pulse":
        y = osc_pulse(freq, sr, P.get("width", 0.5), ph0)
    elif o == "tri":
        y = osc_tri(freq, sr, ph0)
    elif o == "sine":
        y = osc_sine(freq, sr, 0.0)
    elif o == "supersaw":
        n = int(P.get("voices", 7))
        det = float(P.get("detune", 0.2))
        L = np.zeros(N)
        R = np.zeros(N)
        for k in range(n):
            off = 0.0 if n == 1 else (k / (n - 1) * 2 - 1)
            ratio = 2 ** (off * det * 0.5 / 12)
            v = osc_saw(freq * ratio, sr, float(rng.uniform(0, 1))) * (1.0 if abs(off) < 1e-6 else 0.7)
            if k % 2 == 0:
                L += v * 0.8
                R += v * 0.4
            else:
                R += v * 0.8
                L += v * 0.4
        y = np.stack([L, R], 1) / math.sqrt(n)
    elif o == "fm":
        ph, _ = _phase(freq, sr)
        idx = P.get("index", 2.0) * np.exp(-t / max(P.get("idecay", 0.5), 1e-3)) * (0.5 + 0.5 * vel / 127) + P.get("index_sus", 0.1)
        y = np.sin(2 * np.pi * ph + idx * np.sin(2 * np.pi * P.get("ratio", 1.0) * ph))
    elif o == "organ":
        ph, _ = _phase(freq, sr)
        y = np.zeros(N)
        for w, h in zip(P.get("drawbars", (1, 0.5)), (0.5, 1, 2, 3, 4, 6)):
            if h * f0 < sr * 0.45:
                y += w * np.sin(2 * np.pi * h * ph)
        y /= max(1.0, sum(P.get("drawbars", (1,))) * 0.6)
    else:
        raise ValueError(f"osc {o}")
    if P.get("sub"):
        sub = osc_pulse(freq / 2, sr, 0.5, 0.0) * P["sub"]
        y = y + (sub[:, None] if y.ndim == 2 else sub)
    if P.get("noise"):
        nz = rng.uniform(-1, 1, N) * P["noise"]
        y = y + (nz[:, None] if y.ndim == 2 else nz)
    F = P.get("filter")
    if F:
        cut = F.get("cut", 2000) * (f0 / 261.63) ** F.get("key", 0.0)
        if params and "cut" in params:
            cut = float(params["cut"])
        q = float(params.get("q", F.get("q", 0.8))) if params else F.get("q", 0.8)
        if F.get("wobble"):
            per = F["wobble"] * spb
            lfo = 0.5 - 0.5 * np.cos(2 * np.pi * t / max(per, 1e-3))
            fc = cut + F.get("env", 0) * lfo
        elif F.get("env"):
            fa, fd = F.get("fa", 0.003), F.get("fd", 0.2)
            fe = np.where(t < fa, t / max(fa, 1e-4), np.exp(-(t - fa) / max(fd, 1e-3)))
            fc = cut + F["env"] * fe * (0.45 + 0.55 * vel / 127)
        else:
            fc = cut
        y = sweep_lp(y, fc, q, sr)
    env = adsr(N, held, sr, a, d, s, r)
    y = y * (env[:, None] if y.ndim == 2 else env) * (vel / 127) ** 0.9
    if P.get("drive"):
        dr = float(params.get("drive", P["drive"])) if params else P["drive"]
        y = np.tanh(y * dr) / math.tanh(dr)
    return (y * P.get("gain", 0.5)).astype(np.float32)


# ------------------------------------------------------------ chip (NES-like) voices

CHIP_WAVES = {"square", "pulse25", "pulse12", "triangle", "saw", "sine", "noise"}
CHIP_ENV = {"bass": (0.003, 0.08, 0.85, 0.03), "pad": (0.08, 0.3, 0.55, 0.25), "chords": (0.004, 0.12, 0.45, 0.06),
            "arp": (0.002, 0.09, 0.25, 0.04), "melody": (0.004, 0.1, 0.65, 0.07)}
CHIP_ROLE_WAVE = {"bass": "triangle", "pad": "pulse25", "chords": "pulse25", "arp": "pulse12", "melody": "square"}


def chip_note(kind: str, role: str, pitch: int, dur_s: float, vel: int, sr: int) -> np.ndarray:
    a, d, s, r = CHIP_ENV.get(role, CHIP_ENV["melody"])
    held = max(16, int(dur_s * sr))
    N = held + int(r * 5 * sr)
    t = np.arange(N) / sr
    f = float(mtof(pitch))
    if role in ("melody", "notes", "counter") and dur_s > 0.35:
        ph = np.cumsum(f * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.15) / 0.2, 0, 1))) / sr
    else:
        ph = f * t
    fr = ph % 1.0
    if kind == "square":
        x = np.where(fr < 0.5, 0.6, -0.6)
    elif kind == "pulse25":
        x = np.where(fr < 0.25, 0.6, -0.6)
    elif kind == "pulse12":
        x = np.where(fr < 0.125, 0.6, -0.6)
    elif kind == "triangle":
        x = np.round((1 - 4 * np.abs(fr - 0.5)) * 7.5) / 7.5 * 0.7
    elif kind == "saw":
        x = (2 * fr - 1) * 0.55
    else:
        x = np.sin(2 * np.pi * fr) * 0.8
    return (x * adsr(N, held, sr, a, d, s, r) * vel / 127).astype(np.float32)


# ============================================================ drum kits

SYNTH_KITS = {"808", "909", "chip", "lofi", "taiko", "acoustic"}


def _T(sec, sr):
    return np.arange(int(sec * sr)) / sr


def _sweep_sine(f_start, f_end, tc, dur, sr):
    t = _T(dur, sr)
    f = f_end + (f_start - f_end) * np.exp(-t / tc)
    return np.sin(2 * np.pi * np.cumsum(f) / sr), t


def _metal(dur, decay, sr, rng, bright=1.0):
    """808/909-style metallic hat: six detuned square oscillators, high-passed."""
    t = _T(dur, sr)
    x = np.zeros(len(t))
    for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0):
        x += np.sign(np.sin(2 * np.pi * f * 2.0 * bright * t + rng.uniform(0, 6.28)))
    x = x / 6 + rng.uniform(-0.5, 0.5, len(t)) * 0.6
    x = np.diff(np.concatenate([[0], x]))
    x = np.diff(np.concatenate([[0], x])) * 0.5
    return x * np.exp(-t / decay)


def _noise_hit(dur, decay, sr, rng, hp=True):
    t = _T(dur, sr)
    n = rng.uniform(-1, 1, len(t))
    if hp:
        n = np.diff(np.concatenate([[0], n]))
    return n * np.exp(-t / decay), t


def drum_hit(kit: str, pitch: int, vel: int, sr: int, rng: np.random.Generator, gated: bool = False) -> np.ndarray:
    v = (vel / 127) ** 1.1 * 0.65
    k = kit if kit in SYNTH_KITS else "acoustic"
    if k == "chip":
        x = _chip_drum(pitch, sr, rng)
        return (x * v).astype(np.float32)
    if pitch in (35, 36):                                   # kick
        if k == "808":
            s, t = _sweep_sine(120, 46, 0.05, 1.1, sr)
            x = np.tanh(2.2 * s * np.exp(-t / 0.45)) * 0.9
        elif k == "taiko":
            s, t = _sweep_sine(110, 62, 0.06, 1.3, sr)
            n, _ = _noise_hit(1.3, 0.05, sr, rng, hp=False)
            x = (s * np.exp(-t / 0.5) + 0.35 * n) * 0.95
        elif k == "lofi":
            s, t = _sweep_sine(110, 52, 0.035, 0.4, sr)
            x = s * np.exp(-t / 0.12) * 0.85
        else:                                               # 909 / acoustic
            s, t = _sweep_sine(170 if k == "909" else 130, 50, 0.035, 0.5, sr)
            x = np.tanh(1.6 * s * np.exp(-t / 0.2)) * 0.95
            c = int(0.004 * sr)
            x[:c] += rng.uniform(-0.5, 0.5, c) * np.linspace(1, 0, c)
    elif pitch in (38, 40):                                 # snare
        if k == "taiko":                                    # shime-daiko: high tight drum
            s, t = _sweep_sine(520, 420, 0.02, 0.25, sr)
            n, _ = _noise_hit(0.25, 0.03, sr, rng)
            x = 0.7 * s * np.exp(-t / 0.07) + 0.3 * n
        else:
            tone_f = {"808": 238, "909": 200, "lofi": 180}.get(k, 190)
            dec = {"808": 0.14, "909": 0.16, "lofi": 0.12}.get(k, 0.15)
            s, t = _sweep_sine(tone_f * 1.4, tone_f, 0.02, 0.35, sr)
            n, _ = _noise_hit(0.35, dec, sr, rng)
            x = 0.45 * s * np.exp(-t / 0.06) + 0.7 * n
            if k == "lofi":
                x = np.convolve(x, np.ones(6) / 6, "same")
        if gated:
            g = np.zeros(int(0.32 * sr))
            nz = rng.uniform(-1, 1, len(g))
            nz = np.convolve(nz, np.ones(4) / 4, "same")
            env = np.ones(len(g)) * 0.35
            env[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))
            g = nz * env
            y = np.zeros(max(len(x), len(g)))
            y[: len(x)] += x
            y[: len(g)] += g
            x = y
    elif pitch == 37:                                       # rim
        s, t = _sweep_sine(1800, 1700, 0.01, 0.06, sr)
        x = s * np.exp(-t / 0.012) * 0.6
    elif pitch == 39:                                       # clap
        t = _T(0.3, sr)
        x = np.zeros(len(t))
        for j in range(4):
            o = int(j * 0.011 * sr)
            seg = rng.uniform(-1, 1, len(t) - o) * np.exp(-np.arange(len(t) - o) / ((0.009 if j < 3 else 0.09) * sr))
            x[o:] += seg * 0.55
        x = np.diff(np.concatenate([[0], x]))
    elif pitch in (42, 44):                                 # closed / pedal hat
        x = _metal(0.08, 0.025 if k != "lofi" else 0.02, sr, rng) * (1.1 if k != "lofi" else 0.6)
    elif pitch == 46:                                       # open hat
        x = _metal(0.45, 0.16, sr, rng) * 0.9
    elif pitch in (49, 52, 55, 57):                         # crashes
        n, t = _noise_hit(1.8, 0.6 if pitch != 55 else 0.25, sr, rng)
        x = (n * 0.4 + _metal(1.8, 0.5, sr, rng, 1.3) * 0.3)
    elif pitch in (51, 53, 59):                             # ride
        x = _metal(1.2, 0.4, sr, rng, 1.6) * 0.35 + np.sin(2 * np.pi * 3100 * _T(1.2, sr)) * np.exp(-_T(1.2, sr) / 0.3) * 0.08
    elif pitch in (41, 43, 45, 47, 48, 50):                 # toms
        base = {41: 70, 43: 85, 45: 100, 47: 125, 48: 150, 50: 175}[pitch]
        if k == "taiko":
            base *= 0.7
        s, t = _sweep_sine(base * 1.6, base, 0.04, 0.6, sr)
        x = s * np.exp(-t / (0.25 if k != "taiko" else 0.45)) * 0.85
    elif pitch == 56:                                       # cowbell
        t = _T(0.35, sr)
        x = (np.sign(np.sin(2 * np.pi * 540 * t)) + np.sign(np.sin(2 * np.pi * 800 * t))) * 0.22 * np.exp(-t / 0.08)
    elif pitch in (60, 61, 62, 63, 64):                     # bongos / congas
        base = {60: 400, 61: 300, 62: 330, 63: 280, 64: 200}[pitch]
        s, t = _sweep_sine(base * 1.3, base, 0.01, 0.3, sr)
        x = s * np.exp(-t / (0.05 if pitch == 62 else 0.12)) * 0.7
    elif pitch in (65, 66):                                 # timbales
        s, t = _sweep_sine(700 if pitch == 65 else 520, 600 if pitch == 65 else 450, 0.01, 0.4, sr)
        x = s * np.exp(-t / 0.15) * 0.5
    elif pitch in (54, 69, 70, 82):                         # tambourine / cabasa / shaker
        n, t = _noise_hit(0.15, 0.03 if pitch != 54 else 0.06, sr, rng)
        x = np.diff(np.concatenate([[0], n])) * 0.5
    elif pitch in (75, 76, 77):                             # claves / woodblocks
        f = {75: 2500, 76: 1600, 77: 1100}[pitch]
        t = _T(0.08, sr)
        x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.015) * 0.6
    elif pitch == 81:                                       # triangle
        t = _T(1.5, sr)
        x = (np.sin(2 * np.pi * 4200 * t) + 0.5 * np.sin(2 * np.pi * 6300 * t)) * np.exp(-t / 0.5) * 0.15
    elif pitch == 67:                                       # agogo
        t = _T(0.3, sr)
        x = np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.1) * 0.4
    else:
        n, t = _noise_hit(0.1, 0.03, sr, rng)
        x = n * 0.4
    return (x * v).astype(np.float32)


def _chip_drum(pitch: int, sr: int, rnd: np.random.Generator) -> np.ndarray:
    def T(sec):
        return np.arange(int(sec * sr)) / sr
    if pitch in (35, 36):
        t = T(0.35); f = 50 + 110 * np.exp(-t / 0.04)
        x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.18)
        x[: int(0.003 * sr)] += rnd.uniform(-0.6, 0.6, int(0.003 * sr))
    elif pitch in (38, 40, 37, 39):
        t = T(0.25 if pitch != 37 else 0.05)
        tone = np.sin(2 * np.pi * (190 if pitch != 37 else 900) * t) * np.exp(-t / 0.05)
        # 'chip' noise: held random values (like a console noise channel)
        hold = 3
        nz = np.repeat(rnd.uniform(-1, 1, len(t) // hold + 1), hold)[: len(t)]
        x = 0.45 * tone + 0.6 * nz * np.exp(-t / (0.11 if pitch != 37 else 0.02))
    elif pitch in (42, 44, 46, 70, 54, 69):
        dur = {46: 0.28, 54: 0.12}.get(pitch, 0.05)
        t = T(dur + 0.02)
        n = np.diff(np.concatenate([[0], rnd.uniform(-1, 1, len(t))]))
        x = n * np.exp(-t / (dur / 2.5)) * 0.5
    elif pitch in (49, 51, 52, 55, 57):
        t = T(1.2 if pitch != 51 else 0.6)
        n = np.diff(np.concatenate([[0], rnd.uniform(-1, 1, len(t))]))
        x = n * np.exp(-t / (0.45 if pitch != 51 else 0.2)) * 0.3
    else:
        base = {41: 70, 43: 85, 45: 100, 47: 130, 48: 150, 50: 175}.get(pitch, 120)
        t = T(0.4); f = base * (1 + 0.5 * np.exp(-t / 0.03))
        x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.18) * 0.9
    return x


# ============================================================ effects

SPACES = {  # T60 seconds, pre-delay, brightness 0..1
    "room": (0.8, 0.006, 0.55), "plate": (1.7, 0.0, 0.95), "hall": (2.4, 0.02, 0.6),
    "cathedral": (4.6, 0.035, 0.45), "space": (7.5, 0.06, 0.5), "none": None,
}


def reverb_ir(space: str, sr: int, seed: int = 7) -> np.ndarray | None:
    if space not in SPACES:
        raise ValueError(f"reverb: {sorted(SPACES)}")
    p = SPACES[space]
    if p is None:
        return None
    t60, pre, bright = p
    rng = np.random.default_rng(seed)
    n = int(sr * t60 * 1.05)
    t = np.arange(n) / sr
    nz = rng.standard_normal((n, 2))
    w = int(2 + (1 - bright) * 14)
    k = np.ones(w) / w
    dark = np.stack([np.convolve(nz[:, c], k, "same") for c in range(2)], 1) * math.sqrt(w)
    mix = np.clip(t / t60 * (1.6 - bright), 0, 1)[:, None]
    ir = (nz * (1 - mix) + dark * mix) * (10 ** (-3 * t / t60))[:, None]
    fade = np.clip(t / 0.012, 0, 1)[:, None]                  # soft onset (diffuse build-up)
    ir *= fade
    for d, g in ((0.011, 0.5), (0.019, 0.38), (0.027, 0.3), (0.041, 0.22)):   # early reflections
        i = int(d * sr)
        if i < n:
            ir[i, 0] += g * rng.choice([-1, 1])
            ir[i + int(0.003 * sr) if i + int(0.003 * sr) < n else i, 1] += g * rng.choice([-1, 1])
    ir = np.concatenate([np.zeros((int(pre * sr), 2)), ir])
    return ir / np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) * 0.5


def chorus(x: np.ndarray, sr: int, amount: float = 0.3, rate: float = 0.7) -> np.ndarray:
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    N = len(x)
    t = np.arange(N) / sr
    out = np.empty_like(x)
    for c, ph in ((0, 0.0), (1, math.pi / 2)):
        d = (0.007 + 0.0025 * np.sin(2 * np.pi * rate * t + ph)) * sr
        idx = np.arange(N) - d
        wet = np.interp(idx, np.arange(N), x[:, c], left=0.0)
        out[:, c] = x[:, c] * (1 - amount * 0.5) + wet * amount
    return out


def delay(x: np.ndarray, sr: int, seconds: float, feedback: float = 0.35, mix: float = 0.25, taps: int = 5) -> np.ndarray:
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    y = x.copy()
    d = int(seconds * sr)
    for k in range(1, taps + 1):
        sh = d * k
        if sh >= len(x):
            break
        g = mix * feedback ** (k - 1)
        src = x[:-sh].mean(axis=1)
        y[sh:, k % 2] += src * g            # ping-pong
    return y


def bitcrush(x: np.ndarray, bits: float = 10, hold: int = 2) -> np.ndarray:
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    if hold > 1:
        idx = (np.arange(len(y)) // hold) * hold
        y = y[idx]
    return y


def duck_envelope(N: int, sr: int, kick_secs: list[float], depth: float, release: float) -> np.ndarray:
    """Sidechain 'pump': gain dips by `depth` at each kick and recovers over `release` seconds."""
    g = np.ones(N, np.float32)
    if depth <= 0:
        return g
    L = int(release * sr)
    a = int(0.004 * sr)
    curve = np.concatenate([np.linspace(1, 1 - depth, a), 1 - depth * (1 - (np.arange(L) / L) ** 1.6)]).astype(np.float32)
    for s in kick_secs:
        i = int(s * sr) - a // 2
        if i >= N:
            continue
        i0 = max(0, i)
        seg = curve[i0 - i:]
        e = min(N, i0 + len(seg))
        g[i0:e] = np.minimum(g[i0:e], seg[: e - i0])
    return g


def lofi(x: np.ndarray, sr: int, amount: float, seed: int = 11, noise: bool = True, circular: bool = False) -> np.ndarray:
    """Tape/vinyl: wow & flutter, low-pass, soft saturation, bit reduction, hiss and crackle.
    circular=True keeps a loop seamless (LFOs fit whole cycles into the loop, filters wrap around)."""
    if amount <= 0:
        return x
    rng = np.random.default_rng(seed)
    N = len(x)
    t = np.arange(N) / sr
    f1, f2 = 0.5, 6.5
    if circular:
        T = N / sr
        f1, f2 = max(1, round(f1 * T)) / T, max(1, round(f2 * T)) / T
    d = (0.004 + amount * (0.0016 * np.sin(2 * np.pi * f1 * t) + 0.00025 * np.sin(2 * np.pi * f2 * t))) * sr
    idx = np.arange(N) - d
    if circular:
        idx = idx % N
        y = np.stack([np.interp(idx, np.arange(N + 1), np.concatenate([x[:, c], x[:1, c]])) for c in range(x.shape[1])], 1)
        K = 2048
        z = np.concatenate([y[-K:], y, y[:K]])
        z = filt(z, "lowpass", 7500 - 3800 * amount, sr)
        z = filt(z, "highpass", 40 + 60 * amount, sr)
        y = z[K:K + N]
    else:
        y = np.stack([np.interp(idx, np.arange(N), x[:, c], left=0.0) for c in range(x.shape[1])], 1)
        y = filt(y, "lowpass", 7500 - 3800 * amount, sr)
        y = filt(y, "highpass", 40 + 60 * amount, sr)
    y = np.tanh(y * (1 + amount)) / math.tanh(1 + amount)
    y = bitcrush(y, 14 - 4 * amount, 1)
    if not noise:
        return y
    hiss = rng.standard_normal((N, 2)) * 10 ** ((-58 + 8 * amount) / 20)
    crack = np.zeros((N, 2))
    nclick = int(N / sr * 6 * amount)
    pos = rng.integers(0, N, nclick)
    crack[pos, rng.integers(0, 2, nclick)] = rng.uniform(-0.25, 0.25, nclick) * amount
    crack = np.stack([np.convolve(crack[:, c], np.ones(3) / 2, "same") for c in range(2)], 1)
    return y + hiss + crack


def width(x: np.ndarray, w: float) -> np.ndarray:
    m = (x[:, 0] + x[:, 1]) * 0.5
    s = (x[:, 0] - x[:, 1]) * 0.5 * w
    return np.stack([m + s, m - s], 1)


def drive(x: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return x
    k = 1 + amount * 3
    return np.tanh(x * k) / math.tanh(k)
