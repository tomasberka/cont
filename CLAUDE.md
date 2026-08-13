# contenthub — instrukce pro Claude Code

Denní social pipeline pro Hellocomp.cz (fakt z historie → produkt ze skladu →
značkový carousel → caption). Python 3.11+, žádné placené služby, vše free tier.

## Tvůj úkol v tomto repu

1. **Nasazení** → postupuj přesně podle **`DEPLOY.md`** (fáze 0–6, každá má
   ✅ ověření; u kroků 🧑 se zastav a vyžádej vstup uživatele).
   Pozn.: workflow soubory už JSOU v `.github/workflows/` — fázi 1 přeskoč,
   pokud neexistuje složka `github-workflows-INSTALL/`.
2. **Pochopení systému** → `ARCHITECTURE.md` (datový tok, mapa modulů,
   tabulka „kde se co ovládá").
3. **Provoz a ladění** → `README.md`; plná automatika → `AUTONOMY.md`.

## Pravidla (neporušuj)

- Tokeny/klíče POUZE přes `gh secret set` — nikdy do souborů ani commitů.
- Před jakoukoli změnou kódu: `PYTHONPATH=src python -m pytest tests/ -q`
  (16 testů) — a po změně znovu. Test „no amber pixel" je brand guard, nikdy
  ho neobcházej.
- Brand konstanty se mění jedině v `src/contenthub/media_brand.py`
  (modrá #2962CD + bílá, žádný amber).
- Obsah se ladí v datech, ne v kódu: `data/facts_bank.yml` (texty dní),
  `data/overrides.yml` (ruční produkt ke dni), `data/rules.yml` (marže/párování).
- DRY_RUN=1 je default — ostrou publikaci zapíná jen uživatel.

## Rychlé příkazy

```
PYTHONPATH=src python -m contenthub run              # dnešní post (dry-run)
PYTHONPATH=src python scripts/make_plan.py A B       # plán pro rozsah dat
PYTHONPATH=src python scripts/make_presentation.py   # prezentace z plánu
PYTHONPATH=src python scripts/make_reels.py A B       # MP4 reels
```
