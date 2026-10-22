# MIDI Overlay

Turns a MIDI recording into a transparent video of the notes you played, so you can lay it over
footage of yourself playing. Each look is a **theme**: a folder you can copy and restyle.

The first theme is **ewi-staff**. Notes scroll right to left across a treble staff. Each note head
sits on its real staff position, with ledger lines and sharps or flats, and has a tail showing how
long the note lasts. A note lights up while it crosses the playhead, and its name shows in the
corner (for example `F♯4`).

## Setup on Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/ and tick **Add python.exe to PATH**.
2. Open a terminal (PowerShell) in this folder and run:

   ```powershell
   pip install -r requirements.txt
   ```

   This installs `mido` (reads MIDI), `Pillow` (draws frames) and `imageio-ffmpeg` (a bundled ffmpeg).
   If you already have ffmpeg on your PATH (`winget install ffmpeg`), that one is used instead.

3. Try it with the demo melody:

   ```powershell
   python -m midi_overlay render examples\ewi_demo.mid -o demo.mov
   ```

## Quick start: the menu

1. Put your `.mid` files in the `input` folder.
2. Double-click `render.bat` (or run `python -m midi_overlay` with no options).
3. Pick the file, track, theme and format from the numbered lists. Press Enter to accept a default.

The video is saved in the `output` folder as `<file>_<theme>.mov` (or `.webm`, `.mp4`, or a folder of PNGs).
Rendered files in `output` are not tracked by git.

## Everyday use from the command line

```powershell
# What is in the file: tracks, channels, note range, length
python -m midi_overlay info my_take.mid

# Check the look on a few still frames before rendering (times are in seconds)
python -m midi_overlay preview my_take.mid -o check.png --at 5 12.5 30

# Render the overlay
python -m midi_overlay render my_take.mid -o overlay.mov
```

Useful options for `render` and `preview`:

| Option | What it does |
|---|---|
| `-t ewi-staff` | Theme name (a folder in `themes\`) or a path to a theme folder |
| `--offset 2.35` | Seconds into your video where the MIDI starts. Use a negative number if the MIDI started first |
| `--transpose 12` | Shift the displayed notes, e.g. to read an octave higher or match a transposing fingering |
| `--track 1` / `--channel 1` | Use only one track or channel (see `info`) |
| `--size 3840x2160` | Output size; the theme scales with it (default 1920x1080) |
| `--fps 30` | Match your project's frame rate (default 60) |
| `-f mov` | ProRes 4444 with transparency. Default; works in DaVinci Resolve, Premiere, Vegas, Final Cut. Large files |
| `-f webm` | VP9 with transparency. Small files; works in Resolve, Shotcut, Kdenlive, OBS |
| `-f mp4` | Solid background (green by default, `--background`) for editors without alpha support |
| `-f png` | A folder of transparent PNG frames |
| `--start`, `--duration` | Render only part of the video |

### Lining the overlay up with your video

The simplest way: start the MIDI recording and the camera, then play one short, sharp note before
the music. In your editor, find the frame where that note is heard and note its time. Run `info`
or `preview` to find when the first note starts in the MIDI. The difference is your `--offset`.
You can also render with offset 0 and slide the overlay clip in the editor until the first note lines up.

## Making your own theme

Copy `themes\ewi-staff` to a new folder, for example `themes\my-theme`, and edit `theme.json`.
Then use `-t my-theme`. Any value you leave out keeps the default shown below.
Pixel sizes are for a 1080p frame and scale automatically. "Spaces" means multiples of the gap
between staff lines.

```jsonc
{
  "name": "My Theme",
  "layout": "staff",
  "font": "fonts/NotoMusic-Regular.ttf",    // music font for the clef and accidentals
  "panel": {
    "anchor": "bottom",                     // bottom | top | center
    "height": 330, "margin_x": 60, "margin_y": 50, "padding": 36,
    "background": "#0B0F1AB3",              // #RRGGBBAA; use alpha 00 for no panel
    "corner_radius": 28
  },
  "staff": {
    "clef": "treble",                       // treble | treble_8vb | treble_8va | bass
    "line_spacing": 22, "line_width": 3,
    "line_color": "#FFFFFFB0", "clef_color": "#FFFFFF",
    "offset_y": 0
  },
  "scroll": {
    "pixels_per_second": 320,               // faster = notes more spread out
    "playhead": 0.28,                       // where the playhead sits, 0 = left, 1 = right
    "fade_past": 160, "fade_future": 120
  },
  "notes": {
    "color": "#7FD1FF", "active_color": "#FFD86B", "accidental_color": null,
    "head_width": 1.45, "head_height": 1.0, "head_angle": 20,   // spaces, degrees
    "tail_height": 0.42, "tail_alpha": 0.45, "active_tail_alpha": 0.85,
    "glow_radius": 9,
    "accidentals": "sharp",                 // sharp | flat
    "ledger_color": "#FFFFFFB0", "ledger_width": 2.4
  },
  "playhead": {
    "color": "#FFFFFF50", "active_color": "#FFD86B",
    "width": 3, "glow_radius": 8, "extend": 2.5
  },
  "label": { "show": true, "color": "#FFFFFF", "size": 46, "show_octave": true },
  "transpose": 0
}
```

## Project layout

```
midi_overlay/        the program
  midi_reader.py     MIDI file -> notes timed in seconds (handles tempo changes)
  theme.py           loads theme folders
  layouts/staff.py   the scrolling staff look
  sprites.py         anti-aliased note heads, glyphs and glows
  export.py          sends frames to ffmpeg
  menu.py            the interactive menu
themes/ewi-staff/    the EWI theme
fonts/               Noto Music (SIL Open Font License, see fonts/OFL.txt)
examples/            demo MIDI and the script that makes it
input/               your .mid files for the menu
output/              rendered videos (ignored by git)
render.bat           double-click to open the menu
```

## Not done yet

- Breath (CC2) and pitch bend from the EWI are read past, not drawn. They could drive the glow or bend the tail later.
- Other layouts (falling notes, guitar tab, symbol-based themes like an ocarina staff) slot in under `midi_overlay/layouts/`.
- A window with live preview and a packaged `.exe`.
