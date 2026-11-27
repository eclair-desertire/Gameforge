"""gameforge-music — MCP server: game music and SFX as code. No DAW, no GUI.

Compose from theory (moods, modes, roman-numeral progressions, period-based melodies, drums by
style), write MIDI, render with the built-in chiptune synth or FluidSynth + SoundFont, seamless
loops, adaptive stems, loudness normalization, OGG/MP3/WAV, analysis images, stingers and SFX.
Run: bash scripts/run-mcp.sh music
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
import musiccore as M  # noqa: E402
from mcpcompat import Image, Server, tool  # noqa: E402

INSTRUCTIONS = """Game music & SFX as code. You cannot hear audio — judge with the piano-roll preview
(register separation, motif repetition, phrase endings, density) and with mus_analyze numbers
(LUFS, peak, loop seam, spectrum balance); ask the user to listen before calling music final.
Workflow: mus_status (deps) -> mus_theory (mood -> mode/tempo/progression) -> mus_compose (spec;
look at the preview, fix and recompose) -> mus_render (loop=true for music, stems for adaptive
layers, target -16 LUFS mobile / -18 pc) -> mus_analyze -> credits line into .gameforge/credits.md."""

mcp = Server("gameforge-music", instructions=INSTRUCTIONS)
SONGS: dict[str, M.Song] = {}


def _png(img) -> Image:
    return Image(data=A.png(img), format="png")


def _j(d) -> str:
    return json.dumps(d, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))


def _song(name: str) -> M.Song:
    if name not in SONGS:
        raise ValueError(f"no song '{name}'. Songs: {list(SONGS)} — create with mus_compose / mus_stinger / mus_load_midi")
    return SONGS[name]


def _credits(synth: str) -> str | None:
    if synth != "soundfont":
        return None
    sf = A.default_soundfont() or ""
    if "MuseScore_General" in sf:
        return ("MuseScore_General SoundFont (MIT): FluidR3 © 2000-2002, 2008 Frank Wen; FluidR3Mono © 2014-17 Michael Cowgill; "
                "MuseScore_General adaptation © 2018-19 S. Christian Collins; Temple Blocks © 2002 Ethan Winer; Drumline Cymbals © 2016 Michael Schorsch")
    return f"SoundFont: {Path(sf).name} — record its license in credits"


@tool(mcp)
def mus_status() -> str:
    """Which renderers are available: chip synth (always), FluidSynth + SoundFont, ffmpeg (LUFS, OGG/MP3).
    Missing pieces -> tell the user explicitly and run gameforge:doctor (task music)."""
    st = A.status()
    st["missing"] = [k for k, v in (("fluidsynth (brew install fluid-synth)", st["fluidsynth"]), ("SoundFont (~/.cache/gameforge/soundfonts)", st["soundfont"]),
                                    ("ffmpeg (brew install ffmpeg)", st["ffmpeg"])) if not v]
    if st.get("ogg_encoder") == "vorbis(native)":
        st["note"] = "OGG uses ffmpeg's native Vorbis encoder (OK). For best OGG quality: brew install vorbis-tools (oggenc)."
    return _j(st)


@tool(mcp)
def mus_theory(mood: str = "", key: str = "C", mode: str = "", progression: str = "") -> str:
    """Music theory helper. mood -> mode, tempo range, progressions, instruments, drum style.
    key+mode -> scale notes. progression (roman numerals, e.g. 'i bVI bIII bVII', 'I V vi IV', 'V7', 'ii°')
    -> chord names in that key. Moods: heroic, adventure, calm, town, mystery, dungeon, battle, boss, sad,
    horror, chiptune, victory, game_over, lofi, electronic."""
    out: dict = {}
    if mood:
        if mood not in M.MOODS:
            raise ValueError(f"mood: {sorted(M.MOODS)}")
        md = M.MOODS[mood]
        out["mood"] = {"mode": md[0], "tempo": md[1], "progressions": md[2], "instruments": md[3], "drums": md[4]}
        mode = mode or md[0]
    mode = mode or "major"
    out["scale"] = [M.NAMES[p] for p in M.scale_pcs(key, mode)]
    if progression:
        out["chords"] = [c[2] for c in M.progression(progression, key, mode)]
    out["moods"] = sorted(M.MOODS)
    out["modes"] = sorted(M.MODES) + sorted(M.EXTRA_SCALES)
    out["drum_styles"] = sorted(M.DRUM_STYLES)
    return _j(out)


@tool(mcp)
def mus_compose(spec: dict, name: str = "", midi_out: str = "") -> list:
    """Compose a piece from a spec and return its piano-roll preview. Spec keys:
    title, mood (preset), key ('D', 'F#', 'Bb'), mode, tempo, bars, beats_per_bar (4|3), seed,
    progression ('I vi IV V'), chord_bars (bars per chord, 1/0.5/2), loop (true for in-game music),
    ending ('cadence' for a stopping cue), sections [{name, bars, progression?}],
    tracks [{name, role, instrument, layer, volume 0-1, pan -1..1, reverb 0-1, octave, velocity, ...}].
    roles: pad (rhythm sustain|halves|stabs|pulse8|offbeat|waltz) · chords · bass (style root|root_fifth|octave|pulse8|syncopated|walking|pedal)
    · arp (pattern up|down|updown|random, rate beats, span octaves) · drums (style rock|pop|edm|breakbeat|lofi|trap|chip|march|light|sparse|none, fill_every)
    · melody (contour arch|rise|fall|wave, density 0-1, motif_bars, scale override e.g. pentatonic_major)
    · notes (explicit: 'C4:1 E4:.5 r:.5 C4+E4+G4:2 D5:1@110').
    instrument: GM name (piano, strings, flute, harp, french_horn, warm_pad, acoustic_bass, …) or chip wave
    (square, pulse25, pulse12, triangle, saw, sine, noise) or program 0-127. Layers = adaptive intensity
    (1 base … 3 full). Omit tracks to get a mood-based default arrangement."""
    song = M.compose(spec)
    key = name or song.title
    SONGS[key] = song
    info = song.summary()
    if midi_out:
        info["midi"] = str(M.write_midi(song, artlib.ensure_parent(artlib.resolve_path(midi_out))))
    info["name"] = key
    return [_png(M.preview(song)), _j(info)]


@tool(mcp)
def mus_edit(name: str, op: str, track: str = "", value: str = "") -> list:
    """Edit a composed song without recomposing. op: tempo (value BPM) · transpose (value semitones, all
    pitched tracks or `track`) · instrument (track, value) · volume (track, value 0-1) · pan (track, value)
    · reverb (track, value) · layer (track, value) · remove (track) · loop (value true|false)."""
    s = _song(name)
    trs = [t for t in s.tracks if not track or t.name == track]
    if track and not trs:
        raise ValueError(f"no track '{track}'. Tracks: {[t.name for t in s.tracks]}")
    if op == "tempo":
        s.tempo = float(value)
    elif op == "transpose":
        for t in trs:
            if not t.drums:
                for n in t.notes:
                    n.pitch += int(value)
    elif op in ("instrument", "volume", "pan", "reverb", "layer"):
        for t in trs:
            setattr(t, op, (int(value) if value.isdigit() else value) if op == "instrument" else (int(value) if op == "layer" else float(value)))
            if op == "instrument":
                _ = t.program  # validate
    elif op == "remove":
        s.tracks = [t for t in s.tracks if t.name != track]
    elif op == "loop":
        s.loop = value.lower() in ("1", "true", "yes")
    else:
        raise ValueError("op: tempo | transpose | instrument | volume | pan | reverb | layer | remove | loop")
    return [_png(M.preview(s)), _j(s.summary())]


@tool(mcp)
def mus_render(name: str, out: str, synth: str = "auto", fmt: str = "ogg", target_lufs: float = -16.0,
               stems: str = "none", soundfont: str = "", midi: bool = True) -> list:
    """Render a song to audio and analyse it. synth: auto (SoundFont if installed, chip for chip-wave songs)
    | chip | soundfont. fmt: ogg | wav | mp3 | both. Loops (song.loop) are rendered seamlessly (two passes,
    the 2nd kept, so the reverb tail wraps into the start). target_lufs: -16 mobile, -18 pc (−23 broadcast).
    stems: none | layers (one file per intensity layer, same length and same gain as the master — they sum
    to the master in the engine) | tracks. Writes <out>.<fmt> (+ _layerN / _<track> stems, + .mid)."""
    s = _song(name)
    base = artlib.ensure_parent(artlib.resolve_path(out))
    base = base.with_suffix("")
    x, used = A.render(s, synth, A.SR, None, soundfont or None)
    y, norm = A.normalize(x, A.SR, target_lufs)
    gain = 10 ** (norm.get("gain_db", 0) / 20)
    files = A.export(y, A.SR, base, fmt)
    stem_files = []
    if stems in ("layers", "tracks"):
        groups = ({f"layer{L}": [t.name for t in s.tracks if t.layer == L] for L in sorted({t.layer for t in s.tracks})}
                  if stems == "layers" else {t.name: [t.name] for t in s.tracks})
        for gname, names in groups.items():
            xs, _ = A.render(s, used, A.SR, names, soundfont or None)
            ys = np.clip(xs * gain, -1, 1)
            stem_files += A.export(ys, A.SR, base.with_name(f"{base.name}_{gname}"), fmt)
    if midi:
        files.append(str(M.write_midi(s, base.with_suffix(".mid"))))
    info, img = A.analyze(Path(files[0]), loop=s.loop)
    res = {"synth": used, "files": files, "stems": stem_files, "normalize": norm, "analysis": info}
    cr = _credits(used)
    if cr:
        res["credits_line"] = cr
    return [_png(img), _j(res)]


@tool(mcp)
def mus_stinger(kind: str, out: str, key: str = "C", tempo: float = 120, instrument: str = "brass",
                synth: str = "auto", fmt: str = "ogg", target_lufs: float = -14.0) -> list:
    """Short event cue: victory | level_up | item | discovery | defeat | danger | secret. Rendered without
    loop, with a natural tail; returned with its analysis image."""
    s = M.stinger(kind, key, tempo, instrument)
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
    coin, jump, laser, explosion, hit, hurt, powerup, blip, ui_click, ui_confirm, ui_cancel, error, magic,
    whoosh, footstep, land. WAV 44.1 kHz mono, peak −1 dBFS. Returns a waveform sheet."""
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
    """Load an existing MIDI file (from the user, FL Studio export, etc.) to preview, edit or render it."""
    s = M.read_midi(artlib.resolve_path(path))
    s.loop = loop
    SONGS[name or s.title] = s
    return [_png(M.preview(s)), _j({**s.summary(), "name": name or s.title})]


if __name__ == "__main__":
    mcp.run()
