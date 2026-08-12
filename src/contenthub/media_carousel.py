"""3-slide Instagram carousel (1080x1350 each) in HelloComp brand.

Slide 1 — HOOK: giant year (Vafle), fact headline, swipe cue.
Slide 2 — BRIDGE: "od historie k dnešku" line + product photo on white card.
Slide 3 — CTA: wordmark, product name, price pill (logo blue), odkaz v bio.

All backgrounds use the brand 135° navy gradient; accents are blue+white only
(amber is retired — see media_brand.py).
"""
from __future__ import annotations

import datetime as dt
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from . import media_brand as B
from .config import Config, USER_AGENT
from .facts import Fact
from .feed import Product

log = logging.getLogger(__name__)

# PRIMARY canvas is 9:16 (Stories/Reels-ready). All content is composed inside
# the central 4:5 SAFE ZONE, so a center-crop to 1080x1350 (feed) never cuts
# anything off, and IG story UI overlays (~top/bottom 250px) never cover text.
FRAME_W, FRAME_H = 1080, 1920
W, H = 1080, 1350          # safe-zone size — all slide layouts draw in this box
SAFE_Y = (FRAME_H - H) // 2  # = 285
M = 72  # margin


@dataclass
class SlideTexts:
    """Texts for the three slides (fact bank, LLM, or template)."""
    hook_label: str
    hook_headline: str
    bridge_line: str
    cta_line: str
    story_line: str = ""  # 1-2 sentence "why it matters" shown on slide 2

_BRIDGES = (
    "Z historie rovnou do tvého setupu:",
    "A dnešní pokračování příběhu? Máme ho skladem:",
    "Historie se píše dál — třeba u tebe doma:",
)
_CTAS = (
    "Skladem, odesíláme hned",
    "Dnes objednáš, zítra rozbaluješ",
    "Skladem — stačí kliknout",
)


def default_texts(fact: Fact | None, product: Product, date: dt.date,
                  story: str = "") -> SlideTexts:
    rot = date.toordinal()
    if fact and fact.lang == "cs":
        headline = fact.text
        label = "V TENTO DEN V HISTORII TECHNIKY"
        bridge = _BRIDGES[rot % len(_BRIDGES)]
    else:
        headline = product.name
        label = "TIP DNE"
        bridge = "Náš dnešní favorit:"
    return SlideTexts(
        hook_label=label,
        hook_headline=headline,
        bridge_line=bridge,
        cta_line=_CTAS[rot % len(_CTAS)],
        story_line=story,
    )


def _base(cfg: Config, date: dt.date,
          texture: bool = True) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Transparent safe-zone content layer (1080x1350) with header drawn in.

    The gradient background lives on the full 9:16 frame (see _finalize);
    keeping this layer transparent means the 4:5 crop and the 9:16 master
    share pixel-identical content. `texture` is kept for signature
    compatibility — the dot grid is applied on the full frame.
    """
    del texture
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    brand_dir = cfg.fonts_dir.parent / "brand"
    wm = B.wordmark(brand_dir, 40)
    canvas.alpha_composite(wm, (M, M))
    draw = ImageDraw.Draw(canvas)
    date_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 28)
    ds = B.czech_date(date)
    draw.text((W - M - draw.textlength(ds, font=date_font), M + 6),
              ds, font=date_font, fill=B.MUTED)
    return canvas, draw


def _finalize(content: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Compose the safe-zone layer onto the 9:16 frame; return (9:16, 4:5 crop)."""
    frame = B.gradient(FRAME_W, FRAME_H).convert("RGBA")
    frame.alpha_composite(B.dot_grid(FRAME_W, FRAME_H))
    frame.alpha_composite(content, (0, SAFE_Y))
    crop45 = frame.crop((0, SAFE_Y, FRAME_W, SAFE_Y + H))
    return frame, crop45


def _dots(draw: ImageDraw.ImageDraw, active: int) -> None:
    """Carousel position dots, bottom center."""
    n, r, gap = 3, 7, 30
    total = (n - 1) * gap
    x0 = W // 2 - total // 2
    y = H - 46
    for i in range(n):
        color = B.WHITE if i == active else (*B.BRIGHT, 140)
        draw.ellipse([x0 + i * gap - r, y - r, x0 + i * gap + r, y + r], fill=color)


def _product_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:  # noqa: BLE001
        log.warning("Product image download failed: %s", url, exc_info=True)
        return None


STYLES = ("classic", "editorial", "duotone")


def resolve_style(cfg: Config, date: dt.date) -> str:
    """classic | editorial | duotone; 'auto' rotates deterministically by date."""
    s = (cfg.carousel_style or "classic").lower()
    if s == "auto":
        return STYLES[date.toordinal() % len(STYLES)]
    return s if s in STYLES else "classic"


def _slide_hook_editorial(cfg: Config, texts: SlideTexts, fact: Fact | None,
                          date: dt.date) -> Image.Image:
    """Left-aligned magazine layout: ghost year, big ragged-left headline."""
    canvas, draw = _base(cfg, date)
    # ghost year, oversized, anchored bottom-right behind content
    if fact and fact.year:
        gfont = B.display_font(cfg.fonts_dir, 430)
        ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ghost).text((W + 40, H + 30), str(fact.year), font=gfont,
                                   fill=(*B.BRIGHT, 38), anchor="rs")
        canvas.alpha_composite(ghost)
        draw = ImageDraw.Draw(canvas)
    y = 300
    label_font = B.font(cfg.fonts_dir, "Inter-Bold.ttf", 28)
    draw.text((M, y), texts.hook_label, font=label_font, fill=B.BRIGHT)
    y += 56
    # accent rule under the label
    canvas.alpha_composite(B.rounded((110, 8), 4, (*B.ACCENT, 255)), (M, y))
    draw = ImageDraw.Draw(canvas)
    y += 44
    head_font, lines = B.fit_text(
        draw, texts.hook_headline, W - 2 * M, 5,
        (100, 92, 84, 74, 64), lambda s: B.display_font(cfg.fonts_dir, s))
    line_h = int(head_font.size * 1.08)
    for ln in lines:
        draw.text((M, y), ln, font=head_font, fill=B.WHITE)
        y += line_h
    if fact and fact.year:
        y += 30
        yr_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 30)
        draw.text((M, y), f"— rok {fact.year}", font=yr_font, fill=B.MUTED)
    cue_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 30)
    cue = "Posuň dál →"
    draw.text((W - M - draw.textlength(cue, font=cue_font), H - 120),
              cue, font=cue_font, fill=B.MUTED)
    _dots(draw, 0)
    return canvas


def _slide_hook_duotone(cfg: Config, texts: SlideTexts, fact: Fact | None,
                        date: dt.date) -> Image.Image:
    """Solid logo-blue top panel with the headline; giant year below on gradient."""
    canvas, draw = _base(cfg, date, texture=False)
    panel_h = 620
    panel = B.rounded((W - 2 * 40, panel_h), 44, (*B.ACCENT, 255))
    canvas.alpha_composite(panel, (40, 150))
    draw = ImageDraw.Draw(canvas)
    y = 210
    label_font = B.font(cfg.fonts_dir, "Inter-Bold.ttf", 27)
    lw = draw.textlength(texts.hook_label, font=label_font)
    draw.text(((W - lw) // 2, y), texts.hook_label, font=label_font,
              fill=(210, 226, 250))
    y += 66
    head_font, lines = B.fit_text(
        draw, texts.hook_headline, W - 2 * M - 60, 4,
        (78, 70, 62, 54), lambda s: B.display_font(cfg.fonts_dir, s))
    line_h = int(head_font.size * 1.12)
    block_h = len(lines) * line_h
    # center the headline block in the panel area below the label
    label_bottom = 210 + 60
    y = label_bottom + max(0, (150 + panel_h - label_bottom - 50 - block_h) // 2)
    for ln in lines:
        lw = draw.textlength(ln, font=head_font)
        draw.text(((W - lw) // 2, y), ln, font=head_font, fill=B.WHITE)
        y += line_h
    if fact and fact.year:
        yr_font = B.display_font(cfg.fonts_dir, 250)
        draw.text((W // 2, 1010), str(fact.year), font=yr_font,
                  fill=B.WHITE, anchor="mm")
    cue_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 30)
    cue = "Posuň dál →"
    draw.text((W - M - draw.textlength(cue, font=cue_font), H - 120),
              cue, font=cue_font, fill=B.MUTED)
    _dots(draw, 0)
    return canvas


def _slide_hook(cfg: Config, texts: SlideTexts, fact: Fact | None,
                date: dt.date) -> Image.Image:
    canvas, draw = _base(cfg, date)
    y = 320
    if fact and fact.year:
        year_font = B.display_font(cfg.fonts_dir, 300)
        ys = str(fact.year)
        # subtle glow behind the year
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((W // 2, y), ys, font=year_font,
                                  fill=(*B.ACCENT, 190), anchor="mm")
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))
        draw.text((W // 2, y), ys, font=year_font, fill=B.WHITE, anchor="mm")
        y += 220
    else:
        y = 260
    label_font = B.font(cfg.fonts_dir, "Inter-Bold.ttf", 30)
    lw = draw.textlength(texts.hook_label, font=label_font)
    draw.text(((W - lw) // 2, y), texts.hook_label, font=label_font, fill=B.BRIGHT)
    y += 78
    head_font, lines = B.fit_text(
        draw, texts.hook_headline, W - 2 * M, 5,
        (84, 76, 68, 60, 54), lambda s: B.display_font(cfg.fonts_dir, s))
    line_h = int(head_font.size * 1.12)
    for ln in lines:
        lw = draw.textlength(ln, font=head_font)
        draw.text(((W - lw) // 2, y), ln, font=head_font, fill=B.WHITE)
        y += line_h
    # faint giant smile mark anchored bottom-left — brand texture, not a sticker.
    # Vertically the mark must stay WHOLE: the layer bottom is mid-frame on the
    # 9:16 master, so any bottom bleed would decapitate the smile's mouth.
    brand_dir = cfg.fonts_dir.parent / "brand"
    sm = B.smile(brand_dir, 520, alpha=22)
    canvas.alpha_composite(sm, (-90, H - sm.height - 150))
    draw = ImageDraw.Draw(canvas)
    cue_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 30)
    cue = "Posuň dál →"
    draw.text((W - M - draw.textlength(cue, font=cue_font), H - 120),
              cue, font=cue_font, fill=B.MUTED)
    _dots(draw, 0)
    return canvas


def _slide_bridge(cfg: Config, texts: SlideTexts, product: Product,
                  date: dt.date) -> Image.Image:
    canvas, draw = _base(cfg, date)
    y = M + 104

    # story paragraph — the "why it matters" value block
    if texts.story_line:
        story_font = B.font(cfg.fonts_dir, "Inter-Regular.ttf", 34)
        story_lines = B.wrap(draw, texts.story_line, story_font, W - 2 * M - 36)[:4]
        # accent bar alongside the story
        bar_h = len(story_lines) * int(story_font.size * 1.35) + 8
        canvas.alpha_composite(B.rounded((8, bar_h), 4, (*B.ACCENT, 255)), (M, y))
        draw = ImageDraw.Draw(canvas)
        sx = M + 36
        for ln in story_lines:
            draw.text((sx, y), ln, font=story_font, fill=B.WHITE)
            y += int(story_font.size * 1.35)
        y += 34

    br_font, br_lines = B.fit_text(draw, texts.bridge_line, W - 2 * M, 2,
                                   (52, 46, 40), lambda s: B.display_font(cfg.fonts_dir, s))
    for ln in br_lines:
        draw.text((M, y), ln, font=br_font, fill=B.BRIGHT)
        y += int(br_font.size * 1.18)
    y += 26

    card_side = min(W - 2 * M, H - y - 240)
    card_side = max(card_side, 340)
    cx = (W - card_side) // 2
    # blue brand glow instead of plain black shadow
    glow = B.rounded((card_side, card_side), 40, (*B.ACCENT, 110)).filter(
        ImageFilter.GaussianBlur(34))
    canvas.alpha_composite(glow, (cx, y + 10))
    canvas.alpha_composite(B.rounded((card_side, card_side), 40, (*B.WHITE, 255)), (cx, y))
    p_img = _product_image(product.img)
    if p_img:
        inner = card_side - 90
        p_img.thumbnail((inner, inner), Image.LANCZOS)
        canvas.alpha_composite(
            p_img, (cx + (card_side - p_img.width) // 2,
                    y + (card_side - p_img.height) // 2))
    y += card_side + 32
    draw = ImageDraw.Draw(canvas)
    name_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 34)
    for ln in B.wrap(draw, product.name, name_font, W - 2 * M)[:2]:
        lw = draw.textlength(ln, font=name_font)
        draw.text(((W - lw) // 2, y), ln, font=name_font, fill=B.WHITE)
        y += int(name_font.size * 1.25)
    _dots(draw, 1)
    return canvas


def _slide_cta(cfg: Config, texts: SlideTexts, product: Product,
               date: dt.date) -> Image.Image:
    canvas, draw = _base(cfg, date)
    brand_dir = cfg.fonts_dir.parent / "brand"

    # centered wordmark (it already carries the smile — no extra mark above it)
    wm = B.wordmark(brand_dir, 100)
    canvas.alpha_composite(wm, ((W - wm.width) // 2, 440))

    y = 620
    name_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 40)
    for ln in B.wrap(draw, product.name, name_font, W - 2 * M)[:2]:
        lw = draw.textlength(ln, font=name_font)
        draw.text(((W - lw) // 2, y), ln, font=name_font, fill=B.WHITE)
        y += int(name_font.size * 1.3)
    y += 26

    # price pill — logo blue, white text (brand accent rule)
    price_font = B.display_font(cfg.fonts_dir, 64)
    price = product.price_czk
    pw = int(draw.textlength(price, font=price_font)) + 84
    ph = 104
    px = (W - pw) // 2
    canvas.alpha_composite(B.rounded((pw, ph), 52, (*B.ACCENT, 255)), (px, y))
    draw = ImageDraw.Draw(canvas)
    draw.text((W // 2, y + ph // 2 - 4), price, font=price_font,
              fill=B.WHITE, anchor="mm")
    y += ph + 44

    cta_font = B.font(cfg.fonts_dir, "Inter-SemiBold.ttf", 32)
    for i, line in enumerate((texts.cta_line, "Odkaz v bio →")):
        lw = draw.textlength(line, font=cta_font)
        draw.text(((W - lw) // 2, y), line, font=cta_font,
                  fill=B.MUTED if i == 0 else B.WHITE)
        y += 52
    _dots(draw, 2)
    return canvas


_HOOKS = {"classic": _slide_hook, "editorial": _slide_hook_editorial,
          "duotone": _slide_hook_duotone}


def render_carousel(
    texts: SlideTexts,
    fact: Fact | None,
    product: Product,
    cfg: Config,
    date: dt.date,
    out_stem: Path,
    style: str | None = None,
) -> list[Path]:
    """Render the 3 slides as {stem}-1.jpg … {stem}-3.jpg in the given style."""
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    style = style or resolve_style(cfg, date)
    hook = _HOOKS.get(style, _slide_hook)
    log.info("Carousel style: %s", style)
    slides = (
        hook(cfg, texts, fact, date),
        _slide_bridge(cfg, texts, product, date),
        _slide_cta(cfg, texts, product, date),
    )
    paths: list[Path] = []
    for i, content in enumerate(slides, start=1):
        frame, crop45 = _finalize(content)
        p916 = out_stem.parent / f"{out_stem.name}-{i}.jpg"        # 9:16 primary
        p45 = out_stem.parent / f"{out_stem.name}-{i}-45.jpg"      # 4:5 feed crop
        frame.convert("RGB").save(p916, "JPEG", quality=92)
        crop45.convert("RGB").save(p45, "JPEG", quality=92)
        paths.append(p916)
    log.info("Carousel rendered (9:16 + 4:5): %s", ", ".join(p.name for p in paths))
    return paths
