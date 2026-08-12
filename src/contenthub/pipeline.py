"""Daily pipeline orchestrator: fact -> product -> caption -> media -> (publish)."""
from __future__ import annotations

import datetime as dt
import json
import logging

from . import caption as caption_mod
from . import facts as facts_mod
from . import feed as feed_mod
from . import match as match_mod
from . import facts_bank, media_carousel, media_image, media_reel, publish
from .config import Config
from .state import State

log = logging.getLogger(__name__)


def run(cfg: Config, date: dt.date | None = None, force: bool = False) -> dict:
    """Run the daily post pipeline. Returns a result summary dict."""
    date = date or dt.date.today()
    cfg.ensure_dirs()
    state = State(cfg.db_path)

    if state.already_published(date) and not force:
        log.info("Already published for %s — nothing to do (use --force to redo)", date)
        return {"status": "skipped", "reason": "already published"}

    # 1) sources
    products = feed_mod.load_products(cfg.feed_url)
    if not products:
        raise RuntimeError("Product feed is empty — aborting")

    # 2) pick fact + product — curated bank first, live Wikimedia as fallback
    rules = match_mod.RuleSet.load(cfg.rules_path)
    bank_entry = facts_bank.get_entry(facts_bank.load_bank(cfg.bank_path), date)
    if bank_entry:
        fact = facts_mod.Fact(lang="cs", year=bank_entry.year,
                              text=bank_entry.headline, kind="bank")
        keywords = bank_entry.keywords
        log.info("Using curated bank fact for %s: %s", date, bank_entry.headline)
    else:
        all_facts = facts_mod.fetch_all(cfg.wikimedia_langs, date)
        fact, keywords = match_mod.pick_fact(all_facts, rules)

    # product selection cascade: MANUAL override > curator's hint > auto matcher
    overrides = match_mod.load_overrides(cfg.overrides_path)
    ov = match_mod.override_for(overrides, date)
    if ov and ov.get("skip"):
        log.info("Override: skip day %s", date)
        state.close()
        return {"status": "skipped", "reason": "manual override skip", "date": date.isoformat()}
    product = match_mod.apply_override(ov, products, rules) if ov else None
    product_source = "override" if product else None
    if product is None:
        product = match_mod.pick_product(
            products, keywords, rules,
            state.recent_product_ids(cfg.product_cooldown_days), date,
            product_hint=bank_entry.product_hint if bank_entry else "",
        )
        product_source = ("hint" if bank_entry and bank_entry.product_hint
                          else "auto")
    if product is None:
        raise RuntimeError("No product with an image found in the feed")

    # 3) caption (bank-based when curated copy exists — fully offline)
    if bank_entry:
        text, caption_source = caption_mod.bank_caption(bank_entry, product, cfg, date), "bank"
    else:
        text, caption_source = caption_mod.make_caption(fact, product, cfg)

    # 4) media
    headline = fact.headline(date) if fact else None
    # If the fact is English and captioning is template-only, the card shows the
    # evergreen layout (English text on a Czech card would look off-brand).
    if fact and fact.lang != "cs" and caption_source == "template":
        headline = None
    stem = f"post-{date.isoformat()}"
    slide_paths: list = []
    if cfg.post_format == "carousel":
        if bank_entry:  # curated copy — best quality, no LLM needed
            slide_texts = media_carousel.default_texts(fact, product, date,
                                                       story=bank_entry.story)
            slide_texts.hook_headline = bank_entry.headline
            slide_fact = fact
        else:
            slide_texts, slides_source = caption_mod.make_slide_texts(fact, product, cfg)
            # keep fact only if we have a Czech headline for it (Gemini or cs fact)
            slide_fact = fact if (fact and (fact.lang == "cs" or slides_source == "gemini")) else None
            if slide_fact is None and slides_source == "template":
                slide_texts = media_carousel.default_texts(None, product, date)
        slide_paths = media_carousel.render_carousel(
            slide_texts, slide_fact, product, cfg, date, cfg.out_dir / stem)
        image_path = slide_paths[0]
    else:
        image_path = media_image.render_card(headline, product, cfg, date,
                                             cfg.out_dir / f"{stem}.jpg")
    reel_path = None
    if cfg.make_reel:
        reel_path = media_reel.render_reel(headline, product, cfg, date,
                                           cfg.out_dir / f"{stem}.mp4")

    # 5) publish (carousel or single image)
    if cfg.media_public_base:
        base_url = cfg.media_public_base.rstrip("/")
        if cfg.post_format == "carousel" and slide_paths:
            urls = [f"{base_url}/{p.name}" for p in slide_paths]
            result = publish.publish_carousel(cfg, urls, text)
        else:
            result = publish.publish_image(cfg, f"{base_url}/{image_path.name}", text)
    else:
        result = publish.PublishResult(
            False, None, "No MEDIA_PUBLIC_BASE configured — dry run")
        log.info(result.note)

    # 6) record state + sidecar JSON (handy for review/debug)
    state.record(date, product.item_id, fact.text if fact else None,
                 fact.lang if fact else None, text, str(image_path),
                 result.published, result.media_id)
    # the summary must reflect what the POST actually contains — a live-fallback
    # fact that degraded to evergreen mode (non-Czech, no LLM) is NOT in the post
    used_fact = fact
    if cfg.post_format == "carousel":
        used_fact = slide_fact
    elif fact and fact.lang != "cs" and caption_source == "template":
        used_fact = None
    summary = {
        "status": "published" if result.published else "dry-run",
        "date": date.isoformat(),
        "fact": used_fact.text if used_fact else None,
        "fact_lang": used_fact.lang if used_fact else None,
        "fact_keywords": keywords,
        "product": {"id": product.item_id, "name": product.name,
                    "price": product.price_czk, "url": product.url},
        "product_source": product_source,
        "caption": text,
        "caption_source": caption_source,
        "format": cfg.post_format,
        "style": media_carousel.resolve_style(cfg, date) if cfg.post_format == "carousel" else None,
        "slides": [str(p) for p in slide_paths] or None,
        "image": str(image_path),
        "reel": str(reel_path) if reel_path else None,
        "publish_note": result.note,
    }
    (cfg.out_dir / f"{stem}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # manual-publish pack: caption as plain text for copy-paste into the IG app
    (cfg.out_dir / f"{stem}-caption.txt").write_text(text + "\n", encoding="utf-8")
    state.close()
    return summary
