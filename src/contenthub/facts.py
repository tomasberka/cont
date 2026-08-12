"""Fetch 'on this day' facts from the Wikimedia feed API (cs + en)."""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

import requests

from .config import USER_AGENT

log = logging.getLogger(__name__)

API = "https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/all/{mm}/{dd}"


@dataclass
class Fact:
    lang: str  # "cs" or "en"
    year: int | None
    text: str
    kind: str  # events / selected / births / deaths / holidays

    def headline(self, today: dt.date) -> str:
        """'Před 45 lety …' prefix helper for Czech facts."""
        if self.year and self.lang == "cs":
            years = today.year - self.year
            if years > 0:
                return f"Před {years} lety: {self.text}"
        return self.text


def fetch_onthisday(lang: str, date: dt.date, timeout: int = 30) -> list[Fact]:
    url = API.format(lang=lang, mm=f"{date.month:02d}", dd=f"{date.day:02d}")
    resp = requests.get(
        url,
        headers={"Api-User-Agent": USER_AGENT, "User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    facts: list[Fact] = []
    for kind in ("selected", "events", "holidays"):
        for entry in data.get(kind, []):
            text = (entry.get("text") or "").strip()
            if not text:
                continue
            facts.append(Fact(lang=lang, year=entry.get("year"), text=text, kind=kind))
    log.info("Wikimedia %s: %d candidate facts for %s", lang, len(facts), date)
    return facts


def fetch_all(langs: tuple[str, ...], date: dt.date) -> list[Fact]:
    """Fetch facts for every language; a failing language never kills the run."""
    facts: list[Fact] = []
    for lang in langs:
        try:
            facts.extend(fetch_onthisday(lang, date))
        except Exception:  # noqa: BLE001 — degrade gracefully, log the cause
            log.warning("on-this-day fetch failed for lang=%s", lang, exc_info=True)
    return facts
