"""Offline unit tests — no network. Run: PYTHONPATH=src pytest -q"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from contenthub.config import Config, REPO_ROOT
from contenthub.facts import Fact
from contenthub.feed import Product, parse_feed, strip_diacritics
from contenthub.match import RuleSet, pick_fact, pick_product, score_fact

FEED_XML = """<?xml version="1.0" encoding="utf-8"?>
<SHOP>
  <SHOPITEM>
    <ITEM_ID>001</ITEM_ID>
    <PRODUCTNAME>AMD Ryzen 5 5600</PRODUCTNAME>
    <URL>https://www.hellocomp.cz/ryzen-5-5600/</URL>
    <IMGURL>https://cdn.example/ryzen.jpg</IMGURL>
    <PRICE_VAT>2890,00</PRICE_VAT>
    <DELIVERY_DATE>0</DELIVERY_DATE>
    <MANUFACTURER>AMD</MANUFACTURER>
    <CATEGORYTEXT>Heureka.cz | Elektronika | Počítačové komponenty | Procesory</CATEGORYTEXT>
  </SHOPITEM>
  <SHOPITEM>
    <ITEM_ID>003</ITEM_ID>
    <PRODUCTNAME>Intel Core i5 TRAY</PRODUCTNAME>
    <URL>https://www.hellocomp.cz/i5-tray/</URL>
    <IMGURL>https://cdn.example/i5.jpg</IMGURL>
    <PRICE_VAT>3890,00</PRICE_VAT>
    <DELIVERY_DATE>0</DELIVERY_DATE>
    <MANUFACTURER>Intel</MANUFACTURER>
    <CATEGORYTEXT>Heureka.cz | Elektronika | Počítačové komponenty | Procesory</CATEGORYTEXT>
  </SHOPITEM>
  <SHOPITEM>
    <ITEM_ID>004</ITEM_ID>
    <PRODUCTNAME>AMD Ryzen 9 9900X</PRODUCTNAME>
    <URL>https://www.hellocomp.cz/ryzen-9/</URL>
    <IMGURL>https://cdn.example/r9.jpg</IMGURL>
    <PRICE_VAT>12890,00</PRICE_VAT>
    <DELIVERY_DATE>14</DELIVERY_DATE>
    <MANUFACTURER>AMD</MANUFACTURER>
    <CATEGORYTEXT>Heureka.cz | Elektronika | Počítačové komponenty | Procesory</CATEGORYTEXT>
  </SHOPITEM>
  <SHOPITEM>
    <ITEM_ID>002</ITEM_ID>
    <PRODUCTNAME>Logitech G502 myš</PRODUCTNAME>
    <URL>https://www.hellocomp.cz/g502/</URL>
    <IMGURL>https://cdn.example/g502.jpg</IMGURL>
    <PRICE_VAT>1290,00</PRICE_VAT>
    <DELIVERY_DATE>0</DELIVERY_DATE>
    <MANUFACTURER>Logitech</MANUFACTURER>
    <CATEGORYTEXT>Heureka.cz | Elektronika | Klávesnice a myši | Myši</CATEGORYTEXT>
  </SHOPITEM>
</SHOP>""".encode("utf-8")


def rules() -> RuleSet:
    return RuleSet.load(REPO_ROOT / "data" / "rules.yml")


def test_parse_feed():
    products = parse_feed(FEED_XML)
    assert len(products) == 4
    assert products[0].price_czk == "2 890 Kč"
    assert "procesory" in products[0].blob  # diacritics stripped
    assert products[0].in_stock and not products[2].in_stock  # DELIVERY_DATE 0 vs 14


def test_only_in_stock_and_margin_priority():
    """Out-of-stock never picked; TRAY (penalty) loses to boxed CPU."""
    products = parse_feed(FEED_XML)
    r = rules()
    f = Fact("cs", 1971, "Intel uvedl první mikroprocesor 4004.", "events")
    _, hits = score_fact(f, r)
    for day in range(1, 20):  # any rotation day: never TRAY, never out-of-stock
        p = pick_product(products, hits, r, set(), dt.date(2026, 8, day))
        assert p is not None and p.in_stock and "TRAY" not in p.name


def test_strip_diacritics():
    assert strip_diacritics("Grafická karta ŘEŽ") == "graficka karta rez"


def test_tech_fact_scores_above_threshold():
    f = Fact("cs", 1981, "IBM představilo první osobní počítač IBM PC.", "events")
    score, hits = score_fact(f, rules())
    assert score >= rules().min_score
    assert "ibm" in hits and "pocitac" in hits


def test_non_tech_fact_rejected():
    f = Fact("cs", 1960, "Čad vyhlásil nezávislost.", "events")
    fact, _ = pick_fact([f], rules())
    assert fact is None


def test_short_keyword_needs_word_boundary():
    # "mys" must not fire inside unrelated words
    f = Fact("en", 1900, "A mysterious event happened.", "events")
    score, hits = score_fact(f, rules())
    assert "mys" not in hits


def test_processor_fact_matches_processor_product():
    products = parse_feed(FEED_XML)
    f = Fact("cs", 1971, "Intel uvedl první mikroprocesor 4004.", "events")
    _, hits = score_fact(f, rules())
    p = pick_product(products, hits, rules(), set(), dt.date(2026, 8, 11))
    assert p is not None and p.item_id == "001"


def test_cooldown_prefers_fresh_product():
    products = parse_feed(FEED_XML)
    f = Fact("cs", 1971, "Intel uvedl první mikroprocesor 4004.", "events")
    _, hits = score_fact(f, rules())
    p = pick_product(products, hits, rules(), {"001"}, dt.date(2026, 8, 11))
    # only product 001 matches "procesor" terms; cooldown exhausts pool -> falls back
    assert p is not None


def test_template_caption_never_english(tmp_path: Path):
    from contenthub.caption import make_caption

    cfg = Config()
    cfg.gemini_api_key = ""  # force template path
    products = parse_feed(FEED_XML)
    f_en = Fact("en", 1991, "The World Wide Web became publicly available.", "events")
    caption, source = make_caption(f_en, products[0], cfg)
    assert source == "template"
    assert "World Wide Web" not in caption  # falls back to evergreen CZ template
    assert "Kč" in caption and "utm_source" in caption


def test_state_roundtrip(tmp_path: Path):
    from contenthub.state import State

    st = State(tmp_path / "s.db")
    day = dt.date(2026, 8, 11)
    assert not st.already_published(day)
    st.record(day, "001", "fakt", "cs", "caption", "out/x.jpg", published=True)
    assert st.already_published(day)
    assert "001" in st.recent_product_ids(30)
    st.close()


def test_carousel_renders_three_branded_slides(tmp_path: Path):
    from contenthub.media_carousel import default_texts, render_carousel
    from PIL import Image

    cfg = Config()
    p = Product("001", "AMD Ryzen 5 5600", "https://x", "", "2890,00", "AMD",
                "Procesory", "amd ryzen procesory")
    f = Fact("cs", 1971, "Intel uvedl první mikroprocesor 4004.", "events")
    paths = render_carousel(default_texts(f, p, dt.date(2026, 8, 11)), f, p, cfg,
                            dt.date(2026, 8, 11), tmp_path / "post")
    assert len(paths) == 3 and all(pp.exists() for pp in paths)
    img = Image.open(paths[0])
    assert img.size == (1080, 1920)  # 9:16 primary (Stories/Reels-ready)
    crop = Image.open(tmp_path / "post-1-45.jpg")
    assert crop.size == (1080, 1350)  # 4:5 safe-zone crop for the feed
    # safe zone: master's central crop matches the 4:5 export (allowing for
    # independent JPEG encoding noise)
    from PIL import ImageChops, ImageStat
    diff = ImageChops.difference(
        img.crop((0, 285, 1080, 1635)).convert("RGB"), crop.convert("RGB"))
    assert max(ImageStat.Stat(diff).mean) < 2.0, "safe-zone content diverged"
    # brand rule: no amber/orange pixels anywhere (retired 2026-07-19)
    small = img.resize((90, 112))
    assert not any(r > 200 and 90 < g < 190 and b < 90
                   for r, g, b in small.getdata()), "amber-like pixel found — brand violation"


def test_fact_bank_covers_full_year():
    from contenthub.facts_bank import load_bank, get_entry

    bank = load_bank(REPO_ROOT / "data" / "facts_bank.yml")
    assert len(bank) == 366  # every calendar day incl. Feb 29
    curated = [b for b in bank.values() if not b.evergreen]
    assert len(curated) >= 150
    r = rules()
    vocab = {t for rule in r.product_rules for t in rule["triggers"]}
    for b in curated:
        assert b.headline and b.story, b.day  # year optional (annual days like 05-04)
        assert all(k in vocab for k in b.keywords), (b.day, b.keywords)
    e = get_entry(bank, dt.date(2026, 8, 11))
    assert e is not None and e.year == 1882


def test_bank_caption_contains_story_and_tags():
    from contenthub.caption import bank_caption
    from contenthub.facts_bank import BankEntry

    cfg = Config()
    p = parse_feed(FEED_XML)[0]
    e = BankEntry(day="08-11", evergreen=False, year=1882,
                  headline="Praha se poprvé dovolala", story="První ústředna. Jen 11 lidí.",
                  keywords=["telefon"])
    cap = bank_caption(e, p, cfg, dt.date(2026, 8, 11))
    assert "1882" in cap and "První ústředna" in cap
    assert "#vtentoden" in cap and "#smartphone" in cap and "utm_source" in cap


def test_manual_override_and_hint():
    from contenthub.match import apply_override, pick_product

    products = parse_feed(FEED_XML)
    r = rules()
    # exact product_id override
    p = apply_override({"product_id": "002"}, products, r)
    assert p is not None and p.item_id == "002"
    # term override -> best in-stock match
    p = apply_override({"product_term": "procesor"}, products, r)
    assert p is not None and p.in_stock
    # unknown id falls back to None (pipeline then uses auto matcher)
    assert apply_override({"product_id": "nope"}, products, r) is None
    # curator's product_hint beats keyword rules
    p = pick_product(products, ["procesor"], r, set(), dt.date(2026, 8, 14),
                     product_hint="mys")
    assert p is not None and "Logitech" in p.name


def test_bank_caption_hook_under_ig_fold():
    from contenthub.caption import bank_caption
    from contenthub.facts_bank import BankEntry

    cfg = Config()
    p = parse_feed(FEED_XML)[0]
    e = BankEntry(day="08-11", evergreen=False, year=1882,
                  headline="Praha se poprvé dovolala: ústředna s 11 účastníky",
                  story="Story.", keywords=["telefon"])
    first_line = bank_caption(e, p, cfg, dt.date(2026, 8, 11)).split("\n")[0]
    assert len(first_line) <= 125  # standalone hook fits above the IG fold


def test_card_renders_without_network(tmp_path: Path):
    from contenthub.media_image import render_card

    cfg = Config()
    p = Product("001", "AMD Ryzen 5 5600", "https://x", "", "2890,00", "AMD",
                "Procesory", "amd ryzen procesory")  # empty img URL -> no download
    out = render_card("Před 55 lety: Intel uvedl první mikroprocesor.",
                      p, cfg, dt.date(2026, 8, 11), tmp_path / "card.jpg")
    assert out.exists() and out.stat().st_size > 20_000
