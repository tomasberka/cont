"""CLI: python -m contenthub [run|refresh-token] [--date YYYY-MM-DD] [--force] [--live]"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys

from .config import Config
from . import pipeline, publish


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(prog="contenthub")
    sub = p.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="Generate (and optionally publish) today's post")
    runp.add_argument("--date", help="Override date (YYYY-MM-DD), default today")
    runp.add_argument("--force", action="store_true", help="Redo even if already posted")
    runp.add_argument("--live", action="store_true",
                      help="Actually publish (overrides DRY_RUN=1 default)")
    runp.add_argument("--reel", action="store_true", help="Also render the 9:16 reel")

    sub.add_parser("refresh-token", help="Refresh the long-lived IG token")

    args = p.parse_args()
    cfg = Config()

    if args.cmd == "run":
        if args.live:
            cfg.dry_run = False
        if args.reel:
            cfg.make_reel = True
        date = dt.date.fromisoformat(args.date) if args.date else None
        summary = pipeline.run(cfg, date=date, force=args.force)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "refresh-token":
        tok = publish.refresh_long_lived_token(cfg)
        if tok:
            print("New token acquired — update the IG_ACCESS_TOKEN secret with it.")
            print(tok)
            return 0
        print("Token refresh failed or not configured.", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
