from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai_trade_advisor.datasource.paths import default_regime_db
from ai_trade_advisor.regime.feedback.store import FeedbackStore


class HumanJudgmentStore:
    """人工 Regime 判断记录：与多模型预测对比。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_regime_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        FeedbackStore(self.db_path)._init_schema()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS human_regime_judgment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    human_regime TEXT NOT NULL,
                    human_trend TEXT,
                    human_notes TEXT,
                    model_predictions_json TEXT,
                    bar_close REAL
                );
                CREATE INDEX IF NOT EXISTS idx_human_judgment_at
                    ON human_regime_judgment(recorded_at DESC);
                """
            )

    def record(
        self,
        symbol: str,
        *,
        human_regime: str,
        human_trend: str | None = None,
        human_notes: str | None = None,
        model_predictions: dict | None = None,
        bar_close: float | None = None,
        market_context: dict | None = None,
        bar_timestamp: str | None = None,
        as_of: str | None = None,
    ) -> int:
        now = as_of or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO human_regime_judgment (
                    recorded_at, symbol, human_regime, human_trend,
                    human_notes, model_predictions_json, bar_close,
                    market_context_json, bar_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    symbol,
                    human_regime,
                    human_trend,
                    human_notes,
                    json.dumps(model_predictions or {}, ensure_ascii=False),
                    bar_close,
                    json.dumps(market_context or {}, ensure_ascii=False),
                    bar_timestamp,
                ),
            )
            return int(cur.lastrowid or 0)

    def get_by_id(self, judgment_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, recorded_at, symbol, human_regime, human_trend,
                       human_notes, model_predictions_json, bar_close,
                       market_context_json, bar_timestamp, forward_scored_at,
                       realized_regime_json
                FROM human_regime_judgment WHERE id = ?
                """,
                (judgment_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def recent(self, *, symbol: str = "", limit: int = 20, with_scores: bool = False) -> list[dict]:
        query = """
            SELECT id, recorded_at, symbol, human_regime, human_trend,
                   human_notes, model_predictions_json, bar_close,
                   market_context_json, bar_timestamp, forward_scored_at,
                   realized_regime_json
            FROM human_regime_judgment
        """
        params: list = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(limit)

        out: list[dict] = []
        feedback = FeedbackStore(self.db_path) if with_scores else None
        with self._connect() as conn:
            for row in conn.execute(query, params):
                item = self._row_to_dict(row)
                if with_scores and feedback:
                    item["scores"] = feedback.scores_for_judgment(item["id"])
                out.append(item)
        return out

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        preds = {}
        if row["model_predictions_json"]:
            try:
                preds = json.loads(row["model_predictions_json"])
            except json.JSONDecodeError:
                preds = {}
        ctx = {}
        if row["market_context_json"]:
            try:
                ctx = json.loads(row["market_context_json"])
            except json.JSONDecodeError:
                ctx = {}
        realized = {}
        if row["realized_regime_json"]:
            try:
                realized = json.loads(row["realized_regime_json"])
            except json.JSONDecodeError:
                realized = {}
        return {
            "id": row["id"],
            "recorded_at": row["recorded_at"],
            "symbol": row["symbol"],
            "human_regime": row["human_regime"],
            "human_trend": row["human_trend"],
            "human_notes": row["human_notes"],
            "model_predictions": preds,
            "bar_close": row["bar_close"],
            "market_context": ctx,
            "bar_timestamp": row["bar_timestamp"],
            "forward_scored_at": row["forward_scored_at"],
            "realized_regime": realized,
        }

    def latest(self, symbol: str) -> dict | None:
        rows = self.recent(symbol=symbol, limit=1)
        return rows[0] if rows else None

    def count(self, *, symbol: str = "") -> int:
        query = "SELECT COUNT(*) FROM human_regime_judgment"
        params: list = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row[0] if row else 0)

    def count_forward_scored(self, *, symbol: str = "") -> int:
        query = """
            SELECT COUNT(*) FROM human_regime_judgment
            WHERE forward_scored_at IS NOT NULL AND forward_scored_at != ''
        """
        params: list = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row[0] if row else 0)
