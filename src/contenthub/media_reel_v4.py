"""Reel v4 — cinematic motion with smooth slide transitions + animated emoji.

Fixes the "goofy motion" of v3:
  • Smooth slide transitions (smoothleft/smoothright) instead of xfade crossfade
  • Varied, eased Ken Burns per slide (zoom_in → orbital → zoom_out_pan)
  • Emoji with breathing scale + wobble rotation + vertical bob
  • Pulsing glow behind the emoji (separate layer)
  • Kinetic text reveals (slide-up + fade, line-by-line for story)
  • Subtle particles for depth
"""
from __future__ import annotations

import logging
import math
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import media_brand as B
from .config import Config
from .reel_emojis import render_emoji

log = logging.getLogger(__name__)

W, H = 1080, 1920
FPS = 30
SS = 2

SLIDE_S = 3.5
XFADE = 0.8
TOTAL = SLIDE_S * 3 - XFADE * 2
FRAMES_PER = int(SLIDE_S * FPS)
OFF1 = SLIDE_S - XFADE
OFF2 = SLIDE_S * 2 - XFADE * 2
TOTAL_FRAMES = int(TOTAL * FPS)
OV_FPS = 15

MUTED = (188, 202, 224)
ACCENT = B.ACCENT
BRIGHT = B.BRIGHT
WHITE = B.WHITE


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_inout(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _load_fonts(fonts_dir: Path):
    return {
        "year": B.display_font(fonts_dir, 180),
        "headline": B.font(fonts_dir, "Inter-Bold.ttf", 48),
        "story": B.font(fonts_dir, "Inter-Regular.ttf", 28),
    }


def _wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _render_glow(size: int) -> Image.Image:
    """Soft radial glow for behind the emoji."""
    s = size * 3
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s // 2
    for i in range(cx, 0, -3):
        t = i / cx
        a = int(60 * (1 - t) ** 2)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*ACCENT, a))
    return img.filter(ImageFilter.GaussianBlur(size * 0.15))


# ── text overlay rendering ──────────────────────────────────────────
# Layout zones (top → bottom):
#   emoji   y 280-830  (550px emoji, hero element)
#   year    y 950      (180px font, prominent)
#   headliney 1200     (48px font, 1-2 lines)
#   story   y 1500     (28px font, max 2 lines)

def _text_overlay_frame(t: float, year: int, headline: str, story: str,
                        fonts: dict, particles: list) -> Image.Image:
    """Render one text + particles overlay frame."""
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(frame)
    mx = 120
    max_w = W - mx * 2

    # Year — appears early, bold
    y_delay = 0.4
    if t > y_delay:
        yt = _clamp01((t - y_delay) / 0.7)
        alpha = int(255 * _ease_out(yt))
        slide = int(20 * (1 - _ease_out(yt)))
        year_txt = str(year)
        bb = d.textbbox((0, 0), year_txt, font=fonts["year"])
        tw = bb[2] - bb[0]
        tx = (W - tw) // 2
        ty = 950 + slide
        # accent line under year
        line_w = int(tw * 0.4 * yt)
        d.rectangle([(W - line_w) // 2, ty + 165, (W + line_w) // 2, ty + 168],
                    fill=(*ACCENT, int(200 * yt)))
        d.text((tx, ty), year_txt, font=fonts["year"], fill=(*WHITE, alpha))

    # Headline — slide up + fade
    hl_delay = 1.2
    if t > hl_delay and headline:
        ht = _clamp01((t - hl_delay) / 0.8)
        alpha = int(255 * _ease_out(ht))
        slide = int(25 * (1 - _ease_out(ht)))
        fnt, lines = B.fit_text(d, headline, max_w, 2,
                                 (48, 42), lambda s: fonts["headline"])
        y = 1200 + slide
        for line in lines[:2]:
            bb = d.textbbox((0, 0), line, font=fnt)
            tw = bb[2] - bb[0]
            d.text(((W - tw) // 2, y), line, font=fnt, fill=(*WHITE, alpha))
            y += int(bb[3] - bb[1]) + 12

    # Story — 2 lines max
    st_delay = 2.5
    if t > st_delay and story:
        story_lines = _wrap(d, story, fonts["story"], max_w)[:2]
        y = 1500
        for i, line in enumerate(story_lines):
            lt = _clamp01((t - st_delay - i * 0.35) / 0.6)
            if lt <= 0:
                continue
            alpha = int(200 * _ease_out(lt))
            slide = int(10 * (1 - _ease_out(lt)))
            bb = d.textbbox((0, 0), line, font=fonts["story"])
            tw = bb[2] - bb[0]
            d.text(((W - tw) // 2, y + slide), line, font=fonts["story"],
                   fill=(*MUTED, alpha))
            y += int(bb[3] - bb[1]) + 8

    # Subtle particles
    for px, py, sz, speed, phase, life in particles:
        age = t - phase
        if age < 0 or age > life:
            continue
        frac = age / life
        cy = py - speed * age * 50
        cx = px + 12 * math.sin(age * 1.5 + phase)
        if cy < -50 or cy > H + 50:
            continue
        fade = min(frac * 5, 1.0, (1 - frac) * 4) if frac < 1 else 0
        a = int(25 * fade)
        if a < 3:
            continue
        d.ellipse([cx - sz, cy - sz, cx + sz, cy + sz], fill=(*BRIGHT, a))

    return frame


def compose_reel(slide_paths: list[Path], icon: str, out_path: Path,
                 cfg: Config, music_path: Path | None = None,
                 plan_entry: dict | None = None, seed: int = 0) -> Path | None:
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg not found")
        return None
    if len(slide_paths) != 3 or not all(p.exists() for p in slide_paths):
        log.error("need 3 slides")
        return None

    fonts = _load_fonts(cfg.fonts_dir)

    if plan_entry:
        year = plan_entry.get("fact_year", 2000)
        headline = plan_entry.get("headline", plan_entry.get("fact", ""))
        story = plan_entry.get("story", "")
        if not story:
            story = plan_entry.get("caption", "").split("\n\n")[0]
    else:
        year, headline, story = 2000, "", ""

    # particles
    rng = random.Random(seed + 7)
    particles = [
        (rng.uniform(120, W - 120), rng.uniform(200, H - 200),
         rng.uniform(1.5, 3.0), rng.uniform(0.2, 0.5),
         rng.uniform(0, TOTAL * 0.5), rng.uniform(3.0, 5.5))
        for _ in range(10)
    ]

    log.info("Reel v4: icon=%s year=%s headline=%.40s…",
             icon, year, headline)

    with tempfile.TemporaryDirectory() as td:
        # 1. Static emoji + glow PNGs
        emoji_img = render_emoji(icon, size=550)
        emoji_path = Path(td) / "emoji.png"
        emoji_img.save(emoji_path)

        glow_img = _render_glow(550)
        glow_path = Path(td) / "glow.png"
        glow_img.save(glow_path)

        # 2. Text overlay sequence
        text_dir = Path(td) / "text"
        text_dir.mkdir()
        ov_n = int(TOTAL * OV_FPS)
        for i in range(ov_n):
            t = i / OV_FPS
            frame = _text_overlay_frame(t, year, headline, story,
                                        fonts, particles)
            frame.save(text_dir / f"f{i:04d}.png", optimize=False)

        # 3. FFmpeg composition
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
        for p in slide_paths:
            cmd += ["-loop", "1", "-i", str(p)]           # 0,1,2: slides
        cmd += ["-loop", "1", "-i", str(glow_path)]       # 3: glow
        cmd += ["-loop", "1", "-i", str(emoji_path)]      # 4: emoji
        cmd += ["-framerate", str(OV_FPS),
                "-i", str(text_dir / "f%04d.png")]        # 5: text overlay

        fr = FRAMES_PER
        # Varied, eased Ken Burns per slide
        kb1 = (f"scale=2160:3840,"
               f"zoompan=z='min(1.06,1+0.0006*on)':"
               f"x='iw/2-(iw/zoom/2)':"
               f"y='ih/2-(ih/zoom/2)+12*sin(PI*on/{fr})':"
               f"d={fr}:s={W}x{H}:fps={FPS}")
        kb2 = (f"scale=2160:3840,"
               f"zoompan=z='1.05':"
               f"x='iw/2-(iw/zoom/2)+22*sin(2*PI*on/{fr})':"
               f"y='ih/2-(ih/zoom/2)+14*cos(2*PI*on/{fr})':"
               f"d={fr}:s={W}x{H}:fps={FPS}")
        kb3 = (f"scale=2160:3840,"
               f"zoompan=z='max(1.0,1.06-0.0006*on)':"
               f"x='iw/2-(iw/zoom/2)-18*sin(PI*on/{fr})':"
               f"y='ih/2-(ih/zoom/2)':"
               f"d={fr}:s={W}x{H}:fps={FPS}")

        # Emoji position: upper area (so text fits below)
        emoji_y_base = 555
        bob = f"{emoji_y_base}+10*sin(2*PI*t/2.2)"

        fc = [
            # Ken Burns per slide
            f"[0:v]{kb1}[v1]",
            f"[1:v]{kb2}[v2]",
            f"[2:v]{kb3}[v3]",
            # Smooth slide transitions (NOT crossfade)
            f"[v1][v2]xfade=transition=smoothleft:duration={XFADE}:offset={OFF1}[x1]",
            f"[x1][v3]xfade=transition=smoothright:duration={XFADE}:offset={OFF2}[xb]",
            # Vignette
            "[xb]vignette=PI/5[bg]",
            # Glow (pulsing scale, behind emoji)
            f"[3:v]format=rgba,"
            f"scale='iw*(1+0.12*sin(2*PI*t/1.8))':'ih*(1+0.12*sin(2*PI*t/1.8))':eval=frame,"
            f"setsar=1[glow]",
            f"[bg][glow]overlay='(W-w)/2':'{emoji_y_base}-h/2+20':format=auto[bg_glow]",
            # Emoji (breathing scale + wobble rotation)
            f"[4:v]format=rgba,"
            f"scale='iw*(1+0.035*sin(2*PI*t/2.6))':'ih*(1+0.035*sin(2*PI*t/2.6))':eval=frame,"
            f"rotate=angle='2.2*sin(2*PI*t/3.2)*PI/180':fillcolor=none,"
            f"setsar=1[emoji]",
            f"[bg_glow][emoji]overlay='(W-w)/2':'{bob}-h/2':format=auto[bg_emoji]",
            # Text overlay
            f"[5:v]format=rgba,fps={FPS},minterpolate=fps={FPS}:mi_mode=mci,"
            f"scale={W}:{H},setsar=1[tx]",
            f"[bg_emoji][tx]overlay=0:0:format=auto[vout]",
            # Fade in/out
            f"[vout]fade=t=in:st=0:d=0.4,fade=t=out:st={TOTAL-0.4}:d=0.4[v]",
        ]
        cmd += ["-filter_complex", ";".join(fc), "-map", "[v]",
                "-t", str(TOTAL), "-c:v", "libx264", "-preset", "medium",
                "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart", str(out_path)]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("FFmpeg compose (%ds, %d frames)…", TOTAL, TOTAL_FRAMES)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.error("ffmpeg failed:\n%s", proc.stderr[-1500:])
            return None

    log.info("Reel v4 rendered: %s (%.1f MB)",
             out_path, out_path.stat().st_size / 1e6)
    return out_path
