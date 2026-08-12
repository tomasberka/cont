# AUTONOMY — plná automatika s databází (Cloudflare / Vercel)

Cíl: pipeline běží úplně sama — vygeneruje, nahraje média na veřejnou URL,
publikuje na Instagram a zapíše záznam do databáze. Ty jen občas koukneš
na přehled. Vše na free tierech.

## Nejdřív upřímně: kde co má běžet a proč

| Vrstva | Kde | Proč |
|---|---|---|
| Generování (Python, Pillow, FFmpeg) | **GitHub Actions** | Vercel/Cloudflare Workers jsou JS serverless s limity CPU/času — Pillow/FFmpeg tam nepatří. Actions to dělá zdarma a už to běží. |
| Veřejné hostování médií | **Cloudflare R2** | Meta API vyžaduje veřejnou HTTPS URL obrázků. R2: 10 GB zdarma, žádné egress poplatky. |
| Databáze (historie postů) | **Cloudflare D1** | SQLite na edge, 5 GB zdarma, čte se jedním API voláním. |
| Publikace na IG | **Meta Graph API v26.0** | kód `publish.py` je hotový (carousel two-step flow). |
| Demo/dashboard web | **GitHub Pages** (máš) nebo Cloudflare Pages | statický, zdarma. |

„Pipeline na Vercelu" by znamenala přepsat generátor do JS a stejně narazit
na limity — GitHub Actions **je** tvůj běhový stroj, Cloudflare je datová vrstva.

## Co už je hotové (dnes, 12. 8. 2026)

- ✅ **D1 databáze `contenthub` existuje** ve tvém Cloudflare účtu
  (region WEUR, id `d352275f-2efb-4e86-a2e3-57ff3e1d5927`), tabulka `posts`
  je založená (day, product, fact, caption, style, published, media_urls…).
- ✅ Workflow má krok **Sync post record to Cloudflare D1** — zapne se sám,
  jakmile přidáš secrets (viz níže). Bez nich se tiše přeskočí.
- ✅ `scripts/sync_d1.py` — zápis přes oficiální D1 HTTP API.
- ⚠️ **R2 je potřeba jednou zapnout ručně**: Cloudflare dashboard → R2 →
  „Enable R2" (free tier; chce potvrzení účtu). Pak vytvoř bucket
  `contenthub-media` a zapni mu Public access (r2.dev subdoména stačí).

## Zapnutí — 4 kroky, ~30 minut celkem

### Krok 1 — Databáze (5 min) ✅ napůl hotovo
1. Cloudflare dashboard → **My Profile → API Tokens → Create Token** →
   šablona „Edit Cloudflare Workers" nebo custom s právem **D1: Edit**.
2. Do GitHub repa přidej secrets:
   - `CF_ACCOUNT_ID` (dashboard, pravý panel na Overview)
   - `CF_API_TOKEN` (token z bodu 1)
   - `CF_D1_DATABASE_ID` = `d352275f-2efb-4e86-a2e3-57ff3e1d5927`
3. Od dalšího běhu se každý post zapisuje do D1. Dotaz na historii:
   dashboard → D1 → contenthub → Console → `SELECT * FROM posts ORDER BY day DESC;`

### Krok 2 — Média na R2 (10 min)
1. Dashboard → R2 → Enable → Create bucket `contenthub-media` →
   Settings → Public access → Allow (zkopíruj `https://pub-….r2.dev`).
2. R2 → Manage API tokens → Create (Object Read & Write) →
   secrets `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`
   (endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`).
3. Repo variable `MEDIA_PUBLIC_BASE` = tvoje pub-….r2.dev URL.
4. Do workflow přidej upload krok (S3 kompatibilní — `aws s3 cp out/ …`
   s R2 endpointem; šablona je zakomentovaná v `daily-post.yml`).

### Krok 3 — Instagram (až budeš chtít; ~1 hod + čekání)
Instagram Login flow (bez App Review pro vlastní účet) — postup v README
sekce „Meta / Instagram". Výsledek: secrets `IG_USER_ID`, `IG_ACCESS_TOKEN`.

### Krok 4 — Přepnout na ostro (1 min)
V `daily-post.yml` změň default `DRY_RUN` na `0` (nebo spouštěj s live=true).
Od té chvíle: 17:17 → vygenerováno → nahráno na R2 → publikováno na IG →
zapsáno do D1. Lidská práce: nula.

## Pořadí zapínání (doporučené)
1. **Teď**: Krok 1 (D1) — od zítřka máš historii postů v databázi i při ruční publikaci.
2. **Tento týden**: Krok 2 (R2) — média veřejně, připraveno pro API.
3. **Až dozraje důvěra**: Kroky 3+4 — plná automatika.

## Styly carouselu (nové)
`CAROUSEL_STYLE` env / repo variable: `classic` (rok se září uprostřed),
`editorial` (magazínový layout, duch roku v pozadí), `duotone` (modrý panel
+ obří rok), `auto` (default — střídá styly po dnech, feed pak nevypadá
jako ze šablony). Styl každého postu se zapisuje do D1 (sloupec `style`),
takže po pár týdnech uvidíš v datech, který styl má nejlepší engagement.
