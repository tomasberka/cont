"""Batch-render 9:16 carousel reels (MP4) for a date range — designed to run
as a one-click background job on GitHub Actions (workflow: make-reels.yml).

Free to run: FFmpeg on the Actions runner, facts from the bank, products from
the live feed. Output lands in out/reels/ and is uploaded as a run artifact.

Usage: PYTHONPATH=src python scripts/make_reels.py 2026-08-14 2026-08-31
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import facts_bank, feed as feed_mod, match as match_mod, media_reel  # noqa: E402
from contenthub.config import Config, REPO_ROOT  # noqa: E402


def main() -> int:
    start = dt.date.fromisoformat(sys.argv[1])
    end = dt.date.fromisoformat(sys.argv[2])
    cfg = Config()
    out_dir = REPO_ROOT / "out" / "reels"
    out_dir.mkdir(parents=True, exist_ok=True)

    bank = facts_bank.load_bank(cfg.bank_path)
    products = feed_mod.load_products(cfg.feed_url)
    rules = match_mod.RuleSet.load(cfg.rules_path)

    d, done = start, 0
    while d <= end:
        entry = facts_bank.get_entry(bank, d)
        keywords = entry.keywords if entry else []
        product = match_mod.pick_product(products, keywords, rules, set(), d)
        headline = entry.headline if entry else None
        path = media_reel.render_reel(headline, product, cfg, d,
                                      out_dir / f"reel-{d.isoformat()}.mp4")
        print(f"[{'ok' if path else 'skip'}] {d}")
        done += bool(path)
        d += dt.timedelta(days=1)
    print(f"{done} reels -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
