"""Czech caption generation: Gemini 2.5 Flash when a key is set, template fallback otherwise.

Verified Aug 2026:
- Free tier limits for gemini-2.5-flash: ~10 RPM / 250k TPM / 250 RPD — one caption/day is nothing.
- Free-tier prompts may be used by Google for product improvement; paid Tier 1 turns that off.
- EEA note: making API *clients* available to EEA end users requires the paid tier.
  Generating your own marketing copy server-side is internal use; enable billing if in doubt
  (a caption/day costs well under 1 Kč/month).
- Model ID is configurable (GEMINI_MODEL); gemini-3.x-flash is the upgrade path.
"""
from __future__ import annotations

import logging
import time

import requests

from .config import Config
from .facts import Fact
from .feed import Product

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _prompt(fact: Fact | None, product: Product, cfg: Config) -> str:
    fact_part = (
        f"Historický fakt (jazyk: {fact.lang}): {fact.text}"
        if fact
        else "Dnes žádný technologický fakt — udělej klasický produktový tip dne."
    )
    return (
        "Napiš krátký, poutavý český caption pro Instagram pro počítačový e-shop "
        f"{cfg.brand_name}. Formát příspěvku: 'v tento den v historii techniky'.\n"
        f"{fact_part}\n"
        f"Propojený produkt: {product.name} za {product.price_czk}.\n"
        "Pravidla: 2–3 věty, přátelský a hravý tón, 1 emoji, na konci 3 relevantní "
        "české hashtagy. Pokud je fakt anglicky, přelož ho přirozeně do češtiny. "
        "Nezmiňuj Wikipedii. Bez uvozovek, bez disclaimerů, bez úvodních frází typu "
        "'Věděli jste, že' na začátku více než jednou. Odkaz do bio zmiň jednou "
        "('odkaz v bio')."
    )


def _template_caption(fact: Fact | None, product: Product, cfg: Config) -> str:
    """Deterministic offline fallback — used when no GEMINI_API_KEY is configured.

    Only uses Czech facts verbatim; for English-only facts it degrades to the
    evergreen product template rather than posting English text.
    """
    hashtags = "#hellocomp #technika #pocitace"
    if fact and fact.lang == "cs":
        return (
            f"📅 {fact.text}\n\n"
            f"I dnešní technika umí zázraky — třeba {product.name} "
            f"za {product.price_czk}. Odkaz v bio!\n\n{hashtags}"
        )
    return (
        f"💡 Tip dne z {cfg.brand_name}: {product.name} za {product.price_czk}. "
        f"Skladem a připraveno k odeslání — odkaz v bio!\n\n{hashtags}"
    )


def _call_gemini(prompt: str, cfg: Config, retries: int = 3) -> str | None:
    url = GEMINI_URL.format(model=cfg.gemini_model)
    for attempt in range(retries):
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": cfg.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.9, "maxOutputTokens": 400},
                },
                timeout=60,
            )
            if r.status_code == 429:  # free-tier rate limit — back off and retry
                wait = 30 * (attempt + 1)
                log.warning("Gemini 429, retrying in %ss", wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text:
                return text
        except Exception:  # noqa: BLE001
            log.warning("Gemini call failed (attempt %d)", attempt + 1, exc_info=True)
            time.sleep(5)
    return None


# category-aware hashtag sets keyed by bank/rule keywords
_HASHTAGS = {
    "procesor": "#procesor #pcbuild", "cpu": "#procesor #pcbuild",
    "intel": "#intel #pcbuild", "amd": "#amd #pcbuild",
    "graficka": "#gpu #gaming", "nvidia": "#nvidia #gaming", "gpu": "#gpu #gaming",
    "mys": "#gamingsetup #periferie", "klavesnice": "#gamingsetup #periferie",
    "monitor": "#monitor #setup", "internet": "#internet #wifi",
    "wifi": "#wifi #chytradomacnost", "router": "#wifi #sit",
    "telefon": "#smartphone #mobil", "iphone": "#apple #mobil",
    "videohra": "#gaming #retrogaming", "konzole": "#gaming #konzole",
    "atari": "#retrogaming #gaming", "commodore": "#retrogaming #gaming",
    "pocitac": "#pocitac #technika", "computer": "#pocitac #technika",
    "apple": "#apple #technika", "ibm": "#retrocomputing #technika",
    "disketa": "#retrocomputing #nostalgie", "floppy": "#retrocomputing #nostalgie",
    "usb": "#prislusenstvi #technika", "pamet": "#pcbuild #hardware",
    "notebook": "#notebook #technika", "sluchatka": "#sluchatka #audio",
    "virus": "#kyberbezpecnost #it", "hacker": "#kyberbezpecnost #it",
}
_BASE_TAGS = "#hellocomp #vtentoden #historietechniky"

_CAPTION_CTAS = (
    "Swipni doleva pro celý příběh. Produkt? Odkaz v bio. 👆",
    "Swipni pro celý příběh. Produkt najdeš v odkazu v bio. 👀",
    "Víc v carouselu. A jestli tě to chytlo — odkaz v bio. ⚡",
)


def _tags_for(keywords: list[str]) -> str:
    extra = ""
    for kw in keywords:
        if kw in _HASHTAGS:
            extra = _HASHTAGS[kw]
            break
    return f"{_BASE_TAGS} {extra}".strip()


def bank_caption(entry, product: Product, cfg: Config, date) -> str:
    """Caption from curated bank copy — full quality, zero LLM, zero cost.

    Structure = "stručné i obsáhlé v jednom": line 1 is a standalone hook that
    fits above Instagram's ~125-char fold; the story, product and CTA unfold
    below it for readers who tap 'more'.
    """
    hook = f"📅 {entry.headline}"  # headline is max ~11 words -> under the fold
    years = f"Píše se rok {entry.year}. " if entry.year else ""
    cta = _CAPTION_CTAS[date.toordinal() % len(_CAPTION_CTAS)]
    body = (
        f"{hook}\n\n"
        f"{years}{entry.story}\n\n"
        f"{cta}\n"
        f"➡️ {product.name} za {product.price_czk}\n\n"
        f"{_tags_for(entry.keywords)}"
    )
    return _append_link(body, product, cfg)


def make_slide_texts(fact: Fact | None, product: Product, cfg: Config):
    """Carousel texts (hook headline, bridge line) — Gemini JSON with template fallback.

    Returns (SlideTexts, source). Czech hook headline is the key win here: for
    English facts Gemini produces a native Czech headline; the template fallback
    only uses Czech facts verbatim and otherwise degrades to the product tip.
    """
    from .media_carousel import SlideTexts, default_texts  # local import — no cycle

    if cfg.gemini_api_key:
        prompt = (
            "Připravuješ 3slidový Instagram carousel pro český počítačový e-shop "
            f"{cfg.brand_name} ve formátu 'v tento den v historii techniky'.\n"
            + (f"Fakt (jazyk {fact.lang}): {fact.text}\nRok: {fact.year}\n" if fact
               else "Dnes není žádný tech fakt — jde o produktový tip dne.\n")
            + f"Produkt: {product.name} za {product.price_czk}.\n"
            "Vrať POUZE validní JSON bez markdownu s klíči:\n"
            '{"hook_headline": "úderný český titulek faktu, max 12 slov, bez roku",'
            ' "bridge_line": "krátká věta spojující fakt s produktem, max 10 slov",'
            ' "cta_line": "krátké CTA, max 6 slov"}'
        )
        raw = _call_gemini(prompt, cfg)
        if raw:
            try:
                import json as _json
                start, end = raw.find("{"), raw.rfind("}") + 1
                data = _json.loads(raw[start:end])
                return SlideTexts(
                    hook_label=("V TENTO DEN V HISTORII TECHNIKY" if fact else "TIP DNE"),
                    hook_headline=str(data["hook_headline"]).strip(),
                    bridge_line=str(data["bridge_line"]).strip(),
                    cta_line=str(data.get("cta_line", "Skladem — mrkni na to")).strip(),
                ), "gemini"
            except Exception:  # noqa: BLE001
                log.warning("Gemini slide-text JSON parse failed — using template",
                            exc_info=True)
    import datetime as _dt
    return default_texts(fact, product, _dt.date.today()), "template"


def make_caption(fact: Fact | None, product: Product, cfg: Config) -> tuple[str, str]:
    """Return (caption, source) where source is 'gemini' or 'template'."""
    if cfg.gemini_api_key:
        text = _call_gemini(_prompt(fact, product, cfg), cfg)
        if text:
            return _append_link(text, product, cfg), "gemini"
        log.warning("Gemini unavailable — falling back to template caption")
    return _append_link(_template_caption(fact, product, cfg), product, cfg), "template"


def _append_link(caption: str, product: Product, cfg: Config) -> str:
    """IG captions aren't clickable — the UTM link is optional (CAPTION_LINK=0
    hides it for cleaner captions; it always stays in post.json for the bio)."""
    if not cfg.caption_link:
        return caption
    sep = "&" if "?" in product.url else "?"
    return f"{caption}\n\n🛒 {product.url}{sep}{cfg.utm}"
