from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai_trade_advisor.datasource.paths import default_regime_db
from ai_trade_advisor.models import RegimeJudgment


class RegimeHistoryStore:
    """Regime 切换时间线：持久化每次 Regime 变化。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_regime_db()
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
                CREATE TABLE IF NOT EXISTS regime_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    regime_id TEXT,
                    label TEXT NOT NULL,
                    confidence REAL,
                    summary TEXT,
                    vol_regime TEXT,
                    structure_regime TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_regime_history_at
                    ON regime_history(recorded_at DESC);
                """
            )

    def record_if_changed(
        self,
        symbol: str,
        regime: RegimeJudgment,
        *,
        as_of: str | None = None,
    ) -> bool:
        """若 Regime 与最近一条不同则写入，返回是否新增。"""
        key = regime.regime_id or regime.regime
        last = self.latest(symbol)
        if last and last.get("regime_key") == key:
            return False

        now = as_of or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO regime_history (
                    recorded_at, symbol, regime, regime_id, label,
                    confidence, summary, vol_regime, structure_regime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    symbol,
                    regime.regime,
                    regime.regime_id,
                    regime.label,
                    regime.confidence,
                    regime.summary,
                    regime.vol_regime,
                    regime.structure_regime,
                ),
            )
        return True

    def latest(self, symbol: str) -> dict | None:
        rows = self.recent(symbol=symbol, limit=1)
        return rows[0] if rows else None

    def recent(self, *, symbol: str = "", limit: int = 30) -> list[dict]:
        query = """
            SELECT recorded_at, symbol, regime, regime_id, label,
                   confidence, summary, vol_regime, structure_regime
            FROM regime_history
        """
        params: list = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(limit)

        out: list[dict] = []
        with self._connect() as conn:
            for row in conn.execute(query, params):
                rid = row["regime_id"] or row["regime"]
                out.append(
                    {
                        "recorded_at": row["recorded_at"],
                        "symbol": row["symbol"],
                        "regime": row["regime"],
                        "regime_id": row["regime_id"],
                        "regime_key": rid,
                        "label": row["label"],
                        "confidence": row["confidence"],
                        "summary": row["summary"],
                        "vol_regime": row["vol_regime"],
                        "structure_regime": row["structure_regime"],
                    }
                )
        return out
