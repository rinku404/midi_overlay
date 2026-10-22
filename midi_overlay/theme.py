"""Theme loading. A theme is a folder with a theme.json file plus any images or fonts it uses."""

from __future__ import annotations

import copy
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = PROJECT_ROOT / "themes"


class Theme:
    def __init__(self, folder: Path, data: dict):
        self.folder = folder
        self.data = data

    @property
    def name(self) -> str:
        return self.data.get("name", self.folder.name)

    @property
    def layout(self) -> str:
        return self.data.get("layout", "staff")

    def asset(self, relative: str) -> Path:
        """Finds a file next to the theme first, then relative to the project root."""
        for base in (self.folder, PROJECT_ROOT):
            candidate = base / relative
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Theme '{self.name}' refers to missing file: {relative}")


def list_themes() -> list[Path]:
    return sorted(p.parent for p in THEMES_DIR.glob("*/theme.json"))


def load(name_or_path: str) -> Theme:
    folder = Path(name_or_path)
    if not (folder / "theme.json").exists():
        folder = THEMES_DIR / name_or_path
    file = folder / "theme.json"
    if not file.exists():
        available = ", ".join(p.name for p in list_themes()) or "none"
        raise FileNotFoundError(f"Theme not found: {name_or_path} (available: {available})")
    with open(file, encoding="utf-8") as f:
        return Theme(folder.resolve(), json.load(f))


def merge(defaults: dict, overrides: dict) -> dict:
    """Deep-merges theme values over a layout's defaults."""
    result = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def color(value: str | list | tuple, alpha: float = 1.0) -> tuple[int, int, int, int]:
    """Parses '#RRGGBB', '#RRGGBBAA' or [r, g, b(, a)] into an RGBA tuple, scaling alpha."""
    if isinstance(value, str):
        h = value.lstrip("#")
        if len(h) not in (6, 8):
            raise ValueError(f"Bad colour: {value}")
        parts = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
    else:
        parts = list(value)
    if len(parts) == 3:
        parts.append(255)
    r, g, b, a = parts
    return r, g, b, round(a * alpha)
