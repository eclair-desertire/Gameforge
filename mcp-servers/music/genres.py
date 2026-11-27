"""Moods (what the scene feels like) and genres (what the music sounds like) for gameforge-music.

A spec may give a mood, a genre, or both:
  mood  -> mode, tempo energy, chord progressions (A/B sections), melody contour;
  genre -> meter, tempo range, swing, drums, instruments by role and the default arrangement
           (tracks with roles, styles and intensity layers), reverb space, master processing.
genre + mood = the genre's arrangement playing the mood's harmony (e.g. synthwave + sad).
"""
from __future__ import annotations

# ------------------------------------------------------------------ moods
# mode, tempo (lo, hi), progressions: list of (A, B), contour, energy 0..1
MOODS = {
    "heroic": dict(mode="major", tempo=(112, 140), prog=[("I V vi IV", "IV V iii vi"), ("I bVII IV I", "bVI bVII I:2")], contour="rise", energy=0.75),
    "adventure": dict(mode="mixolydian", tempo=(108, 132), prog=[("I bVII IV I", "IV I bVII V"), ("I IV bVII IV", "vi IV I V")], contour="arch", energy=0.65),
    "calm": dict(mode="major", tempo=(70, 96), prog=[("Imaj7 IVmaj7", "vi7 IVmaj7 I V"), ("I vi IV V", "IV I IV V")], contour="wave", energy=0.25),
    "peaceful": dict(mode="lydian", tempo=(66, 88), prog=[("I II I II", "IV I vi V")], contour="wave", energy=0.2),
    "town": dict(mode="major", tempo=(88, 112), prog=[("I IV I V", "IV I ii V"), ("I vi ii V", "IV V iii vi")], contour="arch", energy=0.45),
    "mystery": dict(mode="dorian", tempo=(70, 92), prog=[("i IV i bVII", "bIII IV i i"), ("i bIII IV i", "bVI bVII i i")], contour="wave", energy=0.35),
    "dungeon": dict(mode="phrygian", tempo=(60, 84), prog=[("i bII i bVII", "bVI bII i i"), ("i bVI bII i", "iv bII i i")], contour="fall", energy=0.4),
    "tension": dict(mode="harmonic_minor", tempo=(90, 120), prog=[("i i bVI V", "iv iv bII V")], contour="rise", energy=0.6),
    "battle": dict(mode="harmonic_minor", tempo=(140, 172), prog=[("i bVI bVII V", "iv i bVI V"), ("i iv V i", "bVI bIII bVII V")], contour="rise", energy=0.9),
    "boss": dict(mode="harmonic_minor", tempo=(150, 182), prog=[("i bII i V", "bVI iv bII V"), ("i bVI iv V", "i bII bVII V")], contour="rise", energy=1.0),
    "chase": dict(mode="minor", tempo=(160, 190), prog=[("i bVII bVI bVII", "i bVII bVI V")], contour="rise", energy=0.95),
    "stealth": dict(mode="minor", tempo=(84, 104), prog=[("i i bVI bVI", "iv iv V V")], contour="wave", energy=0.4),
    "sad": dict(mode="minor", tempo=(58, 78), prog=[("i iv bVI V", "bVI bIII bVII V"), ("i bVI bIII bVII", "iv i iv V")], contour="fall", energy=0.2),
    "melancholy": dict(mode="dorian", tempo=(64, 84), prog=[("i IV i IV", "bVII IV i i")], contour="fall", energy=0.25),
    "romantic": dict(mode="major", tempo=(66, 86), prog=[("Imaj7 iii7 vi7 IVmaj7", "ii7 V7 Imaj7 Imaj7")], contour="arch", energy=0.3),
    "hopeful": dict(mode="major", tempo=(80, 104), prog=[("IV I V vi", "IV V I I")], contour="rise", energy=0.5),
    "horror": dict(mode="locrian", tempo=(44, 66), prog=[("i bII i bV", "bII bV i i")], contour="fall", energy=0.3),
    "eerie": dict(mode="whole_tone", tempo=(54, 72), prog=[("i bII i bII", "bVI bII i i")], contour="wave", energy=0.2),
    "epic": dict(mode="minor", tempo=(84, 112), prog=[("i bVI bIII bVII", "iv bVI bVII i"), ("i bVII bVI bVII", "bVI bVII i i")], contour="rise", energy=0.85),
    "triumphant": dict(mode="major", tempo=(100, 126), prog=[("I bVII IV I", "bVI bVII I I")], contour="rise", energy=0.8),
    "playful": dict(mode="major", tempo=(112, 140), prog=[("I vi ii V", "I IV V I"), ("I III IV iv", "I vi ii V")], contour="wave", energy=0.6),
    "whimsical": dict(mode="lydian_dominant", tempo=(96, 124), prog=[("I II I II", "IV bVII I I")], contour="wave", energy=0.5),
    "mechanical": dict(mode="minor", tempo=(110, 130), prog=[("i i bVII bVII", "bVI bVI bVII bVII")], contour="wave", energy=0.6),
    "space": dict(mode="lydian", tempo=(60, 84), prog=[("I II I II", "vi II IV I")], contour="wave", energy=0.25),
    "exotic": dict(mode="phrygian_dominant", tempo=(90, 120), prog=[("I bII I bII", "iv bII I I"), ("I bVII bVI bII", "I bII I I")], contour="arch", energy=0.55),
    "oriental": dict(mode="pentatonic_minor", tempo=(70, 96), prog=[("i bVII i bVII", "bVI bVII i i")], contour="arch", energy=0.4),
    "cozy": dict(mode="major", tempo=(76, 96), prog=[("Imaj7 vi7 ii7 V7", "IVmaj7 iii7 ii7 V7")], contour="wave", energy=0.3),
    "victory": dict(mode="major", tempo=(118, 140), prog=[("I IV V I", "IV V I I")], contour="rise", energy=0.8),
    "game_over": dict(mode="minor", tempo=(60, 80), prog=[("i iv i V", "bVI iv V i")], contour="fall", energy=0.2),
    "menu": dict(mode="major", tempo=(90, 110), prog=[("I V vi IV", "IV V I I")], contour="arch", energy=0.45),
    "credits": dict(mode="major", tempo=(80, 100), prog=[("I V vi iii", "IV I IV V")], contour="arch", energy=0.4),
}

# ------------------------------------------------------------------ genres
# each track template: role + instrument + options; "layer" = adaptive intensity (1 base .. 3 full)
G = {}

def _g(name, **kw):
    G[name] = kw


_g("orchestral", desc="Symphonic score: strings, horns, woodwinds, harp, timpani — RPG, fantasy, adventure",
   tempo=(80, 132), meter="4/4", mood="heroic", drums="orchestral", reverb="hall",
   tracks=[dict(role="pad", instrument="strings", layer=1),
           dict(role="bass", instrument="contrabass", style="root_fifth", layer=1),
           dict(role="ostinato", instrument="pizzicato", figure="1 5 8 5", rate=0.5, layer=2),
           dict(role="drums", style="orchestral", layer=2),
           dict(role="counter", instrument="french_horn", style="contrary", layer=2),
           dict(role="melody", instrument="flute", layer=3)])
_g("epic_orchestral", desc="Trailer/boss: choir, brass, string ostinato, taiko — big battles, finales",
   tempo=(86, 120), meter="4/4", mood="epic", drums="taiko", reverb="cathedral",
   tracks=[dict(role="pad", instrument="choir", octave=3, layer=1),
           dict(role="drone", instrument="contrabass", octave=1, layer=1),
           dict(role="ostinato", instrument="strings", figure="1 1 5 1 b7 1 5 1", rate=0.25, octave=3, layer=1),
           dict(role="drums", style="taiko", layer=2),
           dict(role="power", instrument="brass", style="sustain", octave=3, layer=2),
           dict(role="melody", instrument="french_horn", octave=5, layer=3, density=0.45)])
_g("chamber", desc="Intimate: piano, violin, cello — drama, memories, puzzle, menus",
   tempo=(66, 100), meter="4/4", mood="melancholy", drums="none", reverb="room",
   tracks=[dict(role="arp", instrument="piano", pattern="broken", rate=0.5, octave=3, layer=1),
           dict(role="bass", instrument="cello", style="sustain", layer=1),
           dict(role="counter", instrument="viola", style="contrary", layer=2),
           dict(role="melody", instrument="violin", layer=3, density=0.5)])
_g("piano_solo", desc="Solo piano: Alberti/broken left hand + melody — menus, sad scenes, credits",
   tempo=(60, 96), meter="4/4", mood="sad", drums="none", reverb="room",
   tracks=[dict(role="arp", instrument="piano", pattern="alberti", rate=0.5, octave=3, layer=1),
           dict(role="bass", instrument="piano", style="root", octave=2, layer=1),
           dict(role="melody", instrument="piano", layer=2, density=0.5)])
_g("fantasy_folk", desc="Celtic/medieval tavern & village: fiddle, flute, lute, bodhran — 6/8 jig",
   tempo=(100, 132), meter="6/8", mood="town", drums="jig", reverb="room",
   tracks=[dict(role="chords", instrument="nylon_guitar", rhythm="compound", layer=1),
           dict(role="drone", instrument="bagpipe", octave=2, layer=1, fifth=True),
           dict(role="bass", instrument="acoustic_bass", style="compound", layer=1),
           dict(role="drums", style="jig", layer=2),
           dict(role="melody", instrument="fiddle", layer=2, ornament=0.25, rhythm_style="bouncy"),
           dict(role="counter", instrument="flute", style="thirds", layer=3)])
_g("tavern", desc="Lively tavern: accordion oom-pah, fiddle, tambourine",
   tempo=(108, 140), meter="6/8", mood="playful", drums="shanty", reverb="room",
   tracks=[dict(role="chords", instrument="accordion", rhythm="compound", layer=1),
           dict(role="bass", instrument="tuba", style="compound", layer=1),
           dict(role="drums", style="shanty", layer=2),
           dict(role="melody", instrument="fiddle", layer=2, ornament=0.2, rhythm_style="bouncy")])
_g("waltz", desc="Waltz 3/4: ballroom, music box, nostalgic towns, creepy carnival in minor",
   tempo=(84, 160), meter="3/4", mood="romantic", drums="waltz", reverb="hall",
   tracks=[dict(role="bass", instrument="contrabass", style="waltz", layer=1),
           dict(role="chords", instrument="strings", rhythm="waltz", layer=1),
           dict(role="drums", style="waltz", layer=2),
           dict(role="texture", instrument="celesta", density=0.25, layer=2),
           dict(role="melody", instrument="clarinet", layer=3, rhythm_style="lyrical")])
_g("music_box", desc="Music box / lullaby: celesta, glockenspiel — childhood, dreams, eerie in minor",
   tempo=(66, 96), meter="3/4", mood="calm", drums="none", reverb="hall",
   tracks=[dict(role="arp", instrument="music_box", pattern="broken", rate=0.5, octave=4, layer=1),
           dict(role="bass", instrument="harp", style="waltz", octave=3, layer=1),
           dict(role="melody", instrument="celesta", octave=6, layer=2, density=0.4)])
_g("chiptune", desc="8-bit console: 2 pulse + triangle + noise, fast arps — retro platformers",
   tempo=(130, 170), meter="4/4", mood="playful", drums="chip", reverb="none", engine="chip",
   tracks=[dict(role="bass", instrument="triangle", style="octave", layer=1),
           dict(role="arp", instrument="pulse12", pattern="up", rate=0.25, octave=4, layer=2),
           dict(role="drums", style="chip", kit="chip", layer=2),
           dict(role="melody", instrument="square", layer=3, density=0.7, rhythm_style="bouncy")])
_g("chip_chords", desc="8-bit with fast chord-cycling arpeggios (classic handheld sound)",
   tempo=(120, 160), meter="4/4", mood="adventure", drums="chip_fast", reverb="none", engine="chip",
   tracks=[dict(role="bass", instrument="triangle", style="chip", layer=1),
           dict(role="arp", instrument="pulse25", pattern="cycle", rate=0.0625, octave=4, layer=1),
           dict(role="drums", style="chip_fast", kit="chip", layer=2),
           dict(role="melody", instrument="square", layer=3, density=0.65)])
_g("16bit", desc="16-bit console: synth brass, slap bass, FM-ish bells, punchy room drums",
   tempo=(110, 150), meter="4/4", mood="adventure", drums="16bit", reverb="room",
   tracks=[dict(role="chords", instrument="synth_strings", rhythm="halves", layer=1),
           dict(role="bass", instrument="slap_bass", style="syncopated", layer=1),
           dict(role="arp", instrument="fm_bell", pattern="updown", rate=0.25, layer=2),
           dict(role="drums", style="16bit", layer=2),
           dict(role="melody", instrument="synth_brass", layer=3)])
_g("synthwave", desc="80s retro-futurism: supersaw pads, arpeggiated bass, gated snare, chorus",
   tempo=(84, 118), meter="4/4", mood="hopeful", drums="synthwave", reverb="plate", master=dict(width=1.3),
   tracks=[dict(role="pad", instrument="synth_pad", layer=1),
           dict(role="bass", instrument="analog_bass", style="octave16", layer=1, duck=0.3),
           dict(role="arp", instrument="pluck", pattern="updown", rate=0.25, span=2, layer=2),
           dict(role="drums", style="synthwave", kit="909", gated=True, layer=2),
           dict(role="melody", instrument="saw_lead", layer=3, density=0.5)])
_g("edm", desc="EDM / electro: four-on-the-floor, sidechain-pumped supersaws, pluck leads",
   tempo=(120, 130), meter="4/4", mood="triumphant", drums="edm", reverb="plate",
   tracks=[dict(role="chords", instrument="supersaw", rhythm="offbeat", layer=1, duck=0.7),
           dict(role="bass", instrument="sub_bass", style="pulse8", layer=1, duck=0.6),
           dict(role="drums", style="edm", kit="909", layer=2),
           dict(role="arp", instrument="pluck", pattern="up", rate=0.25, span=2, layer=2, duck=0.4),
           dict(role="melody", instrument="pluck_lead", layer=3, density=0.6)])
_g("house", desc="House: piano/organ stabs, offbeat bass, claps — lobby, shop, rhythm games",
   tempo=(118, 126), meter="4/4", mood="cozy", drums="house", reverb="room",
   tracks=[dict(role="chords", instrument="electric_piano", rhythm="stabs", color="7th", layer=1, duck=0.4),
           dict(role="bass", instrument="analog_bass", style="syncopated", layer=1, duck=0.5),
           dict(role="drums", style="house", kit="909", layer=2),
           dict(role="melody", instrument="pluck_lead", layer=3, density=0.45)])
_g("techno", desc="Techno: driving kick, acid bass, metallic percussion — sci-fi, factories, hacking",
   tempo=(124, 140), meter="4/4", mood="mechanical", drums="techno", reverb="plate",
   tracks=[dict(role="drone", instrument="dark_pad", layer=1, octave=3),
           dict(role="bass", instrument="acid_bass", style="pulse16", layer=1, duck=0.5),
           dict(role="drums", style="techno", kit="909", layer=1),
           dict(role="ostinato", instrument="fm_bell", figure="1 r 5 r 8 r b7 5", rate=0.25, octave=5, layer=2),
           dict(role="melody", instrument="square_lead", layer=3, density=0.35)])
_g("dnb", desc="Drum & bass: fast breaks, rolling reese bass, pads — racing, chase, cyberpunk",
   tempo=(165, 176), meter="4/4", mood="chase", drums="dnb", reverb="plate",
   tracks=[dict(role="pad", instrument="synth_pad", layer=1),
           dict(role="bass", instrument="reese_bass", style="rolling", layer=1),
           dict(role="drums", style="dnb", kit="909", layer=2),
           dict(role="melody", instrument="saw_lead", layer=3, density=0.45)])
_g("dubstep", desc="Dubstep / halftime: wobble bass, sub, big snare on 3",
   tempo=(138, 150), meter="4/4", mood="boss", drums="dubstep", reverb="plate",
   tracks=[dict(role="pad", instrument="dark_pad", layer=1),
           dict(role="bass", instrument="wobble_bass", style="syncopated", layer=1),
           dict(role="drums", style="dubstep", kit="909", layer=2),
           dict(role="melody", instrument="square_lead", layer=3, density=0.4)])
_g("trap", desc="Trap / hip-hop: 808 bass, rolling hats, dark keys",
   tempo=(130, 150), meter="4/4", mood="tension", drums="trap", reverb="room",
   tracks=[dict(role="arp", instrument="bell_keys", pattern="broken", rate=0.5, layer=1),
           dict(role="bass", instrument="808_bass", style="boom", layer=1),
           dict(role="drums", style="trap", kit="808", layer=2),
           dict(role="melody", instrument="flute", layer=3, density=0.4)])
_g("lofi", desc="Lo-fi hip-hop: swung drums, jazzy 7th chords on e-piano, vinyl, tape wobble — cozy, study, menus",
   tempo=(70, 90), meter="4/4", mood="cozy", drums="lofi", reverb="room", swing=0.45, master=dict(lofi=0.7),
   tracks=[dict(role="chords", instrument="electric_piano", rhythm="charleston", color="9th", layer=1),
           dict(role="bass", instrument="fingered_bass", style="boom", layer=1),
           dict(role="drums", style="lofi", kit="lofi", layer=2),
           dict(role="melody", instrument="vibraphone", layer=3, density=0.35)])
_g("jazz", desc="Swing jazz trio/quartet: walking bass, ride, comping piano, sax — noir, casino, lounge",
   tempo=(110, 180), meter="4/4", mood="cozy", drums="jazz_swing", reverb="room", swing=0.65,
   tracks=[dict(role="chords", instrument="piano", rhythm="charleston", color="9th", layer=1),
           dict(role="bass", instrument="acoustic_bass", style="walking", layer=1),
           dict(role="drums", style="jazz_swing", layer=2),
           dict(role="melody", instrument="tenor_sax", layer=3, density=0.6, scale="bebop_dominant")])
_g("noir", desc="Film noir / detective: brushes, muted trumpet, minor 9ths, slow swing",
   tempo=(62, 84), meter="4/4", mood="mystery", drums="brush", reverb="room", swing=0.6,
   tracks=[dict(role="chords", instrument="piano", rhythm="sustain", color="9th", layer=1),
           dict(role="bass", instrument="acoustic_bass", style="walking", layer=1),
           dict(role="drums", style="brush", layer=2),
           dict(role="melody", instrument="muted_trumpet", layer=3, density=0.4)])
_g("bossa", desc="Bossa nova: nylon guitar, soft rim, flute — beaches, resorts, shops",
   tempo=(118, 140), meter="4/4", mood="calm", drums="bossa", reverb="room",
   tracks=[dict(role="chords", instrument="nylon_guitar", rhythm="bossa", color="7th", layer=1),
           dict(role="bass", instrument="acoustic_bass", style="bossa", layer=1),
           dict(role="drums", style="bossa", layer=2),
           dict(role="melody", instrument="flute", layer=3, density=0.5)])
_g("latin", desc="Latin / salsa feel: congas, cowbell, piano montuno, brass",
   tempo=(170, 200), meter="4/4", mood="playful", drums="latin", reverb="room",
   tracks=[dict(role="arp", instrument="piano", pattern="broken", rate=0.5, layer=1),
           dict(role="bass", instrument="acoustic_bass", style="syncopated", layer=1),
           dict(role="drums", style="latin", layer=2),
           dict(role="melody", instrument="trumpet", layer=3)])
_g("reggae", desc="Reggae / dub: offbeat skank, one-drop, deep bass — islands, chill",
   tempo=(66, 84), meter="4/4", mood="calm", drums="reggae", reverb="plate",
   tracks=[dict(role="chords", instrument="electric_guitar", rhythm="reggae", layer=1),
           dict(role="chords", name="Organ", instrument="organ", rhythm="offbeat", layer=1, volume=0.5),
           dict(role="bass", instrument="fingered_bass", style="reggae", layer=1),
           dict(role="drums", style="reggae", layer=2),
           dict(role="melody", instrument="melodica", layer=3)])
_g("rock", desc="Rock: power chords, bass, live kit — action, sports, racing",
   tempo=(120, 160), meter="4/4", mood="heroic", drums="rock", reverb="room",
   tracks=[dict(role="power", instrument="overdrive_guitar", style="chug8", layer=1),
           dict(role="bass", instrument="picked_bass", style="pulse8", layer=1),
           dict(role="drums", style="rock", kit="power", layer=2),
           dict(role="melody", instrument="distortion_guitar", octave=4, layer=3)])
_g("metal", desc="Metal: gallops, double kick, palm-muted chugs, harmonic minor leads — boss, hell",
   tempo=(150, 200), meter="4/4", mood="boss", drums="metal", reverb="room",
   tracks=[dict(role="power", instrument="distortion_guitar", style="gallop", octave=2, layer=1),
           dict(role="bass", instrument="picked_bass", style="gallop", layer=1),
           dict(role="drums", style="metal", kit="power", layer=2),
           dict(role="pad", instrument="choir", octave=3, layer=2),
           dict(role="melody", instrument="distortion_guitar", octave=5, layer=3)])
_g("punk", desc="Punk / pop-punk: fast 8th power chords, simple bass — skate, arcade",
   tempo=(170, 200), meter="4/4", mood="playful", drums="punk", reverb="room",
   tracks=[dict(role="power", instrument="overdrive_guitar", style="chug8", layer=1),
           dict(role="bass", instrument="picked_bass", style="pulse8", layer=1),
           dict(role="drums", style="punk", kit="power", layer=2),
           dict(role="melody", instrument="overdrive_guitar", octave=4, layer=3)])
_g("funk", desc="Funk: 16th clav/guitar, slap bass, tight drums, brass hits",
   tempo=(96, 116), meter="4/4", mood="playful", drums="funk", reverb="room",
   tracks=[dict(role="chords", instrument="clavinet", rhythm="funk16", color="7th", layer=1),
           dict(role="bass", instrument="slap_bass", style="funk", layer=1),
           dict(role="drums", style="funk", layer=2),
           dict(role="melody", instrument="brass", layer=3, density=0.55)])
_g("pop", desc="Pop: piano/guitar strum, bass, pop kit — casual, mobile, menus",
   tempo=(96, 124), meter="4/4", mood="hopeful", drums="pop", reverb="plate",
   tracks=[dict(role="chords", instrument="acoustic_guitar", rhythm="strum", layer=1),
           dict(role="pad", instrument="warm_pad", layer=1),
           dict(role="bass", instrument="fingered_bass", style="syncopated", layer=1),
           dict(role="drums", style="pop", layer=2),
           dict(role="melody", instrument="pluck_lead", layer=3)])
_g("country", desc="Country / western: banjo picking, fiddle, boom-chick bass — frontier, farms",
   tempo=(100, 140), meter="4/4", mood="adventure", drums="shuffle", reverb="room",
   tracks=[dict(role="arp", instrument="banjo", pattern="pinky", rate=0.25, layer=1),
           dict(role="bass", instrument="acoustic_bass", style="root_fifth", layer=1),
           dict(role="drums", style="shuffle", layer=2),
           dict(role="melody", instrument="fiddle", layer=3, ornament=0.15)])
_g("blues", desc="Slow blues 12/8: shuffle, organ, guitar licks in the blues scale",
   tempo=(54, 76), meter="12/8", mood="melancholy", drums="slow_blues", reverb="room",
   tracks=[dict(role="chords", instrument="organ", rhythm="compound", color="7th", layer=1),
           dict(role="bass", instrument="fingered_bass", style="compound", layer=1),
           dict(role="drums", style="slow_blues", layer=2),
           dict(role="melody", instrument="electric_guitar", layer=3, scale="blues", density=0.45)])
_g("ambient", desc="Ambient: long pads, drones, sparse bells — exploration, space, menus, puzzles",
   tempo=(60, 80), meter="4/4", mood="space", drums="none", reverb="space",
   tracks=[dict(role="pad", instrument="atmosphere_pad", layer=1),
           dict(role="drone", instrument="dark_pad", octave=2, layer=1),
           dict(role="texture", instrument="fm_bell", density=0.3, octave=5, layer=2),
           dict(role="melody", instrument="glass_lead", layer=3, density=0.25, rhythm_style="sparse")])
_g("dark_ambient", desc="Horror / dark ambient: drones, dissonant clusters, distant hits — horror, caves",
   tempo=(50, 66), meter="4/4", mood="horror", drums="sparse", reverb="cathedral",
   tracks=[dict(role="drone", instrument="dark_pad", octave=1, layer=1),
           dict(role="pad", instrument="tremolo_strings", layer=1, octave=3),
           dict(role="texture", instrument="music_box", density=0.15, octave=5, layer=2),
           dict(role="drums", style="sparse", layer=2),
           dict(role="melody", instrument="choir", layer=3, density=0.2, rhythm_style="sparse")])
_g("cinematic_tension", desc="Underscore for stealth/suspense: string ostinato, pulses, low hits",
   tempo=(90, 120), meter="4/4", mood="stealth", drums="cinematic_build", reverb="hall",
   tracks=[dict(role="drone", instrument="contrabass", octave=1, layer=1),
           dict(role="ostinato", instrument="strings", figure="1 1 b7 1 5 1 b7 1", rate=0.25, octave=3, layer=1),
           dict(role="pulse", instrument="synth_pad", layer=2),
           dict(role="drums", style="cinematic_build", layer=2),
           dict(role="melody", instrument="cello", octave=3, layer=3, density=0.3, rhythm_style="sparse")])
_g("march", desc="Military / heroic march 4/4: snare rolls, brass, piccolo",
   tempo=(108, 124), meter="4/4", mood="triumphant", drums="march", reverb="hall",
   tracks=[dict(role="bass", instrument="tuba", style="oompah", layer=1),
           dict(role="chords", instrument="brass", rhythm="beats", layer=1),
           dict(role="drums", style="march", layer=2),
           dict(role="fanfare", instrument="trumpet", every=4, layer=2),
           dict(role="melody", instrument="piccolo", layer=3)])
_g("circus", desc="Circus / silly 2/4: oom-pah tuba, calliope, xylophone — comedy, clowns, minigames",
   tempo=(140, 180), meter="2/4", mood="playful", drums="circus", reverb="room",
   tracks=[dict(role="bass", instrument="tuba", style="oompah", layer=1),
           dict(role="chords", instrument="accordion", rhythm="offbeat", layer=1),
           dict(role="drums", style="circus", layer=2),
           dict(role="melody", instrument="calliope", layer=3, density=0.75, rhythm_style="busy"),
           dict(role="counter", instrument="xylophone", style="thirds", layer=3)])
_g("asian", desc="East-Asian flavour: koto, shakuhachi-like flute, taiko — pentatonic/in-sen",
   tempo=(70, 110), meter="4/4", mood="oriental", drums="taiko", reverb="hall",
   tracks=[dict(role="arp", instrument="koto", pattern="broken", rate=0.5, layer=1),
           dict(role="drone", instrument="strings", octave=2, layer=1),
           dict(role="drums", style="taiko", layer=2),
           dict(role="melody", instrument="shakuhachi", layer=3, ornament=0.3, scale="in_sen", density=0.4)])
_g("middle_eastern", desc="Desert / Middle-Eastern flavour: oud-like plucks, frame drums, phrygian dominant",
   tempo=(90, 124), meter="4/4", mood="exotic", drums="latin", reverb="hall",
   tracks=[dict(role="drone", instrument="strings", octave=2, layer=1),
           dict(role="ostinato", instrument="sitar", figure="1 2 1 b2 1 r 5 b6", rate=0.25, octave=3, layer=1),
           dict(role="drums", style="latin", layer=2),
           dict(role="melody", instrument="oboe", layer=3, ornament=0.35, density=0.55)])
_g("pirate", desc="Pirate / sea shanty 6/8: accordion, fiddle, stomp-clap",
   tempo=(100, 132), meter="6/8", mood="adventure", drums="shanty", reverb="room",
   tracks=[dict(role="chords", instrument="accordion", rhythm="compound", layer=1),
           dict(role="bass", instrument="contrabass", style="compound", layer=1),
           dict(role="drums", style="shanty", layer=2),
           dict(role="melody", instrument="fiddle", layer=3, ornament=0.15, rhythm_style="bouncy")])
_g("puzzle", desc="Puzzle / thinking loop: marimba ostinato, pizzicato, light shaker — low distraction",
   tempo=(96, 116), meter="4/4", mood="playful", drums="light", reverb="room",
   tracks=[dict(role="ostinato", instrument="marimba", figure="1 5 8 5 10 5 8 5", rate=0.5, octave=4, layer=1),
           dict(role="bass", instrument="pizzicato", style="root_fifth", octave=2, layer=1),
           dict(role="drums", style="light", layer=2),
           dict(role="melody", instrument="clarinet", layer=3, density=0.35)])
_g("odd_meter", desc="Odd meter 7/8 groove: off-kilter, mechanical, alien worlds, prog boss",
   tempo=(120, 160), meter="7/8", mood="mechanical", drums="odd_groove", reverb="room",
   tracks=[dict(role="power", instrument="overdrive_guitar", style="stops", layer=1),
           dict(role="bass", instrument="analog_bass", style="root_fifth", layer=1),
           dict(role="drums", style="odd_groove", layer=2),
           dict(role="melody", instrument="saw_lead", layer=3)])

GENRES = G

# mood used alone (no genre) -> which genre arranges it
MOOD_DEFAULT_GENRE = {
    "heroic": "orchestral", "adventure": "orchestral", "calm": "chamber", "peaceful": "ambient", "town": "fantasy_folk",
    "mystery": "chamber", "dungeon": "dark_ambient", "tension": "cinematic_tension", "battle": "epic_orchestral",
    "boss": "epic_orchestral", "chase": "dnb", "stealth": "cinematic_tension", "sad": "piano_solo", "melancholy": "chamber",
    "romantic": "waltz", "hopeful": "orchestral", "horror": "dark_ambient", "eerie": "music_box", "epic": "epic_orchestral",
    "triumphant": "march", "playful": "puzzle", "whimsical": "circus", "mechanical": "techno", "space": "ambient",
    "exotic": "middle_eastern", "oriental": "asian", "cozy": "lofi", "victory": "march", "game_over": "piano_solo",
    "menu": "orchestral", "credits": "orchestral",
}

# scene/game type -> suggestions for the brief (genre, mood)
SCENES = {
    "title_menu": [("orchestral", "menu"), ("synthwave", "hopeful"), ("piano_solo", "melancholy"), ("chiptune", "playful")],
    "town_hub": [("fantasy_folk", "town"), ("lofi", "cozy"), ("bossa", "calm"), ("chamber", "town")],
    "overworld": [("orchestral", "adventure"), ("fantasy_folk", "adventure"), ("chiptune", "adventure")],
    "forest_nature": [("ambient", "peaceful"), ("fantasy_folk", "calm"), ("chamber", "mystery")],
    "dungeon_cave": [("dark_ambient", "dungeon"), ("cinematic_tension", "tension"), ("chamber", "dungeon")],
    "battle": [("epic_orchestral", "battle"), ("rock", "battle"), ("chiptune", "battle"), ("edm", "battle")],
    "boss": [("epic_orchestral", "boss"), ("metal", "boss"), ("dubstep", "boss"), ("odd_meter", "boss")],
    "stealth": [("cinematic_tension", "stealth"), ("techno", "stealth"), ("noir", "stealth")],
    "horror": [("dark_ambient", "horror"), ("music_box", "eerie"), ("cinematic_tension", "horror")],
    "racing_sport": [("dnb", "chase"), ("rock", "triumphant"), ("edm", "triumphant"), ("punk", "playful")],
    "puzzle_casual": [("puzzle", "playful"), ("bossa", "calm"), ("lofi", "cozy"), ("pop", "hopeful")],
    "cyberpunk_scifi": [("synthwave", "tension"), ("techno", "mechanical"), ("ambient", "space"), ("dnb", "chase")],
    "shop": [("bossa", "cozy"), ("house", "cozy"), ("jazz", "cozy"), ("tavern", "playful")],
    "tavern_inn": [("tavern", "playful"), ("fantasy_folk", "town"), ("pirate", "adventure")],
    "sad_scene": [("piano_solo", "sad"), ("chamber", "melancholy"), ("ambient", "sad")],
    "victory_credits": [("orchestral", "triumphant"), ("march", "victory"), ("pop", "hopeful")],
    "comedy_minigame": [("circus", "playful"), ("chiptune", "playful"), ("funk", "playful")],
    "western": [("country", "adventure"), ("blues", "melancholy")],
    "noir_detective": [("noir", "mystery"), ("jazz", "mystery")],
    "pirate_sea": [("pirate", "adventure"), ("tavern", "playful")],
    "desert_exotic": [("middle_eastern", "exotic"), ("asian", "oriental")],
}


def resolve(spec: dict) -> tuple[dict, dict, str, str]:
    """-> (mood_dict, genre_dict, mood_name, genre_name), validating names."""
    mood = spec.get("mood") or ""
    genre = spec.get("genre") or ""
    if mood and mood not in MOODS:
        raise ValueError(f"mood: {sorted(MOODS)}")
    if genre and genre not in GENRES:
        raise ValueError(f"genre: {sorted(GENRES)}")
    if not genre:
        genre = MOOD_DEFAULT_GENRE.get(mood, "orchestral") if mood else ""
    if not mood:
        mood = GENRES[genre]["mood"] if genre else "adventure"
    return MOODS[mood], (GENRES[genre] if genre else {}), mood, genre


def catalogue() -> dict:
    return {"genres": {k: v["desc"] for k, v in GENRES.items()},
            "moods": {k: f"{v['mode']}, {v['tempo'][0]}-{v['tempo'][1]} BPM" for k, v in MOODS.items()},
            "scenes": SCENES}
