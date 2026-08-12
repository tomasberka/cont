"""Curated year-round fact bank — the primary, fully-offline content source.

data/facts_bank.yml holds one entry per calendar day (MM-DD), curated by an
agent sweep over Wikipedia's on-this-day (cs+en) and written as polished Czech
copy. Dates and facts stay Wikipedia-grounded; only the wording is original.

The pipeline prefers the bank; the live Wikimedia scorer remains a fallback for
missing/evergreen days. No LLM or paid service is needed at runtime.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


@dataclass
class BankEntry:
    day: str  # "MM-DD"
    evergreen: bool
    year: int | None = None
    headline: str = ""  # Czech hook, no year
    story: str = ""  # 2-sentence Czech "why it matters"
    keywords: list[str] = field(default_factory=list)
    source_lang: str = ""
    product_hint: str = ""  # optional precise search term, beats keyword rules

    def hook_with_years_ago(self, today: dt.date) -> str:
        return self.headline


def load_bank(path: Path) -> dict[str, BankEntry]:
    if not path.exists():
        log.info("No fact bank at %s — live mode only", path)
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    bank: dict[str, BankEntry] = {}
    for day, e in data.items():
        if not isinstance(e, dict):
            continue
        bank[str(day)] = BankEntry(
            day=str(day),
            evergreen=bool(e.get("evergreen", False)),
            year=e.get("year"),
            headline=(e.get("headline_cs") or "").strip(),
            story=(e.get("story_cs") or "").strip(),
            keywords=list(e.get("keywords") or []),
            source_lang=e.get("source_lang") or "",
            product_hint=(e.get("product_hint") or "").strip(),
        )
    log.info("Fact bank loaded: %d days (%d curated)", len(bank),
             sum(1 for b in bank.values() if not b.evergreen))
    return bank


def get_entry(bank: dict[str, BankEntry], date: dt.date) -> BankEntry | None:
    entry = bank.get(f"{date.month:02d}-{date.day:02d}")
    if entry and not entry.evergreen and entry.headline and entry.story:
        return entry
    return None
