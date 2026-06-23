from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai_trade_advisor.datasource.paths import default_events_db
from ai_trade_advisor.bigevent.models import EventImpact, MarketEvent

DEFAULT_DB = default_events_db()


class EventStore:
    """SQLite 事件持久化：去重、历史、价格快照。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    category TEXT,
                    source TEXT,
                    published_at TEXT,
                    importance INTEGER,
                    btc_relevance REAL,
                    payload TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT
                );
                CREATE TABLE IF NOT EXISTS impacts (
                    event_id TEXT PRIMARY KEY,
                    impact_score REAL,
                    impact_level TEXT,
                    direction TEXT,
                    reasoning TEXT,
                    btc_price REAL,
                    analyzed_at TEXT,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_published ON events(published_at);
                CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
                """
            )

    def upsert_events(self, events: list[MarketEvent]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        new_count = 0
        with self._connect() as conn:
            for e in events:
                row = conn.execute("SELECT id FROM events WHERE id = ?", (e.id,)).fetchone()
                payload = json.dumps(e.to_dict(), ensure_ascii=False)
                if row:
                    conn.execute(
                        "UPDATE events SET last_seen_at = ?, payload = ? WHERE id = ?",
                        (now, payload, e.id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO events (
                            id, title, summary, category, source, published_at,
                            importance, btc_relevance, payload, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            e.id, e.title, e.summary, e.category, e.source,
                            e.published_at, e.importance, e.btc_relevance,
                            payload, now, now,
                        ),
                    )
                    new_count += 1
        return new_count

    def save_impacts(self, impacts: list[EventImpact]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for imp in impacts:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO impacts
                    (event_id, impact_score, impact_level, direction, reasoning, btc_price, analyzed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        imp.event_id, imp.impact_score, imp.impact_level,
                        imp.direction, imp.reasoning, imp.btc_price, now,
                    ),
                )

    def recent_events(self, *, limit: int = 50, source_prefix: str | None = None) -> list[MarketEvent]:
        query = "SELECT payload FROM events"
        params: list = []
        if source_prefix:
            query += " WHERE source LIKE ?"
            params.append(f"{source_prefix}%")
        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)

        out: list[MarketEvent] = []
        with self._connect() as conn:
            for row in conn.execute(query, params):
                data = json.loads(row["payload"])
                out.append(_event_from_dict(data))
        return out

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
            return int(row["c"]) if row else 0


def _event_from_dict(data: dict) -> MarketEvent:
    return MarketEvent(
        id=data["id"],
        title=data["title"],
        summary=data.get("summary", ""),
        category=data.get("category", "other"),  # type: ignore[arg-type]
        source=data.get("source", ""),
        published_at=data.get("published_at", ""),
        importance=int(data.get("importance", 3)),
        btc_relevance=float(data.get("btc_relevance", 0.5)),
        tags=data.get("tags") or [],
        source_url=data.get("source_url"),
        country=data.get("country"),
        scheduled_at=data.get("scheduled_at"),
        is_scheduled=bool(data.get("is_scheduled")),
    )
