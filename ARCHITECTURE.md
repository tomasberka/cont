# contenthub — Architektura a mapa projektu

Denní social pipeline pro Hellocomp.cz: fakt → produkt → carousel → caption,
0 Kč provoz, člověk jen nahrává. Tento dokument je **mapa celého systému** —
co kde je, jak to teče a kde se co ovládá.

## Datový tok (jeden den = jeden post)

```
data/facts_bank.yml ──► pipeline.run(date)
(366/366 dní, CZ copy)      │
                            ├─ 1. FAKT      facts_bank.get_entry(date)
                            │               └─ fallback: facts.py (živá Wikipedie + match.pick_fact)
                            ├─ 2. PRODUKT   kaskáda:  data/overrides.yml (ruční)
Shoptet feed (živý) ────►   │                        ► product_hint (v bance)
(1 328 položek)             │                        ► match.pick_product (auto:
                            │                          jen skladem + maržová priorita
                            │                          + 30denní rotace)
                            ├─ 3. TEXTY     caption.bank_caption (hook ≤125 zn. + story + CTA)
                            ├─ 4. VIZUÁL    media_carousel (3 slidy, styl classic/editorial/
                            │               duotone/auto; 9:16 master + 4:5 crop ze safe zóny)
                            ├─ 5. PUBLIKACE publish.py (Meta API v26.0, DRY_RUN=1 default
                            │               → ruční upload z Actions artifactu)
                            └─ 6. ZÁZNAM    state.py (SQLite) + scripts/sync_d1.py (Cloudflare D1)
```

## Struktura repozitáře

```
contenthub/
├── README.md            ← runbook: jak to běží, Meta/Gemini setup, tuning
├── ARCHITECTURE.md      ← tento dokument (mapa systému)
├── GO-LIVE.md           ← krok za krokem: GitHub, Pages, denní rutina (CZ)
├── AUTONOMY.md          ← plná automatika: R2 + D1 + Meta API, pořadí zapínání (CZ)
├── PLAN.md              ← přehledová tabulka srpnového plánu
├── requirements.txt     ← requests, Pillow, PyYAML (nic víc)
├── .env.example         ← všechny přepínače s komentáři
│
├── data/                ══ OBSAH A PRAVIDLA (tady se ladí bez kódu) ══
│   ├── facts_bank.yml   ← 366 dní: headline_cs, story_cs, keywords,
│   │                      volitelně product_hint (přesný výraz pro produkt)
│   ├── rules.yml        ← tech-scoring faktů, mapování fakt→produkt,
│   │                      product_priority (marže: boost/penalty)
│   ├── overrides.yml    ← RUČNÍ výběr produktu ke dni (id/výraz/skip)
│   └── state.db         ← SQLite historie postů (commituje se z Actions)
│
├── src/contenthub/      ══ PIPELINE (14 modulů, ~1 700 řádků) ══
│   ├── pipeline.py      ← orchestrátor (výše popsaný tok)
│   ├── facts_bank.py    ← načtení banky, výběr dne
│   ├── facts.py         ← živá Wikipedie (fallback)
│   ├── match.py         ← RuleSet, scoring faktů, kaskáda výběru produktu,
│   │                      overrides (load/apply)
│   ├── feed.py          ← Shoptet XML → Product (vč. in_stock)
│   ├── caption.py       ← bank_caption (hook/fold), šablony, hashtagy,
│   │                      volitelný Gemini (offline default)
│   ├── media_brand.py   ← JEDINÉ místo s brand konstantami (barvy, fonty,
│   │                      gradient, wordmark, smile, dot-grid)
│   ├── media_carousel.py← 3 slidy, 3 styly, 9:16+4:5, safe zóna
│   ├── media_image.py   ← jednokartový režim (POST_FORMAT=image)
│   ├── media_reel.py    ← 9:16 MP4 (FFmpeg)
│   ├── publish.py       ← Meta Graph API v26.0 (image/carousel/reel, dry-run)
│   ├── state.py         ← SQLite (dedup, cooldown, idempotence)
│   ├── config.py        ← všechna env nastavení na jednom místě
│   └── __main__.py      ← CLI: run / refresh-token
│
├── scripts/             ══ GENERÁTORY (spouštíš ručně nebo z Actions) ══
│   ├── make_plan.py     ← content plán pro rozsah dat → docs/plan/ + prohlížeč
│   ├── make_presentation.py ← obohacení (okruhy, alternativy, časy) → prezentace
│   ├── make_variations.py   ← showroom témat → variations/
│   ├── make_reels.py    ← dávkové MP4 pro rozsah dat
│   └── sync_d1.py       ← zápis postu do Cloudflare D1
│
├── github-workflows-INSTALL/  ══ přesuň do .github/workflows/ při pushi ══
│   ├── daily-post.yml   ← denně 17:17 Praha: post pack + D1 sync + summary
│   ├── weekly-maintenance.yml ← keepalive + kontrola IG tokenu
│   └── make-reels.yml   ← VIDEA NA KLIK (workflow_dispatch, rozsah dat)
│
├── docs/                ══ WEB (GitHub Pages: main → /docs) ══
│   ├── index.html       ← prezentace pro vedení (heslo: HelloComp2026!)
│   ├── presentation.html← prezentace plánu: okruhy, výbava dní, timeline
│   └── plan/            ← prohlížeč plánu + složka na den (slidy, caption, json)
│
├── variations/          ← showroom: 11 témat × (3 slidy 9:16 + 4:5 + caption)
├── assets/              ← brand (wordmark, smile) + fonty (Vafle, Inter, OFL)
├── tests/               ← 16 offline testů (vč. brand-guard na amber a IG fold)
└── out/                 ← denní výstupy (gitignored)
```

## Kde se co ovládá (bez zásahu do kódu)

| Chci…                          | Kde                                      |
|--------------------------------|------------------------------------------|
| přepsat fakt/text pro den      | `data/facts_bank.yml` (den MM-DD)        |
| ručně určit produkt ke dni     | `data/overrides.yml`                     |
| přesnější produkt k faktu      | `product_hint` u dne v bance             |
| ladit marže/priority           | `data/rules.yml → product_priority`      |
| změnit styl vizuálu            | env/variable `CAROUSEL_STYLE`            |
| skrýt URL v captionu (IG-only) | `CAPTION_LINK=0`                         |
| vypnout/zapnout ostrou publikaci| `DRY_RUN` / Actions input `live`        |

## Testy a záruky

`PYTHONPATH=src pytest` — 16 testů, vše offline: parsování feedu, scoring,
kaskáda výběru (sklad, marže, hint, override), banka 366/366, caption pod IG
fold, 9:16↔4:5 konzistence safe zóny, **brand guard** (žádný amber pixel).

## Externí závislosti (vše free tier)

Wikimedia feed API (fakta, jen fallback) · Shoptet Heureka XML (produkty) ·
GitHub Actions (běh) · GitHub Pages (web) · Cloudflare D1 (historie postů;
id `d352275f-2efb-4e86-a2e3-57ff3e1d5927`) · volitelně R2 (média) a Meta
Graph API v26.0 (publikace) · volitelně Gemini (evergreen texty).

## Historie klíčových rozhodnutí

1. **Banka místo živého LLM** — 366 předpřipravených českých příběhů = kvalita
   bez tokenů a bez závislostí za běhu.
2. **9:16 master + 4:5 safe-zone crop** — jeden render, oba formáty, nic se neusekne.
3. **Kaskáda výběru produktu** — automat je default, ale poslední slovo má člověk.
4. **GitHub Actions = výpočet, Cloudflare = data** — Pillow/FFmpeg nepatří do
   serverless; „pipeline na Vercelu" by byl přepis bez přínosu.
5. **Ruční publikace jako mezistupeň** — důvěra roste postupně; API kód čeká hotový.
