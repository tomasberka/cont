"""Apple-emoji style topic icons — modern, rounded, solid, 3D-feeling.

Style: thick solid shapes with radial gradient + soft white highlight + drop shadow.
Each icon is a single solid blob (not thin outlines) — Apple emoji aesthetic.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import media_brand as B

SS = 2  # supersample factor

ACCENT = B.ACCENT
BRIGHT = B.BRIGHT
DETAIL = (180, 200, 230, 255)
DETAIL_L = 200  # for L-mode mask


@lru_cache(maxsize=128)
def _radial_fill(size: int) -> Image.Image:
    """Soft radial gradient: light center → darker edge."""
    s = size * SS * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s // 2
    for i in range(cx, 0, -3):
        t = i / cx
        r = int(BRIGHT[0] + (ACCENT[0] - BRIGHT[0]) * t)
        g = int(BRIGHT[1] + (ACCENT[1] - BRIGHT[1]) * t)
        b = int(BRIGHT[2] + (ACCENT[2] - BRIGHT[2]) * t)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(r, g, b, 255))
    return img.filter(ImageFilter.GaussianBlur(SS * 2))


@lru_cache(maxsize=128)
def _highlight(size: int) -> Image.Image:
    """Soft white highlight for top-left 3D pop."""
    s = int(size * SS * 0.85)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = int(s * 0.3)
    cy = int(s * 0.3)
    for i in range(min(cx, cy), 0, -2):
        t = i / min(cx, cy)
        a = int(100 * (1 - t) ** 2)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(255, 255, 255, a))
    return img.filter(ImageFilter.GaussianBlur(SS * 3))


@lru_cache(maxsize=128)
def _shadow(size: int) -> Image.Image:
    """Soft dark drop shadow."""
    s = int(size * SS * 0.8)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s // 2
    for i in range(cy, 0, -2):
        t = i / cy
        a = int(150 * (1 - t) ** 2)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(0, 0, 0, a))
    return img.filter(ImageFilter.GaussianBlur(SS * 4))


def render_emoji(icon: str, size: int = 500) -> Image.Image:
    """Render one Apple-style emoji icon at the given size.
    Returns an RGBA image (square, transparent background).

    Pipeline:
      1. Draw the SOLID base shape (filled) on RGBA canvas in WHITE
      2. Draw same shape on L-mode mask in white (255)
      3. Composite radial gradient through mask → blue gradient fill
      4. Composite soft white highlight on top-left
      5. Composite soft dark shadow below
      6. Downsample with LANCZOS
    """
    draw_fn = EMOJI_DRAWS.get(icon, _draw_bolt)
    s_canvas = int(size * SS * 1.6)
    canvas = Image.new("RGBA", (s_canvas, s_canvas), (0, 0, 0, 0))
    mask = Image.new("L", (s_canvas, s_canvas), 0)

    cx = cy = s_canvas / 2
    s_draw = size * SS

    # Draw shape: WHITE fill on RGBA canvas, white (255) on L mask
    draw_fn(ImageDraw.Draw(canvas), cx, cy, s_draw, (255, 255, 255, 255))
    draw_fn(ImageDraw.Draw(mask), cx, cy, s_draw, 255)

    # Radial gradient through mask
    fill = _radial_fill(size).resize((s_canvas, s_canvas), Image.LANCZOS)
    fill_canvas = Image.new("RGBA", (s_canvas, s_canvas), (0, 0, 0, 0))
    fill_canvas.paste(fill, (0, 0), mask)

    # Shadow (offset down)
    sh = _shadow(size).resize((s_canvas, s_canvas), Image.LANCZOS)
    shadow_canvas = Image.new("RGBA", (s_canvas, s_canvas), (0, 0, 0, 0))
    shadow_offset = int(size * SS * 0.12)
    shadow_canvas.paste(sh, ((s_canvas - sh.width) // 2,
                              (s_canvas - sh.height) // 2 + shadow_offset), sh)

    # Highlight (top-left)
    hl = _highlight(size).resize((s_canvas, s_canvas), Image.LANCZOS)
    hl_canvas = Image.new("RGBA", (s_canvas, s_canvas), (0, 0, 0, 0))
    hl_canvas.paste(hl, ((s_canvas - hl.width) // 2 - int(size * SS * 0.05),
                          (s_canvas - hl.height) // 2 - int(size * SS * 0.15)), hl)

    # Composite layers
    result = Image.new("RGBA", (s_canvas, s_canvas), (0, 0, 0, 0))
    result.alpha_composite(shadow_canvas)
    result.alpha_composite(fill_canvas)
    result.alpha_composite(hl_canvas)

    # Downsample
    out_size = int(s_canvas / SS)
    return result.resize((out_size, out_size), Image.LANCZOS)


# ── emoji draw functions ─────────────────────────────────────────────
# Each: draw_fn(d, cx, cy, s, fill_color) — draws a SOLID FILLED shape
# The shape acts as a mask for the radial gradient + receives detail overlays.

def _draw_headphones(d, cx, cy, s, c):
    """Solid headphones: thick band + two big rounded cups."""
    # band — thick filled arc (outer + inner radius)
    outer_r = s * 0.55
    inner_r = s * 0.35
    band_h = cy - s * 0.1  # bottom of band
    d.pieslice([cx - outer_r, cy - outer_r - s * 0.1, cx + outer_r, cy + outer_r],
               start=180, end=360, fill=c)
    d.pieslice([cx - inner_r, cy - inner_r - s * 0.1, cx + inner_r, cy + inner_r],
               start=0, end=360, fill=(0, 0, 0, 0) if isinstance(c, tuple) else 0)
    # ear cups — large solid circles
    cup_r = s * 0.28
    for side in (-1, 1):
        x = cx + side * outer_r * 0.85
        d.ellipse([x - cup_r, cy - cup_r * 0.3, x + cup_r, cy + cup_r * 1.3],
                  fill=c)


def _draw_computer(d, cx, cy, s, c):
    """Solid monitor + stand + base."""
    # monitor body (solid rounded rect)
    mw, mh = s * 1.1, s * 0.75
    d.rounded_rectangle(
        [cx - mw / 2, cy - s * 0.5, cx + mw / 2, cy - s * 0.5 + mh],
        radius=s * 0.1, fill=c)
    # stand neck
    nw, nh = s * 0.15, s * 0.2
    d.rectangle([cx - nw / 2, cy - s * 0.5 + mh, cx + nw / 2,
                 cy - s * 0.5 + mh + nh], fill=c)
    # base
    bw = s * 0.5
    d.rounded_rectangle(
        [cx - bw / 2, cy - s * 0.5 + mh + nh - s * 0.02, cx + bw / 2,
         cy - s * 0.5 + mh + nh + s * 0.06],
        radius=s * 0.03, fill=c)


def _draw_globe(d, cx, cy, s, c):
    """Solid sphere."""
    r = s * 0.6
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def _draw_rocket(d, cx, cy, s, c):
    """Solid rocket body + nose + fins."""
    # main body
    bw = s * 0.4
    bh = s * 0.7
    d.rounded_rectangle(
        [cx - bw / 2, cy - bh * 0.4, cx + bw / 2, cy + bh * 0.5],
        radius=s * 0.2, fill=c)
    # nose cone (triangle on top)
    d.polygon([(cx - bw / 2, cy - bh * 0.1),
               (cx, cy - bh * 0.65), (cx + bw / 2, cy - bh * 0.1)], fill=c)
    # fins
    d.polygon([(cx - bw / 2, cy + bh * 0.15),
               (cx - bw / 2 - s * 0.2, cy + bh * 0.55),
               (cx - bw / 2, cy + bh * 0.45)], fill=c)
    d.polygon([(cx + bw / 2, cy + bh * 0.15),
               (cx + bw / 2 + s * 0.2, cy + bh * 0.55),
               (cx + bw / 2, cy + bh * 0.45)], fill=c)


def _draw_chip(d, cx, cy, s, c):
    """Solid chip body with pins."""
    body = s * 0.55
    d.rounded_rectangle(
        [cx - body, cy - body, cx + body, cy + body],
        radius=s * 0.12, fill=c)
    # pins (4 sides, 3 each)
    pin_len = s * 0.2
    pin_w = s * 0.08
    for off in (-0.5, 0, 0.5):
        d.rectangle([cx + off * body - pin_w / 2, cy - body - pin_len,
                     cx + off * body + pin_w / 2, cy - body], fill=c)
        d.rectangle([cx + off * body - pin_w / 2, cy + body,
                     cx + off * body + pin_w / 2, cy + body + pin_len], fill=c)
    for off in (-0.5, 0, 0.5):
        d.rectangle([cx - body - pin_len, cy + off * body - pin_w / 2,
                     cx - body, cy + off * body + pin_w / 2], fill=c)
        d.rectangle([cx + body, cy + off * body - pin_w / 2,
                     cx + body + pin_len, cy + off * body + pin_w / 2], fill=c)


def _draw_gamepad(d, cx, cy, s, c):
    """Solid gamepad body."""
    bw, bh = s * 1.2, s * 0.65
    d.rounded_rectangle(
        [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2],
        radius=s * 0.25, fill=c)


def _draw_monitor(d, cx, cy, s, c):
    """Solid screen + stand + base."""
    sw, sh = s * 1.1, s * 0.7
    d.rounded_rectangle(
        [cx - sw / 2, cy - s * 0.45, cx + sw / 2, cy - s * 0.45 + sh],
        radius=s * 0.08, fill=c)
    # stand
    d.rectangle([cx - s * 0.06, cy - s * 0.45 + sh, cx + s * 0.06,
                 cy - s * 0.45 + sh + s * 0.18], fill=c)
    # base
    d.rounded_rectangle(
        [cx - s * 0.3, cy - s * 0.45 + sh + s * 0.12, cx + s * 0.3,
         cy - s * 0.45 + sh + s * 0.22],
        radius=s * 0.05, fill=c)


def _draw_phone(d, cx, cy, s, c):
    """Solid phone body."""
    pw, ph = s * 0.55, s * 1.0
    d.rounded_rectangle(
        [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2],
        radius=s * 0.12, fill=c)


def _draw_disc(d, cx, cy, s, c):
    """Solid floppy disk body."""
    dw, dh = s * 0.8, s * 0.95
    d.rounded_rectangle(
        [cx - dw / 2, cy - dh / 2, cx + dw / 2, cy + dh / 2],
        radius=s * 0.06, fill=c)


def _draw_shield(d, cx, cy, s, c):
    """Solid shield shape."""
    d.polygon([(cx, cy - s * 0.6), (cx + s * 0.5, cy - s * 0.25),
               (cx + s * 0.42, cy + s * 0.35), (cx, cy + s * 0.6),
               (cx - s * 0.42, cy + s * 0.35), (cx - s * 0.5, cy - s * 0.25)],
              fill=c)


def _draw_bolt(d, cx, cy, s, c):
    """Solid lightning bolt."""
    d.polygon([(cx + s * 0.08, cy - s * 0.6), (cx - s * 0.35, cy + s * 0.1),
               (cx - s * 0.05, cy + s * 0.1), (cx - s * 0.15, cy + s * 0.6),
               (cx + s * 0.32, cy - s * 0.15), (cx + s * 0.02, cy - s * 0.15)],
              fill=c)


def _draw_keyboard(d, cx, cy, s, c):
    """Solid keyboard body."""
    kw, kh = s * 1.3, s * 0.55
    d.rounded_rectangle(
        [cx - kw / 2, cy - kh / 2, cx + kw / 2, cy + kh / 2],
        radius=s * 0.08, fill=c)


def _draw_mouse(d, cx, cy, s, c):
    """Solid mouse body."""
    mw, mh = s * 0.55, s * 0.9
    d.rounded_rectangle(
        [cx - mw / 2, cy - mh / 2, cx + mw / 2, cy + mh / 2],
        radius=mw / 2, fill=c)


def _draw_wifi(d, cx, cy, s, c):
    """Solid wifi — three concentric arcs filled."""
    # Draw as filled pie segments stacked
    for r_frac, start, end in [
        (0.6, 200, 340), (0.45, 200, 340), (0.3, 200, 340),
    ]:
        r = s * r_frac
        w = s * 0.1
        d.pieslice([cx - r, cy - r * 0.8, cx + r, cy + r * 0.4],
                   start=start, end=end, fill=c)
        # cut inner
        ri = r - w
        d.pieslice([cx - ri, cy - ri * 0.8, cx + ri, cy + ri * 0.4],
                   start=start, end=end,
                   fill=(0, 0, 0, 0) if isinstance(c, tuple) else 0)
    # dot at bottom
    dot_r = s * 0.08
    d.ellipse([cx - dot_r, cy + s * 0.15, cx + dot_r, cy + s * 0.31], fill=c)


EMOJI_DRAWS = {
    "chip": _draw_chip, "gamepad": _draw_gamepad, "headphones": _draw_headphones,
    "monitor": _draw_monitor, "globe": _draw_globe, "phone": _draw_phone,
    "disc": _draw_disc, "computer": _draw_computer, "shield": _draw_shield,
    "rocket": _draw_rocket, "bolt": _draw_bolt, "keyboard": _draw_keyboard,
    "mouse": _draw_mouse, "wifi": _draw_wifi,
}
