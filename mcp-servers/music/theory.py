"""Music theory for gameforge-music: notes, scales/modes (incl. world scales), roman-numeral chords
with per-chord durations, chord timelines, meters with beat grouping, swing and humanize."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

NOTE_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"}

# 7-note modes: chords are built diatonically from these
MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10], "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "phrygian_dominant": [0, 1, 4, 5, 7, 8, 10],      # Middle-Eastern / flamenco
    "double_harmonic": [0, 1, 4, 5, 7, 8, 11],        # "Arabic"
    "hungarian_minor": [0, 2, 3, 6, 7, 8, 11],        # gypsy / dark fantasy
    "lydian_dominant": [0, 2, 4, 6, 7, 9, 10],        # whimsical / sci-fi
    "mixolydian_b6": [0, 2, 4, 5, 7, 8, 10],
    "dorian_b2": [0, 1, 3, 5, 7, 9, 10],
}
# colour scales for melodies (not used to build chords)
SCALES = {
    "pentatonic_major": [0, 2, 4, 7, 9], "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10], "major_blues": [0, 2, 3, 4, 7, 9],
    "whole_tone": [0, 2, 4, 6, 8, 10], "chromatic": list(range(12)),
    "hirajoshi": [0, 2, 3, 7, 8], "in_sen": [0, 1, 5, 7, 10], "yo": [0, 2, 5, 7, 9],
    "egyptian": [0, 2, 5, 7, 10], "bebop_dominant": [0, 2, 4, 5, 7, 9, 10, 11],
    "diminished": [0, 2, 3, 5, 6, 8, 9, 11],
}

QUALITIES = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "sus2": [0, 2, 7], "sus4": [0, 5, 7], "5": [0, 7],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "m7b5": [0, 3, 6, 10],
    "dim7": [0, 3, 6, 9], "mmaj7": [0, 3, 7, 11], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14],
    "7sus4": [0, 5, 7, 10], "13": [0, 4, 10, 14, 21], "m11": [0, 3, 7, 10, 14, 17], "7b9": [0, 4, 7, 10, 13],
}

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


# semitones from a mode's tonic up to its relative major (decides sharps vs flats like a key signature)
_REL_MAJOR = {"major": 0, "ionian": 0, "dorian": 10, "phrygian": 8, "lydian": 7, "mixolydian": 5, "minor": 3, "aeolian": 3,
              "locrian": 1, "harmonic_minor": 3, "melodic_minor": 3, "hungarian_minor": 3, "phrygian_dominant": 8,
              "double_harmonic": 0, "lydian_dominant": 7, "mixolydian_b6": 5, "dorian_b2": 10}
_FLAT_MAJORS = {5, 10, 3, 8, 1, 6}   # F Bb Eb Ab Db Gb


def names_for(key: str, mode: str = "major") -> list[str]:
    if len(key) > 1 and key[1] == "b":
        return FLATS
    if len(key) > 1 and key[1] == "#":
        return SHARPS
    rel = (key_root(key) + _REL_MAJOR.get(mode, 0)) % 12
    return FLATS if rel in _FLAT_MAJORS else SHARPS


def note_to_midi(s: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]*)(-?\d+)", s.strip())
    if not m:
        raise ValueError(f"bad note '{s}' (use C4, F#3, Bb2)")
    n = NOTE_IDX[m.group(1).upper()] + m.group(2).count("#") - m.group(2).count("b")
    return 12 * (int(m.group(3)) + 1) + n


def midi_to_name(p: int, key: str = "C", mode: str = "major") -> str:
    return f"{names_for(key, mode)[p % 12]}{p // 12 - 1}"


def key_root(key: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]?)", key.strip())
    if not m:
        raise ValueError(f"bad key '{key}' (use C, F#, Bb)")
    return (NOTE_IDX[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12


def transpose_key(key: str, semis: int, mode: str = "major") -> str:
    pc = (key_root(key) + semis) % 12
    return names_for(FLATS[pc], mode)[pc] if semis else key


def scale_pcs(key: str, mode: str) -> list[int]:
    steps = MODES.get(mode) or SCALES.get(mode)
    if steps is None:
        raise ValueError(f"mode/scale must be one of {sorted(MODES) + sorted(SCALES)}")
    r = key_root(key)
    return [(r + s) % 12 for s in steps]


def parse_roman(sym: str, key: str, mode: str) -> tuple[int, list[int], str]:
    """'i', 'bVII', 'V7', 'ii°', 'IVmaj7', 'Isus4', 'V/V' not supported.
    Plain numerals are diatonic to the mode; numerals with an accidental are relative to the major
    scale (standard practice: in D minor 'bVI' = Bb)."""
    m = re.fullmatch(r"([b#]?)([ivIV]+)(°|o|ø|\+)?(maj9|maj7|mmaj7|m7b5|7sus4|7b9|m11|m7|m9|m6|madd9|dim7|13|7|9|6|add9|sus2|sus4|5)?", sym)
    if not m:
        raise ValueError(f"bad chord '{sym}' (roman numerals: I ii iii IV V vi vii°, bVII, V7, IVmaj7, isus4, I:2 for 2 bars)")
    acc, num, mark, ext = m.groups()
    deg = ROMAN.get(num.upper())
    if deg is None:
        raise ValueError(f"bad roman numeral '{num}'")
    steps = MODES["major"] if acc else MODES.get(mode, MODES["major"])
    root = (key_root(key) + steps[deg - 1] + (-1 if acc == "b" else 1 if acc == "#" else 0)) % 12
    upper = num.isupper()
    if mark in ("°", "o"):
        q = "dim7" if ext == "7" else "dim"
    elif mark == "ø":
        q = "m7b5"
    elif mark == "+":
        q = "aug"
    elif ext in ("sus2", "sus4", "5", "maj7", "maj9", "mmaj7", "m7b5", "dim7", "madd9", "7sus4", "7b9", "13", "m11"):
        q = ext
    elif ext == "add9":
        q = "add9" if upper else "madd9"
    elif ext in ("7", "9", "6"):
        q = ext if upper else {"7": "m7", "9": "m9", "6": "m6"}[ext]
    elif ext in ("m7", "m9", "m6"):
        q = ext
    else:
        q = "maj" if upper else "min"
    nm = (FLATS if acc == "b" else SHARPS if acc == "#" else names_for(key, mode))[root]
    label = nm + {"maj": "", "min": "m"}.get(q, q)
    return root, QUALITIES[q], label


@dataclass
class Chord:
    start: float      # beats
    dur: float
    root: int         # pitch class
    ivs: list[int]
    label: str

    @property
    def pcs(self) -> set[int]:
        return {(self.root + i) % 12 for i in self.ivs}


def timeline(prog: str, key: str, mode: str, start: float, length: float, bpb: float, default_bars: float = 1.0) -> list[Chord]:
    """'I vi IV:2 V' -> chords filling [start, start+length) (progression repeats). ':N' = bars."""
    toks = []
    for tok in prog.split():
        sym, _, bars = tok.partition(":")
        r, ivs, lab = parse_roman(sym, key, mode)
        toks.append((r, ivs, lab, float(bars) if bars else default_bars))
    if not toks:
        raise ValueError("empty progression")
    out, t, i = [], 0.0, 0
    while t < length - 1e-6:
        r, ivs, lab, bars = toks[i % len(toks)]
        d = min(bars * bpb, length - t)
        out.append(Chord(start + t, d, r, ivs, lab))
        t += bars * bpb
        i += 1
    return out


def chord_at(tl: list[Chord], t: float) -> Chord:
    for c in tl:
        if c.start - 1e-6 <= t < c.start + c.dur - 1e-6:
            return c
    return tl[-1] if t >= tl[-1].start else tl[0]


# ------------------------------------------------------------------ meters

METERS = {
    # name: (beats per bar in quarter notes, beat grouping in quarters, steps per bar in 16ths)
    "4/4": (4, [1, 1, 1, 1]), "2/4": (2, [1, 1]), "3/4": (3, [1, 1, 1]), "5/4": (5, [1, 1, 1, 1, 1]),
    "6/8": (3, [1.5, 1.5]), "9/8": (4.5, [1.5, 1.5, 1.5]), "12/8": (6, [1.5, 1.5, 1.5, 1.5]),
    "7/8": (3.5, [1, 1, 1.5]), "5/8": (2.5, [1, 1.5]), "7/4": (7, [1, 1, 1, 1, 1, 1, 1]),
}


def meter(name: str) -> tuple[float, list[float]]:
    if name not in METERS:
        raise ValueError(f"meter: {sorted(METERS)}")
    return METERS[name]


def is_compound(name: str) -> bool:
    return name in ("6/8", "9/8", "12/8")


def felt(name: str) -> float:
    """Quarter notes per felt beat: tempos are given in felt beats (dotted quarter in 6/8, 9/8, 12/8)."""
    return 1.5 if is_compound(name) else 1.0


def strong_beats(name: str) -> list[float]:
    """Positions (quarters from bar start) of the beat groups."""
    _, grp = meter(name)
    pos, out = 0.0, []
    for g in grp:
        out.append(pos)
        pos += g
    return out


def apply_swing(notes, amount: float, unit: float = 0.5):
    """Delay off-beat notes: unit 0.5 = 8th swing, 0.25 = 16th swing. amount 0..1 (1 = full triplet feel)."""
    if amount <= 0:
        return notes
    shift = amount * unit / 3.0
    for n in notes:
        pos = n.start / unit
        if abs(pos - round(pos)) < 1e-3 and int(round(pos)) % 2 == 1:
            n.start += shift
            n.dur = max(0.03, n.dur - shift * 0.8)
    return notes


def humanize(notes, rng: random.Random, timing: float = 0.01, velocity: int = 6):
    for n in notes:
        n.start = max(0.0, n.start + rng.uniform(-timing, timing))
        n.vel = max(1, min(127, n.vel + rng.randint(-velocity, velocity)))
    return notes
