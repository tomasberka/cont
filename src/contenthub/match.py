"""Fact scoring (is it tech?) and fact->product matching, driven by data/rules.yml."""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .facts import Fact
from .feed import Product, strip_diacritics

log = logging.getLogger(__name__)

# Keywords so short they need whole-word matching to avoid false hits
# ("mys" inside "mysterious", "web" inside "weber", ...).
_WHOLE_WORD = {"mys", "web", "sit", "cpu", "gps", "usb", "cip", "www"}


@dataclass
class RuleSet:
    min_score: int
    tech_scoring: dict[str, int]
    product_rules: list[dict]
    evergreen_terms: list[str]
    priority_boost: list[str]
    priority_penalty: list[str]

    @classmethod
    def load(cls, path: Path) -> "RuleSet":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        prio = data.get("product_priority") or {}
        return cls(
            min_score=int(data.get("min_score", 3)),
            tech_scoring={strip_diacritics(k): int(v) for k, v in data["tech_scoring"].items()},
            product_rules=data["product_rules"],
            evergreen_terms=data.get("evergreen_terms", []),
            priority_boost=[strip_diacritics(t) for t in prio.get("boost", [])],
            priority_penalty=[strip_diacritics(t) for t in prio.get("penalty", [])],
        )

    def priority(self, p: Product) -> int:
        """Margin proxy: +1 per boost term, -1 per penalty term in the blob."""
        return (sum(1 for t in self.priority_boost if t in p.blob)
                - sum(1 for t in self.priority_penalty if t in p.blob))


def _contains(haystack: str, needle: str) -> bool:
    if needle in _WHOLE_WORD or len(needle) <= 3:
        return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None
    return needle in haystack


def score_fact(fact: Fact, rules: RuleSet) -> tuple[int, list[str]]:
    """Return (tech-relevance score, matched keywords) for a fact."""
    text = strip_diacritics(fact.text)
    hits = [kw for kw in rules.tech_scoring if _contains(text, kw)]
    score = sum(rules.tech_scoring[kw] for kw in hits)
    return score, hits


def pick_fact(facts: list[Fact], rules: RuleSet) -> tuple[Fact | None, list[str]]:
    """Best tech fact above threshold. Czech facts win ties (native copy > translation)."""
    best: tuple[int, int, Fact, list[str]] | None = None
    for f in facts:
        score, hits = score_fact(f, rules)
        if score < rules.min_score:
            continue
        lang_bonus = 1 if f.lang == "cs" else 0
        key = (score, lang_bonus)
        if best is None or key > (best[0], best[1]):
            best = (score, lang_bonus, f, hits)
    if best is None:
        return None, []
    log.info("Picked fact (score=%d, lang=%s): %s", best[0], best[2].lang, best[2].text[:90])
    return best[2], best[3]


def _candidates(products: list[Product], terms: list[str]) -> list[Product]:
    """Only IN-STOCK products with an image are ever candidates."""
    out: list[Product] = []
    for term in terms:
        t = strip_diacritics(term)
        out.extend(p for p in products if t in p.blob and p.img and p.in_stock)
        if out:
            break  # first term with hits wins — keeps rules ordered by specificity
    return out


def load_overrides(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def override_for(overrides: dict, date: dt.date) -> dict | None:
    """Manual per-day override: exact date wins over yearly MM-DD."""
    return (overrides.get(date.isoformat())
            or overrides.get(f"{date.month:02d}-{date.day:02d}"))


def apply_override(ov: dict, products: list[Product],
                   rules: "RuleSet") -> Product | None:
    """Resolve a manual override to a product (in-stock preferred)."""
    if pid := ov.get("product_id"):
        for p in products:
            if p.item_id == str(pid):
                return p
        log.warning("Override product_id %s not found in feed — falling back", pid)
    if term := ov.get("product_term"):
        cands = _candidates(products, [term])
        if cands:
            cands.sort(key=lambda p: -rules.priority(p))
            return cands[0]
        log.warning("Override term %r matched nothing in stock — falling back", term)
    return None


def pick_product(
    products: list[Product],
    fact_keywords: list[str],
    rules: RuleSet,
    recently_used_ids: set[str],
    date: dt.date,
    product_hint: str = "",
) -> Product | None:
    """Fact keywords -> rules -> candidate products; deterministic daily rotation.

    Keywords are tried in the curator's priority order, and a rule whose terms
    match nothing in the current stock is skipped instead of dumping the post
    on a random product (e.g. a virus fact in a shop with no antivirus falls
    through to its 'internet' keyword and lands on routers).
    """
    cands: list[Product] = []
    tried: set[int] = set()
    # 0) explicit product hint on the fact (curator's precise pick, e.g. "wifi 6 router")
    if product_hint:
        cands = _candidates(products, [product_hint])
    # 1) rules in the order of the fact's own keywords (curation priority)
    if not cands:
        for kw in fact_keywords:
            for ri, rule in enumerate(rules.product_rules):
                if ri in tried or kw not in rule["triggers"]:
                    continue
                tried.add(ri)
                cands = _candidates(products, rule["terms"])
                if cands:
                    break
            if cands:
                break
    # 2) any other matching rule (triggers hit by any keyword)
    if not cands:
        for ri, rule in enumerate(rules.product_rules):
            if ri in tried or not any(t in fact_keywords for t in rule["triggers"]):
                continue
            cands = _candidates(products, rule["terms"])
            if cands:
                break
    # 3) evergreen rotation, then last-resort whole catalogue
    if not cands:
        idx = date.timetuple().tm_yday % len(rules.evergreen_terms)
        cands = _candidates(products, [rules.evergreen_terms[idx]])
    if not cands:
        cands = [p for p in products if p.img and p.in_stock]
    if not cands:  # truly empty stock — last resort, anything with a photo
        cands = [p for p in products if p.img]
    if not cands:
        return None

    fresh = [p for p in cands if p.item_id not in recently_used_ids]
    pool = fresh or cands
    # margin proxy: keep only the highest-priority tier, then rotate within it
    top = max(rules.priority(p) for p in pool)
    pool = [p for p in pool if rules.priority(p) == top]
    # Deterministic rotation: same date -> same pick (idempotent reruns).
    choice = pool[date.toordinal() % len(pool)]
    log.info("Picked product: %s (%s, priority=%d, stock=%s)",
             choice.name, choice.item_id, top, choice.in_stock)
    return choice
