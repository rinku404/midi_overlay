"""Interactive menu: pick a MIDI file from input/, choose the options, render into output/."""

from __future__ import annotations

from pathlib import Path

from . import export, layouts, midi_reader, theme as themes
from .theme import PROJECT_ROOT

INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

FORMAT_HELP = {
    "mov": "ProRes 4444, transparent (Resolve, Premiere, Vegas, Final Cut)",
    "webm": "VP9, transparent, small files (Resolve, Shotcut, Kdenlive, OBS)",
    "mp4": "green background, for editors without transparency",
    "png": "folder of transparent PNG frames",
}


def choose(title: str, options: list[str], default: int = 0) -> int:
    """Shows a numbered list and returns the chosen index. Enter picks the default."""
    print(f"\n{title}")
    for i, option in enumerate(options, 1):
        marker = " (default)" if i - 1 == default else ""
        print(f"  {i}. {option}{marker}")
    while True:
        answer = input("> ").strip()
        if not answer:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print(f"Type a number from 1 to {len(options)}, or press Enter for the default.")


def ask_number(prompt: str, default: float, kind=float):
    while True:
        answer = input(f"{prompt} [{default}]: ").strip().replace(",", ".")
        if not answer:
            return default
        try:
            return kind(answer)
        except ValueError:
            print("That is not a number.")


def run():
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in (".mid", ".midi"))
    if not files:
        print(f"No MIDI files found. Put your .mid files in:\n  {INPUT_DIR}")
        return

    midi = files[choose("Which MIDI file?", [p.name for p in files])]
    notes, tracks = midi_reader.load(str(midi))
    used = [t for t in tracks if t.note_count]
    if len(used) > 1:
        names = [f"{t.name} ({t.note_count} notes)" for t in used]
        pick = choose("Which track?", ["All tracks"] + names)
        if pick:
            notes = midi_reader.filter_notes(notes, track=used[pick - 1].index)
    if not notes:
        print("That file has no notes.")
        return

    theme_dirs = themes.list_themes()
    theme_dir = theme_dirs[choose("Which theme?", [f"{d.name}  ({themes.load(str(d)).name})" for d in theme_dirs])] \
        if len(theme_dirs) > 1 else theme_dirs[0]
    fmt_names = list(export.FORMATS)
    fmt = fmt_names[choose("Which output format?", [f"{f}: {FORMAT_HELP[f]}" for f in fmt_names])]

    print("\nPress Enter to keep each default.")
    offset = ask_number("Seconds into your video where the MIDI starts", 0.0)
    fps = ask_number("Frames per second", 60, int)
    transpose = ask_number("Transpose displayed notes (semitones)", 0, int)

    layout = layouts.create(themes.load(str(theme_dir)), 1920, 1080, notes, transpose)
    duration = max(n.end for n in notes) + offset + 2.0
    out = OUTPUT_DIR / f"{midi.stem}_{theme_dir.name}"
    if fmt != "png":
        out = out.with_suffix(export.FORMATS[fmt][0])
    print(f"\nRendering {duration:.1f}s to {out}")
    result = export.render_video(layout, out, fmt, fps, 0.0, duration, offset)
    print(f"Done: {result or out}")
