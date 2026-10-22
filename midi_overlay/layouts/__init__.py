"""Layouts decide how notes are drawn. A theme picks one with its "layout" key and styles it."""

from __future__ import annotations

from ..midi_reader import Note
from ..theme import Theme
from .staff import StaffLayout

LAYOUTS = {
    "staff": StaffLayout,
}


def create(theme: Theme, width: int, height: int, notes: list[Note], transpose: int = 0):
    try:
        cls = LAYOUTS[theme.layout]
    except KeyError:
        raise ValueError(f"Unknown layout '{theme.layout}' (available: {', '.join(LAYOUTS)})") from None
    return cls(theme, width, height, notes, transpose)
