# contenthub — Hellocomp.cz daily social pipeline

Automatický denní příspěvek „v tento den v historii techniky" pro Instagram/Facebook:
Wikimedia fakt → relevantní produkt z Shoptet feedu → český caption (Gemini) →
vizuál (1080×1350 karta, volitelně 9:16 reel) → publikace přes Meta API.

Běží zdarma na GitHub Actions. **Výchozí režim je DRY RUN** — nic se nepublikuje,
dokud to sám nezapneš.

## How it works

```
data/facts_bank.yml (PRIMARY)        Shoptet Heureka XML feed
366 dní kurátorovaných českých               │
faktů: headline + story + keywords           │
        │ (evergreen den ↓)                  │
Wikimedia on-this-day (cs + en)              │
        │                                    ▼
  tech-relevance scorer  ──keywords──▶  product matcher (rules.yml,
  (min_score gate; no tech fact         30-day cooldown, deterministic
   today → evergreen product tip)       daily rotation)
        │                                     │
        └──────────────┬──────────────────────┘
                       ▼
          caption: Gemini 2.5 Flash (CZ)
          → offline CZ template fallback
                       ▼
          media: 3-slide branded carousel 1080×1350 (default)
                 hook (rok + titulek) → produkt → CTA
                 single card (POST_FORMAT=image), FFmpeg reel (MAKE_REEL=1)
                       ▼
          publish: Meta Graph API v26.0 (two-step
          container flow) — DRY_RUN=1 by default
                       ▼
          SQLite state (dedup, idempotent reruns)
```

## Quick start (local, no keys needed)

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m contenthub run          # dry run for today
PYTHONPATH=src python -m contenthub run --reel   # also render the 9:16 reel
PYTHONPATH=src pytest -q                         # offline test suite
```

### Clean reels on Mac

The reel generator uses the existing slides, with no extra overlays or icons:

```bash
PYTHONPATH=src python3 scripts/make_reels_v5.py 2026-08-14 2026-08-31
```

Files are written to `out/reels/`. Add `--dry` to verify the date range without
rendering.

Outputs land in `out/`: `post-YYYY-MM-DD.jpg`, `.json` (fact, product, caption), optionally `.mp4`.

## Going live — setup checklist

### 1. GitHub (5 min)
1. Push this repo to GitHub as a **public** repo (public = unlimited free Actions minutes).
2. Actions are already configured:
   - `daily-post.yml` — every day 17:17 Prague time (native `timezone:` field).
   - `weekly-maintenance.yml` — keepalive proti 60dennímu auto-vypnutí plánovaných
     workflow + kontrola IG tokenu.
3. Each run uploads `out/` as an artifact — you can review 14 days of generated
   posts in the Actions tab before you ever go live.

### 2. Gemini caption key (10 min, free)
1. https://aistudio.google.com → Get API key.
2. Repo → Settings → Secrets and variables → Actions → new secret `GEMINI_API_KEY`.
3. Bez klíče pipeline běží dál s šablonovým českým captionem (horší, ale funkční).

Verified Aug 2026: free tier = ~10 RPM / 250 requests per day (jeden caption denně
je nic); Google smí free-tier prompty použít pro vývoj produktů — pokud vadí,
zapni billing (Tier 1): jeden caption denně stojí řádově haléře měsíčně a
zároveň to čistě vyřeší EEA komerční podmínky.

### 3. Meta / Instagram (the long pole — start NOW, ~1–2 weeks)
Cesta A — **Instagram Login** (doporučeno, jednodušší; ověřeno Aug 2026):
1. Instagram účet musí být **Professional** (Business/Creator).
2. https://developers.facebook.com → Create App → typ „Instagram".
3. Add product „Instagram API with Instagram Login".
4. Scopes: `instagram_business_basic` + `instagram_business_content_publish`.
   Pro **vlastní účet** funguje Standard Access bez App Review; Business
   Verification + App Review je potřeba jen pro publikaci cizích účtů.
5. Vygeneruj long-lived token (60 dní), ulož jako secrets:
   `IG_USER_ID`, `IG_ACCESS_TOKEN`. Nech `IG_LOGIN_FLOW=instagram` (default).

Cesta B — Facebook Login (přes propojenou FB Page): scopes `instagram_basic`,
`instagram_content_publish`, `pages_read_engagement`; nastav `IG_LOGIN_FLOW=facebook`.

### 4. Public media hosting (needed only for live publishing)
Meta API vyžaduje **veřejnou HTTPS URL** obrázku. Nejjednodušší zdarma:
Cloudflare R2 public bucket, nebo GitHub release asset. Nastav repo **variable**
`MEDIA_PUBLIC_BASE` (např. `https://media.example.com/contenthub`) a nahrávej
`out/post-*.jpg` tamtéž (krok si přidáš do workflow podle zvoleného hostingu).

### 5. Flip the switch
- Ruční test: Actions → Daily post → Run workflow → `live = true`.
- Trvale: změň `DRY_RUN` default v `daily-post.yml` (nebo nastav repo variable).

## Operations notes (verified Aug 2026)

- **Graph API**: pinned `v26.0` (latest stable; `v25.0` supported until 2028-07-29).
  Limit 100 API-published posts / 24 h — jeden denně je hluboko pod limitem.
  Kontrola: `GET /{ig_id}/content_publishing_limit`.
- **Token**: long-lived token vydrží 60 dní. `python -m contenthub refresh-token`
  ho obnoví (Instagram Login flow); weekly workflow na to upozorňuje. Pro plnou
  automatiku přidej PAT secret `GH_PAT_FOR_SECRETS` (scope `secrets:write`).
- **GitHub scheduler**: plánované workflow se v neaktivním repu po 60 dnech vypnou;
  daily commit stavu + weekly keepalive to řeší. Spouštění může mít zpoždění
  v řádu minut (best-effort, proto minuta :17).
- **Wikimedia**: endpoint `api.wikimedia.org/feed/v1/...` je stabilní; Wikifeeds
  API se má postupně nahrazovat (H2 2026+, s dlouhým překryvem) — sleduj
  mediawiki.org „Wikimedia APIs Changelog". Posílá se identifikační User-Agent.
- **Idempotence**: stav v `data/state.db` (commitován zpět do repa). Stejný den =
  stejný výběr produktu; `--force` přegeneruje.
- **Stories/TikTok**: Stories nemají publishing API; TikTok bez auditu appky
  publikuje jen do draftů — proto IG feed + FB Page.

## Fact bank (data/facts_bank.yml)

366 dní předpřipraveného obsahu — pro každý den buď kurátorovaný český fakt
(headline max 11 slov, 2věté story, keywords pro párování produktu; datum i fakt
ověřené z Wikipedie), nebo `evergreen: true` (ten den vyjde produktový tip).
**Pipeline díky tomu běží celoročně 100% zdarma a offline-first** — žádné LLM,
žádné placené API za běhu; Gemini je čistě volitelný bonus pro evergreen dny.
Ručně můžeš kterýkoli den přepsat — je to obyčejné YAML.

## Tuning

- `data/rules.yml` — tech-klíčová slova (scoring faktů) a mapování fakt→produkt.
  Piš bez diakritiky, matchuje se na normalizovaný text.
- `PRODUCT_COOLDOWN_DAYS` (default 30) — jak dlouho se produkt neopakuje.
- `POST_FORMAT` — `carousel` (default, 3 slidy) nebo `image` (jedna karta).
- Brand: `src/contenthub/media_brand.py` je jediné místo s barvami — zrcadlí
  `hellocomp-gtd/public/brand/README.md` (navy gradient 135°, modrá #2962CD +
  bílá, amber je vyřazený). Logo `assets/brand/hellocomp-white.png`, display
  font Vafle Condensed (`assets/fonts/Vafle.ttf`, plná česká diakritika),
  doplňkový Inter (OFL). Test hlídá, že se do vizuálů nevrátí amber.
- Carousel publikace: 3 sloty přes `is_carousel_item` + parent CAROUSEL
  container — počítá se jako 1 post z limitu 100/24 h.
- Hudba pro reel: přidej `assets/music.mp3` (royalty-free, např. Pixabay).
