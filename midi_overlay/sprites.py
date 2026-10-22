"""Small anti-aliased images (note heads, glyphs, glows) that layouts paste onto each frame."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SUPERSAMPLE = 4


class Sprite:
    """An RGBA image plus the point inside it that should land on the target position."""

    def __init__(self, image: Image.Image, anchor: tuple[float, float]):
        self.image = image
        self.anchor = anchor

    def paste(self, canvas: Image.Image, x: float, y: float):
        canvas.alpha_composite(self.image, (round(x - self.anchor[0]), round(y - self.anchor[1])))


def glyph(font_path: Path, char: str, height: float, fill, anchor: str = "center") -> Sprite:
    """Renders one font glyph scaled so its ink is `height` pixels tall."""
    probe = ImageFont.truetype(str(font_path), 200)
    x0, y0, x1, y1 = probe.getbbox(char)
    size = max(1, round(200 * height / max(1, y1 - y0)))
    font = ImageFont.truetype(str(font_path), size)
    x0, y0, x1, y1 = font.getbbox(char)
    pad = 2
    img = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad))
    ImageDraw.Draw(img).text((pad - x0, pad - y0), char, font=font, fill=fill)
    w, h = img.size
    anchors = {"center": (w / 2, h / 2), "left": (0, h / 2), "right": (w, h / 2)}
    return Sprite(img, anchors[anchor])


def text(font: ImageFont.FreeTypeFont, value: str, fill) -> Image.Image:
    x0, y0, x1, y1 = font.getbbox(value)
    img = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)))
    ImageDraw.Draw(img).text((-x0, -y0), value, font=font, fill=fill)
    return img


def note_head(width: float, height: float, angle: float, fill, glow_radius: float = 0, glow_fill=None) -> Sprite:
    """A tilted oval note head, optionally surrounded by a soft glow."""
    ss = SUPERSAMPLE
    margin = glow_radius * 3 + 4
    size = (round((width + 2 * margin) * ss), round((width + 2 * margin) * ss))
    cx, cy = size[0] / 2, size[1] / 2

    oval = Image.new("L", size)
    ImageDraw.Draw(oval).ellipse((cx - width * ss / 2, cy - height * ss / 2,
                                  cx + width * ss / 2, cy + height * ss / 2), fill=255)
    oval = oval.rotate(angle, resample=Image.BICUBIC, center=(cx, cy))
    final_size = (round(size[0] / ss), round(size[1] / ss))
    mask = oval.resize(final_size, Image.LANCZOS)

    img = Image.new("RGBA", final_size)
    if glow_radius > 0:
        glow = Image.new("RGBA", final_size, glow_fill or fill)
        glow_mask = mask.filter(ImageFilter.GaussianBlur(glow_radius))
        glow_mask = glow_mask.point(lambda v: min(255, v * 2))
        glow.putalpha(glow_mask)
        img.alpha_composite(glow)
    solid = Image.new("RGBA", final_size, fill)
    solid.putalpha(mask.point(lambda v: v * fill[3] // 255))
    img.alpha_composite(solid)
    return Sprite(img, (final_size[0] / 2, final_size[1] / 2))


def rounded_rect(size: tuple[int, int], radius: float, fill) -> Image.Image:
    ss = SUPERSAMPLE
    w, h = size
    mask = Image.new("L", (w * ss, h * ss))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius * ss, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    img = Image.new("RGBA", (w, h), fill)
    img.putalpha(mask.point(lambda v: v * fill[3] // 255))
    return img


def glow_line(length: int, thickness: float, radius: float, fill) -> Sprite:
    """A vertical line with a soft glow, used for the playhead when a note is sounding."""
    pad = round(radius * 3)
    w = round(thickness) + 2 * pad
    img = Image.new("RGBA", (w, length + 2 * pad))
    mask = Image.new("L", img.size)
    ImageDraw.Draw(mask).rectangle((pad, pad, pad + round(thickness) - 1, pad + length), fill=255)
    glow = mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, v * 2))
    layer = Image.new("RGBA", img.size, fill)
    layer.putalpha(glow)
    img.alpha_composite(layer)
    core = Image.new("RGBA", img.size, fill)
    core.putalpha(mask)
    img.alpha_composite(core)
    return Sprite(img, (w / 2, pad))
