"""Generate a day-by-day content plan and package it as a deployable browser.

For every date in the range this runs the REAL pipeline (bank fact -> product
match -> carousel in the day's auto style -> caption) and collects the results
into docs/plan/<date>/, then builds:
  - docs/plan/index.html  — Czech calendar viewer (deployable via GitHub Pages)
  - PLAN.md               — summary table for the repo/leadership

Usage: PYTHONPATH=src python scripts/make_plan.py 2026-08-14 2026-08-31
"""
from __future__ import annotations

import datetime as dt
import html
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contenthub import pipeline  # noqa: E402
from contenthub.config import Config, REPO_ROOT  # noqa: E402

CZ_MONTHS = ["ledna", "února", "března", "dubna", "května", "června",
             "července", "srpna", "září", "října", "listopadu", "prosince"]
CZ_DAYS = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
STYLE_LABEL = {"classic": "Classic", "editorial": "Editorial", "duotone": "Duotone"}


def run_range(start: dt.date, end: dt.date, plan_dir: Path) -> list[dict]:
    cfg = Config()
    cfg.ensure_dirs()
    entries = []
    d = start
    while d <= end:
        summary = pipeline.run(cfg, date=d, force=True)
        day_dir = plan_dir / d.isoformat()
        if day_dir.exists():
            shutil.rmtree(day_dir)
        day_dir.mkdir(parents=True)
        stem = f"post-{d.isoformat()}"
        for f in cfg.out_dir.glob(f"{stem}*"):
            shutil.copy(f, day_dir / f.name.replace(stem, "post"))
        summary["dir"] = day_dir.name
        entries.append(summary)
        print(f"[ok] {d}: {summary.get('style')} | "
              f"{(summary.get('fact') or 'TIP DNE')[:60]} | "
              f"{summary['product']['name'][:45]}")
        d += dt.timedelta(days=1)
    return entries


def build_viewer(entries: list[dict], plan_dir: Path, start: dt.date, end: dt.date):
    cards = []
    for e in entries:
        d = dt.date.fromisoformat(e["date"])
        fact = e.get("fact")
        label = html.escape(fact) if fact else "Produktový tip dne"
        badge = STYLE_LABEL.get(e.get("style") or "", "")
        slides = "".join(
            f'<a href="{e["dir"]}/post-{i}.jpg" target="_blank">'
            f'<img src="{e["dir"]}/post-{i}-45.jpg" loading="lazy" alt="slide {i}"></a>'
            for i in (1, 2, 3))
        cap = html.escape((plan_dir / e["dir"] / "post-caption.txt")
                          .read_text(encoding="utf-8").strip())
        cards.append(f"""
<details class="day" id="d{d.day}">
 <summary>
  <span class="dnum">{d.day}.</span>
  <span class="dow">{CZ_DAYS[d.weekday()]}</span>
  <span class="fact">{label}</span>
  <span class="prod">{html.escape(e['product']['name'][:52])} · {e['product']['price']}</span>
  <span class="badge">{badge}</span>
 </summary>
 <div class="body">
  <div class="slides">{slides}</div>
  <div class="cap"><span>CAPTION — zkopíruj a publikuj</span><pre>{cap}</pre></div>
 </div>
</details>""")

    n_facts = sum(1 for e in entries if e.get("fact"))
    page = f"""<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>contenthub — content plán {start.day}.–{end.day}. {CZ_MONTHS[start.month-1]} {start.year}</title>
<style>
:root{{--ink:#0F1118;--mid:#18243C;--blue:#284C87;--accent:#2962CD;--bright:#4D7FC4;--muted:#BCCAE0}}
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;color:#fff;
background:linear-gradient(135deg,var(--ink),var(--mid) 50%,var(--blue)) fixed;background-color:var(--ink)}}
.wrap{{max-width:1000px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:34px;margin:0 0 6px}}
.sub{{color:var(--muted);margin-bottom:10px}}
.stats{{color:var(--bright);font-size:14px;margin-bottom:30px}}
.day{{background:rgba(24,36,60,.55);border:1px solid rgba(77,127,196,.3);border-radius:14px;margin-bottom:10px;overflow:hidden}}
summary{{display:flex;gap:14px;align-items:center;padding:14px 18px;cursor:pointer;list-style:none;flex-wrap:wrap}}
summary::-webkit-details-marker{{display:none}}
.dnum{{font-weight:800;font-size:20px;min-width:36px}}
.dow{{color:var(--bright);font-size:13px;min-width:24px}}
.fact{{flex:1;min-width:200px;font-weight:600;font-size:14px}}
.prod{{color:var(--muted);font-size:13px}}
.badge{{font-size:11px;border:1px solid var(--bright);color:var(--bright);border-radius:99px;padding:2px 10px}}
.body{{padding:6px 18px 18px;border-top:1px solid rgba(77,127,196,.2)}}
.slides{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}}
.slides img{{width:100%;border-radius:10px;border:1px solid rgba(77,127,196,.35)}}
.cap span{{font-size:11px;letter-spacing:1.5px;color:var(--bright)}}
.cap pre{{white-space:pre-wrap;background:rgba(15,17,24,.6);border:1px solid rgba(77,127,196,.3);
border-radius:10px;padding:14px;font-family:inherit;font-size:13px;line-height:1.6;margin:8px 0 0}}
.note{{color:var(--muted);font-size:13px;margin-top:30px;line-height:1.6}}
</style></head><body><div class="wrap">
<h1>Content plán · {start.day}.–{end.day}. {CZ_MONTHS[start.month-1]} {start.year}</h1>
<p class="sub">Každý den vygenerovaný automaticky: fakt z banky → produkt ze skladu → carousel → caption.
Klikni na den, prohlédni slidy (náhled 4:5, klik = 9:16 master), zkopíruj caption.</p>
<p class="stats">{len(entries)} dní · {n_facts}× historický fakt · {len(entries)-n_facts}× produktový tip · 3 vizuální styly v rotaci</p>
{''.join(cards)}
<p class="note">Vygenerováno pipeline contenthub — 0 Kč provoz, žádné AI za běhu.
Slidy jsou finální: 9:16 master (Stories/Reels) + 4:5 crop (feed) ze stejné safe zóny.</p>
</div></body></html>"""
    (plan_dir / "index.html").write_text(page, encoding="utf-8")


def build_plan_md(entries: list[dict], start: dt.date, end: dt.date):
    lines = [
        f"# Content plán {start.day}.–{end.day}. {CZ_MONTHS[start.month-1]} {start.year}",
        "",
        "Vygenerováno pipeline (bank fakt → produkt → carousel → caption). "
        "Kompletní materiály: `docs/plan/<datum>/`, prohlížeč: `docs/plan/index.html`.",
        "",
        "| Datum | Den | Fakt / režim | Produkt | Cena | Styl |",
        "|---|---|---|---|---|---|",
    ]
    for e in entries:
        d = dt.date.fromisoformat(e["date"])
        fact = (e.get("fact") or "— produktový tip —")[:70]
        lines.append(
            f"| {d.day}. {d.month}. | {CZ_DAYS[d.weekday()]} | {fact} "
            f"| {e['product']['name'][:45]} | {e['product']['price']} "
            f"| {e.get('style') or '-'} |")
    (REPO_ROOT / "PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    start = dt.date.fromisoformat(sys.argv[1])
    end = dt.date.fromisoformat(sys.argv[2])
    plan_dir = REPO_ROOT / "docs" / "plan"
    entries = run_range(start, end, plan_dir)
    build_viewer(entries, plan_dir, start, end)
    build_plan_md(entries, start, end)
    (plan_dir / "PLAN.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(entries)} days -> {plan_dir} (+ PLAN.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
