"""Topic icons + clean animated overlay for reels — 100 % local (Pillow + FFmpeg).

Redesign notes (v2): the overlay is a SMALL, crisp, glass badge pinned to the
empty top-center band of the reel — never over the headline or product. Icons are
drawn at 3x resolution and downsampled (true anti-aliasing), with rounded line
caps and a consistent stroke weight. Animation is deliberately subtle: gentle
bob, soft glow pulse, a slow rotating accent ring and three faint orbit dots.
No dust field, no big central cluster. Brand palette stays blue + white.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import media_brand as B
from .feed import strip_diacritics

SS = 3  # supersample factor for crisp icons

# ---- topic -> icon ----
PILLAR_ICON = {
    "Kyberbezpečnost": "shield",
    "Procesory & čipy": "chip",
    "Grafika & gaming": "gamepad",
    "Periferie": "monitor",
    "Internet & síť": "globe",
    "Mobil & telefon": "phone",
    "Data & paměť": "disc",
    "Počítače & software": "computer",
    "Audio & video": "headphones",
    "Produktový tip": "bolt",
}

ICON_TERMS: list[tuple[str, tuple[str, ...]]] = [
    ("rocket", ("raketa", "nasa", "sputnik", "druzice", "satellite", "vesmir",
                "voyager", "obeznou", "orbital", "kosmic", "apollo", "mesic")),
    ("gamepad", ("playstation", "nintendo", "xbox", "videohra", "video game",
                 "konzole", "atari", "commodore", "gpu", "graficka", "nvidia")),
    ("shield", ("virus", "hacker", "kyber", "cyber", "security", "antivir")),
    ("disc", ("disketa", "floppy", "usb", "pamet", "disk", "storage", "memory",
              "pevny", "ssd")),
    ("chip", ("procesor", "processor", "chip", "cpu", "intel", "amd",
              "tranzistor", "polovodic", "semiconductor", "mikroprocesor")),
    ("globe", ("internet", "web", "www", "wifi", "wi-fi", "router", "sit",
               "network", "arpanet", "ethernet", "browser", "prohlizec")),
    ("phone", ("telefon", "smartphone", "iphone", "mobil", "phone")),
    ("monitor", ("monitor", "displej", "display", "televize", "television")),
    ("headphones", ("sluchatka", "headphones", "audio", "radio", "zvuk", "sound")),
    ("keyboard", ("klavesnice", "keyboard")),
    ("mouse", ("mys", "mouse")),
    ("computer", ("pocitac", "computer", "ibm", "macintosh", "apple", "microsoft",
                  "windows", "linux", "software", "programator", "algoritmus",
                  "turing", "notebook", "laptop", "operacni")),
]

_WORD = {"mys", "web", "sit", "cpu", "usb", "chip", "gpu", "ssd", "disk"}


def _hit(text: str, term: str) -> bool:
    if term in _WORD:
        return f" {term} " in f" {text} " or text == term
    return term in text


def pick_icon(fact_keywords: list[str], pillar: str, fact_text: str = "") -> str:
    text = strip_diacritics(
        " ".join(fact_keywords or []) + " " + (fact_text or "")).lower()
    for icon, terms in ICON_TERMS:
        for term in terms:
            if _hit(text, term):
                return icon
    return PILLAR_ICON.get(pillar, "bolt")


# ---- icon drawing (stroke-based, rounded caps) ----
def _line(d, p1, p2, c, lw):
    d.line([p1, p2], fill=c, width=lw)
    r = lw / 2
    for (x, y) in (p1, p2):
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)


def _chip(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=s * 0.2, outline=c, width=lw)
    i = s * 0.5
    d.rectangle([cx - i, cy - i, cx + i, cy + i], outline=c, width=lw)
    pin = s * 0.22
    for off in (-s * 0.55, 0.0, s * 0.55):
        _line(d, (cx + off, cy - s), (cx + off, cy - s - pin), c, lw)
        _line(d, (cx + off, cy + s), (cx + off, cy + s + pin), c, lw)
        _line(d, (cx - s, cy + off), (cx - s - pin, cy + off), c, lw)
        _line(d, (cx + s, cy + off), (cx + s + pin, cy + off), c, lw)


def _gamepad(d, cx, cy, s, c, lw):
    w, h = s * 1.45, s * 0.85
    d.rounded_rectangle([cx - w, cy - h, cx + w, cy + h], radius=h * 0.5, outline=c, width=lw)
    _line(d, (cx - w * 0.6, cy - h * 0.42), (cx - w * 0.6, cy + h * 0.42), c, lw)
    _line(d, (cx - w * 0.85, cy), (cx - w * 0.35, cy), c, lw)
    r = s * 0.2
    for ox, oy in ((w * 0.45, -h * 0.42), (w * 0.75, h * 0.1)):
        d.ellipse([cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r], outline=c, width=lw)


def _headphones(d, cx, cy, s, c, lw):
    d.arc([cx - s * 0.75, cy - s, cx + s * 0.75, cy + s * 0.9], start=180, end=360, fill=c, width=lw)
    cup = s * 0.42
    for side in (-1, 1):
        x = cx + side * s * 0.72
        d.rounded_rectangle([x - cup * 0.4, cy + s * 0.42 - cup * 0.5,
                             x + cup * 0.4, cy + s * 0.42 + cup * 0.5],
                            radius=cup * 0.4, outline=c, width=lw)


def _monitor(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s, cy - s * 0.8, cx + s, cy + s * 0.5], radius=s * 0.12, outline=c, width=lw)
    _line(d, (cx, cy + s * 0.5), (cx, cy + s * 0.92), c, lw)
    _line(d, (cx - s * 0.45, cy + s * 0.92), (cx + s * 0.45, cy + s * 0.92), c, lw)


def _globe(d, cx, cy, s, c, lw):
    d.ellipse([cx - s, cy - s, cx + s, cy + s], outline=c, width=lw)
    d.ellipse([cx - s * 0.42, cy - s, cx + s * 0.42, cy + s], outline=c, width=lw)
    _line(d, (cx - s, cy), (cx + s, cy), c, lw)
    d.arc([cx - s, cy - s * 0.5, cx + s, cy + s * 0.5], start=0, end=180, fill=c, width=lw)
    d.arc([cx - s, cy - s * 0.5, cx + s, cy + s * 0.5], start=180, end=360, fill=c, width=lw)


def _phone(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s * 0.6, cy - s, cx + s * 0.6, cy + s], radius=s * 0.35, outline=c, width=lw)
    _line(d, (cx - s * 0.25, cy + s * 0.72), (cx + s * 0.25, cy + s * 0.72), c, lw)


def _disc(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s, cy - s * 0.85, cx + s, cy + s * 0.85], radius=s * 0.2, outline=c, width=lw)
    d.ellipse([cx - s * 0.4, cy - s * 0.28, cx + s * 0.4, cy + s * 0.34], outline=c, width=lw)
    d.ellipse([cx - s * 0.09, cy - s * 0.02, cx + s * 0.09, cy + s * 0.03], fill=c)


def _computer(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s, cy - s * 0.95, cx + s, cy + s * 0.4], radius=s * 0.15, outline=c, width=lw)
    _line(d, (cx - s * 1.15, cy + s * 0.82), (cx + s * 1.15, cy + s * 0.82), c, lw)
    _line(d, (cx - s * 0.7, cy + s * 0.4), (cx - s * 1.15, cy + s * 0.82), c, lw)
    _line(d, (cx + s * 0.7, cy + s * 0.4), (cx + s * 1.15, cy + s * 0.82), c, lw)


def _shield(d, cx, cy, s, c, lw):
    d.polygon([(cx, cy - s), (cx + s, cy - s * 0.55), (cx + s * 0.72, cy + s),
               (cx, cy + s * 0.72), (cx - s * 0.72, cy + s), (cx - s, cy - s * 0.55)],
              outline=c, width=lw)
    _line(d, (cx - s * 0.32, cy - s * 0.08), (cx - s * 0.06, cy + s * 0.22), c, lw)
    _line(d, (cx - s * 0.06, cy + s * 0.22), (cx + s * 0.38, cy - s * 0.26), c, lw)


def _rocket(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s * 0.42, cy - s * 0.7, cx + s * 0.42, cy + s * 0.78],
                        radius=s * 0.42, outline=c, width=lw)
    d.polygon([(cx - s * 0.42, cy - s * 0.1), (cx - s * 0.86, cy + s * 0.92),
               (cx - s * 0.42, cy + s * 0.78)], outline=c, width=lw)
    d.polygon([(cx + s * 0.42, cy - s * 0.1), (cx + s * 0.86, cy + s * 0.92),
               (cx + s * 0.42, cy + s * 0.78)], outline=c, width=lw)
    d.ellipse([cx - s * 0.18, cy - s * 0.42, cx + s * 0.18, cy - s * 0.04], outline=c, width=lw)
    d.polygon([(cx - s * 0.2, cy + s * 0.78), (cx, cy + s * 1.26), (cx + s * 0.2, cy + s * 0.78)],
              outline=c, width=lw)


def _bolt(d, cx, cy, s, c, lw):
    d.polygon([(cx + s * 0.16, cy - s), (cx - s * 0.55, cy + s * 0.22),
               (cx - s * 0.08, cy + s * 0.22), (cx - s * 0.24, cy + s),
               (cx + s * 0.5, cy - s * 0.28), (cx + s * 0.03, cy - s * 0.28)],
              outline=c, width=lw)


def _keyboard(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s * 1.2, cy - s * 0.6, cx + s * 1.2, cy + s * 0.6],
                        radius=s * 0.16, outline=c, width=lw)
    for r in range(2):
        for col in range(5):
            x = cx - s * 0.9 + col * s * 0.45
            y = cy - s * 0.28 + r * s * 0.5
            d.rectangle([x - s * 0.13, y - s * 0.13, x + s * 0.13, y + s * 0.13],
                        outline=c, width=max(1, lw // 2))


def _mouse(d, cx, cy, s, c, lw):
    d.rounded_rectangle([cx - s * 0.5, cy - s * 0.85, cx + s * 0.5, cy + s * 0.85],
                        radius=s * 0.5, outline=c, width=lw)
    _line(d, (cx, cy - s * 0.85), (cx, cy - s * 0.28), c, lw)


def _wifi(d, cx, cy, s, c, lw):
    for r in (s, s * 0.62, s * 0.28):
        d.arc([cx - r, cy - r * 0.5, cx + r, cy + r * 0.5], start=205, end=335, fill=c, width=lw)
    d.ellipse([cx - s * 0.09, cy + s * 0.4, cx + s * 0.09, cy + s * 0.58], fill=c)


ICONS = {
    "chip": _chip, "gamepad": _gamepad, "headphones": _headphones, "monitor": _monitor,
    "globe": _globe, "phone": _phone, "disc": _disc, "computer": _computer,
    "shield": _shield, "rocket": _rocket, "bolt": _bolt, "keyboard": _keyboard,
    "mouse": _mouse, "wifi": _wifi,
}


def draw_icon(d, name, cx, cy, s, color, lw):
    ICONS.get(name, _bolt)(d, cx, cy, s, color, lw)


# ---- clean glass badge overlay ----
@lru_cache(maxsize=256)
def radial_glow(radius: int, color, max_alpha: int) -> Image.Image:
    """Soft center-bright radial glow on transparent canvas.

    Cached: identical (radius, color, max_alpha) calls reuse one image — the
    orbit-dot halos are the same every frame, so this cuts render time hard.
    Returned images are only alpha-composited (never mutated) — safe to share.
    """
    size = radius * 2
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    steps = 14
    # Draw largest (most transparent) first, smallest (most opaque) last so the
    # center ends brightest — ImageDraw overwrites alpha rather than blending.
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = int(max_alpha * (1 - i / steps) ** 2)
        d.ellipse([radius - r, radius - r, radius + r, radius + r], fill=(*color, a))
    return img.filter(ImageFilter.GaussianBlur(radius * 0.15))


def _badge(icon: str, badge_r: int, t: float, orbit: list[tuple[float, float, float]]) -> Image.Image:
    """One supersampled badge frame: glow + glass circle + glyph + orbit dots."""
    # Canvas must fit the badge plus the widest orbit (off is in *display* px,
    # multiplied by SS to land in supersampled space) and its halo.
    orbit_max = max(off for _, _, off in orbit) if orbit else 0
    glow_pad = int(badge_r * 0.7)
    S = int((badge_r + orbit_max + glow_pad) * 2 * SS) + 20 * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S // 2
    d = ImageDraw.Draw(img)
    r = badge_r * SS

    # soft accent glow (pulses subtly)
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t / 2.6)
    glow = radial_glow(int(r * 1.5), B.ACCENT, 90 + int(50 * pulse))
    img.alpha_composite(glow, (c - glow.width // 2, c - glow.height // 2))

    # glass badge
    d.ellipse([c - r, c - r, c + r, c + r], fill=(*B.WHITE, 16))
    d.ellipse([c - r, c - r, c + r, c + r], outline=(*B.WHITE, 96), width=max(2, SS))
    # thin rotating accent ring segment
    seg0 = (t * 46) % 360
    d.arc([c - r + 6 * SS, c - r + 6 * SS, c + r - 6 * SS, c + r - 6 * SS],
          start=seg0, end=seg0 + 70, fill=(*B.BRIGHT, 170), width=max(2, 2 * SS))

    # glyph
    draw_icon(d, icon, c, c, int(r * 0.52), (*B.WHITE, 235), max(3, int(r * 0.075)))

    # orbit dots (off is display-px -> scale to supersampled space)
    for (off, speed, phase) in orbit:
        ang = phase + speed * t
        rr = r + off * SS
        px = c + math.cos(ang) * rr
        py = c + math.sin(ang) * rr
        pr = 3 * SS
        halo = radial_glow(int(pr * 2.6), B.BRIGHT, 150)
        img.alpha_composite(halo, (int(px) - halo.width // 2, int(py) - halo.height // 2))
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(*B.WHITE, 220))

    return img.resize((S // SS, S // SS), Image.LANCZOS)


def render_overlay_sequence(out_dir: Path, icon: str, W: int = 1080, H: int = 1920,
                            fps: int = 25, duration: float = 10.4, seed: int = 0) -> list[Path]:
    """Render the transparent badge overlay (bob + glow pulse + ring + orbit dots)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    n = int(duration * fps)
    badge_r = int(W * 0.115)  # ~124 px at 1080
    cx = W // 2
    cy = int(H * 0.135)        # top-center clean band (above wordmark/date/year)

    orbit = [
        (badge_r * off, speed, rng.uniform(0, 6.28))
        for off, speed in ((0.18, 0.9), (0.3, -0.7), (0.45, 1.2))
    ]

    paths = []
    for i in range(n):
        t = i / fps
        bob = int(9 * math.sin(2 * math.pi * t / 3.3))
        badge = _badge(icon, badge_r, t, orbit)

        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        frame.alpha_composite(badge, (cx - badge.width // 2, cy + bob - badge.height // 2))
        p = out_dir / f"f{i:04d}.png"
        frame.save(p, optimize=False)
        paths.append(p)
    return paths
