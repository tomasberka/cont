"""Push today's post record to Cloudflare D1 (free tier) after a pipeline run.

Runs as an optional GitHub Actions step — it is a no-op unless these env vars
are set: CF_ACCOUNT_ID, CF_API_TOKEN (token scope: D1 edit), CF_D1_DATABASE_ID.

Usage: python scripts/sync_d1.py out/post-YYYY-MM-DD.json
"""
from __future__ import annotations

import json
import os
import sys

import requests


def main() -> int:
    acc = os.environ.get("CF_ACCOUNT_ID", "")
    tok = os.environ.get("CF_API_TOKEN", "")
    db = os.environ.get("CF_D1_DATABASE_ID", "")
    if not (acc and tok and db):
        print("D1 sync skipped — CF_* secrets not configured (this is fine).")
        return 0

    summary = json.load(open(sys.argv[1], encoding="utf-8"))
    sql = (
        "INSERT INTO posts (day, product_id, product_name, fact_text, fact_lang,"
        " caption, style, published, media_urls) VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(day) DO UPDATE SET product_id=excluded.product_id,"
        " product_name=excluded.product_name, fact_text=excluded.fact_text,"
        " fact_lang=excluded.fact_lang, caption=excluded.caption,"
        " style=excluded.style, published=excluded.published,"
        " media_urls=excluded.media_urls"
    )
    params = [
        summary["date"],
        summary["product"]["id"],
        summary["product"]["name"],
        summary.get("fact") or "",
        summary.get("fact_lang") or "",
        summary["caption"],
        summary.get("style") or "",
        "1" if summary["status"] == "published" else "0",
        json.dumps(summary.get("slides") or [], ensure_ascii=False),
    ]
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{acc}/d1/database/{db}/query",
        headers={"Authorization": f"Bearer {tok}"},
        json={"sql": sql, "params": params},
        timeout=60,
    )
    r.raise_for_status()
    ok = r.json().get("success")
    print("D1 sync:", "ok" if ok else r.text[:400])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
