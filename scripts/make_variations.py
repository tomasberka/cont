"""Generate a per-topic showroom of posts: variations/<topic>/ with slides,
caption and the ideal-match product info.

For every content topic (derived from the product-matching rules), this picks
the best curated fact from the fact bank, matches the ideal product from the
live feed, renders the 3-slide carousel (styles rotate across topics so the
showroom doubles as a style catalogue) and writes the ready-to-post caption.

Usage: PYTHONPATH=src python scripts/make_variations.py [out_dir]
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import caption as caption_mod  # noqa: E402
from contenthub import facts as facts_mod  # noqa: E402
from contenthub import facts_bank, feed as feed_mod, match as match_mod  # noqa: E402
from contenthub.config import Config, REPO_ROOT  # noqa: E402
from contenthub.media_carousel import STYLES, default_texts, render_carousel  # noqa: E402

# topic label -> keywords that identify a bank entry as belonging to the topic
TOPICS = {
    "bezpecnost": ["virus", "hacker", "cyber", "kyber"],
    "procesory-a-cipy": ["procesor", "processor", "microprocessor", "cpu", "intel",
                         "amd", "tranzistor", "transistor", "chip", "cip",
                         "polovodic", "semiconductor"],
    "graficke-karty": ["nvidia", "graficka", "gpu"],
    "mysi-a-klavesnice": ["mys", "mouse", "klavesnice", "keyboard"],
    "monitory-a-tv": ["monitor", "displej", "display", "televize", "television"],
    "internet-a-wifi": ["internet", "web", "www", "arpanet", "ethernet", "network",
                        "wifi", "wi-fi", "router", "sit"],
    "telefony": ["telefon", "smartphone", "iphone", "mobil", "phone"],
    "gaming": ["playstation", "nintendo", "xbox", "videohra", "video game",
               "konzole", "atari", "commodore"],
    "ukladani-dat": ["disketa", "floppy", "pevny disk", "hard disk", "usb",
                     "pamet", "memory", "storage"],
    "pocitace": ["pocitac", "computer", "ibm", "macintosh", "apple", "microsoft",
                 "windows", "linux", "notebook", "laptop", "software",
                 "programator", "turing", "algoritmus", "kalkulacka", "calculator"],
    "audio": ["sluchatka", "audio", "radio"],
}


def pick_entry_for_topic(bank: dict, keywords: list[str]) -> facts_bank.BankEntry | None:
    """Best curated entry whose keywords intersect the topic (prefer cs source,
    then upcoming dates so the showroom stays current)."""
    today = dt.date.today()
    cands = [
        e for e in bank.values()
        if not e.evergreen and any(k in keywords for k in e.keywords)
    ]
    if not cands:
        return None

    def sort_key(e: facts_bank.BankEntry):
        mm, dd = map(int, e.day.split("-"))
        entry_date = dt.date(today.year, mm, dd)
        days_ahead = (entry_date - today).days % 366
        return (0 if e.source_lang == "cs" else 1, days_ahead)

    return sorted(cands, key=sort_key)[0]


def main() -> int:
    out_root = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "variations"
    cfg = Config()
    cfg.ensure_dirs()
    bank = facts_bank.load_bank(cfg.bank_path)
    products = feed_mod.load_products(cfg.feed_url)
    rules = match_mod.RuleSet.load(cfg.rules_path)

    index = []
    for i, (topic, kws) in enumerate(TOPICS.items()):
        entry = pick_entry_for_topic(bank, kws)
        if entry is None:
            print(f"[skip] {topic}: no curated fact")
            continue
        mm, dd = map(int, entry.day.split("-"))
        date = dt.date(dt.date.today().year, mm, dd)
        # topic keywords first — the showroom must show the TOPIC's product,
        # even when the curator ranked another aspect of the fact higher
        ordered = ([k for k in entry.keywords if k in kws]
                   + [k for k in entry.keywords if k not in kws])
        product = match_mod.pick_product(products, ordered, rules, set(), date)
        if product is None:
            print(f"[skip] {topic}: no product match")
            continue

        fact = facts_mod.Fact("cs", entry.year, entry.headline, "bank")
        texts = default_texts(fact, product, date, story=entry.story)
        texts.hook_headline = entry.headline
        style = STYLES[i % len(STYLES)]

        tdir = out_root / topic
        if tdir.exists():
            shutil.rmtree(tdir)
        tdir.mkdir(parents=True)
        render_carousel(texts, fact, product, cfg, date, tdir / "slide", style=style)
        cap = caption_mod.bank_caption(entry, product, cfg, date)
        (tdir / "caption.txt").write_text(cap + "\n", encoding="utf-8")
        meta = {
            "topic": topic, "day": entry.day, "year": entry.year,
            "headline": entry.headline, "story": entry.story,
            "keywords": entry.keywords, "style": style,
            "product": {"id": product.item_id, "name": product.name,
                        "price": product.price_czk, "url": product.url,
                        "img": product.img, "category": product.category},
        }
        (tdir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append(meta)
        print(f"[ok] {topic}: {entry.day} '{entry.headline[:50]}' -> "
              f"{product.name[:45]} ({style})")

    (out_root / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(index)} topics -> {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
