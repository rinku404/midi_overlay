"""Command line: python -m midi_overlay <command> ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import export, layouts, midi_reader, theme as themes


def _size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        return int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError("size must look like 1920x1080") from None


def _load_notes(args) -> list[midi_reader.Note]:
    notes, _ = midi_reader.load(args.midi)
    channel = args.channel - 1 if args.channel else None
    notes = midi_reader.filter_notes(notes, args.track, channel)
    if not notes:
        sys.exit("No notes found (check --track / --channel; run the 'info' command to list them).")
    return notes


def _layout(args, notes):
    width, height = args.size
    return layouts.create(themes.load(args.theme), width, height, notes, args.transpose)


def cmd_info(args):
    notes, tracks = midi_reader.load(args.midi)
    end = max((n.end for n in notes), default=0)
    print(f"{args.midi}: {len(notes)} notes, {end:.2f} s")
    for t in tracks:
        if not t.note_count:
            continue
        chans = ", ".join(str(c + 1) for c in sorted(t.channels))
        print(f"  track {t.index} '{t.name}': {t.note_count} notes, channel(s) {chans}, "
              f"range {_name(t.lowest)} to {_name(t.highest)}")


def _name(pitch: int) -> str:
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][pitch % 12] + str(pitch // 12 - 1)


def cmd_themes(args):
    for folder in themes.list_themes():
        t = themes.load(str(folder))
        print(f"  {folder.name:20s} {t.name} ({t.layout})")


def cmd_preview(args):
    notes = _load_notes(args)
    layout = _layout(args, notes)
    out = Path(args.output)
    for i, at in enumerate(args.at):
        target = out if len(args.at) == 1 else out.with_name(f"{out.stem}_{i + 1}{out.suffix}")
        layout.render(at - args.offset).save(target)
        print(f"wrote {target} (t={at}s)")


def cmd_render(args):
    notes = _load_notes(args)
    layout = _layout(args, notes)
    duration = args.duration
    if duration is None:
        duration = max(n.end for n in notes) + args.offset + args.tail - args.start
    out = Path(args.output)
    print(f"rendering {duration:.1f}s at {args.fps} fps, {args.size[0]}x{args.size[1]}, format {args.format}")
    result = export.render_video(layout, out, args.format, args.fps, args.start, duration,
                                 args.offset, args.background, args.ffmpeg)
    print(f"done: {result or out}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="midi_overlay", description="Render MIDI notes as a video overlay.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="list the tracks, channels and note range of a MIDI file")
    p.add_argument("midi")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("themes", help="list available themes")
    p.set_defaults(func=cmd_themes)

    def common(p):
        p.add_argument("midi", help="the .mid file")
        p.add_argument("-t", "--theme", default="ewi-staff", help="theme name or folder (default: ewi-staff)")
        p.add_argument("-o", "--output", required=True)
        p.add_argument("--size", type=_size, default=(1920, 1080), help="video size, e.g. 3840x2160")
        p.add_argument("--offset", type=float, default=0.0,
                       help="seconds into the video where the MIDI starts (negative if the MIDI starts earlier)")
        p.add_argument("--track", type=int, help="only use this track number (see 'info')")
        p.add_argument("--channel", type=int, help="only use this MIDI channel, 1-16")
        p.add_argument("--transpose", type=int, default=0,
                       help="shift displayed notes by semitones, e.g. 12 to read an octave higher")

    p = sub.add_parser("preview", help="render still frames as PNG to check a theme")
    common(p)
    p.add_argument("--at", type=float, nargs="+", default=[1.0], help="video time(s) in seconds")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("render", help="render the overlay video")
    common(p)
    p.add_argument("-f", "--format", choices=list(export.FORMATS), default="mov",
                   help="mov = ProRes 4444 with transparency (default), webm = VP9 with transparency, "
                        "mp4 = solid background for keying, png = image sequence folder")
    p.add_argument("--fps", type=float, default=60)
    p.add_argument("--start", type=float, default=0.0, help="video time to start rendering from")
    p.add_argument("--duration", type=float, help="seconds to render (default: until the last note + tail)")
    p.add_argument("--tail", type=float, default=2.0, help="extra seconds after the last note")
    p.add_argument("--background", default="#00FF00", help="background colour for mp4")
    p.add_argument("--ffmpeg", help="path to ffmpeg.exe if it is not on PATH")
    p.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    args.func(args)
