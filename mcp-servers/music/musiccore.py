"""GameForge music core: composition from a spec (genre + mood -> sections, chord timelines, parts),
theme variants (re-orchestrate a melody in another genre/key/mode/meter), section slices for
horizontal re-sequencing, stingers, Standard MIDI File writer/reader and a piano-roll preview.

Times are in beats (quarter notes). Pitches are MIDI numbers (C4 = 60). Pure Python + Pillow.
Modules: theory (scales, chords, meters), model (Note/Track/Song), drums, generators, genres, synth.
"""
from __future__ import annotations

import copy
import math
import random
import re
import struct
from pathlib import Path

from PIL import Image, ImageDraw

import drums as D
import generators as Gn
import genres as GE
import synth as S
import theory as T
from model import Note, Song, Track

GM = {  # General MIDI programs (0-based)
    "piano": 0, "bright_piano": 1, "electric_grand": 2, "honky_tonk": 3, "electric_piano": 4, "electric_piano2": 5,
    "harpsichord": 6, "clavinet": 7, "celesta": 8, "glockenspiel": 9, "music_box": 10, "vibraphone": 11, "marimba": 12,
    "xylophone": 13, "tubular_bells": 14, "dulcimer": 15, "organ": 16, "percussive_organ": 17, "rock_organ": 18,
    "church_organ": 19, "reed_organ": 20, "accordion": 21, "harmonica": 22, "melodica": 22, "bandoneon": 23,
    "nylon_guitar": 24, "acoustic_guitar": 25, "jazz_guitar": 26, "electric_guitar": 27, "muted_guitar": 28,
    "overdrive_guitar": 29, "distortion_guitar": 30, "guitar_harmonics": 31, "acoustic_bass": 32, "fingered_bass": 33,
    "electric_bass": 33, "picked_bass": 34, "fretless_bass": 35, "slap_bass": 36, "slap_bass2": 37, "synth_bass": 38,
    "synth_bass2": 39, "violin": 40, "viola": 41, "cello": 42, "contrabass": 43, "tremolo_strings": 44, "pizzicato": 45,
    "harp": 46, "timpani": 47, "strings": 48, "slow_strings": 49, "synth_strings": 50, "synth_strings2": 51, "choir": 52,
    "voice_oohs": 53, "synth_voice": 54, "orchestra_hit": 55, "trumpet": 56, "trombone": 57, "tuba": 58,
    "muted_trumpet": 59, "french_horn": 60, "brass": 61, "synth_brass": 62, "synth_brass2": 63, "soprano_sax": 64,
    "alto_sax": 65, "tenor_sax": 66, "baritone_sax": 67, "oboe": 68, "english_horn": 69, "bassoon": 70, "clarinet": 71,
    "piccolo": 72, "flute": 73, "recorder": 74, "pan_flute": 75, "blown_bottle": 76, "shakuhachi": 77, "whistle": 78,
    "ocarina": 79, "square_wave": 80, "saw_wave": 81, "calliope": 82, "chiff_lead": 83, "charang": 84, "solo_voice": 85,
    "fifths_lead": 86, "bass_lead": 87, "new_age_pad": 88, "warm_pad": 89, "polysynth": 90, "choir_pad": 91,
    "bowed_pad": 92, "metallic_pad": 93, "halo_pad": 94, "sweep_pad": 95, "rain": 96, "soundtrack": 97, "crystal": 98,
    "atmosphere": 99, "brightness": 100, "goblins": 101, "echoes": 102, "sci_fi": 103, "sitar": 104, "banjo": 105,
    "shamisen": 106, "koto": 107, "kalimba": 108, "bagpipe": 109, "fiddle": 110, "shanai": 111, "tinkle_bell": 112,
    "agogo": 113, "steel_drums": 114, "woodblock": 115, "taiko": 116, "melodic_tom": 117, "synth_drum": 118,
    "reverse_cymbal": 119,
}
CHIP_WAVES = S.CHIP_WAVES
CHIP_GM = {"square": 80, "pulse25": 80, "pulse12": 80, "triangle": 33, "saw": 81, "sine": 79, "noise": 118}
DRUM_KIT_GM = {**D.KITS, "909": 24, "chip": 0, "lofi": 32, "taiko": 48, "acoustic": 0}
ROLES = ("pad", "chords", "pulse", "bass", "arp", "ostinato", "power", "drone", "texture", "fanfare", "drums", "melody", "counter", "notes")
ROLE_PAN = {"arp": 0.25, "counter": -0.3, "ostinato": -0.2, "texture": 0.35, "chords": -0.12, "fanfare": 0.2, "power": -0.15}
ROLE_REVERB = {"drums": 0.12, "bass": 0.05, "drone": 0.4, "pad": 0.45, "melody": 0.32, "texture": 0.55, "counter": 0.35}


def instrument_ok(inst) -> None:
    if isinstance(inst, int) or (isinstance(inst, str) and inst.isdigit()):
        return
    if inst in GM or inst in S.PATCHES or inst in CHIP_WAVES or inst == "kit":
        return
    raise ValueError(f"unknown instrument '{inst}'. GM: {sorted(GM)}; synth patches: {sorted(S.PATCHES)}; chip: {sorted(CHIP_WAVES)}; or a GM program 0-127")


def program_of(tr: Track) -> int:
    if tr.drums:
        return DRUM_KIT_GM.get(tr.kit, 0)
    i = tr.instrument
    if isinstance(i, int) or (isinstance(i, str) and i.isdigit()):
        return int(i)
    if i in S.PATCHES:
        return S.PATCHES[i]["gm"]
    if i in CHIP_WAVES:
        return CHIP_GM[i]
    if i in GM:
        return GM[i]
    instrument_ok(i)
    return 0


# ============================================================ compose

FORM_DEFAULTS = {
    "intro": dict(bars=4, layers=[1], intensity=0.6, letter="A"),
    "break": dict(bars=4, layers=[1], intensity=0.5, letter="A"),
    "build": dict(bars=4, layers=[1, 2], intensity=0.8, letter="B"),
    "bridge": dict(letter="C"),
    "outro": dict(bars=4, layers=[1, 2], intensity=0.7, letter="A"),
}


def _basics(spec: dict) -> dict:
    mood_d, genre_d, mood, genre = GE.resolve(spec)
    seed = int(spec.get("seed", 1))
    mode = spec.get("mode") or mood_d["mode"]
    if mode not in T.MODES and mode not in T.SCALES:
        raise ValueError(f"mode/scale must be one of {sorted(T.MODES) + sorted(T.SCALES)}")
    if mode in T.MODES:
        chord_mode, mel_scale = mode, None
    else:  # pentatonic / blues / whole tone ... -> diatonic chords from the parallel major/minor
        chord_mode = "minor" if 3 in T.SCALES[mode] else "major"
        mel_scale = mode
    meter = spec.get("meter") or genre_d.get("meter", "4/4")
    bpb, grp = T.meter(meter)
    if spec.get("tempo"):
        tempo = float(spec["tempo"])
    elif spec.get("genre"):
        lo, hi = genre_d["tempo"]
        e = mood_d["energy"] if spec.get("mood") else 0.5
        tempo = round(lo + (hi - lo) * e)
    else:
        tempo = round(sum(mood_d["tempo"]) / 2)
    tempo = tempo * T.felt(meter)          # felt beats -> quarter-note BPM (internal)
    return dict(mood_d=mood_d, genre_d=genre_d, mood=mood, genre=genre, seed=seed, mode=mode, chord_mode=chord_mode,
                mel_scale=mel_scale, key=spec.get("key", "C"), meter=meter, bpb=bpb, grp=grp, tempo=tempo)


def _sections(spec: dict, b: dict) -> list[dict]:
    progs = b["mood_d"]["prog"][b["seed"] % len(b["mood_d"]["prog"])]
    prog = {"A": spec.get("progression") or progs[0], "B": spec.get("progression_b") or progs[1]}
    prog["C"] = spec.get("progression_c") or prog["B"]
    sb = int(spec.get("section_bars", 8))
    out = []
    if spec.get("sections"):
        raw = [dict(s) for s in spec["sections"]]
    elif spec.get("form"):
        raw = []
        for tok in str(spec["form"]).replace(",", " ").split():
            lift = tok.endswith("+")
            nm = tok.rstrip("+")
            d = dict(name=tok)
            d.update(FORM_DEFAULTS.get(nm.lower(), {}))
            if nm.upper() in ("A", "B", "C"):
                d["letter"] = nm.upper()
            if nm.upper() == "C" or nm.lower() == "bridge":
                d.setdefault("transpose", 5)
            if lift:
                d["transpose"] = d.get("transpose", 0) + 2
            raw.append(d)
    else:
        bars = int(spec.get("bars", 16 if b["bpb"] >= 3 else 32))
        raw = [dict(name="A", bars=bars // 2), dict(name="B", bars=bars - bars // 2)] if bars >= 16 and bars % 2 == 0 else [dict(name="A", bars=bars)]
    for d in raw:
        nm = str(d.get("name", "A"))
        letter = d.get("letter") or (nm[0].upper() if nm[:1].upper() in "ABC" else "A")
        d.setdefault("bars", sb)
        key = d.get("key") or T.transpose_key(b["key"], int(d.get("transpose", 0)), b["chord_mode"])
        out.append(dict(name=nm, bars=int(d["bars"]), letter=letter, key=key, progression=d.get("progression") or prog[letter],
                        tempo=d.get("tempo"), layers=d.get("layers"), mute=d.get("mute", []), intensity=float(d.get("intensity", 1.0)),
                        drums=d.get("drums"), chord_bars=float(d.get("chord_bars", spec.get("chord_bars", 2 if b["meter"] == "2/4" else 1)))))
    return out


def _track_specs(spec: dict, b: dict) -> list[dict]:
    if spec.get("tracks"):
        tmpl = [dict(t) for t in spec["tracks"]]
    else:
        g = b["genre_d"] or GE.GENRES["orchestral"]
        tmpl = [dict(t) for t in g["tracks"]]
    tmpl += [dict(t) for t in spec.get("add_tracks", [])]
    inst_over = spec.get("instruments", {})
    drop = set(spec.get("drop_roles", []))
    names: dict[str, int] = {}
    out = []
    for t in tmpl:
        role = t.get("role", "notes")
        if role not in ROLES:
            raise ValueError(f"track role: {ROLES}")
        if role in drop or t.get("name") in drop:
            continue
        if role == "drums" and (t.get("style") == "none"):
            continue
        nm = t.get("name") or role.capitalize()
        names[nm] = names.get(nm, 0) + 1
        if names[nm] > 1:
            nm = f"{nm}{names[nm]}"
        t["name"] = nm
        if nm in inst_over:
            t["instrument"] = inst_over[nm]
        elif role in inst_over:
            t["instrument"] = inst_over[role]
        if role != "drums":
            t.setdefault("instrument", "piano")
            instrument_ok(t["instrument"])
        if b["genre_d"].get("engine") and "engine" not in t:
            t["engine"] = b["genre_d"]["engine"]
        if spec.get("engine") and "engine" not in t:
            t["engine"] = spec["engine"]
        out.append(t)
    return out


def _theme_map(notes: list[Note], src_key, src_mode, src_bpb, dst_key, dst_mode, dst_bpb, center: int) -> list[Note]:
    """Map a melody into another key/mode (by scale degree) and meter (proportional within the bar)."""
    ss = T.MODES.get(src_mode, T.MODES["major"])
    ds = T.MODES.get(dst_mode, T.MODES["major"])
    sr, dr = T.key_root(src_key), T.key_root(dst_key)
    shift = dr - sr
    if shift > 6:
        shift -= 12
    if shift < -6:
        shift += 12
    out = []
    for n in notes:
        rel = n.pitch - sr
        octv, pc = divmod(rel, 12)
        deg = max(i for i, s in enumerate(ss) if s <= pc)
        off = pc - ss[deg]
        p = sr + shift + 12 * octv + ds[deg] + off
        bar, pos = divmod(n.start, src_bpb)
        st = bar * dst_bpb + pos * dst_bpb / src_bpb
        st = round(st * 4) / 4
        out.append(Note(st, max(0.12, n.dur * dst_bpb / src_bpb), p, n.vel))
    if out:
        mean = sum(n.pitch for n in out) / len(out)
        k = round((center - mean) / 12)
        for n in out:
            n.pitch += 12 * k
    out.sort(key=lambda n: n.start)
    ded = []
    for n in out:
        if ded and abs(ded[-1].start - n.start) < 1e-6:
            continue
        if ded and ded[-1].start + ded[-1].dur > n.start:
            ded[-1].dur = max(0.1, n.start - ded[-1].start)
        ded.append(n)
    return ded


def compose(spec: dict) -> Song:
    b = _basics(spec)
    key, meter, bpb = b["key"], b["meter"], b["bpb"]
    sections = _sections(spec, b)
    tspecs = _track_specs(spec, b)
    gd = b["genre_d"]
    total_bars = sum(s["bars"] for s in sections)
    song = Song(spec.get("title", "Theme"), b["tempo"], key, b["mode"], meter, total_bars, loop=bool(spec.get("loop", True)),
                genre=b["genre"] or "", reverb=spec.get("reverb") or gd.get("reverb", "hall"),
                master={**gd.get("master", {}), **spec.get("master", {})}, spec=copy.deepcopy(spec))
    if song.reverb not in S.SPACES:
        raise ValueError(f"reverb: {sorted(S.SPACES)}")
    seed = b["seed"]
    motif = Gn.parse_notes(spec["motif"]) if spec.get("motif") else None
    theme = spec.get("_theme")

    # tracks
    tracks = []
    for k, t in enumerate(tspecs):
        role = t["role"]
        drum_style = t.get("style") or gd.get("drums", "pop")
        kit = t.get("kit") or (D.STYLES[drum_style]["kit"] if role == "drums" and drum_style in D.STYLES else "standard")
        fx = dict(t.get("fx", {}))
        if t.get("gated"):
            fx["gated"] = True
        tr = Track(t["name"], role, t.get("instrument", "kit" if role == "drums" else "piano"),
                   volume=float(t.get("volume", 0.8)), pan=float(t.get("pan", ROLE_PAN.get(role, 0.0))),
                   reverb=float(t.get("reverb", ROLE_REVERB.get(role, 0.3))), layer=int(t.get("layer", 1)), drums=role == "drums",
                   engine=t.get("engine", "auto"), kit=kit, duck=float(t.get("duck", 0.0)),
                   params={**{k2: v for k2, v in t.items() if k2 not in ("name", "role", "instrument", "volume", "pan", "reverb", "layer", "engine", "kit", "duck", "fx")}, "fx": fx})
        tracks.append(tr)
    order = sorted(range(len(tracks)), key=lambda i: 0 if tracks[i].role == "melody" else 1)

    pos = 0.0
    tempo_map = [(0.0, b["tempo"])]
    for si, sec in enumerate(sections):
        s0, ln = pos, sec["bars"] * bpb
        song.sections.append((s0, sec["name"], sec["key"], sec["bars"]))
        if sec["tempo"]:
            tempo_map.append((s0, float(sec["tempo"]) * T.felt(meter)))
        elif si > 0 and tempo_map[-1][1] != b["tempo"]:
            tempo_map.append((s0, b["tempo"]))
        tl = T.timeline(sec["progression"], sec["key"], b["chord_mode"], s0, ln, bpb, sec["chord_bars"])
        song.chords += tl
        ctx = dict(key=sec["key"], mode=b["chord_mode"], meter=meter, bpb=bpb, grp=b["grp"])
        inten = sec["intensity"]
        mel_notes: list[Note] = []
        letter_seed = {"A": 0, "B": 1, "C": 2}.get(sec["letter"], 3)
        for k in order:
            tr = tracks[k]
            p = tr.params
            if sec["layers"] and tr.layer not in sec["layers"]:
                continue
            if tr.name in sec["mute"] or tr.role in sec["mute"]:
                continue
            rng = random.Random(seed * 1009 + k * 31 + letter_seed * 7)
            sp = dict(p, instrument=tr.instrument)
            if "velocity" in p:
                sp["velocity"] = int(p["velocity"] * (0.7 + 0.3 * inten))
            role = tr.role
            if role in ("pad", "chords", "pulse"):
                sp.setdefault("rhythm", {"pad": "sustain", "chords": "halves", "pulse": "pulse8"}[role])
                sp.setdefault("velocity", int((64 if role == "pad" else 74) * (0.7 + 0.3 * inten)))
                ns = Gn.gen_chords(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "bass":
                sp.setdefault("velocity", int(96 * (0.75 + 0.25 * inten)))
                ns = Gn.gen_bass(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "arp":
                sp.setdefault("velocity", int(72 * (0.7 + 0.3 * inten)))
                ns = Gn.gen_arp(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "ostinato":
                ns = Gn.gen_ostinato(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "power":
                ns = Gn.gen_power(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "drone":
                ns = Gn.gen_drone(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "texture":
                ns = Gn.gen_texture(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "fanfare":
                ns = Gn.gen_fanfare(tl, s0, s0 + ln, ctx, sp, rng)
            elif role == "drums":
                style = sec["drums"] or p.get("style") or gd.get("drums", "pop")
                ns = D.gen_drums(style, s0, sec["bars"], meter, rng, int(p.get("velocity", 100)), int(p.get("fill_every", 4)),
                                 inten, crash_on_start=si == 0 or sec["letter"] != sections[si - 1]["letter"])
            elif role == "melody":
                if theme is not None and k == next(i for i in order if tracks[i].role == "melody"):
                    ns = [Note(n.start, n.dur, n.pitch, n.vel) for n in theme if s0 - 1e-6 <= n.start < s0 + ln]
                else:
                    sp.setdefault("contour", b["mood_d"].get("contour", "arch"))
                    if b["mel_scale"] and "scale" not in sp:
                        sp["scale"] = b["mel_scale"]
                    mot = None
                    if motif:
                        tr_semi = (T.key_root(sec["key"]) - T.key_root(key)) % 12
                        tr_semi = tr_semi - 12 if tr_semi > 6 else tr_semi
                        mot = [Note(n.start, n.dur, n.pitch + tr_semi, n.vel) for n in motif]
                    sp.setdefault("velocity", int(92 * (0.8 + 0.2 * inten)))
                    ns = Gn.gen_melody(tl, s0, s0 + ln, ctx, sp, rng, motif=mot)
                mel_notes += ns
            elif role == "counter":
                ns = Gn.gen_counter(tl, s0, s0 + ln, ctx, sp, rng, mel_notes)
            elif role == "notes":
                txt = p.get("notes", "")
                if p.get("repeat"):
                    one = Gn.parse_notes(txt, int(p.get("velocity", 90)))
                    span = max((n.start + n.dur for n in one), default=bpb)
                    span = math.ceil(span / bpb - 1e-6) * bpb
                    ns, t0 = [], s0
                    while t0 < s0 + ln - 1e-6:
                        ns += [Note(n.start + t0, n.dur, n.pitch, n.vel) for n in one if n.start + t0 < s0 + ln]
                        t0 += span
                else:
                    ns = Gn.parse_notes(txt, int(p.get("velocity", 90)), offset=0.0) if si == 0 else []
            else:
                ns = []
            tr.notes += ns
        pos += ln
    song.tempo_map = tempo_map if len(tempo_map) > 1 else []

    # feel: swing + humanize
    dstyle = next((t.params.get("style") for t in tracks if t.drums), gd.get("drums", ""))
    dst = D.STYLES.get(dstyle or "", {})
    swing = float(spec.get("swing", gd.get("swing", dst.get("swing", 0.0))))
    unit = float(spec.get("swing_unit", 0.25 if dstyle in ("lofi", "boom_bap") else 0.5))
    chip = all(t.engine == "chip" or t.instrument in CHIP_WAVES or t.drums for t in tracks)
    hum = spec.get("humanize", 0.0 if chip else 1.0)
    hr = random.Random(seed + 99)
    for tr in tracks:
        T.apply_swing(tr.notes, swing, unit)
        if hum:
            T.humanize(tr.notes, hr, timing=0.006 * float(hum) * (0.6 if tr.drums else 1.0), velocity=int(4 * float(hum)))
    total = song.length_beats
    for tr in tracks:
        tr.notes = tidy([n for n in tr.notes if n.start < total - 1e-6])

    if spec.get("ending") == "cadence":
        song.loop = False
        last_key = sections[-1]["key"]
        r, ivs, lab = T.parse_roman("I" if 4 in T.MODES.get(b["chord_mode"], [4]) else "i", last_key, b["chord_mode"])
        song.bars += 1
        end = total
        for tr in tracks:
            if tr.drums:
                tr.notes += [Note(end, 1.0, D.GM_DRUM["crash"], 110), Note(end, 1.0, D.GM_DRUM["kick"], 110)]
            elif tr.notes:
                ref = sorted(n.pitch for n in tr.notes)[len(tr.notes) // 2]
                v = Gn.voice(r, ivs, None, ref, False, floor=24)
                for q in (v if tr.role in ("pad", "chords", "arp", "pulse", "power") else [min(v, key=lambda x: abs(x - ref))]):
                    tr.notes.append(Note(end, bpb * 0.95, q, 96))
        song.chords.append(T.Chord(end, bpb, r, ivs, lab))
    song.tracks = tracks
    return song


def tidy(notes: list[Note]) -> list[Note]:
    """Sort; drop duplicates; trim same-pitch overlaps (a note-on before the previous note-off on the
    same key would cut notes short in MIDI players)."""
    notes = sorted(notes, key=lambda n: (n.start, n.pitch))
    last: dict[int, Note] = {}
    out = []
    for n in notes:
        p = last.get(n.pitch)
        if p is not None:
            if abs(p.start - n.start) < 1e-3:
                p.vel = max(p.vel, n.vel)
                p.dur = max(p.dur, n.dur)
                continue
            if p.start + p.dur > n.start - 0.01:
                p.dur = max(0.02, n.start - p.start - 0.01)
        last[n.pitch] = n
        out.append(n)
    return out


def variant(src: Song, changes: dict) -> Song:
    """Same theme, new arrangement: the source melody is mapped into the new key/mode/meter and the
    new genre's (or given) tracks are generated around it with the same harmony and form."""
    spec = copy.deepcopy(src.spec) if src.spec else {"bars": src.bars, "key": src.key, "mode": src.mode}
    for k in ("tracks", "add_tracks", "instruments", "_theme", "drop_roles", "engine"):
        if k not in changes:
            spec.pop(k, None)
    if "genre" in changes:
        for k in ("meter", "tempo", "swing", "reverb", "master"):
            if k not in changes:
                spec.pop(k, None)
    if "mood" in changes and "mode" not in changes:
        spec.pop("mode", None)
    keep = changes.pop("keep_melody", True) if isinstance(changes, dict) else True
    spec.update({k: v for k, v in changes.items() if v is not None})
    for k, v in changes.items():
        if v is None:
            spec.pop(k, None)
    spec["title"] = changes.get("title") or f"{src.title} ({spec.get('genre') or spec.get('mood') or 'variant'})"
    if keep:
        mel = next((t for t in src.tracks if t.role == "melody" and t.notes), None)
        if mel is None:  # e.g. a loaded MIDI: the highest pitched part is the tune
            cands = [t for t in src.tracks if not t.drums and t.notes]
            mel = max(cands, key=lambda t: sum(n.pitch for n in t.notes) / len(t.notes)) if cands else None
        if mel:
            b = _basics(spec)
            oc = int(next((t.get("octave", 5) for t in _track_specs(spec, b) if t["role"] == "melody"), 5))
            kr = T.key_root(b["key"])
            center = 12 * (oc + 1) + (kr if kr <= 7 else kr - 12) + 4      # same register rule as gen_melody
            src_mode = src.mode if src.mode in T.MODES else ("minor" if 3 in T.SCALES.get(src.mode, [4]) else "major")
            theme = _theme_map(mel.notes, src.key, src_mode, src.bpb, b["key"], b["chord_mode"], b["bpb"], center)
            if theme and any(k in changes for k in ("bars", "form", "sections")):
                # new structure: start the tune on bar 1 (drop the source's melody-less intro)
                sh = math.floor(theme[0].start / b["bpb"] + 1e-6) * b["bpb"]
                theme = [Note(n.start - sh, n.dur, n.pitch, n.vel) for n in theme]
            spec["_theme"] = theme
    song = compose(spec)
    song.spec.pop("_theme", None)
    song.spec["_theme_from"] = src.title
    if keep and spec.get("_theme") is not None:
        song.spec["_theme"] = spec["_theme"]
    return song


def slice_song(song: Song, start_beat: float, bars: int, title: str) -> Song:
    """One section as its own song (for per-section loops / horizontal re-sequencing)."""
    end = start_beat + bars * song.bpb
    tm = [(max(0.0, b - start_beat), bpm) for b, bpm in (song.tempo_map or [(0.0, song.tempo)]) if b < end - 1e-6]
    # tempo in effect at the start
    cur = song.tempo
    for b, bpm in (song.tempo_map or []):
        if b <= start_beat + 1e-6:
            cur = bpm
    tm = [(0.0, cur)] + [(b, bpm) for b, bpm in tm if b > 1e-6]
    s = Song(title, cur, song.key, song.mode, song.meter, bars, loop=True, genre=song.genre, reverb=song.reverb, master=dict(song.master))
    s.tempo_map = tm if len(tm) > 1 else []
    s.chords = [T.Chord(c.start - start_beat, c.dur, c.root, c.ivs, c.label) for c in song.chords if start_beat - 1e-6 <= c.start < end]
    for tr in song.tracks:
        t2 = copy.copy(tr)
        t2.notes = [Note(n.start - start_beat, n.dur, n.pitch, n.vel) for n in tr.notes if start_beat - 1e-3 <= n.start < end - 1e-6]
        s.tracks.append(t2)
    return s


# ============================================================ stingers

STINGERS = {  # semitones from the tonic (octave 5); last chord is held by the backing; mood for colour
    "victory": ("{0}:.5 {4}:.5 {7}:.5 {12}:1.5 {7}+{12}+{16}:2.5", "maj", "big"),
    "level_up": ("{0}:.25 {4}:.25 {7}:.25 {12}:.25 {16}:.25 {19}:.25 {12}+{16}+{24}:1.5", "maj", "hit"),
    "quest_complete": ("{7}:.5 {9}:.5 {11}:.5 {12}:1 r:.25 {7}+{12}+{16}:2.5", "maj", "big"),
    "achievement": ("{12}:.25 {19}:.25 {24}:.5 {16}+{19}+{24}:1.5", "maj", "hit"),
    "item": ("{12}:.25 {16}:.25 {19}:.25 {24}:1", "maj", None),
    "chest_open": ("{0}:.17 {4}:.17 {7}:.17 {11}:.17 {14}:.17 {16}:.17 {19}:.17 {11}+{16}+{23}:1.5", "maj7", None),
    "unlock": ("{7}:.25 {12}+{19}:1", "maj", None),
    "shop": ("{4}:.25 {7}:.25 {12}:.25 {16}:.75", "maj", None),
    "heal": ("{0}+{7}:.33 {4}+{11}:.33 {7}+{14}:.33 {12}+{16}+{19}:2", "maj7", None),
    "save": ("{0}:.5 {7}:.5 {4}+{12}:2", "maj", None),
    "puzzle_solved": ("{0}:.25 {4}:.25 {7}:.25 {11}:.25 {12}:.25 {14}:.25 {16}:1.5", "maj7", None),
    "discovery": ("{0}+{7}:1 {2}+{9}:1 {4}+{11}+{14}:2.5", "lyd", "swell"),
    "secret": ("{0}:.25 {4}:.25 {8}:.25 {12}:.25 {14}:.25 {18}:.25 {12}+{16}+{20}+{24}:1.5", "aug", None),
    "new_area": ("{0}+{7}:2 {5}+{9}+{12}:2 {7}+{11}+{14}:3", "maj", "swell"),
    "game_start": ("{0}:.5 {0}:.25 {0}:.25 {7}:.5 {5}:.5 {7}+{12}+{16}:2", "maj", "hit"),
    "transition": ("{0}+{7}+{12}:2 {5}+{9}+{14}:2", "sus", "swell"),
    "defeat": ("{7}:1 {6}:1 {5}:1 {0}+{3}+{7}:3", "min", "low"),
    "death": ("{12}:.75 {11}:.75 {10}:.75 {9}:.75 {3}+{8}:3", "min", "low"),
    "fail": ("{4}:.5 {3}:1.5", "min", None),
    "power_down": ("{12}:.25 {7}:.25 {3}:.25 {0}:.25 {-5}:1.25", "min", None),
    "danger": ("{0}+{1}:.5 r:.25 {0}+{1}:.5 r:.25 {0}+{6}:2", "dim", "low"),
    "warning": ("{0}+{6}:.5 r:.5 {0}+{6}:.5 r:.5 {0}+{6}:.5", "dim", None),
    "boss_appear": ("{-12}+{-11}:1 r:.5 {-12}+{-6}:1 {-12}+{-11}+{-6}+{0}:3", "dim", "big"),
    "countdown": ("{0}:.25 r:.75 {0}:.25 r:.75 {0}:.25 r:.75 {12}:1.5", "maj", None),
}
STINGER_STYLES = {
    "orchestral": dict(lead="trumpet", lead_minor="french_horn", pad="strings", bass="contrabass", kit="orchestra", engine="auto"),
    "chip": dict(lead="square", lead_minor="square", pad="pulse25", bass="triangle", kit="chip", engine="chip"),
    "synth": dict(lead="saw_lead", lead_minor="saw_lead", pad="supersaw", bass="sub_bass", kit="909", engine="auto"),
    "piano": dict(lead="piano", lead_minor="piano", pad=None, bass="piano", kit=None, engine="auto"),
    "magic": dict(lead="celesta", lead_minor="celesta", pad="choir", bass="harp", kit=None, engine="auto"),
    "rock": dict(lead="distortion_guitar", lead_minor="distortion_guitar", pad="overdrive_guitar", bass="picked_bass", kit="power", engine="auto"),
    "lofi": dict(lead="electric_piano", lead_minor="electric_piano", pad="warm_pad", bass="fingered_bass", kit="lofi", engine="auto"),
}


def stinger(kind: str, key: str = "C", tempo: float = 120, instrument: str = "", style: str = "orchestral", seed: int = 1) -> Song:
    """Short musical cue for a game event, in the theme's key: lead line + held final chord + bass +
    percussion accent, orchestrated by style."""
    if kind not in STINGERS:
        raise ValueError(f"stinger: {sorted(STINGERS)}")
    if style not in STINGER_STYLES:
        raise ValueError(f"stinger style: {sorted(STINGER_STYLES)}")
    shape, colour, perc = STINGERS[kind]
    st = STINGER_STYLES[style]
    minor = colour in ("min", "dim")
    lead = instrument or (st["lead_minor"] if minor else st["lead"])
    instrument_ok(lead)
    r = 12 * 5 + T.key_root(key)
    txt = re.sub(r"\{(-?\d+)\}", lambda m: T.midi_to_name(r + int(m.group(1)), key), shape)
    notes = Gn.parse_notes(txt, 100)
    beats = max(n.start + n.dur for n in notes)
    last_t = max(n.start for n in notes)
    final = [n.pitch for n in notes if abs(n.start - last_t) < 1e-6]
    song = Song(f"stinger_{kind}", tempo, key, "minor" if minor else "major", "4/4", max(1, math.ceil(beats / 4 - 1e-6)), loop=False,
                reverb="hall" if style in ("orchestral", "magic") else "room" if style in ("piano", "rock", "lofi") else "plate")
    eng = st["engine"]
    song.tracks.append(Track("Lead", "notes", lead, notes, volume=0.9, reverb=0.4, engine=eng))
    if st["pad"]:
        pad = [Note(last_t, max(1.0, beats - last_t) + 0.5, q - 12, 80) for q in final]
        song.tracks.append(Track("Pad", "pad", st["pad"], pad, volume=0.55, reverb=0.5, engine=eng))
    if st["bass"] and final:
        song.tracks.append(Track("Bass", "bass", st["bass"], [Note(last_t, max(1.0, beats - last_t), min(final) - 24, 92)], volume=0.6, reverb=0.1, engine=eng))
    if st["kit"] and perc:
        dn = []
        if perc in ("big", "hit"):
            dn += [Note(last_t, 1.0, D.GM_DRUM["crash"], 112), Note(last_t, 0.5, D.GM_DRUM["kick"], 110)]
        if perc == "big" and style == "orchestral":
            dn += [Note(max(0, last_t - 1) + k * 0.0625, 0.06, D.GM_DRUM["tom_floor"], 60 + k * 4) for k in range(16)]
        if perc == "swell":
            dn += [Note(0, 0.5, D.GM_DRUM["triangle"] if style != "chip" else D.GM_DRUM["hat"], 80)]
        if perc == "low":
            dn += [Note(last_t, 1.0, D.GM_DRUM["tom_floor"], 105), Note(last_t, 1.0, D.GM_DRUM["kick"], 100)]
        if dn:
            song.tracks.append(Track("Perc", "drums", "kit", dn, volume=0.7, reverb=0.3, drums=True, kit=st["kit"], engine=eng if eng == "chip" else "auto"))
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


def _meta_text(t: int, text: str) -> bytes:
    b = text.encode()
    return bytes([0xFF, t]) + _vlq(len(b)) + b


def write_midi(song: Song, path: Path, repeat: int = 1, tracks: list[str] | None = None, volume_cc: int | None = None,
               pad_beats: float = 0.0) -> Path:
    """Format-1 SMF: tempo map, meter, section markers, one channel per track (drums on channel 10 with
    the GM kit as program). repeat>1 writes the body several times; pad_beats extends the end so
    renderers keep the release tails."""
    sel = [t for t in song.tracks if not tracks or t.name in tracks]
    body = song.length_beats
    num, den = song.meter.split("/")
    ev0 = []
    ev0.append((0, _meta_text(0x03, song.title)))
    ev0.append((0, b"\xff\x58\x04" + bytes([int(num), int(math.log2(int(den))), 36 if T.is_compound(song.meter) else 24, 8])))
    for r in range(repeat):
        for b_, bpm in (song.tempo_map or [(0.0, song.tempo)]):
            ev0.append((int(round((b_ + r * body) * TPQ)), b"\xff\x51\x03" + int(60_000_000 / bpm).to_bytes(3, "big")))
        if r == 0:
            for s0, nm, k, _ in song.sections:
                ev0.append((int(round(s0 * TPQ)), _meta_text(0x06, f"{nm} ({k})")))
    ev0.sort(key=lambda e: e[0])
    meta = bytearray()
    last = 0
    for tick, msg in ev0:
        meta += _vlq(tick - last) + msg
        last = tick
    meta += _vlq(max(0, int((body * repeat + pad_beats) * TPQ) - last)) + b"\xff\x2f\x00"
    chunks = [bytes(meta)]
    ch_next = 0
    for tr in sel:
        if tr.drums:
            ch = 9
        else:
            ch = ch_next % 16
            if ch == 9:
                ch_next += 1
                ch = ch_next % 16
            ch_next += 1
        ev = []
        for r in range(repeat):
            for n in tr.notes:
                s = int(round((n.start + r * body) * TPQ))
                e = int(round((n.start + n.dur + r * body) * TPQ))
                ev.append((s, 1, bytes([0x90 | ch, n.pitch & 0x7F, max(1, min(127, n.vel))])))
                ev.append((max(s + 1, e), 0, bytes([0x80 | ch, n.pitch & 0x7F, 0])))
        ev.sort(key=lambda x: (x[0], x[1]))
        data = bytearray()
        data += _vlq(0) + _meta_text(0x03, tr.name)
        data += _vlq(0) + bytes([0xC0 | ch, program_of(tr) & 0x7F])
        cc7 = volume_cc if volume_cc is not None else int(127 * math.sqrt(max(0.0, min(1.0, tr.volume))))  # sqrt: GM CC7 is a 40·log curve
        data += _vlq(0) + bytes([0xB0 | ch, 7, cc7])
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
    """SMF reader -> Song (notes, tempo map, meter, programs, track names, drum channel)."""
    b = path.read_bytes()
    if b[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    _, fmt, ntr, div = struct.unpack(">IHHH", b[4:14])
    if div & 0x8000:
        raise ValueError("SMPTE-timed MIDI is not supported")
    pos = 14
    tempos: list[tuple[float, float]] = []
    meter = "4/4"
    tracks = []

    def vlq(d, i):
        v = 0
        while True:
            c = d[i]
            i += 1
            v = (v << 7) | (c & 0x7F)
            if not c & 0x80:
                return v, i

    for ti in range(ntr):
        if b[pos:pos + 4] != b"MTrk":
            raise ValueError("bad track chunk")
        ln = struct.unpack(">I", b[pos + 4:pos + 8])[0]
        d = b[pos + 8:pos + 8 + ln]
        pos += 8 + ln
        i, tick, status, name = 0, 0, 0, f"Track{ti}"
        progs: dict[int, int] = {}
        on: dict[tuple[int, int], tuple[int, int]] = {}
        notes: dict[int, list[Note]] = {}
        while i < len(d):
            dt, i = vlq(d, i)
            tick += dt
            c = d[i]
            if c & 0x80:
                status = c
                i += 1
            if status == 0xFF:
                typ = d[i]
                i += 1
                l2, i = vlq(d, i)
                payload = d[i:i + l2]
                i += l2
                if typ == 0x51:
                    tempos.append((tick / div, 60_000_000 / int.from_bytes(payload, "big")))
                elif typ == 0x03:
                    name = payload.decode(errors="replace") or name
                elif typ == 0x58 and len(payload) >= 2:
                    m = f"{payload[0]}/{2 ** payload[1]}"
                    meter = m if m in T.METERS else meter
                continue
            if status in (0xF0, 0xF7):
                l2, i = vlq(d, i)
                i += l2
                continue
            kind, ch = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                if kind == 0xC0:
                    progs[ch] = d[i]
                i += 1
                continue
            p1, p2 = d[i], d[i + 1]
            i += 2
            if kind == 0x90 and p2 > 0:
                on[(ch, p1)] = (tick, p2)
            elif kind in (0x80, 0x90) and (ch, p1) in on:
                st, vel = on.pop((ch, p1))
                notes.setdefault(ch, []).append(Note(st / div, max(1, tick - st) / div, p1, vel))
        for ch, ns in notes.items():
            drums = ch == 9
            nm = name if len(notes) == 1 else f"{name}_ch{ch + 1}"
            tracks.append(Track(nm, "drums" if drums else "notes", "kit" if drums else progs.get(ch, 0), ns, drums=drums,
                                kit=next((k for k, v in D.KITS.items() if v == progs.get(ch, 0)), "standard") if drums else "standard"))
    tempos.sort()
    tempo = tempos[0][1] if tempos else 120.0
    s = Song(path.stem, tempo, "C", "major", meter, 1, tracks, loop=False)
    s.tempo_map = [(0.0, tempo)] + [(bt, bpm) for bt, bpm in tempos[1:] if bt > 0] if len(tempos) > 1 else []
    end = max((n.start + n.dur for t in tracks for n in t.notes), default=4)
    s.bars = max(1, math.ceil(end / s.bpb - 1e-6))
    return s


# ============================================================ preview

PALETTE = [(232, 106, 92), (92, 170, 232), (246, 196, 82), (130, 206, 120), (190, 132, 230), (90, 220, 210), (240, 150, 200), (200, 200, 200), (255, 140, 60), (150, 180, 255)]


def preview(song: Song, max_w: int = 1600) -> Image.Image:
    """Piano roll: tracks coloured, bar grid by meter, chord and section labels (with key), tempo
    changes, drum lane at the bottom, legend with instrument and layer."""
    pitched = [n.pitch for t in song.tracks if not t.drums for n in t.notes]
    lo, hi = (min(pitched) - 2, max(pitched) + 2) if pitched else (48, 84)
    beats = max(song.length_beats, max((n.start + n.dur for t in song.tracks for n in t.notes), default=4))
    px_b = max(4, min(40, int((max_w - 120) / beats)))
    row = max(3, min(9, int(560 / max(1, hi - lo + 1))))
    has_drums = any(t.drums for t in song.tracks)
    drum_rows = sorted({n.pitch for t in song.tracks if t.drums for n in t.notes})
    W = 110 + int(beats * px_b) + 10
    H = 52 + (hi - lo + 1) * row + (len(drum_rows) * 6 + 16 if has_drums else 0) + 64
    img = Image.new("RGB", (W, H), (24, 26, 32))
    dr = ImageDraw.Draw(img)
    top = 52
    for p in range(lo, hi + 1):
        y = top + (hi - p) * row
        if p % 12 in (1, 3, 6, 8, 10):
            dr.rectangle([110, y, W - 10, y + row - 1], fill=(30, 32, 40))
        if p % 12 == 0:
            dr.text((70, y - 4), T.midi_to_name(p, song.key, song.mode if song.mode in T.MODES else "major"), fill=(150, 150, 160))
            dr.line([110, y + row - 1, W - 10, y + row - 1], fill=(48, 50, 60))
    bpb = song.bpb
    for k in range(int(beats) + 1):
        x = 110 + k * px_b
        dr.line([x, top, x, H - 64], fill=(36, 38, 46))
    nb = int(math.ceil(beats / bpb - 1e-6))
    for bi in range(nb + 1):
        x = 110 + bi * bpb * px_b
        dr.line([x, top, x, H - 64], fill=(70, 72, 88))
        if bi < nb and (px_b * bpb >= 14 or bi % 4 == 0):
            dr.text((x + 2, H - 60), str(bi + 1), fill=(130, 130, 140))
    lastx = -99
    for c in song.chords:
        x = 110 + c.start * px_b + 2
        if x - lastx > 7 * len(c.label) * 0.8:
            dr.text((x, 34), c.label, fill=(240, 220, 160))
            lastx = x
    for s0, nm, k, bars in song.sections:
        x = 110 + s0 * px_b
        dr.line([x, 4, x, H - 64], fill=(110, 170, 220))
        dr.text((x + 3, 4), f"[{nm}] {k}", fill=(160, 220, 255))
    for b_, bpm in song.tempo_map[1:]:
        dr.text((110 + b_ * px_b + 3, 18), f"♩={bpm / T.felt(song.meter):.0f}", fill=(255, 170, 120))
    yd = top + (hi - lo + 1) * row + 10
    for k, t in enumerate(song.tracks):
        col = PALETTE[k % len(PALETTE)]
        for n in t.notes:
            x0 = 110 + n.start * px_b
            x1 = max(x0 + 2, 110 + (n.start + n.dur) * px_b - 1)
            if t.drums:
                y = yd + drum_rows.index(n.pitch) * 6
                dr.rectangle([x0, y, x0 + 2, y + 4], fill=col)
            else:
                y = top + (hi - n.pitch) * row
                shade = 0.5 + 0.5 * n.vel / 127
                dr.rectangle([x0, y, x1, y + row - 2], fill=tuple(int(c * shade) for c in col))
    lx, ly = 110, H - 44
    for k, t in enumerate(song.tracks):
        col = PALETTE[k % len(PALETTE)]
        label = f"{t.name}:{t.instrument if not t.drums else t.kit} L{t.layer}"
        w = 22 + 6 * len(label)
        if lx + w > W - 10:
            lx, ly = 110, ly + 13
        dr.rectangle([lx, ly + 2, lx + 9, ly + 11], fill=col)
        dr.text((lx + 13, ly), label, fill=(220, 220, 225))
        lx += w
    dr.text((8, H - 16), f"{song.title}  [{song.genre}]  {song.key} {song.mode}  {song.meter}  {song.tempo / T.felt(song.meter):.0f} BPM  {song.bars} bars  {song.seconds:.1f}s{'  loop' if song.loop else ''}", fill=(200, 200, 205))
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)), Image.LANCZOS)
    return img
