"""Shared HelloComp brand helpers for all rendered media.

Source of truth: hellocomp-gtd/public/brand/README.md —
- backdrop: 135° 3-stop gradient #0F1118 → #18243C (50%) → #284C87 (100%)
- accent rule: BLUE + WHITE ONLY (logo blue #2962CD; bright #4D7FC4).
  Amber/yellow is retired (decision 2026-07-19) — never reintroduce it.
- wordmark: hellocomp-white.png on the dark gradient.
- display font: Vafle Condensed (full Czech glyph coverage); body: Inter.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- palette (brand tokens) ---
HC_INK = (15, 17, 24)        # #0F1118
HC_MID = (24, 36, 60)        # #18243C
HC_BLUE = (40, 76, 135)      # #284C87
ACCENT = (41, 98, 205)       # #2962CD logo blue — THE accent
BRIGHT = (77, 127, 196)      # #4D7FC4
WHITE = (255, 255, 255)
MUTED = (188, 202, 224)      # desaturated blue-white for secondary text

CZ_MONTHS = [
    "ledna", "února", "března", "dubna", "května", "června",
    "července", "srpna", "září", "října", "listopadu", "prosince",
]


def font(fonts_dir: Path, name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(fonts_dir / name), size)


def display_font(fonts_dir: Path, size: int) -> ImageFont.FreeTypeFont:
    return font(fonts_dir, "Vafle.ttf", size)


@lru_cache(maxsize=4)
def _gradient_cached(w: int, h: int) -> Image.Image:
    """135° 3-stop brand gradient (per-pixel projection on the diagonal)."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    # 135deg in CSS = top-left -> bottom-right diagonal
    diag = w * math.cos(math.radians(45)) + h * math.sin(math.radians(45))
    cos45 = sin45 = math.cos(math.radians(45))
    for y in range(h):
        for x in range(0, w, 4):  # 4px horizontal bands — invisible on a gradient
            t = (x * cos45 + y * sin45) / diag
            if t <= 0.5:
                a, b, tt = HC_INK, HC_MID, t / 0.5
            else:
                a, b, tt = HC_MID, HC_BLUE, (t - 0.5) / 0.5
            c = tuple(int(p + (q - p) * tt) for p, q in zip(a, b))
            for dx in range(min(4, w - x)):
                px[x + dx, y] = c
    return img


def gradient(w: int, h: int) -> Image.Image:
    return _gradient_cached(w, h).copy()


def wordmark(brand_dir: Path, target_h: int) -> Image.Image:
    """White wordmark scaled to target height (2576x600 source PNG)."""
    img = Image.open(brand_dir / "hellocomp-white.png").convert("RGBA")
    w = int(img.width * target_h / img.height)
    return img.resize((w, target_h), Image.LANCZOS)


def smile(brand_dir: Path, target_w: int, alpha: int = 255) -> Image.Image:
    """White smile mark (rasterized from smile-white.svg) at target width/alpha."""
    img = Image.open(brand_dir / "smile-white.png").convert("RGBA")
    h = int(img.height * target_w / img.width)
    img = img.resize((target_w, h), Image.LANCZOS)
    if alpha < 255:
        a = img.getchannel("A").point(lambda v: v * alpha // 255)
        img.putalpha(a)
    return img


def dot_grid(w: int, h: int, spacing: int = 56, r: int = 2,
             alpha: int = 26) -> Image.Image:
    """Subtle brand texture: faint bright-blue dot grid."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(spacing // 2, h, spacing):
        for x in range(spacing // 2, w, spacing):
            d.ellipse([x - r, y - r, x + r, y + r], fill=(*BRIGHT, alpha))
    return img


def rounded(size: tuple[int, int], radius: int, color) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=color)
    return img


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont,
         max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        cand = f"{line} {word}".strip()
        if draw.textlength(cand, font=fnt) <= max_width:
            line = cand
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int,
             sizes: tuple[int, ...], mk_font) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Try sizes descending until text fits max_lines; truncate as last resort."""
    for size in sizes:
        fnt = mk_font(size)
        lines = wrap(draw, text, fnt, max_width)
        if len(lines) <= max_lines:
            return fnt, lines
    fnt = mk_font(sizes[-1])
    lines = wrap(draw, text, fnt, max_width)[:max_lines]
    lines[-1] = lines[-1].rstrip(".,") + "…"
    return fnt, lines


def czech_date(date) -> str:
    return f"{date.day}. {CZ_MONTHS[date.month - 1]} {date.year}"
