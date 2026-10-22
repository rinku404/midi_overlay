"""Read a MIDI file into a flat list of notes timed in seconds."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import mido


@dataclass
class Note:
    start: float  # seconds
    end: float  # seconds
    pitch: int  # MIDI note number, 60 = middle C
    velocity: int
    channel: int
    track: int

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TrackInfo:
    index: int
    name: str
    channels: set[int] = field(default_factory=set)
    note_count: int = 0
    lowest: int | None = None
    highest: int | None = None


class TempoMap:
    """Converts absolute ticks to seconds, honouring every tempo change."""

    def __init__(self, ticks_per_beat: int, changes: list[tuple[int, int]]):
        self.tpb = ticks_per_beat
        changes = sorted(changes)
        if not changes or changes[0][0] != 0:
            changes.insert(0, (0, 500000))  # MIDI default: 120 bpm
        self.ticks: list[int] = []
        self.tempos: list[int] = []
        self.seconds: list[float] = []
        elapsed = 0.0
        for i, (tick, tempo) in enumerate(changes):
            if i:
                prev_tick, prev_tempo = self.ticks[-1], self.tempos[-1]
                elapsed += mido.tick2second(tick - prev_tick, self.tpb, prev_tempo)
            self.ticks.append(tick)
            self.tempos.append(tempo)
            self.seconds.append(elapsed)

    def to_seconds(self, tick: int) -> float:
        i = bisect.bisect_right(self.ticks, tick) - 1
        return self.seconds[i] + mido.tick2second(tick - self.ticks[i], self.tpb, self.tempos[i])


def _absolute(track: mido.MidiTrack):
    tick = 0
    for msg in track:
        tick += msg.time
        yield tick, msg


def load(path: str) -> tuple[list[Note], list[TrackInfo]]:
    mid = mido.MidiFile(path)
    tempo_changes = [
        (tick, msg.tempo)
        for track in mid.tracks
        for tick, msg in _absolute(track)
        if msg.type == "set_tempo"
    ]
    if mid.type == 2:
        raise ValueError("MIDI type 2 (independent sequences) is not supported")
    tempo = TempoMap(mid.ticks_per_beat, tempo_changes)

    notes: list[Note] = []
    infos: list[TrackInfo] = []
    for t_index, track in enumerate(mid.tracks):
        info = TrackInfo(t_index, track.name or f"Track {t_index}")
        open_notes: dict[tuple[int, int], list[tuple[int, int]]] = {}
        last_tick = 0
        for tick, msg in _absolute(track):
            last_tick = tick
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes.setdefault((msg.channel, msg.note), []).append((tick, msg.velocity))
            elif msg.type in ("note_off", "note_on"):
                stack = open_notes.get((msg.channel, msg.note))
                if stack:
                    start_tick, vel = stack.pop(0)
                    notes.append(Note(tempo.to_seconds(start_tick), tempo.to_seconds(tick),
                                      msg.note, vel, msg.channel, t_index))
        # Notes never released: close them at the end of the track.
        for (channel, pitch), stack in open_notes.items():
            for start_tick, vel in stack:
                notes.append(Note(tempo.to_seconds(start_tick), tempo.to_seconds(last_tick),
                                  pitch, vel, channel, t_index))
        for n in notes:
            if n.track == t_index:
                info.channels.add(n.channel)
                info.note_count += 1
                info.lowest = n.pitch if info.lowest is None else min(info.lowest, n.pitch)
                info.highest = n.pitch if info.highest is None else max(info.highest, n.pitch)
        infos.append(info)

    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes, infos


def filter_notes(notes: list[Note], track: int | None = None, channel: int | None = None) -> list[Note]:
    return [n for n in notes
            if (track is None or n.track == track) and (channel is None or n.channel == channel)]
