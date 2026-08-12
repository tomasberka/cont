"""Optional 9:16 reel (phase 2, enable with MAKE_REEL=1).

Strategy: render the fact/product as full-quality Pillow frames (start + end card),
then let FFmpeg do a slow Ken Burns zoom between them. This avoids drawtext
escaping issues with Czech diacritics entirely — text is rasterized by Pillow.
Requires ffmpeg on PATH. Music: drop a royalty-free MP3 at assets/music.mp3
(YouTube Audio Library / Pixabay) — silent video is produced if absent.
"""
from __future__ import annotations

import datetime as dt
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import Config
from .feed import Product
from . import media_image

log = logging.getLogger(__name__)

RW, RH = 1080, 1920
DURATION = 12  # seconds


def render_reel(
    fact_headline: str | None,
    product: Product,
    cfg: Config,
    date: dt.date,
    out_path: Path,
) -> Path | None:
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg not found — skipping reel")
        return None

    with tempfile.TemporaryDirectory() as td:
        frame = Path(td) / "frame.jpg"
        # Reuse the card renderer at feed ratio, then pad to 9:16 in FFmpeg.
        media_image.render_card(fact_headline, product, cfg, date, frame)

        music = cfg.fonts_dir.parent / "music.mp3"  # assets/music.mp3
        has_music = music.exists()

        vf = (
            f"scale={RW}:-1,pad={RW}:{RH}:(ow-iw)/2:(oh-ih)/2:color=0x0d111c,"
            f"zoompan=z='min(zoom+0.0012,1.15)':d={DURATION * 25}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={RW}x{RH}:fps=25"
        )
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(frame)]
        if has_music:
            cmd += ["-i", str(music)]
        cmd += ["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]"]
        if has_music:
            cmd += ["-map", "1:a", "-c:a", "aac", "-shortest"]
        cmd += ["-t", str(DURATION), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-r", "25", str(out_path)]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.error("ffmpeg failed: %s", proc.stderr[-800:])
            return None
    log.info("Reel rendered: %s", out_path)
    return out_path
