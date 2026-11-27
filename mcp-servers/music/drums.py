"""Drum & percussion library for gameforge-music: ~30 styles across meters (4/4, 3/4, 6/8, 12/8,
odd meters via a generic groove), fills, intensity, GM drum map and GM drum kits."""
from __future__ import annotations

import random

import theory as T

GM_DRUM = {
    "kick": 36, "kick2": 35, "rim": 37, "snare": 38, "clap": 39, "esnare": 40, "tom_floor": 41, "hat": 42,
    "tom_lo": 45, "pedal": 44, "tom_mid": 47, "open": 46, "tom_hi": 50, "crash": 49, "ride": 51, "china": 52,
    "bell": 53, "tamb": 54, "splash": 55, "cowbell": 56, "crash2": 57, "bongo_hi": 60, "bongo_lo": 61,
    "conga_mute": 62, "conga_hi": 63, "conga_lo": 64, "timbale_hi": 65, "timbale_lo": 66, "agogo": 67,
    "cabasa": 69, "shaker": 70, "guiro": 73, "claves": 75, "wood_hi": 76, "wood_lo": 77, "triangle": 81,
}
KITS = {"standard": 0, "room": 8, "power": 16, "electronic": 24, "808": 25, "jazz": 32, "brush": 40, "orchestra": 48}

# x = hit, X = accent, o = ghost, . = rest — one char per 16th note
STYLES: dict[str, dict] = {
    # ---- rock / pop
    "rock": {"meter": "4/4", "kit": "standard", "fill": "toms", "parts": {"kick": "x.......x.x.....", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}},
    "pop": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.....x.x.......", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x.", "shaker": "..x...x...x...x."}},
    "punk": {"meter": "4/4", "kit": "power", "fill": "snare", "parts": {"kick": "x.x.x.x.x.x.x.x.", "snare": "....X.......X...", "crash": "x.x.x.x.x.x.x.x."}},
    "metal": {"meter": "4/4", "kit": "power", "fill": "toms", "parts": {"kick": "xxxxxxxxxxxxxxxx", "snare": "....X.......X...", "china": "x.......x.......", "hat": "x.x.x.x.x.x.x.x."}},
    "halftime": {"meter": "4/4", "kit": "standard", "fill": "toms", "parts": {"kick": "x.........x.....", "snare": "........X.......", "hat": "x.x.x.x.x.x.x.x."}},
    "shuffle": {"meter": "4/4", "kit": "room", "fill": "snare", "swing": 0.8, "parts": {"kick": "x.......x.......", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}},
    "funk": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.x....x..x.....", "snare": "....X..o.o..X..o", "hat": "xxxxxxxxxxxxxxxx", "open": "..............x."}},
    "disco": {"meter": "4/4", "kit": "standard", "fill": "toms", "parts": {"kick": "x...x...x...x...", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x.", "open": "..x...x...x...x."}},
    # ---- electronic
    "house": {"meter": "4/4", "kit": "electronic", "fill": "none", "parts": {"kick": "x...x...x...x...", "clap": "....X.......X...", "open": "..x...x...x...x.", "shaker": "xxxxxxxxxxxxxxxx"}},
    "techno": {"meter": "4/4", "kit": "electronic", "fill": "none", "parts": {"kick": "x...x...x...x...", "rim": "..x..x....x..x..", "hat": "xxxxxxxxxxxxxxxx", "clap": "....x.......x..."}},
    "edm": {"meter": "4/4", "kit": "electronic", "fill": "snare", "parts": {"kick": "x...x...x...x...", "clap": "....X.......X...", "hat": "..x...x...x...x.", "open": "......x.......x."}},
    "synthwave": {"meter": "4/4", "kit": "electronic", "fill": "toms", "parts": {"kick": "x.......x.......", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x.", "tamb": "....x.......x..."}},
    "dnb": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.........x.....", "snare": "....X.......X...", "hat": "x.xxx.x.x.xxx.x.", "ride": "x...x...x...x..."}},
    "breakbeat": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.........x.....", "snare": "....X..o.o..X...", "hat": "x.xxx.x.x.xxx.x."}},
    "dubstep": {"meter": "4/4", "kit": "electronic", "fill": "snare", "parts": {"kick": "x.........x.....", "snare": "........X.......", "hat": "x.x.x.x.x.x.x.x."}},
    "trap": {"meter": "4/4", "kit": "808", "fill": "none", "parts": {"kick": "x......x..x.....", "clap": "........X.......", "hat": "xxxxxxxxx.xxxxxx", "open": "...............x"}},
    "boom_bap": {"meter": "4/4", "kit": "standard", "fill": "none", "swing": 0.35, "parts": {"kick": "x......xx.x.....", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}},
    "lofi": {"meter": "4/4", "kit": "jazz", "fill": "none", "swing": 0.45, "parts": {"kick": "x......x..x.....", "snare": "....x.......x..o", "hat": "x.x.x.xxx.x.x.x."}},
    "chip": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "..x...x...x...x."}},
    "chip_fast": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"kick": "x.....x.x.......", "snare": "....x.......x.x.", "hat": "x.x.x.x.x.x.x.x."}},
    "16bit": {"meter": "4/4", "kit": "room", "fill": "toms", "parts": {"kick": "x.....x...x.....", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x.", "crash": "x..............."}},
    # ---- world / acoustic
    "jazz_swing": {"meter": "4/4", "kit": "jazz", "fill": "none", "swing": 0.9, "parts": {"ride": "x...x.x.x...x.x.", "pedal": "....x.......x...", "kick": "x.......o.......", "snare": "..........o....."}},
    "brush": {"meter": "4/4", "kit": "brush", "fill": "none", "swing": 0.8, "parts": {"snare": "o.o.o.o.o.o.o.o.", "pedal": "....x.......x...", "kick": "x.......x......."}},
    "bossa": {"meter": "4/4", "kit": "jazz", "fill": "none", "parts": {"kick": "x..xx..xx..xx..x", "rim": "x..x..x...x..x..", "shaker": "xxxxxxxxxxxxxxxx"}},
    "latin": {"meter": "4/4", "kit": "standard", "fill": "toms", "parts": {"kick": "x..x....x..x....", "conga_hi": "..x...x...x.xx..", "conga_lo": "....x.......x...", "cowbell": "x.x.x.x.x.x.x.x.", "claves": "x..x..x...x.x..."}},
    "reggae": {"meter": "4/4", "kit": "standard", "fill": "none", "parts": {"kick": "........X.......", "rim": "........X.......", "hat": "x.x.x.x.x.x.x.x."}},
    "march": {"meter": "4/4", "kit": "standard", "fill": "snare", "parts": {"snare": "x.oox.oox.oox.x.", "kick": "x.......x.......", "crash": "x..............."}},
    "orchestral": {"meter": "4/4", "kit": "orchestra", "fill": "toms", "parts": {"tom_floor": "x.......x.......", "tom_lo": "......x.......x.", "crash": "x..............."}},
    "taiko": {"meter": "4/4", "kit": "orchestra", "fill": "toms", "parts": {"kick": "x..x..x.x..x....", "tom_lo": "....x.......x.xx", "tom_hi": "..x.......x....."}},
    "cinematic_build": {"meter": "4/4", "kit": "orchestra", "fill": "toms", "parts": {"tom_lo": "x.x.x.x.x.x.x.x.", "tom_floor": "x...x...x...x...", "snare": "............xxxx"}},
    "light": {"meter": "4/4", "kit": "room", "fill": "none", "parts": {"kick": "x.......x.......", "rim": "....x.......x...", "shaker": "x.x.x.x.x.x.x.x."}},
    "ambient": {"meter": "4/4", "kit": "room", "fill": "none", "parts": {"kick": "x...............", "shaker": "....x.......x...", "triangle": "x..............."}},
    "sparse": {"meter": "4/4", "kit": "orchestra", "fill": "none", "parts": {"kick": "x...............", "tom_lo": "........x......."}},
    # ---- other meters
    "waltz": {"meter": "3/4", "kit": "room", "fill": "none", "parts": {"kick": "x...........", "snare": "....x...x...", "hat": "x...x...x..."}},
    "jig": {"meter": "6/8", "kit": "room", "fill": "none", "parts": {"kick": "x.....x.....", "tom_lo": "....x.....x.", "shaker": "x.x.x.x.x.x."}},
    "shanty": {"meter": "6/8", "kit": "room", "fill": "none", "parts": {"kick": "x.....x.....", "clap": "......X.....", "tamb": "x.x.x.x.x.x."}},
    "tarantella": {"meter": "6/8", "kit": "standard", "fill": "none", "parts": {"kick": "x.....x.....", "tamb": "x.xxx.x.xxx.", "snare": "......x....."}},
    "slow_blues": {"meter": "12/8", "kit": "room", "fill": "snare", "parts": {"kick": "x...........x...........", "snare": "......X...........X.....", "ride": "x.x.x.x.x.x.x.x.x.x.x.x."}},
    "polka": {"meter": "2/4", "kit": "standard", "fill": "none", "parts": {"kick": "x...x...", "snare": "..x...x.", "crash": "..x...x."}},
    "circus": {"meter": "2/4", "kit": "standard", "fill": "none", "parts": {"kick": "x...x...", "crash": "..x...x.", "snare": "..x...x."}},
    "odd_groove": {"meter": "7/8", "kit": "standard", "fill": "none", "parts": {"kick": "x...x...x.....", "snare": "..x...x....x..", "hat": "x.x.x.x.x.x.x."}},
    "none": {"meter": "any", "kit": "standard", "fill": "none", "parts": {}},
}


def generic_groove(meter: str) -> dict[str, str]:
    """Any meter: kick on the first beat group, snare/clap on the later ones, hats on eighths."""
    bpb, grp = T.meter(meter)
    steps = int(round(bpb * 4))
    kick, snare, hat = ["."] * steps, ["."] * steps, ["."] * steps
    pos = 0.0
    for i, g in enumerate(grp):
        idx = int(round(pos * 4))
        if i == 0:
            kick[idx] = "X"
        elif i == len(grp) // 2 or (len(grp) > 3 and i == len(grp) - 1):
            snare[idx] = "X"
        else:
            kick[idx] = "x" if len(grp) > 3 else kick[idx]
        pos += g
    for k in range(0, steps, 2):
        hat[k] = "x"
    return {"kick": "".join(kick), "snare": "".join(snare), "hat": "".join(hat)}


def gen_drums(style: str, start: float, bars: int, meter: str, rng: random.Random, vel: int = 100,
              fill_every: int = 4, intensity: float = 1.0, crash_on_start: bool = True):
    from model import Note
    if style not in STYLES:
        raise ValueError(f"drum style: {sorted(STYLES)}")
    st = STYLES[style]
    bpb, _ = T.meter(meter)
    steps = int(round(bpb * 4))
    parts = st["parts"]
    if parts and st["meter"] not in (meter, "any"):
        parts = generic_groove(meter)
    out = []
    for b in range(bars):
        fill = fill_every and (b + 1) % fill_every == 0 and st["fill"] != "none" and bars > 1
        for inst, s in parts.items():
            s = (s * (steps // len(s) + 1))[:steps]
            if fill and inst not in ("kick", "crash", "china", "ride"):
                s = s[: steps - 4] + "...."
            for k, ch in enumerate(s):
                if ch == ".":
                    continue
                v = {"x": vel - 12, "X": vel + 6, "o": vel - 52}.get(ch, vel)
                v = int(v * (0.75 + 0.25 * intensity))
                out.append(Note(start + b * bpb + k * 0.25, 0.2, GM_DRUM[inst], max(1, min(127, v + rng.randint(-7, 5)))))
        if fill:
            base = start + b * bpb + bpb - 1
            seq = {"toms": [("snare", 0), ("tom_hi", 0.25), ("tom_mid", 0.5), ("tom_lo", 0.75)],
                   "snare": [("snare", 0), ("snare", 0.25), ("snare", 0.5), ("snare", 0.75)]}.get(st["fill"], [])
            for j, (inst, off) in enumerate(seq):
                out.append(Note(base + off, 0.2, GM_DRUM[inst], min(127, vel - 14 + j * 6)))
    if crash_on_start and style in ("rock", "pop", "punk", "metal", "edm", "march", "synthwave", "16bit", "disco", "dnb", "orchestral", "taiko", "cinematic_build", "breakbeat"):
        out.append(Note(start, 0.5, GM_DRUM["crash"], vel))
    return out
