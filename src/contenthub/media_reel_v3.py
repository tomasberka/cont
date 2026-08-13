"""Enhanced reel v3 — data-driven infographic style.

Visual upgrades over v2:
  • Animated year counter with spin-in effect
  • Timeline bar with glowing dot (year → now)
  • Headline text reveal (slide-up + fade)
  • Floating particle field (data-point aesthetic)
  • Progress bar along the bottom
  • Icon badge kept from v2 (bob + glow + orbit dots)

Pipeline:
  1. Pillow renders 5 transparent overlay layers per frame (year, timeline,
     text, progress, particles) + composites them into one RGBA sequence.
  2. FFmpeg composites the overlay on the Ken-Burns slide background with
     xfade crossfades, vignette, and fade in/out.
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
from .reel_icons import render_overlay_sequence

log = logging.getLogger(__name__)

W, H = 1080, 1920
FPS = 30
SS = 2  # supersample for anti-aliasing
OV_FPS = 15  # overlay render rate (FFmpeg minterpolates to FPS)

SLIDE_S = 3.5
XFADE = 0.7
TOTAL = SLIDE_S * 3 - XFADE * 2
FRAMES_PER = int(SLIDE_S * FPS)
OFF1 = SLIDE_S - XFADE
OFF2 = SLIDE_S * 2 - XFADE * 2
TOTAL_FRAMES = int(TOTAL * FPS)

MUTED = (188, 202, 224)
ACCENT = B.ACCENT
BRIGHT = B.BRIGHT
WHITE = B.WHITE


# ── easings ──────────────────────────────────────────────────────────
def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


# ── helpers ──────────────────────────────────────────────────────────
def _load_fonts(fonts_dir: Path):
    return {
        "year": B.display_font(fonts_dir, 200),
        "year_sm": B.display_font(fonts_dir, 40),
        "headline": B.font(fonts_dir, "Inter-Bold.ttf", 44),
        "label": B.font(fonts_dir, "Inter-Regular.ttf", 28),
        "progress": B.font(fonts_dir, "Inter-SemiBold.ttf", 24),
    }


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
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


# ── per-frame overlay renderers (all draw on a transparent canvas) ──
# Layout zones (top → bottom):
#   badge   ≈ y 200-300  (icon, from reel_icons — we don't touch this)
#   year    ≈ y 480-580  (big year number)
#   timeline≈ y 620-660  (thin horizontal bar)
#   headline≈ y 780-920  (bold title, 1-2 lines)
#   story   ≈ y 980-1200 (body text, 3-5 lines)
#   progress≈ y 1850     (bottom edge)
# All zones have generous gaps — nothing overlaps.

def _year_counter(canvas: Image.Image, year: int, t: float, fonts: dict):
    """Big year counting in with spin effect — NO glow band, clean text only."""
    anim = 1.4
    if t > anim + 0.6:
        return
    d = ImageDraw.Draw(canvas)
    cy = 530  # center of year text, well below badge
    progress = _clamp01(t / anim)

    if progress < 1:
        display = int(year - (year - 1970) * (1 - _ease_out(progress)))
        spin = int(6 * (1 - progress) * math.sin(t * 45))
        draw_y = cy + spin
    else:
        display = year
        draw_y = cy

    txt = str(display)
    bb = d.textbbox((0, 0), txt, font=fonts["year"])
    tw = bb[2] - bb[0]
    tx = (W - tw) // 2

    # subtle motion blur trails during spin (very faint)
    if progress < 1:
        trail_a = int(50 * (1 - progress))
        for i in range(1, 3):
            off = int(i * 3 * (1 - progress))
            d.text((tx, draw_y - 100 + off), txt, font=fonts["year"],
                   fill=(*BRIGHT, trail_a // i))

    d.text((tx, draw_y - 100), txt, font=fonts["year"], fill=(*WHITE, 255))

    # small year label below
    a = int(200 * _clamp01((t - 0.6) * 2.5))
    lb = d.textbbox((0, 0), str(year), font=fonts["year_sm"])
    lw = lb[2] - lb[0]
    d.text(((W - lw) // 2, draw_y + 30), str(year), font=fonts["year_sm"],
           fill=(*BRIGHT, a))


def _timeline(canvas: Image.Image, year: int, t: float, fonts: dict):
    """Horizontal timeline that draws itself — thin, clean, below year."""
    d = ImageDraw.Draw(canvas)
    margin = 140
    bar_y = 640  # below year counter
    bar_w = W - margin * 2
    now = 2026
    span = max(now - year, 1)

    progress = _clamp01(t / 3.5)
    draw_len = bar_w * _ease_out(progress)

    # bar track
    d.rounded_rectangle([margin, bar_y - 2, margin + bar_w, bar_y + 2],
                        radius=2, fill=(*MUTED, 40))

    # drawn bar
    if draw_len > 4:
        d.rounded_rectangle([margin, bar_y - 3, margin + draw_len, bar_y + 3],
                            radius=3, fill=(*BRIGHT, 180))

    # endpoint dot
    dot_x = margin + draw_len
    if draw_len > 8:
        pulse = 0.5 + 0.5 * math.sin(t * 5)
        glow_r = int(18 + 6 * pulse)
        glow = Image.new("RGBA", (glow_r * 2, glow_r * 2), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for i in range(10, 0, -1):
            r = glow_r * i / 10
            a = int(65 * (1 - i / 10) ** 2)
            gd.ellipse([glow_r - r, glow_r - r, glow_r + r, glow_r + r],
                       fill=(*ACCENT, a))
        canvas.alpha_composite(glow, (int(dot_x) - glow_r, bar_y - glow_r))
        d.ellipse([dot_x - 7, bar_y - 7, dot_x + 7, bar_y + 7],
                  fill=(*WHITE, 255))

    # year labels
    a = int(255 * _clamp01((t - 1.5) * 2))
    if a > 0:
        d.text((margin - 5, bar_y + 18), str(year), font=fonts["label"],
               fill=(*BRIGHT, a), anchor="lt")
        d.text((margin + bar_w + 5, bar_y + 18), str(now),
               font=fonts["label"], fill=(*MUTED, a), anchor="rt")

    # decade ticks
    if progress > 0.3:
        ta = int(80 * _clamp01((t - 1.0) * 2))
        decade_start = (year // 10) * 10
        for dec in range(decade_start, now + 1, 10):
            frac = (dec - year) / span
            dx = margin + bar_w * frac
            if margin + 20 < dx < margin + bar_w - 20:
                d.line([(dx, bar_y - 8), (dx, bar_y + 8)],
                       fill=(*MUTED, ta), width=1)


def _text_reveal(canvas: Image.Image, headline: str, story: str,
                 t: float, fonts: dict):
    """Headline slides up + fades; story appears line by line. Well-spaced below timeline."""
    d = ImageDraw.Draw(canvas)
    mx = 130
    max_w = W - mx * 2

    # headline — slide up + fade (appears after year settles)
    hl_delay = 2.2
    if t > hl_delay:
        ht = _clamp01((t - hl_delay) / 0.8)
        alpha = int(255 * _ease_out(ht))
        slide_y = int(25 * (1 - _ease_out(ht)))
        fnt, lines = B.fit_text(d, headline, max_w, 2, (44, 38), lambda s: fonts["headline"])
        y = 800 + slide_y
        for line in lines[:2]:
            bb = d.textbbox((0, 0), line, font=fnt)
            tw = bb[2] - bb[0]
            d.text(((W - tw) // 2, y), line, font=fnt, fill=(*WHITE, alpha))
            y += int(bb[3] - bb[1]) + 12

    # story — line-by-line reveal (appears after headline)
    st_delay = 3.8
    if t > st_delay and story:
        story_lines = _wrap(d, story, fonts["label"], max_w)[:5]
        y = 1000
        for i, line in enumerate(story_lines):
            lt = _clamp01((t - st_delay - i * 0.3) / 0.6)
            if lt <= 0:
                continue
            alpha = int(200 * _ease_out(lt))
            slide = int(15 * (1 - _ease_out(lt)))
            bb = d.textbbox((0, 0), line, font=fonts["label"])
            tw = bb[2] - bb[0]
            d.text(((W - tw) // 2, y + slide), line, font=fonts["label"],
                   fill=(*MUTED, alpha))
            y += int(bb[3] - bb[1]) + 14


def _progress_bar(canvas: Image.Image, t: float):
    """Thin accent bar along the very bottom edge."""
    d = ImageDraw.Draw(canvas)
    bar_h = 4
    y = H - 50  # near bottom
    frac = _clamp01(t / TOTAL)
    filled = int((W - 160) * frac)
    # track
    d.rounded_rectangle([80, y, W - 80, y + bar_h], radius=2, fill=(*MUTED, 30))
    # fill
    if filled > 6:
        d.rounded_rectangle([80, y - 1, 80 + filled, y + bar_h + 1],
                            radius=2, fill=(*ACCENT, 180))
    # leading dot
    if filled > 2:
        dot_x = 80 + filled
        d.ellipse([dot_x - 4, y - 2, dot_x + 4, y + bar_h + 2],
                  fill=(*WHITE, 200))


def _particles(canvas: Image.Image, particles: list, t: float):
    """Very subtle floating data-point particles — sparse and faint."""
    d = ImageDraw.Draw(canvas)
    for px, py, sz, speed, phase, life in particles:
        age = t - phase
        if age < 0 or age > life:
            continue
        frac = age / life
        cy = py - speed * age * 60
        cx = px + 15 * math.sin(age * 1.5 + phase)
        if cy < -50 or cy > H + 50:
            continue
        fade = min(frac * 5, 1.0, (1 - frac) * 4) if frac < 1 else 0
        a = int(30 * fade)  # very faint
        if a < 3:
            continue
        d.ellipse([cx - sz, cy - sz, cx + sz, cy + sz], fill=(*BRIGHT, a))


def _render_overlay_frame(t: float, year: int, headline: str, story: str,
                          fonts: dict, particles: list) -> Image.Image:
    """Render one full-res overlay frame with all animated elements."""
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _year_counter(frame, year, t, fonts)
    _timeline(frame, year, t, fonts)
    _text_reveal(frame, headline, story, t, fonts)
    _progress_bar(frame, t)
    _particles(frame, particles, t)
    return frame


# ── reel composition ─────────────────────────────────────────────────
def compose_reel(slide_paths: list[Path], icon: str, out_path: Path,
                 cfg: Config, music_path: Path | None = None,
                 plan_entry: dict | None = None, seed: int = 0) -> Path | None:
    """Render enhanced reel with data-driven overlay on top of Ken Burns slides."""
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg not found — skipping reel")
        return None
    if len(slide_paths) != 3 or not all(p.exists() for p in slide_paths):
        log.error("reel needs 3 existing slides, got %s", slide_paths)
        return None

    fonts = _load_fonts(cfg.fonts_dir)
    music = music_path or (cfg.fonts_dir.parent / "music.mp3")
    has_music = music.exists()

    # fact metadata for overlays
    if plan_entry:
        year = plan_entry.get("fact_year") or plan_entry.get("year") or 2000
        headline = plan_entry.get("headline") or plan_entry.get("fact", "")
        story = plan_entry.get("story") or plan_entry.get("caption", "")
    else:
        year, headline, story = 2000, "", ""

    # pre-generate particle field — sparse, subtle
    rng = random.Random(seed + 7)
    particles = [
        (rng.uniform(120, W - 120), rng.uniform(H * 0.25, H * 0.85),
         rng.uniform(1.5, 3.5), rng.uniform(0.2, 0.6),
         rng.uniform(0, TOTAL * 0.5), rng.uniform(3.0, 5.5))
        for _ in range(12)
    ]

    log.info("Enhanced reel: year=%s headline=%.40s… particles=%d",
             year, headline, len(particles))

    with tempfile.TemporaryDirectory() as td:
        # 1. render icon badge overlay (v2 style, small glass badge)
        icon_dir = Path(td) / "icon"
        render_overlay_sequence(icon_dir, icon, W, H, FPS, TOTAL, seed=seed)

        # 2. render enhanced overlay frames at OV_FPS, minterpolate in FFmpeg
        enh_dir = Path(td) / "enh"
        enh_dir.mkdir()
        ov_n = int(TOTAL * OV_FPS)
        for i in range(ov_n):
            t = i / OV_FPS
            frame = _render_overlay_frame(t, year, headline, story,
                                          fonts, particles)
            frame.save(enh_dir / f"f{i:04d}.png", optimize=False)

        # 3. FFmpeg: Ken Burns slides + xfade + composite overlays
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
        for p in slide_paths:
            cmd += ["-i", str(p)]
        # input 3: icon badge overlay
        cmd += ["-framerate", str(FPS), "-i", str(icon_dir / "f%04d.png")]
        # input 4: enhanced overlay
        cmd += ["-framerate", str(FPS), "-i", str(enh_dir / "f%04d.png")]
        if has_music:
            cmd += ["-i", str(music)]
            aidx = 5
        else:
            aidx = None

        fr = FRAMES_PER
        fc = [
            # Ken Burns per slide (upscale 2x for smoother zoom)
            f"[0:v]scale=2160:3840,zoompan=z='min(1+0.001*on,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}[v1]",
            f"[1:v]scale=2160:3840,zoompan=z='1.08':x='(iw-iw/zoom)*on/{fr-1}':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}[v2]",
            f"[2:v]scale=2160:3840,zoompan=z='max(1.10-0.001*on,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}[v3]",
            # xfade crossfades
            f"[v1][v2]xfade=transition=fade:duration={XFADE}:offset={OFF1}[x1]",
            f"[x1][v3]xfade=transition=fade:duration={XFADE}:offset={OFF2}[xb]",
            # vignette on background
            "[xb]vignette=PI/5[bg]",
            # icon badge overlay
            f"[3:v]format=rgba,scale={W}:{H},setsar=1[ic]",
            "[bg][ic]overlay=0:0:format=auto[bg2]",
            # enhanced overlay (year, timeline, text, progress, particles)
            f"[4:v]format=rgba,scale={W}:{H},setsar=1,fps={FPS},minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1[en]",
            "[bg2][en]overlay=0:0:format=auto[vout]",
            # fade in/out
            f"[vout]fade=t=in:st=0:d=0.4,fade=t=out:st={TOTAL - 0.4}:d=0.4[v]",
        ]
        cmd += ["-filter_complex", ";".join(fc), "-map", "[v]"]
        if has_music and aidx is not None:
            cmd += ["-map", str(aidx) + ":a", "-c:a", "aac", "-shortest"]
        cmd += ["-t", str(TOTAL), "-c:v", "libx264", "-preset", "medium",
                "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart", str(out_path)]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Running FFmpeg (%d frames, %ds)…", TOTAL_FRAMES, TOTAL)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.error("ffmpeg failed:\n%s", proc.stderr[-1500:])
            return None

    log.info("Enhanced reel rendered: %s (%.1f MB)",
             out_path, out_path.stat().st_size / 1e6)
    return out_path
