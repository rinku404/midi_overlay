"""Staff layout: notes scroll right-to-left across a five-line staff with a clef.

Suits monophonic instruments like the EWI, sax or flute. Each note is a note head on its
real staff position (with ledger lines and accidentals) and a tail showing how long it lasts.
The note lights up when it crosses the playhead.

Pixel values in a theme are for a 1080p frame and scale with the output height.
Values marked "spaces" are multiples of the staff line spacing.
"""

from __future__ import annotations

import bisect
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .. import sprites
from ..midi_reader import Note
from ..theme import Theme, color, merge

DEFAULTS = {
    "font": "fonts/NotoMusic-Regular.ttf",
    "panel": {
        "anchor": "bottom",          # bottom | top | center
        "height": 330,
        "margin_x": 60,
        "margin_y": 50,
        "padding": 36,
        "background": "#0B0F1AB3",   # set alpha to 00 for no panel
        "corner_radius": 28,
    },
    "staff": {
        "clef": "treble",            # treble | treble_8vb | treble_8va | bass
        "line_spacing": 22,
        "line_width": 3,
        "line_color": "#FFFFFFB0",
        "clef_color": "#FFFFFF",
        "offset_y": 0,
    },
    "scroll": {
        "pixels_per_second": 320,
        "playhead": 0.28,            # fraction of the note area, from the left
        "fade_past": 160,
        "fade_future": 120,
    },
    "notes": {
        "color": "#7FD1FF",
        "active_color": "#FFD86B",
        "accidental_color": None,    # defaults to the note colour
        "head_width": 1.45,          # spaces
        "head_height": 1.0,          # spaces
        "head_angle": 20,            # degrees
        "tail_height": 0.42,         # spaces
        "tail_alpha": 0.45,
        "active_tail_alpha": 0.85,
        "glow_radius": 9,
        "accidentals": "sharp",      # sharp | flat
        "ledger_color": "#FFFFFFB0",
        "ledger_width": 2.4,         # spaces
    },
    "playhead": {
        "color": "#FFFFFF50",
        "active_color": "#FFD86B",
        "width": 3,
        "glow_radius": 8,
        "extend": 2.5,               # spaces beyond the top and bottom staff lines
    },
    "label": {
        "show": True,
        "color": "#FFFFFF",
        "size": 46,
        "show_octave": True,
    },
    "transpose": 0,
}

# glyph, diatonic index of the bottom line, glyph height (spaces), glyph centre relative to staff middle (spaces)
CLEFS = {
    "treble": ("\U0001D11E", 2 + 7 * 5, 7.0, -0.25),       # bottom line E4
    "treble_8vb": ("\U0001D120", 2 + 7 * 4, 8.2, 0.35),    # sounds an octave lower
    "treble_8va": ("\U0001D11F", 2 + 7 * 6, 8.2, -0.85),
    "bass": ("\U0001D122", 4 + 7 * 3, 3.3, -0.35),         # bottom line G2
}

LETTERS = "CDEFGAB"
# semitone -> (letter index, accidental) for each spelling preference
SPELLING = {
    "sharp": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (3, 0), (3, 1), (4, 0), (4, 1), (5, 0), (5, 1), (6, 0)],
    "flat": [(0, 0), (1, -1), (1, 0), (2, -1), (2, 0), (3, 0), (4, -1), (4, 0), (5, -1), (5, 0), (6, -1), (6, 0)],
}
ACCIDENTAL_GLYPHS = {1: "♯", -1: "♭"}


class StaffLayout:
    def __init__(self, theme: Theme, width: int, height: int, notes: list[Note], transpose: int = 0):
        self.cfg = cfg = merge(DEFAULTS, theme.data)
        self.width, self.height = width, height
        self.notes = notes
        self.starts = [n.start for n in notes]
        self.max_duration = max((n.duration for n in notes), default=0)
        self.transpose = cfg["transpose"] + transpose
        self.font_path = theme.asset(cfg["font"])
        k = height / 1080  # scale factor from the 1080p design size

        panel, staff, notes_cfg = cfg["panel"], cfg["staff"], cfg["notes"]
        self.s = s = staff["line_spacing"] * k
        try:
            self.clef_glyph, self.clef_ref, clef_height, clef_center = CLEFS[staff["clef"]]
        except KeyError:
            raise ValueError(f"Unknown clef '{staff['clef']}' (available: {', '.join(CLEFS)})") from None
        self.spelling = SPELLING[notes_cfg["accidentals"]]

        # Panel and staff geometry
        ph = panel["height"] * k
        px0, px1 = panel["margin_x"] * k, width - panel["margin_x"] * k
        py0 = {"bottom": height - panel["margin_y"] * k - ph,
               "top": panel["margin_y"] * k,
               "center": (height - ph) / 2}[panel["anchor"]]
        self.panel_box = (round(px0), round(py0), round(px1), round(py0 + ph))
        pad = panel["padding"] * k
        self.mid_y = py0 + ph / 2 + staff["offset_y"] * k
        self.bottom_y = self.mid_y + 2 * s

        self.clef_sprite = sprites.glyph(self.font_path, self.clef_glyph, clef_height * s,
                                         color(staff["clef_color"]), anchor="left")
        clef_x = px0 + pad
        self.clef_pos = (clef_x, self.mid_y + clef_center * s)
        self.notes_left = clef_x + self.clef_sprite.image.width + 1.5 * s
        self.notes_right = px1 - pad
        scroll = cfg["scroll"]
        self.pps = scroll["pixels_per_second"] * k
        self.playhead_x = self.notes_left + scroll["playhead"] * (self.notes_right - self.notes_left)
        self.ahead = (self.notes_right - self.playhead_x) / self.pps + 1
        self.behind = (self.playhead_x - self.notes_left) / self.pps + 1

        # Sprites
        idle, active = color(notes_cfg["color"]), color(notes_cfg["active_color"])
        hw, hh = notes_cfg["head_width"] * s, notes_cfg["head_height"] * s
        glow = notes_cfg["glow_radius"] * k
        self.head = {False: sprites.note_head(hw, hh, notes_cfg["head_angle"], idle),
                     True: sprites.note_head(hw, hh, notes_cfg["head_angle"], active, glow)}
        self.head_w = hw
        self.tail_h = notes_cfg["tail_height"] * s
        self.tail_color = {False: color(notes_cfg["color"], notes_cfg["tail_alpha"]),
                           True: color(notes_cfg["active_color"], notes_cfg["active_tail_alpha"])}
        acc_idle = color(notes_cfg["accidental_color"]) if notes_cfg["accidental_color"] else idle
        self.accidental = {}
        for acc, char in ACCIDENTAL_GLYPHS.items():
            h = 2.6 * s if acc == 1 else 2.3 * s
            self.accidental[(acc, False)] = sprites.glyph(self.font_path, char, h, acc_idle)
            self.accidental[(acc, True)] = sprites.glyph(self.font_path, char, h, active)
        self.ledger_color = color(notes_cfg["ledger_color"])
        self.ledger_half = notes_cfg["ledger_width"] * s / 2
        self.line_w = max(1, round(staff["line_width"] * k))

        playhead = cfg["playhead"]
        extend = playhead["extend"] * s
        self.playhead_top = self.mid_y - 2 * s - extend
        self.playhead_len = round(4 * s + 2 * extend)
        self.playhead_glow = sprites.glow_line(self.playhead_len, max(1, playhead["width"] * k),
                                               playhead["glow_radius"] * k, color(playhead["active_color"]))

        label = cfg["label"]
        self.label_cfg = label
        if label["show"]:
            self.label_font = ImageFont.load_default(size=max(8, round(label["size"] * k)))
            self.octave_font = ImageFont.load_default(size=max(6, round(label["size"] * 0.6 * k)))
            self.label_color = color(label["color"])
            self.label_anchor = (px1 - pad, py0 + pad * 0.6)

        self.static = self._build_static()
        self.fade_mask = self._build_fade_mask()

    # ---- geometry helpers -------------------------------------------------

    def position(self, pitch: int) -> tuple[int, int]:
        """Staff step above the bottom line (2 steps per space) and accidental for a pitch."""
        letter, acc = self.spelling[pitch % 12]
        diatonic = letter + 7 * (pitch // 12)
        return diatonic - self.clef_ref, acc

    def y_of(self, step: int) -> float:
        return self.bottom_y - step * self.s / 2

    # ---- prebuilt layers --------------------------------------------------

    def _build_static(self) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height))
        cfg = self.cfg
        bg = color(cfg["panel"]["background"])
        if bg[3]:
            x0, y0, x1, y1 = self.panel_box
            k = self.height / 1080
            img.alpha_composite(sprites.rounded_rect((x1 - x0, y1 - y0), cfg["panel"]["corner_radius"] * k, bg),
                                (x0, y0))
        draw = ImageDraw.Draw(img)
        line_color = color(cfg["staff"]["line_color"])
        x0 = self.clef_pos[0] - 0.6 * self.s
        for i in range(5):
            y = round(self.mid_y + (i - 2) * self.s)
            draw.rectangle((round(x0), y - self.line_w // 2, round(self.notes_right),
                            y - self.line_w // 2 + self.line_w - 1), fill=line_color)
        self.clef_sprite.paste(img, *self.clef_pos)
        pw = max(1, round(self.cfg["playhead"]["width"] * self.height / 1080))
        px = round(self.playhead_x - pw / 2)
        draw.rectangle((px, round(self.playhead_top), px + pw - 1, round(self.playhead_top) + self.playhead_len),
                       fill=color(self.cfg["playhead"]["color"]))
        return img

    def _build_fade_mask(self) -> Image.Image:
        scroll = self.cfg["scroll"]
        k = self.height / 1080
        left, right = self.notes_left, self.notes_right
        fade_past, fade_future = max(1, scroll["fade_past"] * k), max(1, scroll["fade_future"] * k)
        row = []
        for x in range(self.width):
            if x < left or x > right:
                v = 0
            else:
                v = min(1, (x - left) / fade_past, (right - x) / fade_future)
            row.append(round(255 * v))
        line = Image.new("L", (self.width, 1))
        line.putdata(row)
        return line.resize((self.width, self.height), Image.NEAREST)

    @lru_cache(maxsize=128)
    def _label_sprite(self, pitch: int) -> Image.Image:
        letter, acc = self.spelling[pitch % 12]
        parts = [sprites.text(self.label_font, LETTERS[letter], self.label_color)]
        size = parts[0].height
        if acc:
            parts.append(sprites.glyph(self.font_path, ACCIDENTAL_GLYPHS[acc], size * 0.95, self.label_color).image)
        if self.label_cfg["show_octave"]:
            parts.append(sprites.text(self.octave_font, str(pitch // 12 - 1), self.label_color))
        gap = max(1, size // 12)
        w = sum(p.width for p in parts) + gap * (len(parts) - 1)
        h = max(p.height for p in parts)
        img = Image.new("RGBA", (w, h))
        x = 0
        for i, p in enumerate(parts):
            # the accidental is centred on the letter; letter and octave share the bottom edge
            y = (h - p.height) // 2 if (acc and i == 1) else h - p.height
            img.alpha_composite(p, (x, y))
            x += p.width + gap
        return img

    # ---- per-frame rendering ----------------------------------------------

    def visible(self, t: float) -> list[Note]:
        lo = bisect.bisect_left(self.starts, t - self.behind - self.max_duration)
        hi = bisect.bisect_right(self.starts, t + self.ahead)
        return [n for n in self.notes[lo:hi] if n.end >= t - self.behind]

    def render(self, t: float) -> Image.Image:
        frame = self.static.copy()
        layer = Image.new("RGBA", (self.width, self.height))
        draw = ImageDraw.Draw(layer)
        s, th = self.s, self.tail_h
        placed = []
        sounding = None
        for n in self.visible(t):
            x = self.playhead_x + (n.start - t) * self.pps
            x_end = self.playhead_x + (n.end - t) * self.pps
            is_active = n.start <= t < n.end
            pitch = n.pitch + self.transpose
            step, acc = self.position(pitch)
            y = self.y_of(step)
            draw.rounded_rectangle((x, y - th / 2, max(x_end, x + th), y + th / 2), radius=th / 2,
                                   fill=self.tail_color[is_active])
            # The head waits on the playhead while the note sounds, then leaves with the tail behind it.
            head_x = min(max(self.playhead_x, x), x_end)
            placed.append((head_x, y, step, acc, is_active))
            if is_active and (sounding is None or n.start >= sounding.start):
                sounding = n

        for x, y, step, acc, is_active in placed:
            ledgers = list(range(-2, step - 1, -2)) + list(range(10, step + 1, 2))
            for ls in ledgers:
                ly = round(self.y_of(ls))
                draw.rectangle((round(x - self.ledger_half), ly - self.line_w // 2,
                                round(x + self.ledger_half), ly - self.line_w // 2 + self.line_w - 1),
                               fill=self.ledger_color)
        for x, y, step, acc, is_active in placed:
            self.head[is_active].paste(layer, x, y)
            if acc:
                sprite = self.accidental[(acc, is_active)]
                offset_y = -0.5 * s if acc == -1 else 0
                sprite.paste(layer, x - self.head_w / 2 - 0.25 * s - sprite.image.width / 2, y + offset_y)

        alpha = layer.getchannel("A")
        layer.putalpha(ImageChops.multiply(alpha, self.fade_mask))
        frame.alpha_composite(layer)

        if sounding is not None:
            self.playhead_glow.paste(frame, self.playhead_x, self.playhead_top)
            if self.label_cfg["show"]:
                label = self._label_sprite(sounding.pitch + self.transpose)
                ax, ay = self.label_anchor
                frame.alpha_composite(label, (round(ax - label.width), round(ay)))
        return frame
