"""Reel v2 — compose the 3 carousel slides into a 9:16 MP4 with animated
topic icon overlay, Ken Burns motion and crossfades. All local (FFmpeg + Pillow).

Pipeline:
  1. Each slide (1080x1920) gets a Ken Burns zoompan (in / pan / out).
  2. Slides are joined with smooth xfade crossfades.
  3. A full-res animated icon overlay (reel_icons.render_overlay_sequence)
     is composited over the video with its alpha channel.
  4. Subtle vignette + fade in/out; optional music from assets/music.mp3.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import reel_icons
from .config import Config

log = logging.getLogger(__name__)

RW, RH = 1080, 1920
FPS = 25
SLIDE_S = 4.0          # seconds per slide
XFADE = 0.8            # crossfade duration
TOTAL = SLIDE_S * 3 - XFADE * 2   # 10.4 s
OFF1 = SLIDE_S - XFADE            # 3.2
OFF2 = SLIDE_S * 2 - XFADE * 2    # 6.4


def _ken_burns(motion: str, frames: int) -> str:
    """Return a zoompan filter string for a given motion ('in'|'pan'|'out')."""
    if motion == "pan":
        z = "1.10"
        x = f"(iw-iw/{z})*on/{frames - 1}"
        y = f"ih/2-(ih/{z}/2)"
    elif motion == "out":
        z = f"max(1.12-0.0012*on,1.0)"
        x = f"iw/2-(iw/zoom/2)"
        y = f"ih/2-(ih/zoom/2)"
    else:  # in
        z = f"min(1+0.0012*on,1.12)"
        x = f"iw/2-(iw/zoom/2)"
        y = f"ih/2-(ih/zoom/2)"
    return (f"scale=2160:3840,zoompan=z='{z}':x='{x}':y='{y}'"
            f":d={frames}:s={RW}x{RH}:fps={FPS}")


def compose_reel(slide_paths: list[Path], icon: str, out_path: Path,
                 cfg: Config, music_path: Path | None = None,
                 seed: int = 0) -> Path | None:
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg not found — skipping reel")
        return None
    if len(slide_paths) != 3 or not all(p.exists() for p in slide_paths):
        log.error("reel needs 3 existing slides, got %s", slide_paths)
        return None

    frames = int(SLIDE_S * FPS)
    music = music_path or (cfg.fonts_dir.parent / "music.mp3")
    has_music = music.exists()

    with tempfile.TemporaryDirectory() as td:
        overlay_dir = Path(td) / "ov"
        reel_icons.render_overlay_sequence(overlay_dir, icon,
                                           fps=FPS, duration=TOTAL, seed=seed)

        cmd = ["ffmpeg", "-y"]
        for p in slide_paths:
            cmd += ["-i", str(p)]
        cmd += ["-framerate", str(FPS), "-i", str(overlay_dir / "f%04d.png")]
        if has_music:
            cmd += ["-i", str(music)]

        fc = [
            f"[0:v]{_ken_burns('in', frames)}[v1]",
            f"[1:v]{_ken_burns('pan', frames)}[v2]",
            f"[2:v]{_ken_burns('out', frames)}[v3]",
            f"[v1][v2]xfade=transition=fade:duration={XFADE}:offset={OFF1}[x1]",
            f"[x1][v3]xfade=transition=fade:duration={XFADE}:offset={OFF2}[xb]",
            "[xb]vignette=PI/5[bg]",
            f"[3:v]format=rgba,scale={RW}:{RH},setsar=1[ov]",
            "[bg][ov]overlay=0:0:format=auto[vout]",
            f"[vout]fade=t=in:st=0:d=0.4,fade=t=out:st={TOTAL - 0.4}:d=0.4[v]",
        ]
        cmd += ["-filter_complex", ";".join(fc), "-map", "[v]"]
        if has_music:
            cmd += ["-map", "4:a", "-c:a", "aac", "-shortest"]
        cmd += ["-t", str(TOTAL), "-c:v", "libx264", "-preset", "medium",
                "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart", str(out_path)]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.error("ffmpeg failed: %s", proc.stderr[-1200:])
            return None
    log.info("Reel rendered: %s", out_path)
    return out_path
