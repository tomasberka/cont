"""Reel v5 — clean cinematic slides with smooth transitions.

The slides already contain all important content (year, headline, product).
This module focuses purely on smooth motion and professional transitions:
  • Subtle, eased Ken Burns per slide (barely noticeable drift + zoom)
  • Smooth slide transitions (smoothleft/smoothright) with motion blur
  • Vignette for cinematic feel
  • Fade in/out

No emoji, no glow, no text overlay — just the slides, animated well.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)

W, H = 1080, 1920
FPS = 30

SLIDE_S = 3.5
XFADE = 0.7
TOTAL = SLIDE_S * 3 - XFADE * 2
FRAMES_PER = int(SLIDE_S * FPS)
OFF1 = SLIDE_S - XFADE
OFF2 = SLIDE_S * 2 - XFADE * 2


def compose_reel(slide_paths: list[Path], out_path: Path,
                 cfg: Config, **kwargs) -> Path | None:
    """Compose 3 slides into a cinematic reel with smooth transitions."""
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg not found")
        return None
    if len(slide_paths) != 3 or not all(p.exists() for p in slide_paths):
        log.error("need 3 existing slides, got %s", slide_paths)
        return None

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
    for p in slide_paths:
        cmd += ["-loop", "1", "-i", str(p)]

    fr = FRAMES_PER
    xf = XFADE

    # Subtle, eased Ken Burns — barely noticeable motion
    # Slide 1: slow zoom in with gentle drift
    kb1 = (f"scale=2160:3840,"
           f"zoompan=z='min(1.04,1+0.0004*on)':"
           f"x='iw/2-(iw/zoom/2)+8*sin(PI*on/{fr})':"
           f"y='ih/2-(ih/zoom/2)+5*cos(PI*on/{fr})':"
           f"d={fr}:s={W}x{H}:fps={FPS}")
    # Slide 2: subtle orbital motion (camera drifts around center)
    kb2 = (f"scale=2160:3840,"
           f"zoompan=z='1.04':"
           f"x='iw/2-(iw/zoom/2)+10*sin(2*PI*on/{fr})':"
           f"y='ih/2-(ih/zoom/2)+6*cos(2*PI*on/{fr})':"
           f"d={fr}:s={W}x{H}:fps={FPS}")
    # Slide 3: slow zoom out with opposite drift
    kb3 = (f"scale=2160:3840,"
           f"zoompan=z='max(1.0,1.04-0.0004*on)':"
           f"x='iw/2-(iw/zoom/2)-8*sin(PI*on/{fr})':"
           f"y='ih/2-(ih/zoom/2)':"
           f"d={fr}:s={W}x{H}:fps={FPS}")

    fc = [
        f"[0:v]{kb1}[v1]",
        f"[1:v]{kb2}[v2]",
        f"[2:v]{kb3}[v3]",
        # Smooth slide transitions with motion blur (cinematic)
        f"[v1][v2]xfade=transition=smoothleft:duration={xf}:offset={OFF1}[x1]",
        f"[x1][v3]xfade=transition=smoothright:duration={xf}:offset={OFF2}[xb]",
        # Vignette for cinematic feel
        "[xb]vignette=PI/5[vg]",
        # Fade in/out
        f"[vg]fade=t=in:st=0:d=0.4,fade=t=out:st={TOTAL-0.4}:d=0.4[v]",
    ]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]",
            "-t", str(TOTAL), "-c:v", "libx264", "-preset", "medium",
            "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", str(out_path)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("FFmpeg compose v5 (%.1fs)…", TOTAL)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("ffmpeg failed:\n%s", proc.stderr[-800:])
        return None

    log.info("Reel v5: %s (%.1f MB)", out_path, out_path.stat().st_size / 1e6)
    return out_path
