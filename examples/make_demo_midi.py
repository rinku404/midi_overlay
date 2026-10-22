"""Writes examples/ewi_demo.mid: a short melody with legato, accidentals and ledger-line notes."""

from pathlib import Path

import mido

# (note, beats) - 0 is a rest
MELODY = [
    (62, 1), (65, 0.5), (69, 0.5), (71, 1), (74, 1),        # D F A B D
    (73, 0.5), (71, 0.5), (70, 1), (66, 1), (0, 0.5),       # C# B Bb F#
    (81, 0.5), (84, 1), (88, 1.5), (86, 0.5), (83, 1),      # high notes with ledger lines
    (60, 1), (57, 0.5), (55, 0.5), (52, 1), (63, 2),        # low notes, Eb
]

mid = mido.MidiFile(ticks_per_beat=480)
track = mido.MidiTrack()
mid.tracks.append(track)
track.append(mido.MetaMessage("track_name", name="EWI", time=0))
track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(100), time=0))
pending = 480  # one beat of silence first
for note, beats in MELODY:
    ticks = round(beats * 480)
    if note == 0:
        pending += ticks
        continue
    track.append(mido.Message("note_on", note=note, velocity=90, time=pending))
    track.append(mido.Message("note_off", note=note, velocity=0, time=ticks - 20))
    pending = 20
out = Path(__file__).with_name("ewi_demo.mid")
mid.save(out)
print(f"wrote {out}")
