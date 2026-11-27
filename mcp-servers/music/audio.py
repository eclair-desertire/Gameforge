"""GameForge music audio: chiptune synth (numpy), FluidSynth renderer (SoundFont), seamless loop
rendering, stems, loudness (ffmpeg ebur128 / loudnorm), OGG export, analysis image (waveform +
spectrogram + loop seam check) and an sfxr-style game SFX generator."""
from __future__ import annotations

import io
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import musiccore as M

SR = 48000
SF_DIR = Path(os.path.expanduser(os.environ.get("GAMEFORGE_SOUNDFONTS", "~/.cache/gameforge/soundfonts")))


# ============================================================ tools discovery


def which_fluidsynth():
    return shutil.which("fluidsynth") or next((p for p in ("/opt/homebrew/bin/fluidsynth", "/usr/local/bin/fluidsynth") if os.path.exists(p)), None)


def which_ffmpeg():
    return shutil.which("ffmpeg") or next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if os.path.exists(p)), None)


def default_soundfont():
    env = os.environ.get("GAMEFORGE_SOUNDFONT")
    if env and os.path.exists(env):
        return env
    if SF_DIR.is_dir():
        for ext in (".sf3", ".sf2"):
            for f in sorted(SF_DIR.glob(f"*{ext}")):
                return str(f)
    return None


def status() -> dict:
    sf = default_soundfont()
    return {"fluidsynth": which_fluidsynth(), "soundfont": sf, "ffmpeg": which_ffmpeg(), "ogg_encoder": _ogg_encoder()[0] or None,
            "chip_synth": True,
            "ready_for": [x for x, ok in (("chip", True), ("soundfont", bool(which_fluidsynth() and sf)), ("ogg+lufs", bool(which_ffmpeg()))) if ok]}


# ============================================================ wav io


def write_wav(path: Path, x: np.ndarray, sr: int = SR, bits: int = 16) -> Path:
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = x[:, None]
    x = np.clip(x, -1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(bits // 8)
        w.setframerate(sr)
        if bits == 16:
            w.writeframes((x * 32767).astype("<i2").tobytes())
        else:
            i = (x * 8388607).astype("<i4")
            b = i.view(np.uint8).reshape(-1, 4)[:, :3]
            w.writeframes(b.tobytes())
    return path


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    path = Path(path)
    if path.suffix.lower() != ".wav":
        ff = which_ffmpeg()
        if not ff:
            raise ValueError("reading non-WAV audio needs ffmpeg")
        tmp = Path(tempfile.mkdtemp()) / "dec.wav"
        subprocess.run([ff, "-v", "error", "-y", "-i", str(path), "-c:a", "pcm_s16le", str(tmp)], check=True)
        path = tmp
    with wave.open(str(path), "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        i = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        i = np.where(i & 0x800000, i - 0x1000000, i)
        x = i.astype(np.float32) / 8388608
    elif sw == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
    else:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    return x.reshape(-1, ch), sr


# ============================================================ chiptune synth

ROLE_WAVE = {"bass": "triangle", "pad": "pulse25", "chords": "pulse25", "arp": "pulse12", "melody": "square", "notes": "square"}
ENV = {  # attack, decay, sustain level, release (seconds)
    "bass": (0.003, 0.08, 0.85, 0.03), "pad": (0.08, 0.3, 0.55, 0.25), "chords": (0.004, 0.12, 0.45, 0.06),
    "arp": (0.002, 0.09, 0.25, 0.04), "melody": (0.004, 0.1, 0.65, 0.07), "notes": (0.004, 0.1, 0.65, 0.07),
}


def _osc(kind: str, phase: np.ndarray) -> np.ndarray:
    f = phase % 1.0
    if kind == "square":
        return np.where(f < 0.5, 0.6, -0.6)
    if kind == "pulse25":
        return np.where(f < 0.25, 0.6, -0.6)
    if kind == "pulse12":
        return np.where(f < 0.125, 0.6, -0.6)
    if kind == "triangle":  # 4-bit stepped triangle like the NES
        tri = 1 - 4 * np.abs(f - 0.5)
        return np.round(tri * 7.5) / 7.5 * 0.7
    if kind == "saw":
        return (2 * f - 1) * 0.55
    if kind == "sine":
        return np.sin(2 * np.pi * f) * 0.8
    raise ValueError(kind)


def _env(n: int, sr: int, a: float, d: float, s: float, r: float, held: int) -> np.ndarray:
    t = np.arange(n) / sr
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    if held < n:
        rel = np.exp(-(np.arange(n - held)) / (max(r, 1e-3) * sr))
        e[held:] = e[held - 1 if held > 0 else 0] * rel
    return e


def _drum(pitch: int, n_vel: float, sr: int, rnd: np.random.Generator) -> np.ndarray:
    def T(sec):
        return np.arange(int(sec * sr)) / sr
    if pitch == 36:  # kick
        t = T(0.35); f = 50 + 110 * np.exp(-t / 0.04)
        x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.18)
        x[: int(0.003 * sr)] += rnd.uniform(-0.6, 0.6, int(0.003 * sr))
    elif pitch in (38, 40, 37):  # snare / rim
        t = T(0.25 if pitch != 37 else 0.05)
        tone = np.sin(2 * np.pi * (190 if pitch != 37 else 900) * t) * np.exp(-t / 0.05)
        noise = rnd.uniform(-1, 1, len(t)) * np.exp(-t / (0.11 if pitch != 37 else 0.02))
        x = 0.45 * tone + 0.6 * noise
    elif pitch == 39:  # clap: three bursts
        t = T(0.25); x = np.zeros(len(t))
        for k in range(3):
            o = int(k * 0.012 * sr)
            seg = rnd.uniform(-1, 1, len(t) - o) * np.exp(-np.arange(len(t) - o) / (0.012 * sr if k < 2 else 0.08 * sr))
            x[o:] += seg * 0.6
    elif pitch in (42, 44, 46, 70, 54):  # hats / shaker / tambourine
        dur = {42: 0.05, 44: 0.06, 46: 0.28, 70: 0.07, 54: 0.12}[pitch]
        t = T(dur + 0.02); n = rnd.uniform(-1, 1, len(t))
        n = np.diff(np.concatenate([[0], n]))  # crude high-pass
        x = n * np.exp(-t / (dur / 2.5)) * 0.5
    elif pitch in (49, 51, 57):  # crash / ride
        t = T(1.6 if pitch == 49 else 0.8); n = rnd.uniform(-1, 1, len(t))
        n = np.diff(np.concatenate([[0], n]))
        x = n * np.exp(-t / (0.55 if pitch == 49 else 0.25)) * 0.35
    elif pitch in (45, 47, 50, 41, 43, 48):  # toms / timpani
        base = {41: 70, 43: 85, 45: 100, 47: 130, 48: 150, 50: 175}.get(pitch, 110)
        t = T(0.45); f = base * (1 + 0.5 * np.exp(-t / 0.03))
        x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.2) * 0.9
    else:
        t = T(0.1); x = rnd.uniform(-1, 1, len(t)) * np.exp(-t / 0.03) * 0.4
    return x * n_vel


def _reverb_ir(sr: int, seconds: float = 1.6, seed: int = 7) -> np.ndarray:
    rnd = np.random.default_rng(seed)
    n = int(sr * seconds)
    t = np.arange(n) / sr
    ir = rnd.standard_normal((n, 2)) * np.exp(-t / (seconds / 6.9))[:, None]
    ir[: int(0.012 * sr)] = 0  # pre-delay
    return ir / np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) * 0.6


def _fft_conv(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    out = np.fft.irfft(np.fft.rfft(x, N, axis=0) * np.fft.rfft(ir, N, axis=0), N, axis=0)[:n]
    return out


def render_chip(song: M.Song, sr: int = SR, repeat: int = 1, tracks: list[str] | None = None, reverb: float = 0.25, seed: int = 3) -> np.ndarray:
    """Synthesize the song (or selected tracks) into stereo float audio. repeat>1 for loop renders."""
    rnd = np.random.default_rng(seed)
    spb = 60.0 / song.tempo
    body = song.length_beats
    total = int((body * repeat * spb + 2.0) * sr)
    dry = np.zeros((total, 2), np.float32)
    send = np.zeros((total, 2), np.float32)
    for tr in song.tracks:
        if tracks and tr.name not in tracks:
            continue
        kind = tr.instrument if isinstance(tr.instrument, str) and tr.instrument in M.CHIP_WAVES else ROLE_WAVE.get(tr.role, "square")
        a, d, s, r = ENV.get(tr.role, ENV["notes"])
        gl = math.cos((tr.pan + 1) * math.pi / 4)
        gr = math.sin((tr.pan + 1) * math.pi / 4)
        buf = np.zeros(total, np.float32)
        for rep in range(repeat):
            for n in tr.notes:
                st = int((n.start + rep * body) * spb * sr)
                if st >= total:
                    continue
                v = n.vel / 127
                if tr.drums or kind == "noise":
                    x = _drum(n.pitch if tr.drums else 38, v, sr, rnd)
                else:
                    held = int(n.dur * spb * sr)
                    ln = held + int(r * 5 * sr)
                    t = np.arange(ln) / sr
                    f = 440.0 * 2 ** ((n.pitch - 69) / 12)
                    if tr.role in ("melody", "notes") and n.dur * spb > 0.35:  # delayed vibrato on long lead notes
                        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.15) / 0.2, 0, 1)
                        phase = np.cumsum(f * vib) / sr
                    else:
                        phase = f * t
                    x = _osc(kind, phase) * _env(ln, sr, a, d, s, r, held) * v
                e = min(total, st + len(x))
                buf[st:e] += x[: e - st].astype(np.float32)
        buf *= tr.volume
        dry[:, 0] += buf * gl
        dry[:, 1] += buf * gr
        send[:, 0] += buf * gl * tr.reverb
        send[:, 1] += buf * gr * tr.reverb
    if reverb > 0 and np.any(send):
        wet = _fft_conv(send, _reverb_ir(sr))[:total]
        dry += wet.astype(np.float32) * reverb * 2.5
    return dry


# ============================================================ fluidsynth


def render_fluidsynth(song: M.Song, sf: str | None = None, sr: int = SR, repeat: int = 1, tracks: list[str] | None = None,
                      gain: float = 0.6, reverb: bool = True) -> np.ndarray:
    fs = which_fluidsynth()
    sf = sf or default_soundfont()
    if not fs:
        raise ValueError("FluidSynth not installed (brew install fluid-synth) — use synth='chip' or run gameforge:doctor")
    if not sf or not os.path.exists(sf):
        raise ValueError(f"no SoundFont in {SF_DIR} — run gameforge:doctor (MuseScore_General.sf3, MIT) or pass soundfont=")
    tmp = Path(tempfile.mkdtemp(prefix="gf_mus_"))
    mid = M.write_midi(song, tmp / "song.mid", repeat=repeat, tracks=tracks)
    out = tmp / "out.wav"
    cmd = [fs, "-ni", "-q", "-g", str(gain), "-r", str(sr), "-o", f"synth.reverb.active={'1' if reverb else '0'}",
           "-o", "synth.chorus.active=0", "-F", str(out), sf, str(mid)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not out.exists():
        raise ValueError(f"fluidsynth failed: {p.stderr.strip()[:400]}")
    x, fsr = read_audio(out)
    shutil.rmtree(tmp, ignore_errors=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x


# ============================================================ render pipeline


def _loop_cut(x: np.ndarray, song: M.Song, sr: int) -> np.ndarray:
    """Body rendered twice: keep the 2nd pass so the reverb/release tail of the end flows into the start."""
    L = int(round(song.length_beats * 60.0 / song.tempo * sr))
    seg = x[L: 2 * L]
    if len(seg) < L:
        seg = np.concatenate([seg, np.zeros((L - len(seg), x.shape[1]), x.dtype)])
    return seg


def _trim_tail(x: np.ndarray, song: M.Song, sr: int, max_tail: float = 3.0) -> np.ndarray:
    L = int(song.length_beats * 60.0 / song.tempo * sr)
    end = min(len(x), L + int(max_tail * sr))
    y = x[:end]
    mag = np.max(np.abs(y), axis=1)
    above = np.nonzero(mag > 10 ** (-60 / 20))[0]
    if len(above):
        y = y[: min(len(y), max(L, above[-1] + int(0.05 * sr)))]
    fade = min(len(y), int(0.05 * sr))
    y[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return y


def render(song: M.Song, synth: str = "auto", sr: int = SR, tracks: list[str] | None = None, soundfont: str | None = None) -> tuple[np.ndarray, str]:
    if synth == "auto":
        synth = "soundfont" if (which_fluidsynth() and (soundfont or default_soundfont())) else "chip"
        if all((isinstance(t.instrument, str) and t.instrument in M.CHIP_WAVES) or t.drums for t in song.tracks):
            synth = "chip"
    rep = 2 if song.loop else 1
    if synth == "chip":
        x = render_chip(song, sr, rep, tracks)
    elif synth == "soundfont":
        x = render_fluidsynth(song, soundfont, sr, rep, tracks)
    else:
        raise ValueError("synth: auto | chip | soundfont")
    x = _loop_cut(x, song, sr) if song.loop else _trim_tail(x, song, sr)
    return x.astype(np.float32), synth


# ============================================================ loudness & export


def lufs(path: Path) -> dict:
    ff = which_ffmpeg()
    if not ff:
        x, sr = read_audio(path)
        rms = np.sqrt(np.mean(x ** 2) + 1e-12)
        return {"integrated_lufs": round(20 * math.log10(rms) - 0.7, 1), "true_peak_db": round(20 * math.log10(np.max(np.abs(x)) + 1e-9), 1), "method": "approx (no ffmpeg)"}
    p = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = p.stderr
    I = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", txt)
    LRA = re.findall(r"LRA:\s+([\d.]+) LU", txt)
    pk = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", txt)
    f = lambda s: float("-inf") if s == "-inf" else float(s)
    return {"integrated_lufs": f(I[-1]) if I else None, "lra": float(LRA[-1]) if LRA else None,
            "true_peak_db": f(pk[-1]) if pk else None, "method": "ffmpeg ebur128"}


def normalize(x: np.ndarray, sr: int, target_lufs: float = -16.0, ceiling_db: float = -1.0) -> tuple[np.ndarray, dict]:
    """Linear gain to the target loudness (measured with ffmpeg) + soft ceiling. Linear gain keeps loops seamless."""
    tmp = Path(tempfile.mkdtemp()) / "m.wav"
    write_wav(tmp, x, sr)
    m = lufs(tmp)
    cur = m["integrated_lufs"]
    if cur is None or cur == float("-inf"):
        return x, {"skipped": "silence"}
    g = 10 ** ((target_lufs - cur) / 20)
    y = x * g
    ceil = 10 ** (ceiling_db / 20)
    over = np.abs(y) > ceil * 0.9
    if np.any(over):  # soft knee limiter above 90% of the ceiling
        knee = ceil * 0.9
        s = np.sign(y)
        a = np.abs(y)
        y = np.where(a > knee, s * (knee + (ceil - knee) * np.tanh((a - knee) / (ceil - knee))), y)
    return y.astype(np.float32), {"measured_lufs": cur, "gain_db": round(20 * math.log10(g), 2), "target_lufs": target_lufs}


def _ogg_encoder() -> tuple[str, list[str]]:
    """Best available Vorbis encoder: libvorbis (ffmpeg) > oggenc (vorbis-tools) > ffmpeg native vorbis."""
    ff = which_ffmpeg()
    if ff:
        enc = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if " libvorbis " in enc:
            return "libvorbis", ["-c:a", "libvorbis", "-q:a", "{q}"]
    if shutil.which("oggenc"):
        return "oggenc", []
    if ff:
        return "vorbis(native)", ["-c:a", "vorbis", "-strict", "experimental", "-b:a", "192k"]
    return "", []


def export(x: np.ndarray, sr: int, path: Path, fmt: str = "ogg", quality: int = 6) -> list[str]:
    """fmt: wav | ogg | mp3 | both (wav+ogg). Returns written files; notes the encoder used for OGG."""
    path = Path(path)
    wav = path.with_suffix(".wav")
    write_wav(wav, x, sr, 16)
    files = [str(wav)]
    ff = which_ffmpeg()
    if fmt in ("ogg", "both"):
        name, args = _ogg_encoder()
        ogg = path.with_suffix(".ogg")
        if name == "oggenc":
            subprocess.run([shutil.which("oggenc"), "-Q", "-q", str(quality), "-o", str(ogg), str(wav)], check=True)
        elif name:
            subprocess.run([ff, "-v", "error", "-y", "-i", str(wav)] + [a.replace("{q}", str(quality)) for a in args] + [str(ogg)], check=True)
        else:
            raise ValueError("OGG export needs ffmpeg or oggenc — run gameforge:doctor, or use fmt='wav'")
        files.append(str(ogg))
    if fmt == "mp3":
        if not ff:
            raise ValueError("MP3 export needs ffmpeg")
        mp3 = path.with_suffix(".mp3")
        subprocess.run([ff, "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "2", str(mp3)], check=True)
        files.append(str(mp3))
    if fmt in ("ogg", "mp3"):
        wav.unlink()
        files.remove(str(wav))
    return files


# ============================================================ analysis


def _cmap(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0, 1)
    r = np.clip(1.5 * v - 0.2, 0, 1)
    g = np.clip(1.8 * v - 0.7, 0, 1)
    b = np.clip(0.6 + 0.8 * v - 1.4 * v * v, 0, 1)
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def analyze(path: Path, loop: bool | None = None) -> tuple[dict, Image.Image]:
    x, sr = read_audio(Path(path))
    mono = x.mean(axis=1)
    dur = len(mono) / sr
    peak = float(np.max(np.abs(x)) + 1e-12)
    info = {"file": str(path), "seconds": round(dur, 3), "sample_rate": sr, "channels": x.shape[1],
            "peak_dbfs": round(20 * math.log10(peak), 2), "dc_offset": round(float(mono.mean()), 5)}
    info.update(lufs(Path(path)))
    thr = 10 ** (-60 / 20)
    nz = np.nonzero(np.abs(mono) > thr)[0]
    info["silence_head_ms"] = round(nz[0] / sr * 1000, 1) if len(nz) else None
    info["silence_tail_ms"] = round((len(mono) - nz[-1]) / sr * 1000, 1) if len(nz) else None
    # spectral balance
    N = min(len(mono), sr * 30)
    spec = np.abs(np.fft.rfft(mono[:N] * np.hanning(N))) ** 2
    fr = np.fft.rfftfreq(N, 1 / sr)
    bands = {"sub_<60": (0, 60), "low_60-250": (60, 250), "mid_250-2k": (250, 2000), "high_2k-8k": (2000, 8000), "air_>8k": (8000, sr / 2)}
    tot = spec.sum() + 1e-12
    info["spectrum_%"] = {k: round(100 * spec[(fr >= a) & (fr < b)].sum() / tot, 1) for k, (a, b) in bands.items()}
    # loop seam: compare the very end with the very start
    # click test: the jump across the loop point vs the normal sample-to-sample motion around it
    w = int(0.01 * sr)
    jump = float(np.max(np.abs(x[-1] - x[0])))
    local = np.concatenate([np.abs(np.diff(x[-w:], axis=0)).ravel(), np.abs(np.diff(x[:w], axis=0)).ravel()])
    typical = float(np.percentile(local, 99) + 1e-6)
    rms_end = float(np.sqrt(np.mean(x[-4 * w:] ** 2)) + 1e-9)
    rms_start = float(np.sqrt(np.mean(x[:4 * w] ** 2)) + 1e-9)
    seam = {"sample_jump": round(jump, 4), "jump_vs_local": round(jump / typical, 2), "rms_ratio_end_start": round(rms_end / rms_start, 2)}
    if jump / typical > 3:
        seam["verdict"] = "click risk at the loop point (discontinuity) — render with loop=true or add a short crossfade"
    elif not 0.1 < rms_end / rms_start < 10:
        seam["verdict"] = "level jump at the loop point — check the arrangement of the last/first bar"
    else:
        seam["verdict"] = "ok (continuous; a louder downbeat at the start is normal)"
    if loop is not False:
        info["loop_seam"] = seam
    # image: waveform + spectrogram
    W, Hw, Hs = 1200, 160, 260
    img = Image.new("RGB", (W, Hw + Hs + 24), (20, 22, 28))
    dr = ImageDraw.Draw(img)
    cols = np.array_split(mono, W)
    for i, c in enumerate(cols):
        if len(c):
            a, b = float(c.min()), float(c.max())
            dr.line([i, Hw / 2 - b * Hw / 2.1, i, Hw / 2 - a * Hw / 2.1], fill=(120, 200, 255))
    dr.line([0, Hw / 2, W, Hw / 2], fill=(60, 60, 70))
    hop = max(256, len(mono) // W)
    nfft = 2048
    frames = []
    for i in range(0, max(1, len(mono) - nfft), hop):
        seg = mono[i:i + nfft]
        if len(seg) < nfft:
            break
        frames.append(np.abs(np.fft.rfft(seg * np.hanning(nfft))))
    if frames:
        S = 20 * np.log10(np.array(frames).T + 1e-9)
        S = (S - (S.max() - 80)) / 80
        fbins = np.fft.rfftfreq(nfft, 1 / sr)
        ys = np.geomspace(40, sr / 2, Hs)
        idx = np.searchsorted(fbins, ys).clip(0, len(fbins) - 1)
        Sm = S[idx][::-1]
        sp = Image.fromarray(_cmap(Sm)).resize((W, Hs))
        img.paste(sp, (0, Hw))
    dr.text((6, Hw + Hs + 6), f"{Path(path).name}  {dur:.2f}s  peak {info['peak_dbfs']} dBFS  {info.get('integrated_lufs')} LUFS", fill=(220, 220, 225))
    return info, img


# ============================================================ SFX (sfxr-style)

SFX_KINDS = ["coin", "jump", "laser", "explosion", "hit", "hurt", "powerup", "blip", "ui_click", "ui_confirm", "ui_cancel", "error", "magic", "whoosh", "footstep", "land"]


def _sfx_params(kind: str, r: random.Random) -> dict:
    U = r.uniform
    P = dict(wave="square", f=440.0, slide=0.0, vib=0.0, vib_hz=0.0, a=0.002, sus=0.05, dec=0.2, punch=0.0,
             arp=1.0, arp_t=0.0, rep=0.0, lpf=1.0, lpf_sweep=0.0, hpf=0.0, duty=0.5, noise_mix=0.0, gain=0.8)
    if kind == "coin":
        P.update(f=U(850, 1350), arp=U(1.3, 1.6), arp_t=U(0.04, 0.08), sus=U(0.03, 0.08), dec=U(0.15, 0.3), duty=U(0.3, 0.5))
    elif kind == "jump":
        P.update(f=U(260, 480), slide=U(1.2, 2.4), sus=U(0.04, 0.1), dec=U(0.15, 0.28), duty=U(0.2, 0.5))
    elif kind == "laser":
        P.update(wave=r.choice(["square", "saw"]), f=U(800, 1500), slide=-U(3.5, 7), sus=U(0.03, 0.08), dec=U(0.1, 0.22), duty=U(0.1, 0.4))
    elif kind == "explosion":
        P.update(wave="noise", f=U(60, 160), slide=-U(0.3, 1.2), a=0.001, sus=U(0.08, 0.2), dec=U(0.5, 1.1), punch=U(0.3, 0.7), lpf=U(0.4, 0.8), lpf_sweep=-U(0.5, 1.5), gain=1.0)
    elif kind == "hit":
        P.update(wave=r.choice(["noise", "square"]), f=U(180, 380), slide=-U(2, 5), sus=0.01, dec=U(0.08, 0.16), punch=U(0.3, 0.6), noise_mix=U(0.3, 0.7))
    elif kind == "hurt":
        P.update(wave="saw", f=U(300, 520), slide=-U(1.5, 3), sus=U(0.02, 0.06), dec=U(0.15, 0.3), noise_mix=U(0.2, 0.4), vib=U(0.05, 0.12), vib_hz=U(18, 30))
    elif kind == "powerup":
        P.update(f=U(280, 460), slide=U(0.8, 1.8), sus=U(0.15, 0.3), dec=U(0.2, 0.35), rep=U(0.08, 0.14), vib=U(0.0, 0.03), vib_hz=8)
    elif kind == "blip":
        P.update(f=U(600, 1100), sus=U(0.02, 0.05), dec=U(0.03, 0.08), duty=U(0.25, 0.5))
    elif kind == "ui_click":
        P.update(wave=r.choice(["triangle", "sine"]), f=U(1500, 2600), a=0.0005, sus=0.005, dec=U(0.015, 0.035), gain=0.6)
    elif kind == "ui_confirm":
        P.update(wave="triangle", f=U(600, 800), arp=U(1.45, 1.55), arp_t=U(0.06, 0.08), sus=0.06, dec=0.12)
    elif kind == "ui_cancel":
        P.update(wave="triangle", f=U(560, 700), arp=U(0.72, 0.8), arp_t=U(0.06, 0.08), sus=0.05, dec=0.12)
    elif kind == "error":
        P.update(wave="square", f=U(150, 220), arp=0.85, arp_t=0.09, sus=0.12, dec=0.08, duty=0.5, rep=0.0, gain=0.7)
    elif kind == "magic":
        P.update(wave=r.choice(["sine", "triangle"]), f=U(500, 800), slide=U(0.6, 1.4), vib=U(0.02, 0.05), vib_hz=U(6, 11), sus=U(0.2, 0.35), dec=U(0.4, 0.7), rep=U(0.06, 0.1), a=0.03)
    elif kind == "whoosh":
        P.update(wave="noise", f=400, a=U(0.08, 0.16), sus=U(0.05, 0.12), dec=U(0.15, 0.3), lpf=U(0.08, 0.2), lpf_sweep=U(1.5, 3), hpf=0.05, gain=0.9)
    elif kind == "footstep":
        P.update(wave="noise", f=120, a=0.001, sus=0.005, dec=U(0.05, 0.09), lpf=U(0.15, 0.3), punch=0.4, noise_mix=0.0, gain=0.9)
    elif kind == "land":
        P.update(wave="sine", f=U(90, 130), slide=-U(1.5, 3), a=0.001, sus=0.01, dec=U(0.12, 0.2), noise_mix=U(0.3, 0.5), punch=0.5)
    else:
        raise ValueError(f"sfx kind: {SFX_KINDS}")
    return P


def synth_sfx(P: dict, sr: int = 44100, seed: int = 0) -> np.ndarray:
    nr = np.random.default_rng(seed)
    dur = P["a"] + P["sus"] + P["dec"]
    n = int(dur * sr) + 1
    t = np.arange(n) / sr
    f = P["f"] * np.exp(P["slide"] * t)
    if P["arp_t"] > 0:
        f = np.where(t >= P["arp_t"], f * P["arp"], f)
    if P["rep"] > 0:  # retrigger: restart the slide periodically
        tt = t % P["rep"]
        f = P["f"] * np.exp(P["slide"] * tt) * (1 + 0.25 * np.floor(t / P["rep"]))
    if P["vib"] > 0:
        f = f * (1 + P["vib"] * np.sin(2 * np.pi * P["vib_hz"] * t))
    f = np.clip(f, 20, sr / 2 - 100)
    ph = np.cumsum(f) / sr
    w = P["wave"]
    if w == "noise":
        # pitched noise: hold random values for one period (classic sfxr noise)
        idx = np.floor(ph * 8).astype(int)
        vals = nr.uniform(-1, 1, idx.max() + 2)
        x = vals[idx]
    elif w in ("square",):
        x = np.where((ph % 1) < P["duty"], 0.7, -0.7)
    else:
        x = _osc({"saw": "saw", "sine": "sine", "triangle": "triangle"}[w], ph)
    if P["noise_mix"] > 0:
        x = x * (1 - P["noise_mix"]) + nr.uniform(-1, 1, n) * P["noise_mix"]
    env = np.where(t < P["a"], t / max(P["a"], 1e-4), np.where(t < P["a"] + P["sus"], 1.0 + P["punch"] * (1 - (t - P["a"]) / max(P["sus"], 1e-4)), np.clip(1 - (t - P["a"] - P["sus"]) / max(P["dec"], 1e-4), 0, 1) ** 1.6))
    x = x * env
    if P["lpf"] < 1 or P["lpf_sweep"]:
        y = np.empty_like(x)
        acc = 0.0
        cut = P["lpf"]
        for i in range(n):
            c = min(1.0, max(0.005, cut * math.exp(P["lpf_sweep"] * t[i])))
            acc += c * (x[i] - acc)
            y[i] = acc
        x = y
    if P["hpf"] > 0:
        y = np.empty_like(x)
        prev_x = prev_y = 0.0
        a = 1 - P["hpf"]
        for i in range(n):
            prev_y = a * (prev_y + x[i] - prev_x)
            prev_x = x[i]
            y[i] = prev_y
        x = y
    fade = min(n, int(0.004 * sr))
    x[-fade:] *= np.linspace(1, 0, fade)
    pk = np.max(np.abs(x)) + 1e-9
    return (x / pk * 10 ** (-1 / 20) * P["gain"]).astype(np.float32)


def sfx_set(kind: str, variations: int, seed: int, out_dir: Path, name: str = "", sr: int = 44100) -> tuple[list[str], Image.Image]:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = random.Random(seed)
    files, waves = [], []
    for v in range(variations):
        P = _sfx_params(kind, r)
        x = synth_sfx(P, sr, seed * 101 + v)
        f = out_dir / f"{name or 'sfx_' + kind}_{v + 1:02d}.wav"
        write_wav(f, x, sr)
        files.append(str(f))
        waves.append(x)
    W, H = 1000, 90 * len(waves)
    img = Image.new("RGB", (W, H), (20, 22, 28))
    dr = ImageDraw.Draw(img)
    mx = max(len(w) for w in waves)
    for k, w in enumerate(waves):
        y0 = k * 90 + 45
        cols = np.array_split(w, max(1, int(W * len(w) / mx)))
        for i, c in enumerate(cols):
            if len(c):
                dr.line([i, y0 - c.max() * 40, i, y0 - c.min() * 40], fill=(255, 190, 110))
        dr.text((6, k * 90 + 4), f"{Path(files[k]).name}  {len(w) / sr * 1000:.0f} ms", fill=(220, 220, 225))
    return files, img


def png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()
