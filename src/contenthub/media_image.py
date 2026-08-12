"""Static post card (1080x1350) — the v1 daily visual.

Layout: dark gradient background, brand + date header, wrapped fact headline,
product photo on a white rounded card, product name + price + CTA footer.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import Config, USER_AGENT
from .feed import Product

log = logging.getLogger(__name__)

from . import media_brand as B

W, H = 1080, 1350
MARGIN = 64

# HelloComp brand palette (blue + white only — amber is retired; see media_brand.py)
ACCENT = B.ACCENT
TEXT = B.WHITE
MUTED = B.MUTED

CZ_MONTHS = B.CZ_MONTHS


def _font(cfg: Config, name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(cfg.fonts_dir / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        cand = f"{line} {word}".strip()
        if draw.textlength(cand, font=font) <= max_width:
            line = cand
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit_headline(draw: ImageDraw.ImageDraw, cfg: Config, text: str,
                  max_width: int, max_lines: int = 4) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Shrink font until the headline fits max_lines; hard-truncate as last resort."""
    for size in (60, 54, 48, 44, 40, 36):
        font = _font(cfg, "Inter-ExtraBold.ttf", size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = _font(cfg, "Inter-ExtraBold.ttf", 36)
    lines = _wrap(draw, text, font, max_width)[:max_lines]
    lines[-1] = lines[-1].rstrip(".,") + "…"
    return font, lines


def _gradient(w: int, h: int) -> Image.Image:
    return B.gradient(w, h)  # brand 135° 3-stop gradient


def _load_product_image(url: str, timeout: int = 30) -> Image.Image | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        return img.convert("RGBA")
    except Exception:  # noqa: BLE001
        log.warning("Product image download failed: %s", url, exc_info=True)
        return None


def _rounded(size: tuple[int, int], radius: int, color) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                                          radius=radius, fill=color)
    return img


def render_card(
    fact_headline: str | None,
    product: Product,
    cfg: Config,
    date: dt.date,
    out_path: Path,
) -> Path:
    canvas = _gradient(W, H).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # --- header: white wordmark + Czech date ---
    wm = B.wordmark(cfg.fonts_dir.parent / "brand", 38)
    canvas.alpha_composite(wm, (MARGIN, MARGIN))
    date_font = _font(cfg, "Inter-SemiBold.ttf", 30)
    date_str = f"{date.day}. {CZ_MONTHS[date.month - 1]} {date.year}"
    draw.text((W - MARGIN - draw.textlength(date_str, font=date_font), MARGIN + 4),
              date_str, font=date_font, fill=MUTED)

    y = MARGIN + 90

    # --- fact headline (or evergreen label) ---
    label_font = _font(cfg, "Inter-SemiBold.ttf", 26)
    if fact_headline:
        label = "V TENTO DEN V HISTORII TECHNIKY"
        headline = fact_headline
    else:
        label = "TIP DNE"
        headline = product.name
    draw.text((MARGIN, y), label, font=label_font, fill=ACCENT)
    y += 48
    head_font, lines = _fit_headline(draw, cfg, headline, W - 2 * MARGIN)
    line_h = int(head_font.size * 1.22)
    for ln in lines:
        draw.text((MARGIN, y), ln, font=head_font, fill=TEXT)
        y += line_h
    y += 36

    # --- product photo on white rounded card ---
    footer_h = 230
    card_side = min(W - 2 * MARGIN, H - footer_h - y - 24)
    card_side = max(card_side, 360)
    card_x = (W - card_side) // 2
    shadow = _rounded((card_side, card_side), 36, (0, 0, 0, 120)).filter(
        ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow, (card_x + 8, y + 12))
    canvas.alpha_composite(_rounded((card_side, card_side), 36, (255, 255, 255, 255)),
                           (card_x, y))
    p_img = _load_product_image(product.img)
    if p_img:
        inner = card_side - 80
        p_img.thumbnail((inner, inner), Image.LANCZOS)
        px = card_x + (card_side - p_img.width) // 2
        py = y + (card_side - p_img.height) // 2
        canvas.alpha_composite(p_img, (px, py))
    y += card_side + 40

    # --- footer: product name, price pill, CTA ---
    name_font = _font(cfg, "Inter-SemiBold.ttf", 36)
    name_lines = _wrap(draw, product.name, name_font, W - 2 * MARGIN)[:2]
    fy = H - footer_h + 10
    for ln in name_lines:
        draw.text((MARGIN, fy), ln, font=name_font, fill=TEXT)
        fy += int(name_font.size * 1.25)

    price_font = _font(cfg, "Inter-Bold.ttf", 40)
    price = product.price_czk
    pw = int(draw.textlength(price, font=price_font)) + 56
    ph = 76
    py0 = H - MARGIN - ph
    canvas.alpha_composite(_rounded((pw, ph), 38, (*ACCENT, 255)), (MARGIN, py0))
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN + 28, py0 + (ph - price_font.size) // 2 - 4), price,
              font=price_font, fill=B.WHITE)

    cta_font = _font(cfg, "Inter-SemiBold.ttf", 30)
    cta = "Odkaz v bio →"
    draw.text((W - MARGIN - draw.textlength(cta, font=cta_font), py0 + (ph - 30) // 2),
              cta, font=cta_font, fill=MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=92)
    log.info("Card rendered: %s", out_path)
    return out_path
