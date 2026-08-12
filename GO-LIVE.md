# GO-LIVE plán — contenthub na GitHubu (ruční publikace, 0 Kč)

Cíl: pipeline běží každý den sama na GitHub Actions, vygeneruje hotový post
(3 slidy + caption) a ty ho jen ručně nahraješ do Instagramu. Žádný Meta login,
žádné API klíče, žádné placené služby.

## Krok 1 — Založ veřejný repozitář (5 minut)

Veřejný = neomezené Actions minuty zdarma.

```bash
cd C:\Users\office\contenthub

# workflow soubory na správné místo (vzdálené nástroje je tam nemohly zapsat):
mkdir .github\workflows
move github-workflows-INSTALL\daily-post.yml .github\workflows\
move github-workflows-INSTALL\weekly-maintenance.yml .github\workflows\
rmdir github-workflows-INSTALL

git init
git add -A
git commit -m "contenthub: denní social pipeline pro Hellocomp.cz"
```

Pak na github.com: **New repository** → název `contenthub` → **Public** →
bez README (už ho máme) → a podle instrukcí:

```bash
git remote add origin https://github.com/<TVUJ-UCET>/contenthub.git
git branch -M main
git push -u origin main
```

> Poznámka: research doc počítal s privátním know-how — v repu nejsou žádné
> tajnosti (feed je veřejný, fakta z Wikipedie, brand assety už veřejně na webu).
> Kdybys přesto chtěl privátní repo, máš 2 000 minut/měsíc zdarma — denní job
> (~3 min) se vejde s velkou rezervou.

## Krok 1b — Zapni demo web pro vedení (1 klik)

V repu je složka `docs/` s interním demo webem (chráněný heslem).
Na GitHubu: **Settings → Pages → Branch: main, složka /docs → Save.**
Za ~1 minutu běží na `https://<TVUJ-UCET>.github.io/contenthub/`.

- Heslo pro vedení: `HelloComp2026!` (pošli jim URL + heslo zvlášť).
- Obsah je šifrovaný AES-256 přímo v souboru — bez hesla nikdo nic nepřečte,
  ani když je repo veřejné. (Změna hesla = přegenerovat `docs/index.html`.)

## Krok 2 — Ověř první běh (2 minuty)

1. Na GitHubu: **Actions** → **Daily post** → **Run workflow** (nech `live=false`).
2. Po ~3 minutách se běh zazelená. Otevři ho:
   - **Summary** dole ukáže hotový caption ke zkopírování,
   - **Artifacts** obsahuje `post-…` se 3 slidy (JPG).

## Krok 3 — Denní rutina (1 minuta denně)

Každý den v 17:17 se post vygeneruje sám. Ty jen:

1. Otevřeš poslední běh **Daily post** (klidně z mobilu — github.com funguje v prohlížeči).
2. Stáhneš 3 slidy z artifactu, zkopíruješ caption ze Summary.
3. V IG appce: Nový příspěvek → vybereš 3 fotky (carousel) → vložíš caption → publikovat.

Tip: na mobilu se artifact stahuje jako ZIP — pohodlnější je nechat si slidy
poslat přes sdílený disk, nebo publikovat z počítače.

## Krok 4 — Údržba (automatická)

- **Keepalive**: denní commit stavu + pondělní keepalive commit drží plánovač
  při životě (GitHub jinak po 60 dnech neaktivity cron vypne).
- **State**: `data/state.db` se commituje zpět — historie postů, žádné opakování
  produktů 30 dní.
- Jediná ruční věc: jednou za čas mrkni, že běhy jsou zelené.

## Volitelné upgrady (až budeš chtít, vše zdarma)

| Upgrade | Co dá | Kdy |
|---|---|---|
| `GEMINI_API_KEY` secret | živé texty pro evergreen dny (~187/rok) | kdykoli, 10 min |
| Meta Instagram Login | plná automatika bez ručního nahrávání | až budeš mít jistotu |
| `MAKE_REEL=1` | 9:16 video verze navíc | až budou carousely zajeté |

## Co kde je

- `data/facts_bank.yml` — 366 dní připraveného obsahu; kterýkoli den můžeš ručně přepsat
- `data/rules.yml` — párování fakt → produkt
- `src/contenthub/media_brand.py` — jediné místo s brand barvami/fonty
- `GO-LIVE.md` — tenhle plán
