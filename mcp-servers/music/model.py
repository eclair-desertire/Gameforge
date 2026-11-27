"""Data model for gameforge-music: Note, Track, Song (+ tempo map: beats <-> seconds)."""
from __future__ import annotations

from dataclasses import dataclass, field

import theory as T


@dataclass
class Note:
    start: float          # beats (quarter notes)
    dur: float
    pitch: int
    vel: int = 90


@dataclass
class Track:
    name: str
    role: str
    instrument: str | int = "piano"
    notes: list[Note] = field(default_factory=list)
    volume: float = 0.8
    pan: float = 0.0
    reverb: float = 0.3
    layer: int = 1
    drums: bool = False
    engine: str = "auto"        # auto | sf | chip | synth
    kit: str = "standard"       # GM drum kit for the sf engine; synth/chip kits: 808, 909, chip, acoustic, taiko, lofi
    duck: float = 0.0           # sidechain ducking depth 0..1 (pumping to the kick)
    params: dict = field(default_factory=dict)


@dataclass
class Song:
    title: str
    tempo: float
    key: str
    mode: str
    meter: str = "4/4"
    bars: int = 8
    tracks: list[Track] = field(default_factory=list)
    chords: list = field(default_factory=list)                 # list[T.Chord]
    sections: list = field(default_factory=list)               # (start_beat, name, key, bars)
    tempo_map: list = field(default_factory=list)              # (beat, bpm), first at 0
    loop: bool = True
    genre: str = ""
    reverb: str = "hall"                                       # room | hall | cathedral | plate | space | none
    master: dict = field(default_factory=dict)                 # drive, width
    spec: dict = field(default_factory=dict)

    @property
    def bpb(self) -> float:
        return T.meter(self.meter)[0]

    @property
    def length_beats(self) -> float:
        return self.bars * self.bpb

    def _map(self):
        return self.tempo_map or [(0.0, self.tempo)]

    def sec(self, beat: float) -> float:
        """Seconds at a beat (tempo map aware; periodic beyond the end for loop renders)."""
        L = self.length_beats
        S = self._sec_in(L)
        k = int(beat // L) if L > 0 else 0
        return k * S + self._sec_in(beat - k * L)

    def _sec_in(self, beat: float) -> float:
        m = self._map()
        total = 0.0
        for i, (b, bpm) in enumerate(m):
            nb = m[i + 1][0] if i + 1 < len(m) else float("inf")
            if beat <= b:
                break
            seg = min(beat, nb) - b
            total += seg * 60.0 / bpm
            if beat <= nb:
                break
        return total

    @property
    def seconds(self) -> float:
        return self.sec(self.length_beats)

    def summary(self) -> dict:
        return {
            "title": self.title, "genre": self.genre, "bpm": round(self.tempo / T.felt(self.meter), 1),
            "bpm_note": "felt beat (dotted quarter)" if T.is_compound(self.meter) else "quarter note",
            "tempo_changes": [(round(b / self.bpb) + 1, round(bpm / T.felt(self.meter), 1)) for b, bpm in self.tempo_map[1:]] or None,
            "key": self.key, "mode": self.mode, "meter": self.meter, "bars": self.bars,
            "seconds": round(self.seconds, 2), "loop": self.loop,
            "sections": [{"name": n, "bar": int(s // self.bpb) + 1, "bars": b, "key": k} for s, n, k, b in self.sections],
            "tracks": [{"name": t.name, "role": t.role, "instrument": t.instrument, "engine": t.engine, "notes": len(t.notes), "layer": t.layer,
                        "range": [T.midi_to_name(min(n.pitch for n in t.notes), self.key, self.mode if self.mode in T.MODES else "major"), T.midi_to_name(max(n.pitch for n in t.notes), self.key, self.mode if self.mode in T.MODES else "major")]
                        if t.notes and not t.drums else None} for t in self.tracks],
            "chords": " | ".join(c.label for c in self.chords[:24]),
        }
