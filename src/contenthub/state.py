"""SQLite state: post history for dedup/cooldown and idempotent daily runs."""
from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    day TEXT PRIMARY KEY,          -- ISO date, one post per day
    product_id TEXT NOT NULL,
    fact_text TEXT,
    fact_lang TEXT,
    caption TEXT,
    media_path TEXT,
    published INTEGER DEFAULT 0,   -- 0 = dry-run/generated, 1 = live on IG
    ig_media_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class State:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(_SCHEMA)
        self.conn.commit()

    def already_published(self, day: dt.date) -> bool:
        row = self.conn.execute(
            "SELECT published FROM posts WHERE day = ?", (day.isoformat(),)
        ).fetchone()
        return bool(row and row[0])

    def recent_product_ids(self, cooldown_days: int) -> set[str]:
        cutoff = (dt.date.today() - dt.timedelta(days=cooldown_days)).isoformat()
        rows = self.conn.execute(
            "SELECT product_id FROM posts WHERE day >= ?", (cutoff,)
        ).fetchall()
        return {r[0] for r in rows}

    def record(
        self,
        day: dt.date,
        product_id: str,
        fact_text: str | None,
        fact_lang: str | None,
        caption: str,
        media_path: str,
        published: bool,
        ig_media_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO posts (day, product_id, fact_text, fact_lang, caption,
                                  media_path, published, ig_media_id)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(day) DO UPDATE SET
                 product_id=excluded.product_id, fact_text=excluded.fact_text,
                 fact_lang=excluded.fact_lang, caption=excluded.caption,
                 media_path=excluded.media_path, published=excluded.published,
                 ig_media_id=excluded.ig_media_id""",
            (
                day.isoformat(),
                product_id,
                fact_text,
                fact_lang,
                caption,
                media_path,
                int(published),
                ig_media_id,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
