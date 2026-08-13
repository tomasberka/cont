"""Batch render clean reels for all plan dates.

Reads PLAN.json + facts_bank.yml to get fact year, headline, and story
for the data-driven overlays. Uses media_reel_v5.compose_reel().
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from contenthub.config import Config
from contenthub.reel_icons import pick_icon
from contenthub.media_reel_v5 import compose_reel

PLAN = REPO / "docs" / "plan" / "PLAN.json"
FACTS = REPO / "data" / "facts_bank.yml"
OUT = REPO / "out" / "reels"


def _parse_year_from_caption(caption: str) -> int | None:
    m = re.search(r"rok\s+(\d{4})", caption)
    return int(m.group(1)) if m else None


def _load_facts_years() -> dict[str, int]:
    """Parse facts_bank.yml to extract year per MM-DD key."""
    years: dict[str, int] = {}
    if not FACTS.exists():
        return years
    cur_key = None
    for line in FACTS.read_text().splitlines():
        m = re.match(r'^"?(?:0?(?:\d{1,2})-(?:\d{1,2}))"?\s*:', line)
        if m:
            raw = line.split(":")[0].strip().strip('"')
            # normalize MM-DD
            parts = raw.split("-")
            if len(parts) == 2:
                mm = parts[0].zfill(2)
                dd = parts[1].zfill(2)
                cur_key = f"{mm}-{dd}"
        elif line.strip().startswith("year:") and cur_key:
            ym = re.search(r"year:\s*(\d{4})", line)
            if ym:
                years[cur_key] = int(ym.group(1))
    return years


def main(dry: bool = False):
    cfg = Config()
    plan = json.loads(PLAN.read_text())
    fact_years = _load_facts_years()
    log.info("Loaded %d fact years from bank", len(fact_years))

    rendered = 0
    for entry in plan:
        date = entry["date"]
        mm_dd = entry.get("dir", date[5:])  # "2026-08-14" → "08-14"
        slide_dir = REPO / "docs" / "plan" / mm_dd
        slides = [slide_dir / f"post-{n}.jpg" for n in (1, 2, 3)]

        if not all(s.exists() for s in slides):
            log.warning("Skip %s — missing slides", date)
            continue

        icon = pick_icon(
            entry.get("fact_keywords", []),
            entry.get("pillar", ""),
            entry.get("fact", ""),
        )

        # year from facts_bank (preferred) or from caption
        year = fact_years.get(mm_dd)
        if not year:
            year = _parse_year_from_caption(entry.get("caption", ""))
        if not year:
            year = 2000

        enriched = {
            **entry,
            "fact_year": year,
            "headline": entry.get("fact", ""),
            "story": entry.get("caption", "").split("\n\n")[0] if entry.get("caption") else "",
        }

        out = OUT / f"reel-{date}.mp4"
        if dry:
            log.info("DRY %s  icon=%s  year=%d", date, icon, year)
            continue

        log.info("Rendering %s…", date)
        compose_reel(slides, out, cfg)
        rendered += 1

    log.info("Done — rendered %d clean reels", rendered)


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    main(dry)
