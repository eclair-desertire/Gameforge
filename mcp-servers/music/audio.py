"""GameForge music audio: hybrid renderer — per track, FluidSynth + SoundFont (GM instruments and
kits), the built-in synthesizer (synth patches, 808/909/lofi/taiko kits, GM fallback without a
SoundFont) or the chiptune engine — mixed with sends into one algorithmic reverb space, sidechain
ducking, track FX, master FX (lo-fi tape, width, drive), seamless loops, stems, loudness (ffmpeg
ebur128), OGG/MP3/WAV export, analysis image and an sfxr-style SFX generator."""
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
import hashlib
import zlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import musiccore as M
import synth as S
from model import Song, Track

SR = 48000
SF_DIR = Path(os.path.expanduser(os.environ.get("GAMEFORGE_SOUNDFONTS", "~/.cache/gameforge/soundfonts")))
SF_GAIN = 3.5          # FluidSynth group level relative to the built-in synth (calibrated: same parts, same RMS)


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
            "builtin_synth": True, "synth_patches": sorted(S.PATCHES), "synth_kits": sorted(S.SYNTH_KITS),
            "ready_for": [x for x, ok in (("chip", True), ("synth", True), ("soundfont", bool(which_fluidsynth() and sf)), ("ogg+lufs", bool(which_ffmpeg()))) if ok]}


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
    tmpdir = None
    if path.suffix.lower() != ".wav":
        ff = which_ffmpeg()
        if not ff:
            raise ValueError("reading non-WAV audio needs ffmpeg")
        tmpdir = Path(tempfile.mkdtemp())
        tmp = tmpdir / "dec.wav"
        subprocess.run([ff, "-v", "error", "-y", "-i", str(path), "-c:a", "pcm_s16le", str(tmp)], check=True)
        path = tmp
    with wave.open(str(path), "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
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


# ============================================================ engines per track


def engine_of(tr: Track, pref: str, sf_ok: bool) -> str:
    """-> 'chip' | 'synth' | 'sf'. pref: auto | chip | soundfont | synth (whole-song preference)."""
    e = tr.engine
    if pref == "chip" or e == "chip":
        return "chip"
    if tr.drums:
        if tr.kit == "chip":
            return "chip"
        if pref == "synth" or e == "synth" or tr.kit in S.SYNTH_KITS:
            return "synth"
        return "sf" if sf_ok else "synth"
    inst = tr.instrument
    if isinstance(inst, str) and inst in S.CHIP_WAVES:
        return "chip"
    if pref == "synth" or e == "synth":
        return "synth"
    if e == "sf" or pref == "soundfont":
        return "sf" if sf_ok else "synth"
    if isinstance(inst, str) and inst in S.PATCHES:
        return "synth"
    return "sf" if sf_ok else "synth"


def _patch_for(tr: Track) -> dict:
    i = tr.instrument
    if isinstance(i, str) and i in S.PATCHES:
        return S.PATCHES[i]
    return S.PATCHES[S.gm_fallback(M.program_of(tr))]


def _pan(buf: np.ndarray, pan: float) -> np.ndarray:
    gl = math.cos((pan + 1) * math.pi / 4) * math.sqrt(2)
    gr = math.sin((pan + 1) * math.pi / 4) * math.sqrt(2)
    out = buf.copy()
    out[:, 0] *= gl
    out[:, 1] *= gr
    return out


def _place(buf: np.ndarray, x: np.ndarray, st: int):
    if st >= len(buf):
        return
    e = min(len(buf), st + len(x))
    if x.ndim == 1:
        buf[st:e] += x[: e - st, None]
    else:
        buf[st:e] += x[: e - st]


def _track_fx(x: np.ndarray, fx: dict, song: Song, sr: int) -> np.ndarray:
    if not fx:
        return x
    spb = 60.0 / song.tempo
    if fx.get("highpass"):
        x = S.filt(x, "highpass", float(fx["highpass"]), sr)
    if fx.get("lowpass"):
        x = S.filt(x, "lowpass", float(fx["lowpass"]), sr)
    if fx.get("drive"):
        x = S.drive(x, float(fx["drive"]))
    if fx.get("bitcrush"):
        x = S.bitcrush(x, float(fx["bitcrush"]), 2)
    if fx.get("chorus"):
        x = S.chorus(x, sr, float(fx["chorus"]))
    if fx.get("delay"):
        x = S.delay(x, sr, float(fx["delay"]) * spb, float(fx.get("feedback", 0.35)), float(fx.get("delay_mix", 0.22)))
    return x


def render_track(tr: Track, song: Song, sr: int, rep: int, total: int, eng: str) -> np.ndarray:
    """Dry stereo buffer of one track (pan applied, volume not) for the chip/synth engines."""
    rng = np.random.default_rng(zlib.crc32(tr.name.encode()) + 17)
    buf = np.zeros((total, 2), np.float32)
    body = song.length_beats
    spb = 60.0 / song.tempo
    cache: dict = {}
    gated = bool(tr.params.get("fx", {}).get("gated"))
    patch = None if (tr.drums or eng == "chip") else _patch_for(tr)
    kind = (tr.instrument if isinstance(tr.instrument, str) and tr.instrument in S.CHIP_WAVES
            else S.CHIP_ROLE_WAVE.get(tr.role, "square"))
    pparams = {k: tr.params[k] for k in ("cut", "q", "drive") if k in tr.params}
    for r in range(rep):
        prev = None
        prev_end = -1.0
        for n in tr.notes:
            t0 = song.sec(n.start + r * body)
            st = int(round(t0 * sr))
            if st >= total:
                continue
            if tr.drums:
                key = (n.pitch, n.vel // 6)
                if eng == "chip" or tr.kit == "chip":
                    x = cache.get(key)
                    if x is None:
                        x = S.drum_hit("chip", n.pitch, n.vel, sr, rng)
                        cache[key] = x
                else:
                    x = S.drum_hit(tr.kit, n.pitch, n.vel, sr, rng, gated=gated)
            else:
                dur_s = max(0.02, song.sec(n.start + n.dur + r * body) - t0)
                if eng == "chip" and kind == "noise":
                    x = S.drum_hit("chip", 38, n.vel, sr, rng)
                elif eng == "chip":
                    key = (n.pitch, round(dur_s, 3), n.vel // 4)
                    x = cache.get(key)
                    if x is None:
                        x = S.chip_note(kind, tr.role, n.pitch, dur_s, n.vel, sr)
                        cache[key] = x
                else:
                    legato = prev is not None and t0 - prev_end < 0.03
                    key = (n.pitch, round(dur_s, 3), n.vel // 6, prev if (legato and patch.get("glide")) else None)
                    x = cache.get(key)
                    if x is None:
                        x = S.render_note(patch, n.pitch, dur_s, n.vel, sr, rng, spb, prev if legato else None, pparams or None)
                        cache[key] = x
                prev, prev_end = n.pitch, t0 + dur_s
            _place(buf, x, st)
    fx = dict((patch or {}).get("fx", {}))
    fx.update({k: v for k, v in tr.params.get("fx", {}).items() if k != "gated"})
    buf = _track_fx(buf, fx, song, sr)
    return _pan(buf, tr.pan).astype(np.float32)


# ============================================================ fluidsynth


def render_fluidsynth(song: Song, sf: str | None = None, sr: int = SR, repeat: int = 1, tracks: list[str] | None = None,
                      gain: float = 0.6, volume_cc: int | None = None, pad_beats: float = 0.0) -> np.ndarray:
    """Dry render (FluidSynth reverb/chorus off — the space is added by our reverb, shared with all engines)."""
    fs = which_fluidsynth()
    sf = sf or default_soundfont()
    if not fs:
        raise ValueError("FluidSynth not installed (brew install fluid-synth) — use synth='synth' or 'chip', or run gameforge:doctor")
    if not sf or not os.path.exists(sf):
        raise ValueError(f"no SoundFont in {SF_DIR} — run gameforge:doctor (MuseScore_General.sf3, MIT) or pass soundfont=")
    tmp = Path(tempfile.mkdtemp(prefix="gf_mus_"))
    try:
        mid = M.write_midi(song, tmp / "song.mid", repeat=repeat, tracks=tracks, volume_cc=volume_cc, pad_beats=pad_beats)
        out = tmp / "out.wav"
        cmd = [fs, "-ni", "-q", "-g", str(gain), "-r", str(sr), "-o", "synth.reverb.active=0",
               "-o", "synth.chorus.active=0", "-F", str(out), sf, str(mid)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if p.returncode != 0 or not out.exists():
            raise ValueError(f"fluidsynth failed: {p.stderr.strip()[:400]}")
        x, _ = read_audio(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x


# ============================================================ render pipeline

# automix: target loudness (dB, mean power of the active parts) per role; `volume` trims around 0.8
ROLE_TARGET_DB = {"melody": -18, "notes": -18, "counter": -23, "fanfare": -21, "drums": -19, "bass": -20, "power": -21,
                  "chords": -24, "pulse": -25, "pad": -25, "arp": -24, "ostinato": -24, "drone": -27, "texture": -25}
_CACHE: "OrderedDict[str, np.ndarray]" = OrderedDict()
_CACHE_MAX = 24


def _fit(x: np.ndarray, total: int) -> np.ndarray:
    if len(x) >= total:
        return x[:total]
    return np.concatenate([x, np.zeros((total - len(x), x.shape[1]), x.dtype)])


def _kick_secs(song: Song, rep: int) -> list[float]:
    body = song.length_beats
    return sorted(song.sec(n.start + r * body) for r in range(rep) for t in song.tracks if t.drums for n in t.notes if n.pitch in (35, 36))


def _loop_len(song: Song, sr: int) -> int:
    return int(round(song.seconds * sr))


def _wrap(x: np.ndarray, L: int) -> np.ndarray:
    """Seamless loop: one pass rendered with its full tail; everything after the loop end (releases,
    echoes, reverb) is added onto the start — exactly what plays when the loop repeats."""
    y = x[:L].copy()
    k = L
    while k < len(x):
        seg = x[k:k + L]
        y[: len(seg)] += seg
        k += L
    return y


def _trim_tail(x: np.ndarray, song: Song, sr: int, max_tail: float = 4.0) -> np.ndarray:
    L = _loop_len(song, sr)
    end = min(len(x), L + int(max_tail * sr))
    y = x[:end].copy()
    mag = np.max(np.abs(y), axis=1)
    above = np.nonzero(mag > 10 ** (-60 / 20))[0]
    if len(above):
        y = y[: min(len(y), max(L, above[-1] + int(0.05 * sr)))]
    fade = min(len(y), int(0.05 * sr))
    y[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return y


def active_db(x: np.ndarray, sr: int) -> float:
    """Loudness of a part while it plays: mean power of 50 ms windows within 40 dB of its loudest window."""
    p = (x.astype(np.float64) ** 2).mean(axis=1) if x.ndim == 2 else x.astype(np.float64) ** 2
    w = int(0.05 * sr)
    n = len(p) // w
    if n == 0:
        return -120.0
    e = p[: n * w].reshape(n, w).mean(1)
    if e.max() <= 1e-14:
        return -120.0
    act = e[e > e.max() * 1e-4]
    return float(10 * math.log10(act.mean()))


def _digest(song: Song, tr: Track, eng: str, rep: int, total: int, sr: int, sf: str | None, vol_cc) -> str:
    h = hashlib.sha1()
    h.update(repr((song.tempo, song.tempo_map, song.meter, song.length_beats, rep, total, sr, eng, sf, vol_cc,
                   tr.name, tr.role, tr.instrument, tr.kit, tr.pan, tr.engine, sorted((k, repr(v)) for k, v in tr.params.items()))).encode())
    h.update(np.array([(n.start, n.dur, n.pitch, n.vel) for n in tr.notes], np.float64).tobytes())
    return h.hexdigest()


def _cached(key: str):
    x = _CACHE.get(key)
    if x is not None:
        _CACHE.move_to_end(key)
    return x


def _store(key: str, x: np.ndarray):
    _CACHE[key] = x
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


def _sf_track(song: Song, tr: Track, sf, sr, total, vol_cc, pad_beats) -> np.ndarray:
    return _fit(render_fluidsynth(song, sf, sr, 1, [tr.name], volume_cc=vol_cc, pad_beats=pad_beats), total)


def render(song: Song, synth: str = "auto", sr: int = SR, tracks: list[str] | None = None, soundfont: str | None = None,
           mix: str = "auto", gains: dict | None = None, info: dict | None = None) -> tuple[np.ndarray, str]:
    """synth: auto (per track: SoundFont for GM instruments if installed, built-in synth for synth patches
    and synth kits, chip engine for chip waves) | soundfont | synth (everything built-in) | chip.
    mix: auto (each part brought to its role's target loudness, `volume` = trim around 0.8) | manual
    (`volume` as a plain gain). gains: precomputed per-track linear gains (used for section slices so
    they keep the song's balance); info: receives {'gains': ..., 'engines': ...}."""
    if synth not in ("auto", "soundfont", "synth", "chip"):
        raise ValueError("synth: auto | soundfont | synth | chip")
    if mix not in ("auto", "manual"):
        raise ValueError("mix: auto | manual")
    sf_ok = bool(which_fluidsynth() and (soundfont or default_soundfont()))
    if synth == "soundfont" and not sf_ok:
        raise ValueError("synth='soundfont' needs FluidSynth + a SoundFont — run gameforge:doctor, or use synth='auto'/'synth'")
    L = _loop_len(song, sr)
    tail_s = (S.SPACES.get(song.reverb) or (0, 0, 0))[0] * 1.1 + 2.5
    total = L + int(tail_s * sr)
    pad_beats = tail_s * (song.tempo_map[-1][1] if song.tempo_map else song.tempo) / 60.0
    sel = [t for t in song.tracks if (not tracks or t.name in tracks) and t.notes]
    plan = {t.name: engine_of(t, synth, sf_ok) for t in sel}
    kicks = _kick_secs(song, 2 if song.loop else 1)
    release = 0.55 * 60.0 / song.tempo
    sf = soundfont or default_soundfont()

    bufs: dict[str, np.ndarray] = {}
    todo_sf = []
    for t in sel:
        vol_cc = 100 if mix == "auto" else None
        key = _digest(song, t, plan[t.name], 1, total, sr, sf if plan[t.name] == "sf" else None, vol_cc if plan[t.name] == "sf" else None)
        x = _cached(key)
        if x is not None:
            bufs[t.name] = x
        elif plan[t.name] == "sf":
            todo_sf.append((t, key, vol_cc))
        else:
            x = render_track(t, song, sr, 1, total, plan[t.name])
            _store(key, x)
            bufs[t.name] = x
    if todo_sf:
        with ThreadPoolExecutor(max_workers=min(4, len(todo_sf))) as ex:
            futs = {ex.submit(_sf_track, song, t, soundfont, sr, total, vc, pad_beats): (t, key) for t, key, vc in todo_sf}
            for f, (t, key) in futs.items():
                x = f.result()
                _store(key, x)
                bufs[t.name] = x

    used_gains = {}
    dry = np.zeros((total, 2), np.float32)
    send = np.zeros((total, 2), np.float32)
    for t in sel:
        x = bufs[t.name]
        if gains and t.name in gains:
            g = gains[t.name]
        elif mix == "auto":
            target = ROLE_TARGET_DB.get(t.role, -22) + 20 * math.log10(max(t.volume, 1e-3) / 0.8)
            g = 10 ** (max(-30.0, min(18.0, target - active_db(x, sr))) / 20)
        else:
            g = t.volume * (SF_GAIN if plan[t.name] == "sf" else 1.0)
        used_gains[t.name] = g
        y = x * g
        if t.duck > 0:
            y = y * S.duck_envelope(total, sr, kicks, t.duck, release)[:, None]
        dry += y
        send += y * t.reverb
    ir = S.reverb_ir(song.reverb, sr)
    if ir is not None and np.any(send):
        wet = S.convolve(send, ir)[:total]
        dry += wet.astype(np.float32) * 0.9
    x = _wrap(dry, L) if song.loop else _trim_tail(dry, song, sr, max_tail=tail_s)
    m = song.master or {}
    if m.get("lofi"):
        x = S.lofi(x, sr, float(m["lofi"]), seed=5, noise=not tracks, circular=song.loop).astype(np.float32)
    if m.get("drive"):
        x = S.drive(x, float(m["drive"]))
    if m.get("width"):
        x = S.width(x, float(m["width"]))
    engines = sorted(set(plan.values()))
    used = "+".join({"sf": "soundfont"}.get(e, e) for e in engines) or "none"
    if info is not None:
        info["gains"] = used_gains
        info["engines"] = plan
    return x.astype(np.float32), used


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


def normalize(x: np.ndarray, sr: int, target_lufs: float = -16.0, ceiling_db: float = -1.5) -> tuple[np.ndarray, dict]:
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
    elif rms_end / rms_start > 8:
        seam["verdict"] = "sound is cut at the loop point (loud end, quiet start) — check the arrangement of the last/first bar"
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

SFX_KINDS = ["coin", "jump", "double_jump", "laser", "shoot", "explosion", "hit", "punch", "hurt", "death", "powerup", "heal",
             "pickup", "blip", "select", "ui_click", "ui_confirm", "ui_cancel", "ui_hover", "error", "magic", "teleport", "charge",
             "zap", "whoosh", "footstep", "land", "bounce", "alarm", "door", "splash", "thunder"]


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
    elif kind == "double_jump":
        P.update(f=U(380, 560), slide=U(2.0, 3.2), sus=U(0.03, 0.06), dec=U(0.1, 0.18), duty=U(0.12, 0.3), rep=U(0.05, 0.07))
    elif kind == "shoot":
        P.update(wave="noise", f=U(500, 900), slide=-U(2, 4), a=0.001, sus=0.01, dec=U(0.08, 0.16), punch=U(0.4, 0.8), noise_mix=0.0, lpf=U(0.5, 0.9))
    elif kind == "punch":
        P.update(wave="noise", f=U(90, 160), slide=-U(1, 3), a=0.001, sus=0.005, dec=U(0.08, 0.14), punch=0.8, lpf=U(0.2, 0.35), gain=1.0)
    elif kind == "death":
        P.update(wave="square", f=U(400, 560), slide=-U(1.0, 1.8), sus=U(0.2, 0.35), dec=U(0.3, 0.5), vib=U(0.08, 0.15), vib_hz=U(8, 12), duty=0.5)
    elif kind == "heal":
        P.update(wave="sine", f=U(420, 560), slide=U(0.5, 0.9), a=0.02, sus=U(0.2, 0.3), dec=U(0.3, 0.5), rep=U(0.09, 0.13), vib=0.02, vib_hz=6)
    elif kind == "pickup":
        P.update(f=U(600, 900), arp=U(1.25, 1.34), arp_t=U(0.03, 0.05), sus=U(0.02, 0.05), dec=U(0.08, 0.14), duty=U(0.4, 0.5))
    elif kind == "select":
        P.update(wave="square", f=U(900, 1300), arp=2.0, arp_t=0.03, sus=0.02, dec=0.06, duty=0.25, gain=0.6)
    elif kind == "ui_hover":
        P.update(wave="sine", f=U(2200, 3200), a=0.001, sus=0.002, dec=U(0.01, 0.02), gain=0.4)
    elif kind == "teleport":
        P.update(wave="sine", f=U(200, 300), slide=U(2.5, 4), a=0.01, sus=U(0.2, 0.3), dec=U(0.2, 0.3), vib=U(0.1, 0.2), vib_hz=U(25, 40))
    elif kind == "charge":
        P.update(wave="saw", f=U(110, 160), slide=U(1.8, 2.6), a=U(0.2, 0.4), sus=U(0.3, 0.5), dec=0.08, vib=0.03, vib_hz=14, lpf=U(0.3, 0.5), lpf_sweep=U(1, 2))
    elif kind == "zap":
        P.update(wave="saw", f=U(1200, 2000), slide=-U(5, 9), a=0.001, sus=0.01, dec=U(0.06, 0.12), noise_mix=U(0.3, 0.5), vib=0.3, vib_hz=60)
    elif kind == "bounce":
        P.update(wave="sine", f=U(180, 260), slide=U(2.5, 3.5), a=0.001, sus=0.01, dec=U(0.1, 0.16), punch=0.3)
    elif kind == "alarm":
        P.update(wave="square", f=U(650, 850), sus=U(0.6, 0.9), dec=0.08, vib=U(0.2, 0.28), vib_hz=U(2.5, 4), duty=0.5, gain=0.6)
    elif kind == "door":
        P.update(wave="noise", f=U(70, 110), slide=-0.3, a=U(0.02, 0.05), sus=U(0.15, 0.3), dec=U(0.15, 0.3), lpf=U(0.12, 0.2), punch=0.3, gain=0.9)
    elif kind == "splash":
        P.update(wave="noise", f=U(500, 800), slide=-U(0.5, 1.2), a=0.004, sus=U(0.05, 0.1), dec=U(0.3, 0.5), lpf=U(0.4, 0.7), lpf_sweep=-U(0.8, 1.6), gain=0.9)
    elif kind == "thunder":
        P.update(wave="noise", f=U(40, 80), slide=-0.2, a=0.005, sus=U(0.3, 0.5), dec=U(1.2, 2.0), punch=U(0.5, 0.9), lpf=U(0.15, 0.3), lpf_sweep=-U(0.3, 0.7), gain=1.0)
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
        fr = ph % 1.0
        x = {"saw": (2 * fr - 1) * 0.55, "sine": np.sin(2 * np.pi * fr) * 0.8, "triangle": (1 - 4 * np.abs(fr - 0.5)) * 0.7}[w]
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
