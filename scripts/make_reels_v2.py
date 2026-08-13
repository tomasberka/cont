"""Batch-compose 9:16 reels from the EXISTING carousel slides in docs/plan/<date>/.

No feed, no network: slides + PLAN.json (fact keywords + pillar) are already on
disk, so this is a pure local render. Each reel gets a topic icon overlay with
alpha background + Ken Burns + crossfades (see contenthub.media_reel_v2).

Usage: PYTHONPATH=src python scripts/make_reels_v2.py [START] [END]
       (defaults to the whole plan; or pass e.g. 2026-08-14 2026-08-16)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import media_reel_v2, reel_icons  # noqa: E402
from contenthub.config import Config, REPO_ROOT  # noqa: E402

PLAN_DIR = REPO_ROOT / "docs" / "plan"


def main() -> int:
    plan = json.loads((PLAN_DIR / "PLAN.json").read_text(encoding="utf-8"))
    plan.sort(key=lambda e: e["date"])
    if len(sys.argv) >= 3:
        start = dt.date.fromisoformat(sys.argv[1])
        end = dt.date.fromisoformat(sys.argv[2])
        plan = [e for e in plan if start <= dt.date.fromisoformat(e["date"]) <= end]

    cfg = Config()
    out_dir = REPO_ROOT / "out" / "reels"
    out_dir.mkdir(parents=True, exist_ok=True)

    done = 0
    for e in plan:
        d = dt.date.fromisoformat(e["date"])
        dir_ = PLAN_DIR / (e.get("dir") or e["date"])
        slides = [dir_ / f"post-{n}.jpg" for n in (1, 2, 3)]
        if not all(s.exists() for s in slides):
            print(f"[skip] {d} — chybí slidy v {dir_}")
            continue
        icon = reel_icons.pick_icon(e.get("fact_keywords") or [], e.get("pillar") or "",
                                    e.get("fact") or "")
        seed = d.toordinal()
        path = media_reel_v2.compose_reel(
            slides, icon, out_dir / f"reel-{d.isoformat()}.mp4", cfg, seed=seed)
        print(f"[{'ok' if path else 'fail'}] {d} · ikona={icon}")
        done += bool(path)
    print(f"{done} reels -> {out_dir}")
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
