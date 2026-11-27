"""GameForge music core: theory (scales, modes, roman-numeral chords, moods), part generators
(chords with voice leading, bass, arpeggio, drums, motif-based melody, pads), explicit note
notation, song model, Standard MIDI File writer/reader and a piano-roll preview image.

Times are in beats (quarter notes). Pitches are MIDI numbers (C4 = 60). Pure Python + Pillow.
"""
from __future__ import annotations

import math
import random
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

# ============================================================ theory

NOTE_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10], "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
}
EXTRA_SCALES = {  # melody-only colour scales (not used to build diatonic chords)
    "pentatonic_major": [0, 2, 4, 7, 9], "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10], "whole_tone": [0, 2, 4, 6, 8, 10],
}

QUALITIES = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "sus2": [0, 2, 7], "sus4": [0, 5, 7], "5": [0, 7],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "m7b5": [0, 3, 6, 10],
    "dim7": [0, 3, 6, 9], "mmaj7": [0, 3, 7, 11], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14],
}

MOODS = {
    # mood: mode, tempo range, progressions (roman, relative to the mode), instruments by role, drum style
    "heroic": ("major", (112, 140), ["I V vi IV", "I bVII IV I", "I IV V IV"], {"lead": "french_horn", "pad": "strings", "bass": "contrabass", "color": "harp"}, "march"),
    "adventure": ("mixolydian", (110, 132), ["I bVII IV I", "I IV bVII IV"], {"lead": "flute", "pad": "strings", "bass": "acoustic_bass", "color": "pizzicato"}, "pop"),
    "calm": ("major", (72, 96), ["I vi IV V", "Imaj7 IVmaj7", "I iii IV I"], {"lead": "flute", "pad": "warm_pad", "bass": "acoustic_bass", "color": "piano"}, "none"),
    "town": ("major", (88, 108), ["I IV I V", "I vi ii V", "IV V iii vi"], {"lead": "flute", "pad": "accordion", "bass": "acoustic_bass", "color": "acoustic_guitar"}, "light"),
    "mystery": ("dorian", (70, 92), ["i IV i bVII", "i bIII IV i"], {"lead": "celesta", "pad": "warm_pad", "bass": "fretless_bass", "color": "harp"}, "none"),
    "dungeon": ("phrygian", (60, 84), ["i bII i bVII", "i bVI bII i"], {"lead": "choir", "pad": "strings", "bass": "contrabass", "color": "harp"}, "sparse"),
    "battle": ("harmonic_minor", (140, 172), ["i bVI bVII V", "i iv V i", "i bVI III V"], {"lead": "brass", "pad": "strings", "bass": "electric_bass", "color": "pizzicato"}, "rock"),
    "boss": ("harmonic_minor", (150, 180), ["i bII i V", "i bVI iv V"], {"lead": "brass", "pad": "choir", "bass": "electric_bass", "color": "distortion_guitar"}, "rock"),
    "sad": ("minor", (58, 76), ["i iv bVI V", "i bVI bIII bVII", "vi IV I V"], {"lead": "cello", "pad": "strings", "bass": "contrabass", "color": "piano"}, "none"),
    "horror": ("locrian", (48, 66), ["i bII", "i bV"], {"lead": "choir", "pad": "warm_pad", "bass": "contrabass", "color": "music_box"}, "none"),
    "chiptune": ("major", (130, 160), ["I V vi IV", "I IV V I", "vi IV I V"], {"lead": "square", "pad": "pulse25", "bass": "triangle", "color": "pulse12"}, "chip"),
    "victory": ("major", (120, 140), ["I IV V I"], {"lead": "trumpet", "pad": "strings", "bass": "tuba", "color": "glockenspiel"}, "march"),
    "game_over": ("minor", (60, 80), ["i iv i V"], {"lead": "piano", "pad": "strings", "bass": "contrabass", "color": "harp"}, "none"),
    "lofi": ("dorian", (70, 88), ["im7 IV7", "IVmaj7 iiim7 iim7 Imaj7"], {"lead": "electric_piano", "pad": "warm_pad", "bass": "fingered_bass", "color": "vibraphone"}, "lofi"),
    "electronic": ("minor", (118, 130), ["i bVI bIII bVII", "i bVII bVI bVII"], {"lead": "saw_lead", "pad": "warm_pad", "bass": "synth_bass", "color": "square_lead"}, "edm"),
}

GM = {  # common General MIDI programs (0-based)
    "piano": 0, "bright_piano": 1, "electric_piano": 4, "harpsichord": 6, "clavinet": 7, "celesta": 8,
    "glockenspiel": 9, "music_box": 10, "vibraphone": 11, "marimba": 12, "xylophone": 13, "tubular_bells": 14,
    "organ": 19, "accordion": 21, "harmonica": 22, "nylon_guitar": 24, "acoustic_guitar": 25,
    "electric_guitar": 27, "muted_guitar": 28, "overdrive_guitar": 29, "distortion_guitar": 30,
    "acoustic_bass": 32, "fingered_bass": 33, "electric_bass": 33, "picked_bass": 34, "fretless_bass": 35, "slap_bass": 36,
    "synth_bass": 38, "synth_bass2": 39, "violin": 40, "viola": 41, "cello": 42, "contrabass": 43,
    "tremolo_strings": 44, "pizzicato": 45, "harp": 46, "timpani": 47, "strings": 48, "slow_strings": 49,
    "synth_strings": 50, "choir": 52, "voice_oohs": 53, "orchestra_hit": 55, "trumpet": 56, "trombone": 57,
    "tuba": 58, "french_horn": 60, "brass": 61, "synth_brass": 62, "soprano_sax": 64, "alto_sax": 65,
    "tenor_sax": 66, "oboe": 68, "english_horn": 69, "bassoon": 70, "clarinet": 71, "piccolo": 72,
    "flute": 73, "recorder": 74, "pan_flute": 75, "ocarina": 79, "square_lead": 80, "saw_lead": 81,
    "calliope": 82, "chiff_lead": 83, "warm_pad": 89, "polysynth": 90, "choir_pad": 91, "bowed_pad": 92,
    "halo_pad": 94, "sweep_pad": 95, "ice_rain": 96, "atmosphere": 99, "sitar": 104, "banjo": 105,
    "shamisen": 106, "koto": 107, "kalimba": 108, "bagpipe": 109, "fiddle": 110, "steel_drums": 114,
    "taiko": 116, "melodic_tom": 117, "synth_drum": 118,
}
CHIP_WAVES = {"square", "pulse25", "pulse12", "triangle", "saw", "sine", "noise"}

DRUM = {"kick": 36, "rim": 37, "snare": 38, "clap": 39, "esnare": 40, "tom_lo": 45, "hat": 42, "pedal_hat": 44,
        "tom_mid": 47, "open_hat": 46, "tom_hi": 50, "crash": 49, "ride": 51, "tamb": 54, "shaker": 70, "timpani": 47}

DRUM_STYLES = {  # 16 steps per bar; x = hit, X = accent, o = ghost
    "rock": {"kick": "x.......x.x.....", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."},
    "pop": {"kick": "x.....x.x.......", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x.", "shaker": "..x...x...x...x."},
    "edm": {"kick": "x...x...x...x...", "clap": "....X.......X...", "hat": "..x...x...x...x.", "open_hat": "......x.......x."},
    "breakbeat": {"kick": "x.........x.....", "snare": "....X..o.o..X...", "hat": "x.xxx.x.x.xxx.x."},
    "lofi": {"kick": "x......x..x.....", "snare": "....x.......x..o", "hat": "x.x.x.xxx.x.x.x."},
    "trap": {"kick": "x......x..x.....", "clap": "........X.......", "hat": "xxxxxxxxx.xxxxxx"},
    "chip": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "..x...x...x...x."},
    "march": {"snare": "x.oox.oox.oox.x.", "kick": "x.......x.......", "crash": "x..............."},
    "light": {"kick": "x.......x.......", "rim": "....x.......x...", "shaker": "x.x.x.x.x.x.x.x."},
    "sparse": {"kick": "x...............", "tom_lo": "........x.......", "timpani": "x.......x......."},
    "none": {},
}


def note_to_midi(s: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]*)(-?\d+)", s.strip())
    if not m:
        raise ValueError(f"bad note '{s}' (use C4, F#3, Bb2)")
    n = NOTE_IDX[m.group(1).upper()] + m.group(2).count("#") - m.group(2).count("b")
    return 12 * (int(m.group(3)) + 1) + n


def midi_to_name(p: int) -> str:
    return f"{NAMES[p % 12]}{p // 12 - 1}"


def key_root(key: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]?)", key.strip())
    if not m:
        raise ValueError(f"bad key '{key}' (use C, F#, Bb)")
    return (NOTE_IDX[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12


def scale_pcs(key: str, mode: str) -> list[int]:
    steps = MODES.get(mode) or EXTRA_SCALES.get(mode)
    if steps is None:
        raise ValueError(f"mode must be one of {sorted(MODES) + sorted(EXTRA_SCALES)}")
    r = key_root(key)
    return [(r + s) % 12 for s in steps]


ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def parse_roman(sym: str, key: str, mode: str) -> tuple[int, list[int], str]:
    """'i', 'bVII', 'V7', 'ii°', 'IVmaj7', 'sus4' ... -> (root pitch class, intervals, label)."""
    m = re.fullmatch(r"([b#]?)([ivIV]+)(°|o|ø|\+)?(maj9|maj7|mmaj7|m7b5|m7|m9|m6|madd9|dim7|7|9|6|add9|sus2|sus4|5)?", sym)
    if not m:
        raise ValueError(f"bad chord '{sym}' (roman numerals: I ii iii IV V vi vii°, bVII, V7, IVmaj7, isus4)")
    acc, num, mark, ext = m.groups()
    deg = ROMAN.get(num.upper())
    if deg is None:
        raise ValueError(f"bad roman numeral '{num}'")
    # convention: plain numerals are diatonic to the mode; numerals WITH an accidental are relative
    # to the major scale (in D minor 'bVI' = Bb, 'bVII' = C, 'VI' = Bb as well)
    steps = MODES["major"] if acc else MODES.get(mode, MODES["major"])
    root = (key_root(key) + steps[deg - 1] + (-1 if acc == "b" else 1 if acc == "#" else 0)) % 12
    upper = num.isupper()
    if mark in ("°", "o"):
        q = "dim7" if ext == "7" else "dim"
    elif mark == "ø":
        q = "m7b5"
    elif mark == "+":
        q = "aug"
    elif ext in ("sus2", "sus4", "5", "add9", "maj7", "maj9", "mmaj7", "m7b5", "dim7", "madd9"):
        q = ext if not (ext == "add9" and not upper) else "madd9"
    elif ext in ("7", "9", "6"):
        q = ext if upper else {"7": "m7", "9": "m9", "6": "m6"}[ext]
    elif ext in ("m7", "m9", "m6"):
        q = ext
    else:
        q = "maj" if upper else "min"
    return root, QUALITIES[q], f"{NAMES[root]}{'' if q == 'maj' else 'm' if q == 'min' else q}"


def progression(prog: str, key: str, mode: str) -> list[tuple[int, list[int], str]]:
    return [parse_roman(s, key, mode) for s in prog.split()]


# ============================================================ song model


@dataclass
class Note:
    start: float
    dur: float
    pitch: int
    vel: int = 90


@dataclass
class Track:
    name: str
    role: str
    instrument: str | int = "piano"
    notes: list[Note] = field(default_factory=list)
    volume: float = 0.8      # 0..1
    pan: float = 0.0         # -1..1
    reverb: float = 0.3      # 0..1 send
    layer: int = 1           # adaptive-music intensity layer
    drums: bool = False

    @property
    def program(self) -> int:
        if self.drums or self.instrument == "kit":
            return 0
        if isinstance(self.instrument, int):
            return self.instrument
        if self.instrument in CHIP_WAVES:
            return {"square": 80, "pulse25": 80, "pulse12": 80, "triangle": 33, "saw": 81, "sine": 79, "noise": 118}[self.instrument]
        if self.instrument not in GM:
            raise ValueError(f"unknown instrument '{self.instrument}'. GM names: {sorted(GM)}; chip: {sorted(CHIP_WAVES)}; or a program number 0-127")
        return GM[self.instrument]


@dataclass
class Song:
    title: str
    tempo: float
    key: str
    mode: str
    beats_per_bar: int = 4
    bars: int = 8
    tracks: list[Track] = field(default_factory=list)
    chords: list[tuple[float, float, str]] = field(default_factory=list)   # (start, dur, label) for preview
    sections: list[tuple[float, str]] = field(default_factory=list)
    loop: bool = True

    @property
    def length_beats(self) -> float:
        return self.bars * self.beats_per_bar

    @property
    def seconds(self) -> float:
        return self.length_beats * 60.0 / self.tempo

    def summary(self) -> dict:
        return {
            "title": self.title, "tempo": self.tempo, "key": self.key, "mode": self.mode, "bars": self.bars,
            "time": f"{self.beats_per_bar}/4", "seconds": round(self.seconds, 2), "loop": self.loop,
            "tracks": [{"name": t.name, "role": t.role, "instrument": t.instrument, "notes": len(t.notes), "layer": t.layer,
                        "range": [midi_to_name(min(n.pitch for n in t.notes)), midi_to_name(max(n.pitch for n in t.notes))] if t.notes and not t.drums else None}
                       for t in self.tracks],
            "chords": " | ".join(c[2] for c in self.chords[: 16]),
        }


# ============================================================ generators


def _voice(root_pc: int, ivs: list[int], prev: list[int] | None, center: int, spread: bool) -> list[int]:
    """Choose an inversion/octave close to the previous chord (smooth voice leading)."""
    pcs = [(root_pc + i) % 12 for i in ivs]
    cands = []
    for inv in range(len(pcs)):
        order = pcs[inv:] + pcs[:inv]
        for base_oct in range(center // 12 - 2, center // 12 + 2):
            v, last = [], None
            for pc in order:
                p = base_oct * 12 + pc
                while last is not None and p <= last:
                    p += 12
                v.append(p)
                last = p
            if spread and len(v) >= 3 and v[0] - 12 >= 48:   # open the voicing, but stay above the bass (C3)
                v = [v[0] - 12] + v[1:]
            cands.append(v)
    def cost(v):
        c = abs(sum(v) / len(v) - center) * 0.6
        if prev:
            c += sum(min(abs(a - b) for b in prev) for a in v)
        return c
    return min(cands, key=cost)


def gen_chords(chords, beats_per_chord, total_beats, octave=4, rhythm="sustain", spread=False, vel=72, seed=0):
    rnd = random.Random(seed)
    out, prev, t, i = [], None, 0.0, 0
    center = 12 * (octave + 1) + 2   # a bit lower so pads/chords sit under the melody
    pat = {"sustain": [(0, 1.0)], "halves": [(0, 0.5), (0.5, 0.5)], "stabs": [(0, 0.12), (0.375, 0.12), (0.625, 0.12)],
           "pulse8": [(k / 8, 1 / 8) for k in range(8)], "offbeat": [(k / 8 + 1 / 16, 1 / 16) for k in range(8)],
           "waltz": [(1 / 3, 1 / 3 * 0.9), (2 / 3, 1 / 3 * 0.9)]}.get(rhythm)
    if pat is None:
        raise ValueError("chord rhythm: sustain | halves | stabs | pulse8 | offbeat | waltz")
    while t < total_beats - 1e-6:
        root, ivs, label = chords[i % len(chords)]
        v = _voice(root, ivs, prev, center, spread)
        prev = v
        d = min(beats_per_chord, total_beats - t)
        for st, ln in pat:
            for p in v:
                out.append(Note(t + st * d, max(0.05, ln * d * 0.98), p, max(1, min(127, vel + rnd.randint(-6, 6)))))
        t += beats_per_chord
        i += 1
    return out


def gen_bass(chords, beats_per_chord, total_beats, octave=2, style="root", vel=96, seed=0, beats_per_bar=4):
    rnd = random.Random(seed)
    out, t, i = [], 0.0, 0
    base = 12 * (octave + 1)
    while t < total_beats - 1e-6:
        root, ivs, _ = chords[i % len(chords)]
        nxt = chords[(i + 1) % len(chords)][0]
        r = base + root
        fifth = r + 7 if 7 in ivs or ivs[-1] >= 7 else r + ivs[-1]
        d = min(beats_per_chord, total_beats - t)
        if style == "root":
            seq = [(0, d, r)]
        elif style == "root_fifth":
            seq = [(k, 1, r if k % 2 == 0 else fifth) for k in range(int(d))]
        elif style == "octave":
            seq = [(k * 0.5, 0.45, r if k % 2 == 0 else r + 12) for k in range(int(d * 2))]
        elif style == "pulse8":
            seq = [(k * 0.5, 0.45, r) for k in range(int(d * 2))]
        elif style == "syncopated":
            seq = [(0, 0.75, r), (0.75, 0.75, r), (1.5, 0.5, fifth)] + ([(2.5, 0.5, r + 12), (3.0, 1.0, r)] if d >= 4 else [])
        elif style == "walking":
            tones = [r, r + ivs[1], fifth]
            seq = [(k, 1, tones[k % 3]) for k in range(int(d) - 1)]
            target = base + nxt
            seq.append((int(d) - 1, 1, target - 1 if rnd.random() < 0.5 else target + 1))  # chromatic approach
        elif style == "pedal":
            seq = [(0, d, base + chords[0][0])]
        else:
            raise ValueError("bass style: root | root_fifth | octave | pulse8 | syncopated | walking | pedal")
        for st, ln, p in seq:
            if st < d:
                out.append(Note(t + st, min(ln, d - st) * 0.95, p, vel + rnd.randint(-5, 5) + (6 if st == 0 else 0)))
        t += beats_per_chord
        i += 1
    return out


def gen_arp(chords, beats_per_chord, total_beats, octave=4, pattern="up", rate=0.5, span=1, vel=74, seed=0):
    rnd = random.Random(seed)
    out, t, i = [], 0.0, 0
    while t < total_beats - 1e-6:
        root, ivs, _ = chords[i % len(chords)]
        base = 12 * (octave + 1) + root
        tones = sorted({base + iv + 12 * o for o in range(span) for iv in ivs[:4]})
        seq = {"up": tones, "down": tones[::-1], "updown": tones + tones[-2:0:-1], "random": tones}.get(pattern)
        if seq is None:
            raise ValueError("arp pattern: up | down | updown | random")
        d = min(beats_per_chord, total_beats - t)
        k = 0
        while k * rate < d - 1e-6:
            p = rnd.choice(tones) if pattern == "random" else seq[k % len(seq)]
            out.append(Note(t + k * rate, rate * 0.9, p, vel + (10 if (k * rate) % 1 == 0 else 0) + rnd.randint(-4, 4)))
            k += 1
        t += beats_per_chord
        i += 1
    return out


def gen_drums(style, bars, beats_per_bar=4, fill_every=4, vel=100, seed=0, humanize=True):
    rnd = random.Random(seed)
    pat = DRUM_STYLES.get(style)
    if pat is None:
        raise ValueError(f"drum style: {sorted(DRUM_STYLES)}")
    steps = 4 * beats_per_bar
    out = []
    for b in range(bars):
        fill = fill_every and (b + 1) % fill_every == 0 and style not in ("none", "sparse")
        for inst, s in pat.items():
            s = (s * 2)[:steps]
            if fill and inst in ("snare", "clap", "hat", "open_hat"):
                s = s[: steps - 4]   # leave the last beat to the fill
            for k, ch in enumerate(s):
                if ch == ".":
                    continue
                v = {"x": vel - 10, "X": vel + 8, "o": vel - 50}.get(ch, vel)
                jitter = rnd.uniform(-0.012, 0.012) if humanize else 0
                out.append(Note(max(0, b * beats_per_bar + k * 0.25 + jitter), 0.2, DRUM[inst], max(1, min(127, v + (rnd.randint(-8, 6) if humanize else 0)))))
        if fill:
            base = b * beats_per_bar + beats_per_bar - 1
            for j, (inst, off) in enumerate((("snare", 0), ("snare", 0.25), ("tom_hi", 0.5), ("tom_lo", 0.75))):
                out.append(Note(base + off, 0.2, DRUM[inst], min(127, vel - 10 + j * 5)))
    if style in ("rock", "pop", "edm", "march", "breakbeat"):
        out.append(Note(0, 0.5, DRUM["crash"], vel))
    return out


def gen_melody(chords, beats_per_chord, total_beats, key, mode, octave=5, contour="arch", density=0.6,
               motif_bars=2, seed=0, beats_per_bar=4, vel=92, phrase_bars=4, scale_override=None):
    """Period-based melody (how game themes are usually written): 4-bar phrases in pairs —
    antecedent (question) ends on a long non-tonic chord tone, consequent (answer) ends on a long
    tonic. Each 2-bar half is the motif or its variation; motion is mostly stepwise, leaps are
    followed by a step back, strong beats land on chord tones, range stays within ~an octave."""
    rnd = random.Random(seed)
    pcs = scale_pcs(key, scale_override or mode)
    tonic = key_root(key)
    center = 12 * (octave + 1) + (tonic if tonic <= 7 else tonic - 12) + 7      # around the 5th of the key
    lo, hi = center - 9, center + 9
    pool = [p for p in range(lo, hi + 1) if p % 12 in pcs]

    def chord_at(t):
        return chords[int(t // beats_per_chord) % len(chords)]

    def chord_pcs(t):
        r, ivs, _ = chord_at(t)
        return {(r + iv) % 12 for iv in ivs}

    def nearest(p, allowed=None):
        cand = [q for q in pool if allowed is None or q % 12 in allowed] or pool
        return min(cand, key=lambda q: (abs(q - p), q))

    # motif: rhythm covering motif_bars minus the final held note, stepwise shape
    cells = [[1, 1], [0.5, 0.5, 1], [1.5, 0.5], [0.5, 0.5, 0.5, 0.5], [1, 0.5, 0.5], [0.75, 0.25, 1]]
    w = [3, 3, 2, 1 + 3 * density, 2, 1 + density]
    span = motif_bars * beats_per_bar - 2          # leave room for a 2-beat landing note
    rhythm = []
    while sum(rhythm) < span:
        rhythm += rnd.choices(cells, w)[0]
    while sum(rhythm) > span:
        over = sum(rhythm) - span
        if rhythm[-1] > over:
            rhythm[-1] -= over
        else:
            rhythm.pop()
    shape = [0]
    for _ in rhythm[1:]:
        st = rnd.choices([1, -1, 2, -2, 0, 3, -3], [5, 4, 2, 2, 1.5, 1, 0.7])[0]
        if abs(shape[-1]) >= 2 and len(shape) > 1:   # after a leap, step back
            st = -1 if shape[-1] > 0 else 1
        shape.append(st)

    def play_half(t0, start_pitch, steps, rh, end_kind, rising):
        notes, t, idx = [], t0, pool.index(nearest(start_pitch))
        for i, d in enumerate(rh):
            if t >= total_beats - 1e-6:
                break
            stp = steps[i] if i < len(steps) else 0
            if not rising:
                stp = -stp if rnd.random() < 0.5 else stp
            idx = max(0, min(len(pool) - 1, idx + stp))
            p = pool[idx]
            strong = abs(t - round(t)) < 1e-6 and int(round(t)) % (2 if beats_per_bar == 4 else beats_per_bar) == 0
            if strong:
                p = nearest(p, chord_pcs(t))
                idx = pool.index(p)
            notes.append(Note(t, min(d, total_beats - t) * 0.92, p, vel + (8 if strong else 0) + rnd.randint(-5, 4)))
            t += d
        # landing note (2 beats)
        if t < total_beats - 1e-6:
            last = notes[-1].pitch if notes else start_pitch
            if end_kind == "tonic":
                p = nearest(last, {tonic})
            else:
                allowed = chord_pcs(t) - {tonic} or chord_pcs(t)
                p = nearest(last, allowed)
            ln = min(2.0, total_beats - t)
            notes.append(Note(t, ln * 0.96, p, vel + 4))
            t += ln
        return notes, (notes[-1].pitch if notes else start_pitch)

    out, t, k = [], 0.0, 0
    cur = nearest(center - 2, chord_pcs(0))
    half = motif_bars * beats_per_bar
    while t < total_beats - 1e-6:
        phrase_idx = k // 2                     # which 4-bar phrase
        in_answer = phrase_idx % 2 == 1         # antecedent / consequent
        second_half = k % 2 == 1
        steps = list(shape)
        rh = list(rhythm)
        if second_half:                         # variation: invert the shape, keep the rhythm
            steps = [-s for s in steps]
        if in_answer and not second_half:       # answer restates the motif a step higher
            cur = nearest(cur + 2)
        last_phrase = t + half >= total_beats - 1e-6
        end_kind = "tonic" if (second_half and in_answer) or last_phrase else ("chord" if second_half else "chord")
        rising = {"arch": not second_half, "rise": True, "fall": False, "wave": k % 2 == 0}.get(contour, True)
        ns, cur = play_half(t, cur, steps, rh, end_kind, rising)
        out += ns
        t += half
        k += 1
    return out


def parse_notes(text: str, default_vel: int = 90) -> list[Note]:
    """'C4:1 E4:.5 r:.5 C4+E4+G4:2 D5:1@110' — pitch(es):beats[@velocity], r = rest."""
    out, t = [], 0.0
    for tok in text.split():
        m = re.fullmatch(r"([^:]+):([\d.]+)(?:@(\d+))?", tok)
        if not m:
            raise ValueError(f"bad note token '{tok}' (format C4:1, r:.5, C4+E4+G4:2, D5:1@110)")
        pitches, dur, v = m.group(1), float(m.group(2)), int(m.group(3) or default_vel)
        if pitches.lower() != "r":
            for p in pitches.split("+"):
                out.append(Note(t, dur * 0.95, note_to_midi(p), v))
        t += dur
    return out


# ============================================================ compose


def compose(spec: dict) -> Song:
    title = spec.get("title", "Theme")
    mood = spec.get("mood")
    md = MOODS.get(mood) if mood else None
    if mood and md is None:
        raise ValueError(f"mood: {sorted(MOODS)}")
    mode = spec.get("mode") or (md[0] if md else "major")
    key = spec.get("key", "C")
    tempo = float(spec.get("tempo") or (sum(md[1]) / 2 if md else 110))
    bpb = int(spec.get("beats_per_bar", 4))
    bars = int(spec.get("bars", 8))
    seed = int(spec.get("seed", 1))
    prog = spec.get("progression") or (md[2][seed % len(md[2])] if md else "I V vi IV")
    chord_bars = float(spec.get("chord_bars", 1))
    bpc = chord_bars * bpb
    song = Song(title, tempo, key, mode, bpb, bars, loop=bool(spec.get("loop", True)))
    total = bars * bpb

    sections = spec.get("sections") or [{"name": "A", "bars": bars}]
    if sum(int(s["bars"]) for s in sections) != bars:
        raise ValueError("sum of section bars must equal `bars`")
    tracks_spec = spec.get("tracks")
    if not tracks_spec:
        inst = md[3] if md else {"lead": "flute", "pad": "warm_pad", "bass": "acoustic_bass", "color": "harp"}
        chip = inst["lead"] in CHIP_WAVES
        tracks_spec = [{"name": "Pad", "role": "pad", "instrument": inst["pad"], "layer": 1, "volume": 0.55},
                       {"name": "Bass", "role": "bass", "style": "octave" if chip else "root_fifth", "instrument": inst["bass"], "layer": 1, "volume": 0.65},
                       {"name": "Arp", "role": "arp", "instrument": inst["color"], "pattern": "updown", "rate": 0.25 if chip else 0.5, "layer": 2, "volume": 0.55},
                       {"name": "Drums", "role": "drums", "style": md[4] if md else "pop", "layer": 2, "volume": 0.75},
                       {"name": "Lead", "role": "melody", "instrument": inst["lead"], "layer": 3}]
        if (md and md[4] == "none"):
            tracks_spec = [t for t in tracks_spec if t["role"] != "drums"]

    sec_start = 0
    sec_chords = []
    for s in sections:
        sp = s.get("progression", prog)
        ch = progression(sp, key, mode)
        sec_chords.append((sec_start * bpb, int(s["bars"]) * bpb, ch, s.get("name", "")))
        song.sections.append((sec_start * bpb, s.get("name", "")))
        sec_start += int(s["bars"])
    for st, ln, ch, _ in sec_chords:
        t = 0.0
        i = 0
        while t < ln - 1e-6:
            song.chords.append((st + t, min(bpc, ln - t), ch[i % len(ch)][2]))
            t += bpc
            i += 1

    for k, ts in enumerate(tracks_spec):
        role = ts.get("role", "notes")
        tr = Track(ts.get("name", f"T{k}"), role, ts.get("instrument", "kit" if role == "drums" else "piano"), volume=float(ts.get("volume", 0.8)),
                   pan=float(ts.get("pan", 0.0)), reverb=float(ts.get("reverb", 0.3)), layer=int(ts.get("layer", 1)), drums=role == "drums")
        tseed = seed * 31 + k
        for si, (st, ln, ch, _) in enumerate(sec_chords):
            sbars = int(ln // bpb)
            if role == "chords" or role == "pad":
                ns = gen_chords(ch, bpc, ln, int(ts.get("octave", 4)), ts.get("rhythm", "sustain" if role == "pad" else "halves"),
                                spread=role == "pad" or ts.get("spread", False), vel=int(ts.get("velocity", 66 if role == "pad" else 76)), seed=tseed)
            elif role == "bass":
                ns = gen_bass(ch, bpc, ln, int(ts.get("octave", 2)), ts.get("style", "root"), int(ts.get("velocity", 96)), tseed, bpb)
            elif role == "arp":
                ns = gen_arp(ch, bpc, ln, int(ts.get("octave", 4)), ts.get("pattern", "up"), float(ts.get("rate", 0.5)), int(ts.get("span", 1)), int(ts.get("velocity", 72)), tseed)
            elif role == "drums":
                ns = gen_drums(ts.get("style", "pop"), sbars, bpb, int(ts.get("fill_every", 4)), int(ts.get("velocity", 100)), tseed)
            elif role == "melody":
                ns = gen_melody(ch, bpc, ln, key, mode, int(ts.get("octave", 5)), ts.get("contour", "arch"), float(ts.get("density", 0.6)),
                                int(ts.get("motif_bars", 2)), tseed + si * 7, bpb, int(ts.get("velocity", 92)), scale_override=ts.get("scale"))
            elif role == "notes":
                ns = parse_notes(ts.get("notes", ""), int(ts.get("velocity", 90))) if si == 0 else []
                st = 0
            else:
                raise ValueError("track role: pad | chords | bass | arp | drums | melody | notes")
            for n in ns:
                n.start += st
            tr.notes += [n for n in ns if n.start < total - 1e-6]
        song.tracks.append(tr)
    if spec.get("ending") == "cadence":
        # final bar: tonic chord hit on every pitched track, song stops (no loop)
        song.loop = False
        tonic = progression("I" if mode in ("major", "lydian", "mixolydian") else "i", key, mode)[0]
        song.bars += 1
        end = total
        for tr in song.tracks:
            if tr.drums:
                tr.notes.append(Note(end, 1.0, DRUM["crash"], 110))
                tr.notes.append(Note(end, 1.0, DRUM["kick"], 110))
            elif tr.notes:
                ref = sorted(n.pitch for n in tr.notes)[len(tr.notes) // 2]
                v = _voice(tonic[0], tonic[1], None, ref, False)
                for p in (v if tr.role in ("pad", "chords", "arp") else [min(v, key=lambda q: abs(q - ref))]):
                    tr.notes.append(Note(end, bpb * 0.95, p, 96))
        song.chords.append((end, bpb, tonic[2]))
    return song


def stinger(kind: str, key: str = "C", tempo: float = 120, instrument: str = "brass", seed: int = 1) -> Song:
    """Short musical cues for game events (victory, defeat, item, level_up, discovery, danger)."""
    r = 12 * 5 + key_root(key)
    shapes = {
        "victory": "{0}:.5 {4}:.5 {7}:.5 {12}:1.5 {7}+{12}+{16}:2",
        "level_up": "{0}:.25 {4}:.25 {7}:.25 {12}:.25 {16}:.25 {19}:.25 {24}:1.5",
        "item": "{12}:.25 {16}:.25 {19}:.25 {24}:1",
        "discovery": "{0}+{7}:1 {2}+{9}:1 {4}+{11}+{14}:2",
        "defeat": "{7}:1 {6}:1 {5}:1 {0}+{3}+{7}:3",
        "danger": "{0}+{1}:.5 r:.25 {0}+{1}:.5 r:.25 {0}+{6}:2",
        "secret": "{19}:.25 {18}:.25 {15}:.25 {9}:.25 {8}:.25 {16}:.25 {20}:.25 {24}:1",
    }
    if kind not in shapes:
        raise ValueError(f"stinger: {sorted(shapes)}")
    txt = shapes[kind]
    txt = re.sub(r"\{(\d+)\}", lambda m: midi_to_name(r + int(m.group(1))), txt)
    notes = parse_notes(txt, 100)
    beats = max(n.start + n.dur for n in notes)
    song = Song(f"stinger_{kind}", tempo, key, "major", 4, max(1, math.ceil(beats / 4)), loop=False)
    song.tracks.append(Track("Cue", "notes", instrument, notes, volume=0.9, reverb=0.4))
    return song


# ============================================================ MIDI IO

TPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(song: Song, path: Path, repeat: int = 1, tracks: list[str] | None = None) -> Path:
    """Format-1 SMF. repeat>1 writes the body several times (used for seamless loop renders)."""
    sel = [t for t in song.tracks if not tracks or t.name in tracks]
    body = song.length_beats
    chunks = []
    meta = bytearray()
    meta += _vlq(0) + b"\xff\x03" + _vlq(len(song.title.encode())) + song.title.encode()
    us = int(60_000_000 / song.tempo)
    meta += _vlq(0) + b"\xff\x51\x03" + us.to_bytes(3, "big")
    meta += _vlq(0) + b"\xff\x58\x04" + bytes([song.beats_per_bar, 2, 24, 8])
    meta += _vlq(int(body * repeat * TPQ)) + b"\xff\x2f\x00"
    chunks.append(bytes(meta))
    ch_next = 0
    for tr in sel:
        ch = 9 if tr.drums else ch_next
        if not tr.drums:
            ch_next += 1
            if ch_next == 9:
                ch_next = 10
        ev = []
        for r in range(repeat):
            for n in tr.notes:
                s = int(round((n.start + r * body) * TPQ))
                e = int(round((n.start + n.dur + r * body) * TPQ))
                ev.append((s, 1, bytes([0x90 | ch, n.pitch & 0x7F, max(1, min(127, n.vel))])))
                ev.append((max(s + 1, e), 0, bytes([0x80 | ch, n.pitch & 0x7F, 0])))
        ev.sort(key=lambda x: (x[0], x[1]))
        data = bytearray()
        name = tr.name.encode()
        data += _vlq(0) + b"\xff\x03" + _vlq(len(name)) + name
        if not tr.drums:
            data += _vlq(0) + bytes([0xC0 | ch, tr.program & 0x7F])
        data += _vlq(0) + bytes([0xB0 | ch, 7, int(max(0, min(1, tr.volume)) * 127)])
        data += _vlq(0) + bytes([0xB0 | ch, 10, int((max(-1, min(1, tr.pan)) + 1) * 63.5)])
        data += _vlq(0) + bytes([0xB0 | ch, 91, int(max(0, min(1, tr.reverb)) * 127)])
        last = 0
        for tick, _, msg in ev:
            data += _vlq(tick - last) + msg
            last = tick
        data += _vlq(0) + b"\xff\x2f\x00"
        chunks.append(bytes(data))
    out = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), TPQ)
    for c in chunks:
        out += b"MTrk" + struct.pack(">I", len(c)) + c
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return path


def read_midi(path: Path) -> Song:
    """Minimal SMF reader -> Song (notes, tempo, programs, track names). For preview/analysis/chip render."""
    b = path.read_bytes()
    if b[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    _, fmt, ntr, div = struct.unpack(">IHHH", b[4:14])
    pos = 14
    tempo = 120.0
    tracks = []
    for ti in range(ntr):
        assert b[pos:pos + 4] == b"MTrk", "bad track chunk"
        ln = struct.unpack(">I", b[pos + 4:pos + 8])[0]
        d = b[pos + 8:pos + 8 + ln]
        pos += 8 + ln
        i, tick, status, name, prog, drums = 0, 0, 0, f"Track{ti}", 0, False
        on: dict[tuple[int, int], tuple[int, int]] = {}
        notes = []
        while i < len(d):
            v = 0
            while True:
                c = d[i]; i += 1
                v = (v << 7) | (c & 0x7F)
                if not c & 0x80:
                    break
            tick += v
            c = d[i]
            if c & 0x80:
                status = c; i += 1
            if status == 0xFF:
                typ = d[i]; i += 1
                ln2 = 0
                while True:
                    c = d[i]; i += 1
                    ln2 = (ln2 << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                payload = d[i:i + ln2]; i += ln2
                if typ == 0x51:
                    tempo = 60_000_000 / int.from_bytes(payload, "big")
                elif typ == 0x03:
                    name = payload.decode(errors="replace") or name
                continue
            if status in (0xF0, 0xF7):
                ln2 = 0
                while True:
                    c = d[i]; i += 1
                    ln2 = (ln2 << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                i += ln2
                continue
            kind, ch = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                if kind == 0xC0:
                    prog = d[i]
                i += 1
                continue
            p1, p2 = d[i], d[i + 1]; i += 2
            if ch == 9:
                drums = True
            if kind == 0x90 and p2 > 0:
                on[(ch, p1)] = (tick, p2)
            elif kind in (0x80, 0x90):
                if (ch, p1) in on:
                    st, vel = on.pop((ch, p1))
                    notes.append(Note(st / div, max(1, tick - st) / div, p1, vel))
        if notes:
            tracks.append(Track(name, "drums" if drums else "notes", prog, notes, drums=drums))
    end = max((n.start + n.dur for t in tracks for n in t.notes), default=4)
    return Song(path.stem, tempo, "C", "major", 4, max(1, math.ceil(end / 4 - 1e-6)), tracks, loop=False)


# ============================================================ preview

PALETTE = [(232, 106, 92), (92, 170, 232), (246, 196, 82), (130, 206, 120), (190, 132, 230), (90, 220, 210), (240, 150, 200), (200, 200, 200)]


def preview(song: Song, max_w: int = 1400) -> Image.Image:
    """Piano roll: tracks coloured, bar grid, chord and section labels, drum lane at the bottom."""
    pitched = [n.pitch for t in song.tracks if not t.drums for n in t.notes]
    lo, hi = (min(pitched) - 2, max(pitched) + 2) if pitched else (48, 84)
    beats = max(song.length_beats, max((n.start + n.dur for t in song.tracks for n in t.notes), default=4))
    px_b = max(8, min(40, int((max_w - 120) / beats)))
    row = max(3, min(9, int(520 / max(1, hi - lo + 1))))
    has_drums = any(t.drums for t in song.tracks)
    drum_rows = sorted({n.pitch for t in song.tracks if t.drums for n in t.notes})
    W = 110 + int(beats * px_b) + 10
    H = 40 + (hi - lo + 1) * row + (len(drum_rows) * 7 + 16 if has_drums else 0) + 60
    img = Image.new("RGB", (W, H), (24, 26, 32))
    dr = ImageDraw.Draw(img)
    top = 40
    for p in range(lo, hi + 1):
        y = top + (hi - p) * row
        if p % 12 in (1, 3, 6, 8, 10):
            dr.rectangle([110, y, W - 10, y + row - 1], fill=(30, 32, 40))
        if p % 12 == 0:
            dr.text((70, y - 4), midi_to_name(p), fill=(150, 150, 160))
            dr.line([110, y + row - 1, W - 10, y + row - 1], fill=(48, 50, 60))
    for b in range(int(beats) + 1):
        x = 110 + b * px_b
        dr.line([x, top, x, H - 60], fill=(60, 62, 75) if b % song.beats_per_bar == 0 else (36, 38, 46))
        if b % song.beats_per_bar == 0:
            dr.text((x + 2, H - 56), str(b // song.beats_per_bar + 1), fill=(130, 130, 140))
    for st, ln, label in song.chords:
        dr.text((110 + st * px_b + 2, 22), label, fill=(240, 220, 160))
    for st, name in song.sections:
        dr.text((110 + st * px_b + 2, 6), f"[{name}]", fill=(160, 220, 255))
    yd = top + (hi - lo + 1) * row + 10
    for k, t in enumerate(song.tracks):
        col = PALETTE[k % len(PALETTE)]
        for n in t.notes:
            x0 = 110 + n.start * px_b
            x1 = max(x0 + 2, 110 + (n.start + n.dur) * px_b - 1)
            if t.drums:
                y = yd + drum_rows.index(n.pitch) * 7
                dr.rectangle([x0, y, x0 + 3, y + 5], fill=col)
            else:
                y = top + (hi - n.pitch) * row
                shade = 0.5 + 0.5 * n.vel / 127
                dr.rectangle([x0, y, x1, y + row - 2], fill=tuple(int(c * shade) for c in col))
    # legend
    lx = 110
    for k, t in enumerate(song.tracks):
        col = PALETTE[k % len(PALETTE)]
        dr.rectangle([lx, H - 34, lx + 10, H - 24], fill=col)
        label = f"{t.name} ({t.instrument})"
        dr.text((lx + 14, H - 36), label, fill=(220, 220, 225))
        lx += 22 + 7 * len(label)
    dr.text((8, H - 18), f"{song.title}  {song.key} {song.mode}  {song.tempo:.0f} BPM  {song.bars} bars  {song.seconds:.1f}s{'  loop' if song.loop else ''}", fill=(200, 200, 205))
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)), Image.LANCZOS)
    return img
