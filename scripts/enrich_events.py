"""Enrich the content plan with extra 'on this day' events per day.

For every date in docs/plan/PLAN.json this fetches the Wikimedia on-this-day
feed (cs + en), scores every candidate with the same tech_scoring rules the
pipeline uses, and keeps a curated mix: tech-relevant events first, then
Wikipedia's hand-picked 'selected' items, plus notable tech births/deaths.

The result is cached to docs/plan/EVENTS.json (committed) so the deployed
dashboard stays 100 % static and free — no runtime network, no API cost.

Usage: PYTHONPATH=src python scripts/enrich_events.py [--limit 6] [--offline]
  --offline   only rebuild/trim from an existing EVENTS.json cache, no network
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import match  # noqa: E402
from contenthub.config import Config, REPO_ROOT, USER_AGENT  # noqa: E402
from contenthub.feed import strip_diacritics  # noqa: E402

PLAN_DIR = REPO_ROOT / "docs" / "plan"
EVENTS_PATH = PLAN_DIR / "EVENTS.json"
API = "https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/all/{mm}/{dd}"

KIND_LABEL = {
    "selected": "Výročí",
    "events": "Událost",
    "births": "Narození",
    "deaths": "Úmrtí",
}


def fetch(lang: str, date: dt.date) -> list[dict]:
    url = API.format(lang=lang, mm=f"{date.month:02d}", dd=f"{date.day:02d}")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    data = r.json()
    out: list[dict] = []
    for kind in ("selected", "events", "births", "deaths"):
        for e in data.get(kind, []):
            text = (e.get("text") or "").strip()
            if not text:
                continue
            out.append({"year": e.get("year"), "text": text, "kind": kind, "lang": lang})
    return out


def tech_score(entry: dict, rules: match.RuleSet) -> tuple[int, list[str]]:
    text = strip_diacritics(entry["text"])
    hits = [kw for kw in rules.tech_scoring if match._contains(text, kw)]
    return sum(rules.tech_scoring[kw] for kw in hits), hits


def overlaps(a: str, b: str) -> bool:
    """Rough duplicate check between two Czech/English sentences."""
    wa = set(strip_diacritics(a).split())
    wb = set(strip_diacritics(b).split())
    if not wa or not wb:
        return False
    inter = wa & wb
    return len(inter) / min(len(wa), len(wb)) > 0.5


def curate(cands: list[dict], rules: match.RuleSet, main: dict, limit: int) -> list[dict]:
    """Pick the best non-duplicate mix: tech events, then selected, then tech births."""
    main_text = strip_diacritics(
        (main.get("fact") or "") + " " + (main.get("caption") or "")
    )
    main_year = main.get("year")
    seen: list[dict] = []

    def add(e: dict) -> None:
        if len(seen) >= limit:
            return
        if overlaps(e["text"], main_text):
            return
        if main_year and e.get("year") == main_year and e["kind"] in ("selected", "events"):
            return
        for i, s in enumerate(seen):
            if overlaps(e["text"], s["text"]):
                return
            # cross-language duplicate: same year + kind -> keep Czech
            if (s["year"] == e.get("year") and s["kind"] == e["kind"]
                    and s["lang"] != e["lang"]):
                if e["lang"] == "cs":
                    seen[i] = e
                return
        seen.append(e)

    scored = []
    for e in cands:
        sc, _ = tech_score(e, rules)
        e["score"] = sc
        scored.append(e)

    tech_events = sorted(
        [e for e in scored if e["kind"] in ("events", "selected") and e["score"] >= rules.min_score],
        key=lambda e: (-e["score"], -(e["year"] or 0)),
    )
    selected = sorted(
        [e for e in scored if e["kind"] == "selected" and e["score"] < rules.min_score],
        key=lambda e: -(e["year"] or 0),
    )
    tech_births = sorted(
        [e for e in scored if e["kind"] in ("births", "deaths") and e["score"] >= rules.min_score],
        key=lambda e: (-e["score"], -(e["year"] or 0)),
    )

    for e in tech_events + selected + tech_births:
        add(e)
    for e in scored:  # fallback: fill remaining with general events
        if len(seen) >= limit:
            break
        add(e)

    out = []
    for e in seen:
        out.append({
            "year": e["year"],
            "text": e["text"],
            "kind": e["kind"],
            "label": KIND_LABEL.get(e["kind"], e["kind"]),
            "tech": bool(e["score"] >= rules.min_score),
        })
    out.sort(key=lambda e: -(e["year"] or 0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    rules = match.RuleSet.load(cfg.rules_path)
    plan = json.loads((PLAN_DIR / "PLAN.json").read_text(encoding="utf-8"))

    cache = {}
    if EVENTS_PATH.exists():
        cache = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))

    for e in plan:
        date = dt.date.fromisoformat(e["date"])
        key = e["date"]
        if args.offline:
            if key in cache:
                cache[key] = cache[key][: args.limit]
            continue
        cands: list[dict] = []
        for lang in ("cs", "en"):
            try:
                cands.extend(fetch(lang, date))
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {date} {lang}: {exc}", file=sys.stderr)
        m = re.search(r"(?:Píše se rok|rok)\s+(\d{3,4})", e.get("caption") or "")
        year = int(m.group(1)) if m else None
        main = {"fact": e.get("fact") or "", "caption": e.get("caption") or "", "year": year}
        cache[key] = curate(cands, rules, main, args.limit)
        n_tech = sum(1 for x in cache[key] if x["tech"])
        print(f"[ok] {date}: {len(cache[key])} extra events ({n_tech} tech)")

    EVENTS_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"events: {EVENTS_PATH} ({EVENTS_PATH.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
