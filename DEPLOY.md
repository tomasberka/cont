# DEPLOY.md — kompletní nasazení contenthubu (pro Claude Code)

> **Instrukce pro agenta (Claude Code):** Pracuješ ve složce
> `C:\Users\office\contenthub` (Windows). Projdi fáze 0–6 v pořadí. Po každé
> fázi ověř výsledek podle „✅ Ověření" a teprve pak pokračuj. U kroků
> označených 🧑 se zastav a vyžádej si vstup od uživatele — nikdy nehádej
> tokeny ani nepřeskakuj ověření. Nic z tohoto souboru nevyžaduje placené
> služby; vše běží na free tierech GitHub + Cloudflare.

---

## Fáze 0 — Preflight (2 min)

```bash
cd C:\Users\office\contenthub
python --version          # potřeba 3.11+
pip install -r requirements.txt
:: cmd:
set PYTHONPATH=src && python -m pytest tests/ -q
:: PowerShell místo toho:
::   $env:PYTHONPATH="src"; python -m pytest tests/ -q
```

✅ Ověření: **16 testů zelených.** Pokud ne, STOP — oprav před nasazením.

Zkontroluj přítomnost: `data/facts_bank.yml` (366 dní), `data/overrides.yml`,
`docs/index.html`, `docs/presentation.html`, `docs/plan/index.html`,
`github-workflows-INSTALL/` (3 soubory). Pokud existuje
`contenthub-complete.zip` nebo `docs-plan-UNZIP-ME.zip` v kořeni: ZIPy do
gitu nepatří — `docs-plan-UNZIP-ME.zip` nejdřív rozbal do `docs\` (přepiš
staré složky dní), pak oba ZIPy smaž nebo přesuň mimo repo.

## Fáze 1 — Workflow soubory na místo (1 min)

> Pokud `.github\workflows\` už obsahuje 3 .yml soubory (rozbalený finální ZIP),
> tuto fázi PŘESKOČ a pokračuj Fází 2.

```bash
mkdir .github\workflows
move github-workflows-INSTALL\daily-post.yml .github\workflows\
move github-workflows-INSTALL\weekly-maintenance.yml .github\workflows\
move github-workflows-INSTALL\make-reels.yml .github\workflows\
rmdir github-workflows-INSTALL
```

✅ Ověření: `.github\workflows\` obsahuje přesně 3 `.yml` soubory.

## Fáze 2 — Git + GitHub (5 min)

🧑 Zeptej se uživatele: **název GitHub účtu/organizace** (dále `<UCET>`).
Repo musí být **PUBLIC** (= neomezené Actions minuty zdarma; žádná tajemství
v repu nejsou).

Preferuj `gh` CLI (pokud chybí: `winget install GitHub.cli`, pak `gh auth login`):

```bash
git init
git add -A
git commit -m "contenthub: denni social pipeline pro Hellocomp.cz"
gh repo create contenthub --public --source . --push
```

(Bez `gh`: vytvoř repo ručně na github.com a `git remote add origin … && git push -u origin main`.)

✅ Ověření: `gh repo view contenthub --web` otevře repo; větev `main` obsahuje
`.github/workflows` a `docs/`.

## Fáze 3 — GitHub Pages (2 min)

```bash
gh api repos/<UCET>/contenthub/pages -X POST -f "source[branch]=main" -f "source[path]=/docs"
```

(Fallback ručně: Settings → Pages → Branch `main`, složka `/docs` → Save.)

✅ Ověření (build trvá ~1–2 min):
- `https://<UCET>.github.io/contenthub/` → přihlašovací brána prezentace
  (heslo `HelloComp2026!` — sděl uživateli, ať ho pošle vedení ZVLÁŠŤ, ne v mailu s URL)
- `https://<UCET>.github.io/contenthub/plan/` → prohlížeč content plánu
- `https://<UCET>.github.io/contenthub/presentation.html` → prezentace plánu

## Fáze 4 — Databáze Cloudflare D1 (5 min)

D1 databáze **už existuje** v účtu uživatele:
- name: `contenthub` · region WEUR
- **database_id: `d352275f-2efb-4e86-a2e3-57ff3e1d5927`**
- tabulka `posts` je založená

🧑 Vyžádej si od uživatele dvě hodnoty (z Cloudflare dashboardu):
1. **Account ID** (Overview, pravý panel)
2. **API token** — My Profile → API Tokens → Create Token → Custom:
   pouze právo **D1 : Edit** (minimální scope!)

```bash
gh secret set CF_ACCOUNT_ID --body "<ACCOUNT_ID>"
gh secret set CF_API_TOKEN --body "<TOKEN>"
gh secret set CF_D1_DATABASE_ID --body "d352275f-2efb-4e86-a2e3-57ff3e1d5927"
```

✅ Ověření: `gh secret list` ukazuje 3 CF_* secrets. (Sync běží automaticky
v denním workflow; krok se bez secrets tiše přeskakuje, se secrets zapisuje.)

## Fáze 5 — První běh a denní rutina (3 min)

```bash
gh workflow run daily-post.yml
gh run watch
```

✅ Ověření po doběhnutí:
1. Run Summary obsahuje sekci **„Dnešní post"** s captionem ke zkopírování.
2. Artifact `post-…` obsahuje slidy: `post-N.jpg` (9:16) + `post-N-45.jpg` (4:5).
3. Pokud jsou CF_* secrets nastavené: v Cloudflare D1 Console
   `SELECT * FROM posts ORDER BY day DESC LIMIT 1;` vrátí dnešní záznam.
4. Videa na klik: `gh workflow run make-reels.yml -f start=2026-08-14 -f end=2026-08-16`
   → artifact se 3 MP4.

Řekni uživateli denní rutinu (~1 min): otevřít poslední run → stáhnout
artifact → zkopírovat caption ze Summary → nahrát do IG jako carousel.

## Fáze 6 — Volitelné stupně automatiky (později, dle důvěry)

| Krok | Co | Kde je návod |
|---|---|---|
| R2 média | 🧑 dashboard: Enable R2 → bucket `contenthub-media` → public → repo variable `MEDIA_PUBLIC_BASE`; odkomentuj upload krok v `daily-post.yml` | AUTONOMY.md, krok 2 |
| Gemini texty pro evergreen | 🧑 klíč z aistudio.google.com → `gh secret set GEMINI_API_KEY` | README, krok 2 |
| Instagram API (plná automatika) | 🧑 Meta app (Instagram Login, vlastní účet bez App Review) → `IG_USER_ID`, `IG_ACCESS_TOKEN` → pak `DRY_RUN=0` | README „Meta / Instagram", AUTONOMY.md krok 3–4 |

## Bezpečnostní pravidla (dodržuj)

- Tokeny POUZE přes `gh secret set` / GitHub Secrets — nikdy do souborů, commitů ani logů.
- Cloudflare token vždy s minimálním rozsahem (D1:Edit, případně jen daný R2 bucket).
- V repu Settings → Actions → doporuč zapnout „Allow <UCET> and select non-<UCET> actions" (používáme jen oficiální `actions/*`).
- Heslo prezentace se posílá jiným kanálem než URL.

## Když se něco pokazí

- Actions run červený → přečti log kroku „Run pipeline"; nejčastější příčina je
  dočasný výpadek feedu/Wikimedie — `gh run rerun <id>` obvykle stačí.
- Pages 404 → build ještě běží, počkej 2 min; jinak zkontroluj Settings → Pages.
- D1 sync warning → zkontroluj scope tokenu (musí mít D1:Edit) a Account ID.
- Kompletní mapa systému: `ARCHITECTURE.md`. Provozní detaily: `README.md`.
