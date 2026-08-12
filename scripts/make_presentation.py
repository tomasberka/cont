"""Enrich the content plan and build a self-contained presentation page.

Enrichment per day (computed locally, no LLM, no cost):
  - pillar        content pillar (okruh) derived from the fact's keywords
  - alt_products  top alternative products from live stock (same rules)
  - post_time     recommended posting slot for the weekday
  - format_tip    story/reel repurposing tip for the 9:16 master
Outputs:
  - docs/plan/PLAN.json      (enriched, drives future dashboards)
  - docs/presentation.html   (self-contained Czech presentation, thumbnails embedded)

Usage: PYTHONPATH=src python scripts/make_presentation.py
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import feed as feed_mod, match as match_mod  # noqa: E402
from contenthub.config import Config, REPO_ROOT  # noqa: E402

PLAN_DIR = REPO_ROOT / "docs" / "plan"

PILLARS = {  # okruh label -> keywords
    "Kyberbezpečnost": ["virus", "hacker", "cyber", "kyber"],
    "Procesory & čipy": ["procesor", "processor", "microprocessor", "cpu", "intel",
                         "amd", "tranzistor", "transistor", "chip", "cip",
                         "polovodic", "semiconductor"],
    "Grafika & gaming": ["nvidia", "graficka", "gpu", "playstation", "nintendo",
                         "xbox", "videohra", "video game", "konzole", "atari",
                         "commodore"],
    "Periferie": ["mys", "mouse", "klavesnice", "keyboard", "monitor", "displej",
                  "display"],
    "Internet & síť": ["internet", "web", "www", "arpanet", "ethernet", "network",
                       "wifi", "wi-fi", "router", "sit"],
    "Mobil & telefon": ["telefon", "smartphone", "iphone", "mobil", "phone"],
    "Data & paměť": ["disketa", "floppy", "pevny disk", "hard disk", "usb",
                     "pamet", "memory", "storage"],
    "Počítače & software": ["pocitac", "computer", "ibm", "macintosh", "apple",
                            "microsoft", "windows", "linux", "notebook", "laptop",
                            "software", "programator", "turing", "algoritmus"],
    "Audio & video": ["sluchatka", "audio", "radio", "televize", "television",
                      "kalkulacka", "calculator"],
}

POST_TIME = {0: "17:00–18:00", 1: "17:00–18:00", 2: "17:00–18:00",
             3: "17:00–19:00", 4: "16:00–17:00", 5: "10:00–12:00",
             6: "18:00–20:00"}
FORMAT_TIP = {
    0: "Feed carousel (4:5) + slide 1 jako Story s odkazem",
    1: "Feed carousel (4:5); story verze večer jako připomínka",
    2: "Feed carousel + anketa ve Story („Znali jste to?“)",
    3: "Feed carousel; 9:16 master použij jako Reel podklad",
    4: "Feed carousel odpoledne — páteční dosah bývá nejsilnější",
    5: "Story-first: 9:16 master ráno, feed post k obědu",
    6: "Feed carousel večer + Story kvíz k faktu",
}


def pillar_for(keywords: list[str]) -> str:
    for kw in keywords:
        for label, kws in PILLARS.items():
            if kw in kws:
                return label
    return "Produktový tip"


def alt_products(products, keywords, rules, chosen_id, date):
    """Top alternative picks from stock for the same keywords (variety row)."""
    out, seen = [], {chosen_id}
    for kw in keywords:
        for rule in rules.product_rules:
            if kw in rule["triggers"]:
                for term in rule["terms"]:
                    t = match_mod.strip_diacritics(term)
                    for p in products:
                        if t in p.blob and p.img and p.item_id not in seen:
                            seen.add(p.item_id)
                            out.append({"name": p.name, "price": p.price_czk})
                            if len(out) >= 3:
                                return out
    return out


def thumb_b64(path: Path, width: int = 300, q: int = 62) -> str:
    im = Image.open(path)
    im.thumbnail((width, 10000), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=q, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    cfg = Config()
    entries = json.loads((PLAN_DIR / "PLAN.json").read_text(encoding="utf-8"))
    products = feed_mod.load_products(cfg.feed_url)
    rules = match_mod.RuleSet.load(cfg.rules_path)

    for e in entries:
        d = dt.date.fromisoformat(e["date"])
        kws = e.get("fact_keywords") or []
        e["pillar"] = pillar_for(kws) if e.get("fact") else "Produktový tip"
        e["alt_products"] = alt_products(products, kws, rules,
                                         e["product"]["id"], d) if kws else []
        e["post_time"] = POST_TIME[d.weekday()]
        e["format_tip"] = FORMAT_TIP[d.weekday()]
    (PLAN_DIR / "PLAN.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- presentation page ----
    pillar_counts: dict[str, int] = {}
    for e in entries:
        pillar_counts[e["pillar"]] = pillar_counts.get(e["pillar"], 0) + 1
    chips = "".join(
        f'<span class="chip">{html.escape(p)} <b>{n}×</b></span>'
        for p, n in sorted(pillar_counts.items(), key=lambda x: -x[1]))

    CZ_DAYS = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
    cards = []
    for e in entries:
        d = dt.date.fromisoformat(e["date"])
        t1 = thumb_b64(PLAN_DIR / e["dir"] / "post-1-45.jpg")
        fact = e.get("fact")
        title = html.escape(fact) if fact else "Produktový tip dne"
        story = html.escape((e.get("caption") or "").split("\n\n")[1] if fact and "\n\n" in (e.get("caption") or "") else "")
        alts = "".join(f'<li>{html.escape(a["name"][:52])} · {a["price"]}</li>'
                       for a in e.get("alt_products") or [])
        alts_html = f'<div class="alts"><span>Alternativy ze skladu:</span><ul>{alts}</ul></div>' if alts else ""
        cards.append(f"""
<div class="card">
 <img src="data:image/jpeg;base64,{t1}" alt="{e['date']}" loading="lazy">
 <div class="cbody">
  <div class="cdate">{d.day}. {d.month}. · {CZ_DAYS[d.weekday()]} · <em>{e.get('style','')}</em></div>
  <span class="pillar">{html.escape(e['pillar'])}</span>
  <h3>{title}</h3>
  <p class="story">{story}</p>
  <div class="prod">➡ {html.escape(e['product']['name'][:55])} · <b>{e['product']['price']}</b></div>
  {alts_html}
  <div class="kit">🕐 {e['post_time']} &nbsp;·&nbsp; {html.escape(e['format_tip'])}</div>
 </div>
</div>""")

    n_facts = sum(1 for e in entries if e.get("fact"))
    page = f"""<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>contenthub — srpen: plán, okruhy, výbava</title><style>
:root{{--ink:#0F1118;--mid:#18243C;--blue:#284C87;--accent:#2962CD;--bright:#4D7FC4;--muted:#BCCAE0}}
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;color:#fff;
background:linear-gradient(135deg,var(--ink),var(--mid) 50%,var(--blue)) fixed;background-color:var(--ink)}}
.wrap{{max-width:1120px;margin:0 auto;padding:48px 22px 80px}}
h1{{font-size:40px;margin:0}}
.sub{{color:var(--muted);margin:10px 0 26px;max-width:720px;line-height:1.6}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:34px}}
.stat{{background:rgba(24,36,60,.55);border:1px solid rgba(77,127,196,.3);border-radius:14px;padding:16px}}
.stat b{{display:block;font-size:30px}}
.stat span{{font-size:12px;color:var(--muted)}}
h2{{font-size:26px;margin:38px 0 8px}}
.lead{{color:var(--muted);margin:0 0 18px;max-width:720px;line-height:1.6;font-size:14px}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.chip{{background:rgba(41,98,205,.25);border:1px solid var(--bright);border-radius:99px;
padding:5px 14px;font-size:13px}}
.chip b{{color:var(--bright)}}
.data{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}}
.dcell{{background:rgba(24,36,60,.5);border:1px solid rgba(77,127,196,.28);border-radius:12px;padding:14px}}
.dcell b{{font-size:14px;display:block;margin-bottom:4px}}
.dcell p{{font-size:12px;color:var(--muted);margin:0;line-height:1.5}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.card{{background:rgba(24,36,60,.55);border:1px solid rgba(77,127,196,.3);border-radius:16px;
overflow:hidden;display:flex}}
.card img{{width:132px;object-fit:cover}}
.cbody{{padding:14px 16px;flex:1}}
.cdate{{font-size:12px;color:var(--muted)}}
.pillar{{display:inline-block;margin:6px 0;background:var(--accent);border-radius:99px;
padding:2px 10px;font-size:11px;font-weight:700}}
h3{{font-size:15px;margin:2px 0 6px;line-height:1.3}}
.story{{font-size:12px;color:var(--muted);margin:0 0 8px;line-height:1.5}}
.prod{{font-size:12px;margin-bottom:6px}}
.alts span{{font-size:10px;letter-spacing:1px;color:var(--bright);text-transform:uppercase}}
.alts ul{{margin:2px 0 8px;padding-left:16px;font-size:11px;color:var(--muted)}}
.kit{{font-size:11px;color:var(--bright);border-top:1px solid rgba(77,127,196,.2);padding-top:8px}}
footer{{margin-top:44px;color:#8fa3c4;font-size:13px;line-height:1.7}}
a{{color:var(--bright)}}
</style></head><body><div class="wrap">
<h1>contenthub · srpen naostro</h1>
<p class="sub">Denní obsah pro Hellocomp.cz na autopilota. Tohle je živý výstup pipeline —
každý den níže vznikl automaticky: fakt → produkt ze skladu → značkový carousel → caption.
Plná galerie se slidy a captiony: <a href="plan/index.html">prohlížeč plánu</a>.</p>
<div class="stats">
 <div class="stat"><b>{len(entries)}</b><span>dní připraveno (14.–31. 8.)</span></div>
 <div class="stat"><b>{n_facts}</b><span>historických příběhů</span></div>
 <div class="stat"><b>{len(pillar_counts)}</b><span>obsahových okruhů</span></div>
 <div class="stat"><b>3</b><span>vizuální styly v rotaci</span></div>
 <div class="stat"><b>2</b><span>formáty: 9:16 + 4:5</span></div>
 <div class="stat"><b>0 Kč</b><span>měsíční provoz</span></div>
</div>

<h2>Co pipeline chytá o každém dni</h2>
<p class="lead">Každý post nese strukturovaná data — základ pro vyhodnocování, co funguje.</p>
<div class="data">
 <div class="dcell"><b>📅 Fakt & příběh</b><p>datum výročí, rok, český titulek + 2věté story z kurátorované banky (366 dní)</p></div>
 <div class="dcell"><b>📦 Produkt</b><p>ideální match ze živého skladu (1 328 položek), cena, URL s UTM, 30denní rotace</p></div>
 <div class="dcell"><b>🏷️ Okruh</b><p>obsahový pilíř odvozený z klíčových slov — 9 okruhů pokrývá celý sortiment</p></div>
 <div class="dcell"><b>🎨 Styl & formát</b><p>classic / editorial / duotone; 9:16 master + 4:5 crop ze safe zóny</p></div>
 <div class="dcell"><b>✍️ Caption</b><p>hotový text s hashtags podle kategorie a rotujícím CTA</p></div>
 <div class="dcell"><b>🗄️ Databáze</b><p>každý post se zapisuje do Cloudflare D1 — historie a podklad pro analytiku stylů</p></div>
</div>

<h2>Obsahové okruhy v srpnu</h2>
<div class="chips">{chips}</div>

<h2>Výbava na každý den</h2>
<p class="lead">Ke každému dni: hlavní produkt + alternativy ze skladu (kdyby se vyprodal),
doporučený čas publikace a tip, jak vytěžit 9:16 master ve Stories/Reels.</p>
<div class="grid">{''.join(cards)}</div>

<h2>Timeline & akce na klik</h2>
<div class="data">
 <div class="dcell"><b>✅ Hotovo</b><p>366denní banka faktů · 3 styly · 9:16 + 4:5 ·
  srpnový plán ({len(entries)} dní) · testy · D1 databáze</p></div>
 <div class="dcell"><b>🎬 Videa na klik</b><p>GitHub → Actions → <b>Make reels (video)</b> → Run workflow.
  Na pozadí (zdarma) se vyrendrují 9:16 MP4 reels pro zvolený rozsah dní a stáhneš je jako balíček.</p></div>
 <div class="dcell"><b>📱 Denní post na klik</b><p>Actions → <b>Daily post</b> → Run workflow.
  Jinak běží sám každý den v 17:17 — slidy + caption najdeš v běhu.</p></div>
 <div class="dcell"><b>🚀 Další</b><p>R2 hosting médií → Instagram API → plná automatika bez kliknutí.</p></div>
</div>

<footer>contenthub · interní projekt Hellocomp.cz · pipeline běží zdarma na GitHub Actions ·
data Wikipedie + vlastní kurátorovaná banka · výběr produktů: pouze skladem, preferovaná vlastní
(vysokomaržová) řada · vygenerováno 12. 8. 2026</footer>
</div></body></html>"""
    out = REPO_ROOT / "docs" / "presentation.html"
    out.write_text(page, encoding="utf-8")
    print(f"presentation: {out} ({out.stat().st_size // 1024} KB), "
          f"pillars: {pillar_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
