"""Part generators for gameforge-music. Every generator works on a chord timeline (theory.Chord list)
inside [start, end) and knows the meter's beat grouping, so they behave in 4/4, 3/4, 6/8, 7/8 alike.

ctx = {"key", "mode", "meter", "bpb", "grp"}; p = the track spec (dict) for options; rng = random.Random.
"""
from __future__ import annotations

import math

import theory as T
from model import Note

C3 = 48


# ------------------------------------------------------------------ helpers

def _bars(start, end, bpb):
    b = start
    while b < end - 1e-6:
        yield b
        b += bpb


def _groups(ctx):
    pos, out = 0.0, []
    for g in ctx["grp"]:
        out.append((pos, g))
        pos += g
    return out


def voice(root_pc, ivs, prev, center, spread=False, floor=C3):
    """Pick an inversion/octave near the previous chord (smooth voice leading), kept above `floor`."""
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
            if spread and len(v) >= 3 and v[0] - 12 >= floor:
                v = [v[0] - 12] + v[1:]
            if v[0] >= floor - 5:
                cands.append(v)

    def cost(v):
        c = abs(sum(v) / len(v) - center) * 0.6
        if prev:
            c += sum(min(abs(a - b) for b in prev) for a in v)
        return c
    return min(cands or [[center]], key=cost)


def colorize(ch: T.Chord, color: str, key: str) -> list[int]:
    """triad | 7th | 9th — add jazz/pop extensions to plain triads."""
    ivs = list(ch.ivs)
    if color == "triad" or len(ivs) > 3:
        return ivs
    dominant = (ch.root - T.key_root(key)) % 12 == 7
    minor = 3 in ivs and 7 in ivs
    if color in ("7th", "9th"):
        if 6 in ivs:
            ivs = [0, 3, 6, 10]
        elif minor:
            ivs = [0, 3, 7, 10]
        elif dominant:
            ivs = [0, 4, 7, 10]
        else:
            ivs = [0, 4, 7, 11]
    if color == "9th":
        ivs = ivs + [14]
    return ivs


# ------------------------------------------------------------------ chords / comp / pads

def _comp_positions(rhythm, bpb, ctx, chord_dur):
    """(offset in beats from the bar start, length) list for one bar."""
    grp = _groups(ctx)
    if rhythm == "beats":
        return [(o, g * 0.9) for o, g in grp]
    if rhythm == "halves":
        mid = grp[len(grp) // 2][0]
        return [(0, mid * 0.95), (mid, (bpb - mid) * 0.95)]
    if rhythm == "pulse8":
        return [(k * 0.5, 0.45) for k in range(int(bpb * 2))]
    if rhythm == "pulse16":
        return [(k * 0.25, 0.2) for k in range(int(bpb * 4))]
    if rhythm == "offbeat":            # ska / upbeat skank on every 8th off-beat
        return [(k + 0.5, 0.25) for k in range(int(bpb))]
    if rhythm == "reggae":             # chops on beats 2 and 4
        return [(o, 0.3) for i, (o, g) in enumerate(grp) if i % 2 == 1]
    if rhythm == "stabs":
        return [(0, 0.15), (1.5, 0.15), (2.5, 0.15)] if bpb == 4 else [(0, 0.15), (grp[-1][0], 0.15)]
    if rhythm == "charleston":
        return [(0, 0.8), (1.5, 0.4)] if bpb >= 3 else [(0, 0.8)]
    if rhythm == "bossa":
        return [(0, 0.45), (1.5, 0.45), (3.0, 0.45)] if bpb == 4 else [(0, 0.45)]
    if rhythm == "funk16":
        return [(0, 0.12), (0.75, 0.12), (1.5, 0.12), (2.25, 0.12), (3.25, 0.12)] if bpb == 4 else [(0, 0.12)]
    if rhythm == "waltz":              # pah-pah on the later beats
        return [(o, g * 0.5) for o, g in grp[1:]]
    if rhythm == "strum":              # D . D U . U D U
        return [(0, 0.9), (1, 0.45), (1.5, 0.45), (2.5, 0.45), (3, 0.45), (3.5, 0.45)] if bpb == 4 else [(o, g * 0.8) for o, g in grp]
    if rhythm == "compound":           # 6/8 / 12/8 lilt: long-short
        return [(o, 1.0) for o, g in grp] + [(o + 1.0, 0.45) for o, g in grp if g >= 1.5]
    return None                        # sustain


def gen_chords(tl, start, end, ctx, p, rng):
    rhythm = p.get("rhythm", "sustain")
    octave = int(p.get("octave", 4))
    spread = bool(p.get("spread", rhythm == "sustain"))
    vel = int(p.get("velocity", 70))
    color = p.get("color", "triad")
    strum = float(p.get("strum", 0.03 if rhythm in ("strum", "beats") and p.get("instrument", "") in ("acoustic_guitar", "nylon_guitar", "electric_guitar", "banjo") else 0))
    center = 12 * (octave + 1) + 2
    out, prev = [], None
    bpb = ctx["bpb"]
    for ch in tl:
        if ch.start >= end or ch.start + ch.dur <= start:
            continue
        v = voice(ch.root, colorize(ch, color, ctx["key"]), prev, center, spread)
        prev = v
        if rhythm == "sustain":
            hits = [(ch.start, ch.dur * 0.98)]
        else:
            hits = []
            for bar in _bars(ch.start, ch.start + ch.dur, bpb):
                pos = _comp_positions(rhythm, bpb, ctx, ch.dur)
                if pos is None:
                    raise ValueError("chord rhythm: sustain | beats | halves | pulse8 | pulse16 | offbeat | reggae | stabs | charleston | bossa | funk16 | waltz | strum | compound")
                hits += [(bar + o, d) for o, d in pos if bar + o < ch.start + ch.dur - 1e-6]
        for k, (t, d) in enumerate(hits):
            up = rhythm == "strum" and k % 2 == 1
            order = v[::-1] if up else v
            for j, pch in enumerate(order):
                out.append(Note(t + j * strum, max(0.05, d - j * strum), pch, max(1, min(127, vel + (8 if abs((t - ch.start) % bpb) < 1e-6 else 0) + rng.randint(-5, 5)))))
    return [n for n in out if start - 1e-6 <= n.start < end]


# ------------------------------------------------------------------ bass

def gen_bass(tl, start, end, ctx, p, rng):
    style = p.get("style", "root")
    octave = int(p.get("octave", 2))
    vel = int(p.get("velocity", 96))
    base = 12 * (octave + 1)
    bpb = ctx["bpb"]
    grp = _groups(ctx)
    tonic = T.key_root(ctx["key"])
    out = []
    for i, ch in enumerate(tl):
        if ch.start >= end or ch.start + ch.dur <= start:
            continue
        nxt = tl[i + 1] if i + 1 < len(tl) else tl[0]
        r = base + ch.root
        if r - base >= 7 and style not in ("high",):
            r -= 12 if r - 12 >= 12 * octave + 4 else 0
        fifth = r + 7
        third = r + (3 if 3 in ch.ivs else 4)
        octv = r + 12
        seq = []
        for bar in _bars(ch.start, ch.start + ch.dur, bpb):
            bl = min(bpb, ch.start + ch.dur - bar)
            if style in ("root", "sustain"):
                seq.append((bar, bl, r))
            elif style == "root_fifth":
                seq += [(bar + o, g * 0.95, r if k % 2 == 0 else fifth) for k, (o, g) in enumerate(grp) if o < bl]
            elif style == "octave":
                seq += [(bar + k * 0.5, 0.45, r if k % 2 == 0 else octv) for k in range(int(bl * 2))]
            elif style == "octave16":
                seq += [(bar + k * 0.25, 0.22, r if k % 2 == 0 else octv) for k in range(int(bl * 4))]
            elif style == "pulse8":
                seq += [(bar + k * 0.5, 0.45, r) for k in range(int(bl * 2))]
            elif style == "pulse16":
                seq += [(bar + k * 0.25, 0.2, r) for k in range(int(bl * 4))]
            elif style == "syncopated":
                seq += [(bar, 0.75, r), (bar + 0.75, 0.75, r), (bar + 1.5, 0.5, fifth)] + ([(bar + 2.5, 0.5, octv), (bar + 3.0, 0.9, r)] if bl >= 4 else [])
            elif style == "walking":
                beats = [o for o, g in grp if o < bl]
                tones = [r, third, fifth, octv - 1]
                for k, o in enumerate(beats):
                    last = k == len(beats) - 1 and bar + bpb >= ch.start + ch.dur - 1e-6
                    if last:
                        tgt = base + nxt.root
                        pch = tgt + (1 if rng.random() < 0.5 else -1)
                    else:
                        pch = tones[k % len(tones)] if k else r
                    seq.append((bar + o, 0.9, pch))
            elif style == "pedal":
                seq.append((bar, bl, base + tonic))
            elif style == "funk":
                seq += [(bar, 0.2, r), (bar + 0.75, 0.2, r), (bar + 1.5, 0.2, octv), (bar + 2.25, 0.2, r), (bar + 2.75, 0.2, fifth), (bar + 3.5, 0.2, octv)][: 6 if bl >= 4 else 2]
            elif style == "reggae":          # one-drop: rests on 1, melodic answer
                seq += [(bar + 1.0, 0.45, r), (bar + 1.5, 0.45, third), (bar + 2.5, 0.45, fifth), (bar + 3.0, 0.9, r)] if bl >= 4 else [(bar + 1, 0.9, r)]
            elif style == "bossa":
                seq += [(bar, 1.4, r), (bar + 1.5, 0.45, fifth), (bar + 2, 1.4, fifth), (bar + 3.5, 0.45, r)] if bl >= 4 else [(bar, bl * 0.9, r)]
            elif style == "waltz":
                seq.append((bar, grp[0][1] * 0.95, r if (bar - ch.start) // bpb % 2 == 0 else fifth))
            elif style == "oompah":          # polka / circus / march
                seq += [(bar + o, g * 0.5, r if k % 2 == 0 else fifth) for k, (o, g) in enumerate(grp) if k % 2 == 0 and o < bl]
            elif style == "boom":            # hip-hop
                seq += [(bar, 1.4, r), (bar + 1.75, 0.5, r), (bar + 2.5, 1.2, fifth if rng.random() < 0.4 else r)] if bl >= 4 else [(bar, bl, r)]
            elif style == "rolling":         # drum & bass
                seq += [(bar, 0.7, r), (bar + 0.75, 0.7, r), (bar + 1.75, 0.5, octv), (bar + 2.5, 1.2, r)] if bl >= 4 else [(bar, bl, r)]
            elif style == "gallop":          # metal: 8th + two 16ths
                for k in range(int(bl)):
                    seq += [(bar + k, 0.45, r), (bar + k + 0.5, 0.22, r), (bar + k + 0.75, 0.22, r)]
            elif style == "chip":
                seq += [(bar + k * 0.5, 0.3, r if k % 2 == 0 else octv) for k in range(int(bl * 2))]
            elif style == "compound":        # 6/8 / 12/8: root on each dotted beat, fifth pickup
                for o, g in grp:
                    if o < bl:
                        seq += [(bar + o, 1.0, r), (bar + o + 1.0, 0.45, fifth)] if g >= 1.5 else [(bar + o, g * 0.9, r)]
            else:
                raise ValueError("bass style: root | sustain | root_fifth | octave | octave16 | pulse8 | pulse16 | syncopated | walking | pedal | funk | reggae | bossa | waltz | oompah | boom | rolling | gallop | chip | compound")
        for t, d, pch in seq:
            if t < ch.start + ch.dur - 1e-6:
                acc = 8 if abs((t - start) % bpb) < 1e-6 else 0
                out.append(Note(t, min(d, ch.start + ch.dur - t), pch, max(1, min(127, vel + acc + rng.randint(-6, 4)))))
    return [n for n in out if start - 1e-6 <= n.start < end]


# ------------------------------------------------------------------ arp / ostinato

def gen_arp(tl, start, end, ctx, p, rng):
    pattern = p.get("pattern", "up")
    rate = float(p.get("rate", 0.5))
    span = int(p.get("span", 1))
    octave = int(p.get("octave", 4))
    vel = int(p.get("velocity", 72))
    color = p.get("color", "triad")
    out = []
    for ch in tl:
        if ch.start >= end or ch.start + ch.dur <= start:
            continue
        base = 12 * (octave + 1) + ch.root
        ivs = colorize(ch, color, ctx["key"])[:4]
        tones = sorted({base + iv + 12 * o for o in range(span) for iv in ivs})
        seqs = {"up": tones, "down": tones[::-1], "updown": tones + tones[-2:0:-1], "random": tones,
                "alberti": [tones[0], tones[-1], tones[1 if len(tones) > 2 else 0], tones[-1]],
                "pinky": [tones[0], tones[-1] + 12, tones[1], tones[-1] + 12],
                "broken": [tones[0], tones[min(2, len(tones) - 1)], tones[1], tones[min(2, len(tones) - 1)]],
                "cycle": tones}  # chiptune chord: very fast cycling
        seq = seqs.get(pattern)
        if seq is None:
            raise ValueError(f"arp pattern: {sorted(seqs)}")
        k = 0
        while k * rate < ch.dur - 1e-6:
            t = ch.start + k * rate
            pch = rng.choice(tones) if pattern == "random" else seq[k % len(seq)]
            accent = 10 if abs((t - ch.start) % 1) < 1e-6 else 0
            out.append(Note(t, rate * (0.95 if pattern == "cycle" else 0.85), pch, max(1, min(127, vel + accent + rng.randint(-4, 4)))))
            k += 1
    return [n for n in out if start - 1e-6 <= n.start < end]


def gen_ostinato(tl, start, end, ctx, p, rng):
    """Repeated figure relative to each chord root, e.g. figure '1 1 5 1 8 1 5 1' (scale-free: 1=root,
    3=third of the chord, 5=fifth, 8=octave, b7, 9) at `rate` beats per note — epic strings, pulses."""
    fig = str(p.get("figure", "1 5 8 5")).split()
    rate = float(p.get("rate", 0.25))
    octave = int(p.get("octave", 3))
    vel = int(p.get("velocity", 80))
    out = []
    for ch in tl:
        if ch.start >= end or ch.start + ch.dur <= start:
            continue
        base = 12 * (octave + 1) + ch.root
        third = 3 if 3 in ch.ivs else 4
        degree = {"1": 0, "3": third, "5": 7, "8": 12, "b7": 10, "7": 11 if 11 in ch.ivs else 10, "9": 14, "6": 9, "4": 5, "10": 12 + third, "12": 19}
        k = 0
        while k * rate < ch.dur - 1e-6:
            d = fig[k % len(fig)]
            if d not in ("r", "-"):
                out.append(Note(ch.start + k * rate, rate * 0.8, base + degree.get(d, 0), vel + (10 if k % len(fig) == 0 else 0) + rng.randint(-5, 3)))
            k += 1
    return [n for n in out if start - 1e-6 <= n.start < end]


# ------------------------------------------------------------------ power chords / drone / texture / fanfare

def gen_power(tl, start, end, ctx, p, rng):
    style = p.get("style", "chug8")
    octave = int(p.get("octave", 3))
    vel = int(p.get("velocity", 100))
    out = []
    for ch in tl:
        if ch.start >= end or ch.start + ch.dur <= start:
            continue
        r = 12 * (octave + 1) + ch.root
        if r > 12 * (octave + 1) + 7:
            r -= 12
        shape = [r, r + 7, r + 12]
        hits = []
        for bar in _bars(ch.start, ch.start + ch.dur, ctx["bpb"]):
            bl = min(ctx["bpb"], ch.start + ch.dur - bar)
            if style == "sustain":
                hits.append((bar, bl * 0.97, vel))
            elif style == "chug8":
                hits += [(bar + k * 0.5, 0.4, vel if k % 4 == 0 else vel - 25) for k in range(int(bl * 2))]
            elif style == "chug16":
                hits += [(bar + k * 0.25, 0.2, vel if k % 4 == 0 else vel - 28) for k in range(int(bl * 4))]
            elif style == "gallop":
                for k in range(int(bl)):
                    hits += [(bar + k, 0.45, vel), (bar + k + 0.5, 0.22, vel - 20), (bar + k + 0.75, 0.22, vel - 20)]
            elif style == "stops":
                hits += [(bar + o, 0.3, vel) for o, g in _groups(ctx) if o < bl and (o == 0 or rng.random() < 0.5)]
            else:
                raise ValueError("power style: sustain | chug8 | chug16 | gallop | stops")
        for t, d, v in hits:
            for pch in shape:
                out.append(Note(t, d, pch, max(1, min(127, v + rng.randint(-4, 4)))))
    return [n for n in out if start - 1e-6 <= n.start < end]


def gen_drone(tl, start, end, ctx, p, rng):
    """Sustained root (+fifth) — 'section' follows the section tonic, 'chord' follows each chord root.
    Re-struck every `bars` bars so SoundFont sustains do not die out."""
    follow = p.get("follow", "section")
    octave = int(p.get("octave", 2))
    fifth = bool(p.get("fifth", True))
    every = float(p.get("bars", 4)) * ctx["bpb"]
    vel = int(p.get("velocity", 70))
    base = 12 * (octave + 1)
    out = []
    t = start
    while t < end - 1e-6:
        ln = min(every, end - t)
        root = T.key_root(ctx["key"]) if follow == "section" else T.chord_at(tl, t).root
        notes = [base + root] + ([base + root + 7] if fifth else [])
        for pch in notes:
            out.append(Note(t, ln * 0.99, pch, vel))
        t += every
    return out


def gen_texture(tl, start, end, ctx, p, rng):
    """Sparse twinkles/swells from chord tones and scale (bells, celesta, music box, pads) — ambience."""
    density = float(p.get("density", 0.35))
    octave = int(p.get("octave", 5))
    length = float(p.get("length", 1.5))
    vel = int(p.get("velocity", 60))
    pcs = T.scale_pcs(ctx["key"], ctx["mode"])
    out = []
    t = start
    step = 0.5
    while t < end - 1e-6:
        if rng.random() < density * step:
            ch = T.chord_at(tl, t)
            pool = sorted(ch.pcs) if rng.random() < 0.7 else pcs
            pc = rng.choice(list(pool))
            pch = 12 * (octave + 1) + pc
            if rng.random() < 0.25 and pch + 12 <= 96:
                pch += 12
            out.append(Note(t, length * rng.uniform(0.6, 1.4), pch, vel + rng.randint(-12, 8)))
        t += step
    return out


def gen_fanfare(tl, start, end, ctx, p, rng):
    """Brass call at section starts and every `every` bars: rising triad in 8ths/triplets + held top."""
    every = int(p.get("every", 4)) * ctx["bpb"]
    octave = int(p.get("octave", 4))
    vel = int(p.get("velocity", 100))
    out = []
    t = start
    while t < end - 1e-6:
        ch = T.chord_at(tl, t)
        r = 12 * (octave + 1) + ch.root
        third = r + (3 if 3 in ch.ivs else 4)
        figure = [(0, 0.33, r), (0.33, 0.33, third), (0.67, 0.33, r + 7), (1.0, 1.9, r + 12)]
        for o, d, pch in figure:
            if t + o < end:
                out.append(Note(t + o, d, pch, vel + (8 if o == 1.0 else 0)))
                out.append(Note(t + o, d, pch - 12, vel - 10))
        t += every
    return out


# ------------------------------------------------------------------ melody / counter

def _cells(meter_name: str, style: str):
    if T.is_compound(meter_name):
        cells = [[1.5], [1.0, 0.5], [0.5, 0.5, 0.5], [0.75, 0.25, 0.5], [0.5, 1.0]]
        w = {"lyrical": [4, 3, 1, 1, 2], "bouncy": [1, 4, 2, 3, 2], "busy": [1, 2, 5, 2, 1], "sparse": [6, 2, 0.5, 0.5, 1]}.get(style, [2, 3, 3, 2, 2])
    else:
        cells = [[1, 1], [0.5, 0.5, 1], [1.5, 0.5], [0.5, 0.5, 0.5, 0.5], [1, 0.5, 0.5], [0.75, 0.25, 1], [2], [0.25, 0.25, 0.5, 1]]
        w = {"lyrical": [4, 2, 3, 0.5, 1, 1, 3, 0], "bouncy": [1, 2, 3, 1, 2, 4, 0.5, 1], "busy": [1, 2, 1, 5, 3, 1, 0, 3], "sparse": [3, 1, 2, 0, 0.5, 0.5, 6, 0]}.get(style, [3, 3, 2, 2, 2, 1, 1, 0.5])
    return cells, w


def gen_melody(tl, start, end, ctx, p, rng, motif=None):
    """Period-form melody, the way game themes are written. Each 2-bar half has a job:
    a (motif) -> b (answer: motif rhythm, mirrored contour, half cadence on the 2nd/5th degree)
    -> a' (motif sequenced higher: the climax) -> c (cadence: steps down to a long tonic).
    Strong beats land on chord tones, leaps are answered by a step back, the motif's rhythm comes
    back in every half so the tune is recognisable. `motif` (explicit notes) = leitmotif: its rhythm
    and contour are used instead of a generated one. `ornament` adds grace notes / turns."""
    key, mode = ctx["key"], ctx["mode"]
    bpb, grp, meter = ctx["bpb"], ctx["grp"], ctx["meter"]
    octave = int(p.get("octave", 5))
    density = float(p.get("density", 0.6))
    vel = int(p.get("velocity", 92))
    motif_bars = int(p.get("motif_bars", 2 if bpb <= 4.5 else 1))
    style = p.get("rhythm_style", "auto")
    ornament = float(p.get("ornament", 0.0))
    contour = p.get("contour", "arch")
    pcs = T.scale_pcs(key, p.get("scale") or mode)
    tonic = T.key_root(key)
    center = 12 * (octave + 1) + (tonic if tonic <= 7 else tonic - 12) + 4
    pool = [q for q in range(center - 10, center + 15) if q % 12 in pcs]
    strong = T.strong_beats(meter)
    half = motif_bars * bpb
    land = sum(grp[-((len(grp) + 1) // 2):]) if motif_bars == 1 else sum(grp[len(grp) // 2:]) if len(grp) > 1 else grp[0]
    land = min(land, half / 2)
    span = half - land

    def clamp(i):
        return max(0, min(len(pool) - 1, i))

    def idx_of(pch):
        return min(range(len(pool)), key=lambda i: (abs(pool[i] - pch), pool[i]))

    def on_strong(t):
        x = (t - start) % bpb
        return any(abs(x - s) < 1e-6 for s in strong)

    def snap(i, t, reach=1):
        ch = T.chord_at(tl, t).pcs
        cands = [j for j in range(clamp(i - reach), clamp(i + reach) + 1) if pool[j] % 12 in ch]
        return min(cands, key=lambda j: (abs(j - i), j)) if cands else i

    # ---- motif: rhythm + steps (scale degrees)
    if motif:
        rhythm = [n.dur for n in motif]
        while rhythm and sum(rhythm) > span + 1e-6:
            rhythm.pop()
        if sum(rhythm) < span - 1e-6:
            rhythm.append(span - sum(rhythm))
        mi = [idx_of(n.pitch) for n in motif][: len(rhythm)]
        mi += [mi[-1]] * (len(rhythm) - len(mi))
        steps = [0] + [b - a for a, b in zip(mi, mi[1:])]
        start_idx = mi[0]
    else:
        if style == "auto":
            style = "busy" if density > 0.75 else "lyrical" if density < 0.4 else "normal"
        cells, w = _cells(meter, style)
        rhythm = []
        while sum(rhythm) < span - 1e-6:
            rhythm += rng.choices(cells, w)[0]
        while sum(rhythm) > span + 1e-6:
            over = sum(rhythm) - span
            if rhythm[-1] > over + 1e-6:
                rhythm[-1] -= over
            else:
                rhythm.pop()
        steps, net = [0], 0
        for _ in rhythm[1:]:
            for _try in range(12):
                st = rng.choices([1, -1, 2, -2, 3, -3, 0], [5, 4, 2, 2, 1, 0.8, 0.8])[0]
                if len(steps) > 1 and abs(steps[-1]) >= 2:
                    st = -1 if steps[-1] > 0 else 1          # answer a leap with a step back
                if st == 0 and steps[-1] == 0:
                    continue
                if abs(net + st) > 4:
                    continue
                break
            steps.append(st)
            net += st
        if all(abs(s) <= 1 for s in steps) and len(steps) > 2:   # give the motif one memorable leap
            k = 1 + rng.randrange(len(steps) - 1)
            steps[k] = 2 if steps[k] >= 0 else -2
        first_ch = T.chord_at(tl, start).pcs
        start_idx = snap(idx_of(center - (3 if contour == "rise" else -2 if contour == "fall" else 0)), start, 2)
        start_idx = start_idx if pool[start_idx] % 12 in first_ch else snap(start_idx, start, 3)

    def realize(t0, i0, rh, st, snap_strong=True, dyn=0):
        out, i, t = [], i0, t0
        for k, d in enumerate(rh):
            if t >= end - 1e-6:
                break
            i = clamp(i + (st[k] if k else 0)) if k else clamp(i0)
            if snap_strong and on_strong(t):
                i = snap(i, t)
            out.append([t, min(d, end - t), i, vel + dyn + (7 if on_strong(t) else 0) + rng.randint(-4, 3)])
            t += d
        return out, i, t

    def landing(t, i, kind):
        ch = T.chord_at(tl, t).pcs
        if kind == "tonic":
            allowed = {tonic}
        else:
            pref = ({(tonic + 2) % 12, (tonic + 7) % 12} & ch) or (ch - {tonic}) or ch
            allowed = pref
        cands = [j for j in range(len(pool)) if pool[j] % 12 in allowed] or [i]
        return min(cands, key=lambda j: (abs(j - i), -j if kind == "half" else j))

    n_halves = max(1, int(math.ceil((end - start) / half - 1e-6)))
    plan = (["a", "b", "a2", "c"] * (n_halves // 4 + 1))[:n_halves]
    if n_halves % 4 == 2:
        plan[-2:] = ["a", "c"]
    elif n_halves % 4 == 3:
        plan[-3:] = ["a", "b", "c"]
    elif n_halves == 1:
        plan = ["a_end"]
    lift = {"rise": 3, "arch": 2, "wave": -1, "fall": -2}.get(contour, 2)
    notes = []
    t, cur = start, start_idx
    for h, role in enumerate(plan):
        t0 = start + h * half
        if t0 >= end - 1e-6:
            break
        period = h // 4
        if role in ("a", "a_end"):
            body, cur, t = realize(t0, start_idx + (1 if period % 2 == 1 and contour == "rise" else 0), rhythm, steps, dyn=0)
        elif role == "a2":
            body, cur, t = realize(t0, start_idx + lift, rhythm, steps, dyn=6)
        elif role == "b":
            rh = list(rhythm)
            if len(rh) >= 3 and not motif:                    # vary the tail of the rhythm
                tail = sum(rh[-2:])
                rh = rh[:-2] + ([tail / 2, tail / 2] if rng.random() < 0.5 else [tail * 0.75, tail * 0.25])
            st = [-s for s in steps] + [0] * (len(rh) - len(steps))
            body, cur, t = realize(t0, cur + rng.choice([-1, 1]), rh, st, dyn=2)
        else:                                                # cadence: step down to the tonic
            rh = list(rhythm)
            tg = [j for j in range(len(pool)) if pool[j] % 12 == tonic and j <= cur + 1]
            tgt = max(tg) if tg else min(j for j in range(len(pool)) if pool[j] % 12 == tonic)
            n = len(rh)
            body, tt = [], t0
            for k, d in enumerate(rh):
                frac = (k + 1) / (n + 1)
                i = clamp(round(cur + (tgt + 1 - cur) * frac)) if cur > tgt else clamp(round(cur + (tgt - 1 - cur) * frac))
                if k == 0 and motif is None:
                    i = clamp(cur + (1 if cur <= tgt else 0))
                if on_strong(tt) and k < n - 1:
                    j = snap(i, tt)
                    i = j if abs(j - i) <= 1 else i
                body.append([tt, min(d, end - tt), i, vel - 2 * k + rng.randint(-3, 3)])
                tt += d
            cur, t = (body[-1][2] if body else cur), tt
        kind = {"a": "chord", "b": "half", "a2": "chord", "c": "tonic", "a_end": "tonic"}[role]
        if h == len(plan) - 1:
            kind = "tonic"
        for bt, d, i, v in body:
            if bt < end - 1e-6:
                notes.append((bt, d, pool[i], v))
        if t < end - 1e-6:
            li = landing(t, cur, kind)
            notes.append((t, min(land, end - t), pool[li], vel + 4))
            cur = li
            t += land
    out = []
    for bt, d, pch, v in notes:
        v = max(1, min(127, v))
        if ornament and d >= 0.75 and rng.random() < ornament:
            ii = idx_of(pch)
            up = pool[clamp(ii + 1)]
            if rng.random() < 0.5:
                out.append(Note(bt, 0.12, up, v - 15))
                out.append(Note(bt + 0.12, d * 0.9 - 0.12, pch, v))
            else:
                lo = pool[clamp(ii - 1)]
                tq = min(0.125, d / 6)
                for k, q in enumerate((up, pch, lo)):
                    out.append(Note(bt + k * tq, tq, q, v - 12))
                out.append(Note(bt + 3 * tq, d * 0.92 - 3 * tq, pch, v))
        else:
            out.append(Note(bt, d * (0.96 if d >= 1.5 else 0.9), pch, v))
    return out


def gen_counter(tl, start, end, ctx, p, rng, melody_notes):
    """Second voice against a melody: thirds/sixths below (parallel), contrary motion in half notes,
    or sustained chord tones — keeps a gap of at least a third and never doubles the melody."""
    style = p.get("style", "contrary")
    octave = int(p.get("octave", 4))
    vel = int(p.get("velocity", 74))
    pcs = T.scale_pcs(ctx["key"], ctx["mode"])
    lo, hi = 12 * (octave + 1) - 2, 12 * (octave + 1) + 16
    pool = [q for q in range(lo, hi + 1) if q % 12 in pcs]
    mel = sorted([n for n in melody_notes if start - 1e-6 <= n.start < end], key=lambda n: n.start)

    def mel_at(t):
        cand = [n for n in mel if n.start <= t + 1e-6]
        return cand[-1].pitch if cand else None

    out = []
    if style == "thirds":
        for n in mel:
            if n.dur < 0.3:
                continue
            below = [q for q in pool if 3 <= n.pitch - q <= 9]
            if below:
                tgt = min(below, key=lambda q: abs(n.pitch - q - 4))  # prefer a third/sixth
                out.append(Note(n.start, n.dur, tgt, vel))
    else:
        step = float(p.get("rate", 2.0 if style == "contrary" else 4.0))
        t = start
        prev_m, cur = None, None
        while t < end - 1e-6:
            ch = T.chord_at(tl, t)
            m = mel_at(t)
            cands = [q for q in pool if q % 12 in ch.pcs and (m is None or 3 <= m - q <= 12)] or [q for q in pool if q % 12 in ch.pcs]
            if style == "contrary" and cur is not None and prev_m is not None and m is not None:
                want = cur - 2 if m > prev_m else cur + 2
            else:
                want = (m - 7) if m else 12 * (octave + 1) + 4
            tgt = min(cands, key=lambda q: abs(q - want)) if cands else want
            d = min(step, end - t)
            out.append(Note(t, d * 0.95, tgt, vel + rng.randint(-5, 4)))
            prev_m, cur = m, tgt
            t += step
    return out


def parse_notes(text: str, default_vel: int = 90, offset: float = 0.0) -> list[Note]:
    """'C4:1 E4:.5 r:.5 C4+E4+G4:2 D5:1@110' — pitch(es):beats[@velocity], r = rest."""
    import re
    out, t = [], offset
    for tok in text.split():
        m = re.fullmatch(r"([^:]+):([\d.]+)(?:@(\d+))?", tok)
        if not m:
            raise ValueError(f"bad note token '{tok}' (format C4:1, r:.5, C4+E4+G4:2, D5:1@110)")
        pitches, dur, v = m.group(1), float(m.group(2)), int(m.group(3) or default_vel)
        if pitches.lower() != "r":
            for q in pitches.split("+"):
                out.append(Note(t, dur * 0.95, T.note_to_midi(q), v))
        t += dur
    return out
