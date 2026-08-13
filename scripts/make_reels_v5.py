"""Batch render clean reels for a date range on macOS.

Usage:
  PYTHONPATH=src python3 scripts/make_reels_v5.py 2026-08-14 2026-08-31
  PYTHONPATH=src python3 scripts/make_reels_v5.py 2026-08-14 2026-08-14 --dry
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from contenthub.config import Config
from contenthub.media_reel_v5 import compose_reel

PLAN = REPO / "docs" / "plan" / "PLAN.json"
OUT = REPO / "out" / "reels"


def main(start: dt.date, end: dt.date, dry: bool = False) -> int:
    cfg = Config()
    plan = json.loads(PLAN.read_text())

    rendered = 0
    selected = 0
    for entry in plan:
        date = dt.date.fromisoformat(entry["date"])
        if not start <= date <= end:
            continue
        selected += 1
        slide_dir = REPO / "docs" / "plan" / entry.get("dir", entry["date"])
        slides = [slide_dir / f"post-{n}.jpg" for n in (1, 2, 3)]

        if not all(s.exists() for s in slides):
            log.error("Skip %s — missing slides", date)
            continue

        out = OUT / f"reel-{date.isoformat()}.mp4"
        if dry:
            log.info("DRY %s", date)
            rendered += 1
            continue

        log.info("Rendering %s…", date)
        if compose_reel(slides, out, cfg):
            rendered += 1
        else:
            log.error("Failed %s", date)

    action = "checked" if dry else "rendered"
    log.info("Done — %s %d/%d clean reels", action, rendered, selected)
    return 0 if rendered == selected else 1


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--dry"]
    if len(args) != 2:
        raise SystemExit("Usage: make_reels_v5.py START_DATE END_DATE [--dry]")
    start = dt.date.fromisoformat(args[0])
    end = dt.date.fromisoformat(args[1])
    if start > end:
        raise SystemExit("START_DATE must not be after END_DATE")
    raise SystemExit(main(start, end, "--dry" in sys.argv))
