"""gameforge-music — MCP server: game music and SFX as code. No DAW, no GUI.

Compose from theory in ~40 genres x ~30 moods (meters 4/4 3/4 6/8 12/8 2/4 7/8 5/4..., swing, world
scales), song forms with sections (intro/A/B/bridge/outro, key changes, tempo changes, intensity),
theme variants (same melody re-orchestrated in another genre/key/mode/meter), MIDI, hybrid rendering
(FluidSynth + SoundFont, built-in synthesizer with synth patches and 808/909/lofi/taiko kits, chiptune
engine), seamless loops, adaptive stems by layer, per-section loops, loudness, OGG/MP3/WAV, analysis
images, stingers and SFX.  Run: bash scripts/run-mcp.sh music
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

import artlib  # noqa: E402
import audio as A  # noqa: E402
import drums as D  # noqa: E402
import genres as GE  # noqa: E402
import musiccore as M  # noqa: E402
import synth as S  # noqa: E402
import theory as T  # noqa: E402
from mcpcompat import Image, Server, tool  # noqa: E402

INSTRUCTIONS = """Game music & SFX as code, any genre. You cannot hear audio — judge with the piano-roll
preview (register separation, motif repetition, phrase endings, density, sections) and mus_analyze
numbers (LUFS, peak, loop seam, spectrum balance); ask the user to listen before calling music final.
Workflow: mus_status (deps) -> mus_theory (scene/genre/mood catalogue) -> mus_compose (genre + mood +
form; look at the preview, fix and recompose) -> mus_variant (same theme for other scenes) ->
mus_render (loop for music, stems=layers for adaptive, stems=sections for horizontal re-sequencing,
-16 LUFS mobile / -18 pc) -> mus_stinger / mus_sfx -> credits line into .gameforge/credits.md."""

mcp = Server("gameforge-music", instructions=INSTRUCTIONS)
SONGS: dict[str, M.Song] = {}


def _png(img) -> Image:
    return Image(data=A.png(img), format="png")


def _j(d) -> str:
    return json.dumps(d, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))


def _song(name: str) -> M.Song:
    if name not in SONGS:
        raise ValueError(f"no song '{name}'. Songs: {list(SONGS)} — create with mus_compose / mus_variant / mus_stinger / mus_load_midi")
    return SONGS[name]


def _credits(used: str) -> str | None:
    if "soundfont" not in used:
        return None
    sf = A.default_soundfont() or ""
    if "MuseScore_General" in sf:
        return ("MuseScore_General SoundFont (MIT): FluidR3 © 2000-2002, 2008 Frank Wen; FluidR3Mono © 2014-17 Michael Cowgill; "
                "MuseScore_General adaptation © 2018-19 S. Christian Collins; Temple Blocks © 2002 Ethan Winer; Drumline Cymbals © 2016 Michael Schorsch")
    return f"SoundFont: {Path(sf).name} — record its license in credits"


@tool(mcp)
def mus_status() -> str:
    """Which renderers are available: built-in synth + chip engine (always), FluidSynth + SoundFont
    (orchestral/acoustic GM instruments), ffmpeg (LUFS, OGG/MP3). Missing pieces -> tell the user
    explicitly and run gameforge:doctor (task music). Without a SoundFont, GM instruments fall back to
    built-in synth patches (works, but orchestral/acoustic genres sound synthetic)."""
    st = A.status()
    st["missing"] = [k for k, v in (("fluidsynth (brew install fluid-synth)", st["fluidsynth"]), ("SoundFont (~/.cache/gameforge/soundfonts)", st["soundfont"]),
                                    ("ffmpeg (brew install ffmpeg)", st["ffmpeg"])) if not v]
    if st.get("ogg_encoder") == "vorbis(native)":
        st["note"] = "OGG uses ffmpeg's native Vorbis encoder (OK). For best OGG quality: brew install vorbis-tools (oggenc)."
    return _j(st)


@tool(mcp)
def mus_theory(scene: str = "", genre: str = "", mood: str = "", key: str = "C", mode: str = "", progression: str = "",
               catalogue: bool = False) -> str:
    """Music theory & style helper.
    scene (title_menu, town_hub, overworld, forest_nature, dungeon_cave, battle, boss, stealth, horror,
    racing_sport, puzzle_casual, cyberpunk_scifi, shop, tavern_inn, sad_scene, victory_credits,
    comedy_minigame, western, noir_detective, pirate_sea, desert_exotic) -> suggested (genre, mood) pairs.
    genre -> its meter, tempo range, drums, instruments and arrangement. mood -> mode, tempo, A/B progressions.
    key+mode -> scale notes. progression (roman numerals: 'i bVI bIII bVII', 'I V vi IV', 'V7', 'ii°', 'IV:2')
    -> chord names. catalogue=true -> every genre (with description), mood, scene, meter, mode/scale, drum
    style, track role, synth patch and GM instrument name."""
    out: dict = {}
    if scene:
        if scene not in GE.SCENES:
            raise ValueError(f"scene: {sorted(GE.SCENES)}")
        out["scene"] = [{"genre": g, "mood": m, "genre_desc": GE.GENRES[g]["desc"]} for g, m in GE.SCENES[scene]]
    if genre:
        if genre not in GE.GENRES:
            raise ValueError(f"genre: {sorted(GE.GENRES)}")
        g = GE.GENRES[genre]
        out["genre"] = {k: v for k, v in g.items()}
    if mood:
        if mood not in GE.MOODS:
            raise ValueError(f"mood: {sorted(GE.MOODS)}")
        out["mood"] = GE.MOODS[mood]
        mode = mode or GE.MOODS[mood]["mode"]
    mode = mode or "major"
    out["scale"] = [T.names_for(key, mode if mode in T.MODES else "major")[p] for p in T.scale_pcs(key, mode)]
    if progression:
        cm = mode if mode in T.MODES else ("minor" if 3 in T.SCALES[mode] else "major")
        out["chords"] = [T.parse_roman(tok.partition(":")[0], key, cm)[2] for tok in progression.split()]
    if catalogue or not (scene or genre or mood or progression):
        out.update(GE.catalogue())
        out["meters"] = sorted(T.METERS)
        out["modes"] = sorted(T.MODES)
        out["melody_scales"] = sorted(T.SCALES)
        out["drum_styles"] = sorted(D.STYLES)
        out["drum_kits"] = {"soundfont (GM)": sorted(D.KITS), "built-in": sorted(S.SYNTH_KITS)}
        out["roles"] = list(M.ROLES)
        out["synth_patches"] = sorted(S.PATCHES)
        out["chip_waves"] = sorted(S.CHIP_WAVES)
        out["gm_instruments"] = sorted(M.GM)
        out["forms"] = "letters A/B/C (+ = up a whole step, C/bridge = key of IV), intro, break, build, outro — e.g. 'intro A A B A+ outro'"
    return _j(out)


@tool(mcp)
def mus_compose(spec: dict, name: str = "", midi_out: str = "") -> list:
    """Compose a piece from a spec; returns the piano-roll preview + summary. Spec keys (all optional):
    genre (see mus_theory catalogue: orchestral, epic_orchestral, chiptune, synthwave, lofi, jazz, metal,
    fantasy_folk, waltz, ambient, dark_ambient, edm, techno, dnb, bossa, reggae, circus, asian, ...),
    mood (heroic, calm, battle, boss, sad, horror, mystery, cozy, epic, playful, tension, ...),
    title, key ('D','F#','Bb'), mode (major, minor, dorian, phrygian, harmonic_minor, phrygian_dominant,
    or a melody scale: pentatonic_minor, blues, hirajoshi, in_sen, whole_tone...), tempo (felt beats:
    dotted quarter in 6/8 & 12/8), meter (4/4 3/4 2/4 6/8 9/8 12/8 5/4 7/8 5/8 7/4), seed,
    bars (default 16 = A 8 + B 8) or form ('intro A A B A+ outro') or sections [{name, bars, progression,
    key | transpose, tempo, layers [1,2], mute [track names/roles], intensity 0-1, drums style}],
    progression / progression_b / progression_c (roman, 'I:2' = 2 bars), chord_bars, swing 0-1,
    humanize 0-1, motif ('E5:1 G5:.5 A5:.5 B5:2' — leitmotif used by the melody), loop (default true),
    ending ('cadence' for a stopping piece), reverb (room|plate|hall|cathedral|space|none),
    master {lofi 0-1, width, drive}, engine (auto|sf|synth|chip for all tracks),
    instruments {role or track name: instrument} to swap the genre's instruments,
    drop_roles [roles/track names], add_tracks [...], or tracks [...] to replace the genre arrangement.
    Track: {name, role, instrument, layer 1-3, volume, pan, reverb, octave, velocity, engine, duck 0-1
    (sidechain pump), fx {delay beats, chorus, drive, lowpass, highpass, bitcrush}, + role options}.
    Roles: pad/chords/pulse (rhythm sustain|beats|halves|pulse8|pulse16|offbeat|reggae|stabs|charleston|
    bossa|funk16|waltz|strum|compound, color triad|7th|9th) · bass (style root|root_fifth|octave|octave16|
    pulse8|pulse16|syncopated|walking|pedal|funk|reggae|bossa|waltz|oompah|boom|rolling|gallop|chip|compound)
    · arp (pattern up|down|updown|random|alberti|pinky|broken|cycle, rate, span) · ostinato (figure
    '1 5 8 5', rate) · power (style chug8|chug16|gallop|stops|sustain) · drone · texture (density) ·
    fanfare (every) · drums (style, kit, fill_every, gated) · melody (contour arch|rise|fall|wave,
    density, rhythm_style lyrical|bouncy|busy|sparse, ornament 0-1, scale) · counter (style
    contrary|thirds|sustain) · notes ('C4:1 E4:.5 r:.5 C4+E4+G4:2 D5:1@110', repeat).
    Instruments: GM names (strings, flute, harp, french_horn, piano...), built-in synth patches
    (supersaw, saw_lead, pluck, synth_pad, acid_bass, 808_bass, fm_bell, ...), chip waves (square,
    pulse25, pulse12, triangle, saw, noise) or a GM program number."""
    song = M.compose(spec)
    key = name or song.title
    SONGS[key] = song
    info = song.summary()
    if midi_out:
        info["midi"] = str(M.write_midi(song, artlib.ensure_parent(artlib.resolve_path(midi_out))))
    info["name"] = key
    return [_png(M.preview(song)), _j(info)]


@tool(mcp)
def mus_variant(name: str, changes: dict, new_name: str = "", keep_melody: bool = True) -> list:
    """Same theme, new arrangement — the leitmotif approach (menu theme -> battle version -> sad version).
    Takes a composed song and `changes` (genre, mood, key, mode, tempo, meter, seed, instruments, form...):
    the melody is mapped by scale degree into the new key/mode and proportionally into the new meter
    (e.g. a 4/4 theme as a 3/4 waltz), harmony and form are kept unless changed, the new genre's
    arrangement is generated around it. keep_melody=false re-generates the melody too."""
    src = _song(name)
    song = M.variant(src, {**changes, "keep_melody": keep_melody})
    key = new_name or song.title
    SONGS[key] = song
    info = song.summary()
    info["name"] = key
    info["from"] = name
    return [_png(M.preview(song)), _j(info)]


@tool(mcp)
def mus_edit(name: str, op: str, track: str = "", value: str = "") -> list:
    """Edit a song without recomposing. op: tempo (value felt BPM) · transpose (value semitones, all
    pitched tracks or `track`) · instrument (track, value) · volume / pan / reverb / layer / duck (track,
    value) · engine (track or all, auto|sf|synth|chip) · kit (drum track, value) · remove (track) ·
    loop (true|false) · reverb_space (room|plate|hall|cathedral|space|none) · lofi (0-1) · width."""
    s = _song(name)
    trs = [t for t in s.tracks if not track or t.name == track]
    if track and not trs:
        raise ValueError(f"no track '{track}'. Tracks: {[t.name for t in s.tracks]}")
    if op == "tempo":
        f = float(value) * T.felt(s.meter) / s.tempo
        s.tempo = float(value) * T.felt(s.meter)
        s.tempo_map = [(b, bpm * f) for b, bpm in s.tempo_map]
    elif op == "transpose":
        for t in trs:
            if not t.drums:
                for n in t.notes:
                    n.pitch += int(value)
        if not track:
            s.key = T.transpose_key(s.key, int(value))
    elif op == "instrument":
        v = int(value) if value.isdigit() else value
        M.instrument_ok(v)
        for t in trs:
            t.instrument = v
    elif op in ("volume", "pan", "reverb", "duck"):
        for t in trs:
            setattr(t, op, float(value))
    elif op == "layer":
        for t in trs:
            t.layer = int(value)
    elif op == "engine":
        if value not in ("auto", "sf", "synth", "chip"):
            raise ValueError("engine: auto | sf | synth | chip")
        for t in trs:
            t.engine = value
    elif op == "kit":
        if value not in D.KITS and value not in S.SYNTH_KITS:
            raise ValueError(f"kit: {sorted(D.KITS) + sorted(S.SYNTH_KITS)}")
        for t in trs:
            if t.drums:
                t.kit = value
    elif op == "remove":
        s.tracks = [t for t in s.tracks if t.name != track]
    elif op == "loop":
        s.loop = value.lower() in ("1", "true", "yes")
    elif op == "reverb_space":
        if value not in S.SPACES:
            raise ValueError(f"reverb: {sorted(S.SPACES)}")
        s.reverb = value
    elif op in ("lofi", "width", "drive"):
        s.master[op] = float(value)
    else:
        raise ValueError("op: tempo | transpose | instrument | volume | pan | reverb | duck | layer | engine | kit | remove | loop | reverb_space | lofi | width | drive")
    return [_png(M.preview(s)), _j(s.summary())]


def _render_set(s: M.Song, base: Path, synth: str, fmt: str, target_lufs: float, stems: str, soundfont: str | None, mix: str) -> dict:
    info: dict = {}
    x, used = A.render(s, synth, A.SR, None, soundfont, mix=mix, info=info)
    y, norm = A.normalize(x, A.SR, target_lufs)
    gain = 10 ** (norm.get("gain_db", 0) / 20)
    files = A.export(y, A.SR, base, fmt)
    stem_files = []
    if stems in ("layers", "tracks"):
        groups = ({f"layer{L}": [t.name for t in s.tracks if t.layer == L] for L in sorted({t.layer for t in s.tracks})}
                  if stems == "layers" else {t.name: [t.name] for t in s.tracks if t.notes})
        for gname, names in groups.items():
            xs, _ = A.render(s, synth, A.SR, names, soundfont, mix=mix, gains=info["gains"])
            stem_files += A.export(np.clip(xs * gain, -1, 1), A.SR, base.with_name(f"{base.name}_{gname}"), fmt)
    return {"x": y, "used": used, "files": files, "stems": stem_files, "normalize": norm, "gain": gain, "gains": info["gains"]}


@tool(mcp)
def mus_render(name: str, out: str, synth: str = "auto", fmt: str = "ogg", target_lufs: float = -16.0,
               stems: str = "none", soundfont: str = "", midi: bool = True, mix: str = "auto") -> list:
    """Render a song to audio and analyse it. synth: auto (per track: SoundFont for GM instruments if
    installed, built-in synth for synth patches/kits, chip engine for chip waves) | soundfont | synth
    (all built-in, no SoundFont needed) | chip. fmt: ogg | wav | mp3 | both. Loops (song.loop) are
    seamless (two passes, the 2nd kept, so reverb tails wrap into the start). target_lufs: -16 mobile,
    -18 pc. stems: none | layers (one file per intensity layer, same length and gain as the master —
    they sum to the master in the engine) | tracks | sections (each section as its own seamless loop
    for horizontal re-sequencing: <out>_<section>.<fmt>). mix: auto (every part brought to its role's
    loudness — balanced in any genre; track volume = trim around 0.8) | manual (volume = plain gain).
    Writes <out>.<fmt> (+ stems, + .mid)."""
    s = _song(name)
    base = artlib.ensure_parent(artlib.resolve_path(out)).with_suffix("")
    sf = soundfont or None
    r = _render_set(s, base, synth, fmt, target_lufs, stems if stems in ("layers", "tracks") else "none", sf, mix)
    files, stem_files = r["files"], r["stems"]
    if stems == "sections":
        if len(s.sections) < 2:
            raise ValueError("stems='sections' needs a song with 2+ sections (form/sections in the spec)")
        seen = {}
        for s0, nm, k, bars in s.sections:
            seen[nm] = seen.get(nm, 0) + 1
            label = nm.replace("+", "_lift") + (f"_{seen[nm]}" if seen[nm] > 1 else "")
            sub = M.slice_song(s, s0, bars, f"{s.title}_{label}")
            xs, _ = A.render(sub, synth, A.SR, None, sf, mix=mix, gains=r["gains"])
            stem_files += A.export(np.clip(xs * r["gain"], -1, 1), A.SR, base.with_name(f"{base.name}_{label}"), fmt)
    elif stems not in ("none", "layers", "tracks"):
        raise ValueError("stems: none | layers | tracks | sections")
    if midi:
        files.append(str(M.write_midi(s, base.with_suffix(".mid"))))
    info, img = A.analyze(Path(files[0]), loop=s.loop)
    res = {"synth": r["used"], "files": files, "stems": stem_files, "normalize": r["normalize"],
           "mix_gains_db": {k: round(20 * np.log10(max(v, 1e-9)), 1) for k, v in r["gains"].items()}, "analysis": info}
    cr = _credits(r["used"])
    if cr:
        res["credits_line"] = cr
    return [_png(img), _j(res)]


@tool(mcp)
def mus_stinger(kind: str, out: str, key: str = "C", tempo: float = 120, style: str = "orchestral", instrument: str = "",
                synth: str = "auto", fmt: str = "ogg", target_lufs: float = -14.0) -> list:
    """Short event cue in the theme's key: victory, level_up, quest_complete, achievement, item,
    chest_open, unlock, shop, heal, save, puzzle_solved, discovery, secret, new_area, game_start,
    transition, defeat, death, fail, power_down, danger, warning, boss_appear, countdown.
    style: orchestral | chip | synth | piano | magic | rock | lofi (match the soundtrack's genre);
    instrument overrides the lead. Lead line + held final chord + bass + percussion accent; rendered
    without loop with a natural tail; returns its analysis image."""
    s = M.stinger(kind, key, tempo, instrument, style)
    SONGS[s.title] = s
    x, used = A.render(s, synth)
    y, norm = A.normalize(x, A.SR, target_lufs)
    base = artlib.ensure_parent(artlib.resolve_path(out)).with_suffix("")
    files = A.export(y, A.SR, base, fmt)
    info, img = A.analyze(Path(files[0]), loop=False)
    res = {"synth": used, "files": files, "seconds": info["seconds"], "lufs": info.get("integrated_lufs"), "name": s.title}
    if _credits(used):
        res["credits_line"] = _credits(used)
    return [_png(img), _j(res)]


@tool(mcp)
def mus_sfx(kind: str, out_dir: str, variations: int = 4, seed: int = 1, name: str = "") -> list:
    """Procedural game SFX (sfxr-style), several variations per kind for runtime randomization:
    coin, pickup, jump, double_jump, bounce, land, footstep, laser, shoot, zap, explosion, thunder, hit,
    punch, hurt, death, powerup, heal, charge, magic, teleport, whoosh, splash, door, alarm, blip, select,
    ui_click, ui_hover, ui_confirm, ui_cancel, error. WAV 44.1 kHz mono, peak −1 dBFS. Returns a waveform sheet."""
    files, img = A.sfx_set(kind, max(1, min(12, variations)), seed, artlib.resolve_path(out_dir), name)
    return [_png(img), _j({"files": files, "note": "own procedural SFX — no third-party license"})]


@tool(mcp)
def mus_analyze(path: str, loop: bool = True) -> list:
    """Analyse any audio file (wav/ogg/mp3): duration, peak, integrated LUFS and LRA, true peak, silence at
    the edges, spectral balance, loop-seam click test; returns waveform + spectrogram."""
    info, img = A.analyze(artlib.resolve_path(path), loop=loop)
    return [_png(img), _j(info)]


@tool(mcp)
def mus_load_midi(path: str, name: str = "", loop: bool = False) -> list:
    """Load an existing MIDI file (from the user, a DAW export, etc.) to preview, edit, re-orchestrate
    (mus_variant) or render it."""
    s = M.read_midi(artlib.resolve_path(path))
    s.loop = loop
    SONGS[name or s.title] = s
    return [_png(M.preview(s)), _j({**s.summary(), "name": name or s.title})]


if __name__ == "__main__":
    mcp.run()
