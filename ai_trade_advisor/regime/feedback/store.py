from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_trade_advisor.datasource.paths import default_regime_db


class FeedbackStore:
    """反馈闭环：模型打分、rollup、版本化参数。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_regime_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_judgment_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(human_regime_judgment)")}
        migrations = [
            ("market_context_json", "TEXT"),
            ("bar_timestamp", "TEXT"),
            ("forward_scored_at", "TEXT"),
            ("realized_regime_json", "TEXT"),
        ]
        for name, typ in migrations:
            if name not in cols:
                conn.execute(f"ALTER TABLE human_regime_judgment ADD COLUMN {name} {typ}")

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

                CREATE TABLE IF NOT EXISTS model_judgment_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    judgment_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    score_type TEXT NOT NULL,
                    trend_score REAL,
                    regime_score REAL,
                    pred_score REAL,
                    total_score REAL,
                    details_json TEXT,
                    scored_at TEXT NOT NULL,
                    UNIQUE(judgment_id, model_id, score_type)
                );
                CREATE INDEX IF NOT EXISTS idx_scores_judgment
                    ON model_judgment_scores(judgment_id);

                CREATE TABLE IF NOT EXISTS model_performance_rollup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    segment_primary TEXT,
                    model_id TEXT,
                    window_days INTEGER,
                    sample_count INTEGER,
                    instant_avg REAL,
                    forward_avg REAL,
                    combined_score REAL,
                    low_confidence INTEGER DEFAULT 0,
                    updated_at TEXT,
                    UNIQUE(symbol, segment_primary, model_id, window_days)
                );

                CREATE TABLE IF NOT EXISTS model_params (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    params_json TEXT NOT NULL,
                    metrics_json TEXT,
                    status TEXT DEFAULT 'active',
                    effective_from TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(model_id, version)
                );
                """
            )
            self._migrate_judgment_columns(conn)

    def save_scores(self, scores: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            for s in scores:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO model_judgment_scores (
                        judgment_id, model_id, score_type,
                        trend_score, regime_score, pred_score, total_score,
                        details_json, scored_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s["judgment_id"],
                        s["model_id"],
                        s["score_type"],
                        s.get("trend_score"),
                        s.get("regime_score"),
                        s.get("pred_score"),
                        s.get("total_score"),
                        json.dumps(s.get("details") or {}, ensure_ascii=False),
                        s["scored_at"],
                    ),
                )

    def scores_for_judgment(self, judgment_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT judgment_id, model_id, score_type, trend_score, regime_score,
                       pred_score, total_score, details_json, scored_at
                FROM model_judgment_scores WHERE judgment_id = ?
                ORDER BY score_type, total_score DESC
                """,
                (judgment_id,),
            ).fetchall()
        return [self._row_score(r) for r in rows]

    def _row_score(self, row: sqlite3.Row) -> dict[str, Any]:
        details = {}
        if row["details_json"]:
            try:
                details = json.loads(row["details_json"])
            except json.JSONDecodeError:
                pass
        return {
            "judgment_id": row["judgment_id"],
            "model_id": row["model_id"],
            "score_type": row["score_type"],
            "trend_score": row["trend_score"],
            "regime_score": row["regime_score"],
            "pred_score": row["pred_score"],
            "total_score": row["total_score"],
            "details": details,
            "scored_at": row["scored_at"],
        }

    def pending_forward_judgments(self, *, min_age_minutes: int) -> list[dict[str, Any]]:
        """尚未 forward 打分且已超过 N bar 等待期的标注。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, recorded_at, symbol, human_regime, human_trend,
                       human_notes, model_predictions_json, bar_close,
                       market_context_json, bar_timestamp, forward_scored_at,
                       realized_regime_json
                FROM human_regime_judgment
                WHERE forward_scored_at IS NULL
                ORDER BY recorded_at ASC
                """
            ).fetchall()

        now = datetime.now(timezone.utc)
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                recorded = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            age_min = (now - recorded).total_seconds() / 60.0
            if age_min < min_age_minutes:
                continue
            out.append(self._row_judgment(row))
        return out

    def mark_forward_scored(
        self,
        judgment_id: int,
        *,
        realized: dict[str, Any],
        scored_at: str | None = None,
    ) -> None:
        now = scored_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE human_regime_judgment
                SET forward_scored_at = ?, realized_regime_json = ?
                WHERE id = ?
                """,
                (now, json.dumps(realized, ensure_ascii=False), judgment_id),
            )

    def _row_judgment(self, row: sqlite3.Row) -> dict[str, Any]:
        preds = {}
        if row["model_predictions_json"]:
            try:
                preds = json.loads(row["model_predictions_json"])
            except json.JSONDecodeError:
                pass
        ctx = {}
        if row["market_context_json"]:
            try:
                ctx = json.loads(row["market_context_json"])
            except json.JSONDecodeError:
                pass
        realized = {}
        if row["realized_regime_json"]:
            try:
                realized = json.loads(row["realized_regime_json"])
            except json.JSONDecodeError:
                pass
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

    def upsert_rollup(self, rows: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO model_performance_rollup (
                        symbol, segment_primary, model_id, window_days,
                        sample_count, instant_avg, forward_avg, combined_score,
                        low_confidence, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, segment_primary, model_id, window_days)
                    DO UPDATE SET
                        sample_count=excluded.sample_count,
                        instant_avg=excluded.instant_avg,
                        forward_avg=excluded.forward_avg,
                        combined_score=excluded.combined_score,
                        low_confidence=excluded.low_confidence,
                        updated_at=excluded.updated_at
                    """,
                    (
                        r["symbol"],
                        r["segment_primary"],
                        r["model_id"],
                        r["window_days"],
                        r["sample_count"],
                        r.get("instant_avg"),
                        r.get("forward_avg"),
                        r.get("combined_score"),
                        1 if r.get("low_confidence") else 0,
                        now,
                    ),
                )

    def leaderboard(
        self,
        *,
        symbol: str = "",
        segment: str = "",
        window_days: int = 30,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT symbol, segment_primary, model_id, window_days,
                   sample_count, instant_avg, forward_avg, combined_score,
                   low_confidence, updated_at
            FROM model_performance_rollup
            WHERE window_days = ?
        """
        params: list[Any] = [window_days]
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if segment:
            query += " AND segment_primary = ?"
            params.append(segment)
        query += " ORDER BY combined_score DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "symbol": r["symbol"],
                "segment_primary": r["segment_primary"],
                "model_id": r["model_id"],
                "window_days": r["window_days"],
                "sample_count": r["sample_count"],
                "instant_avg": r["instant_avg"],
                "forward_avg": r["forward_avg"],
                "combined_score": r["combined_score"],
                "low_confidence": bool(r["low_confidence"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def active_params(self, model_id: str | None = None) -> dict[str, dict[str, Any]]:
        query = "SELECT model_id, version, params_json, metrics_json FROM model_params WHERE status = 'active'"
        params: list[Any] = []
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        out: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            for row in conn.execute(query, params):
                try:
                    p = json.loads(row["params_json"])
                except json.JSONDecodeError:
                    p = {}
                out[row["model_id"]] = {
                    "version": row["version"],
                    "params": p,
                    "metrics": json.loads(row["metrics_json"]) if row["metrics_json"] else {},
                }
        return out

    def save_params_candidate(
        self,
        model_id: str,
        params: dict[str, Any],
        *,
        metrics: dict[str, Any] | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM model_params WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            version = int(row["v"]) + 1
            conn.execute(
                """
                INSERT INTO model_params (
                    model_id, version, params_json, metrics_json,
                    status, effective_from, created_at
                ) VALUES (?, ?, ?, ?, 'candidate', ?, ?)
                """,
                (
                    model_id,
                    version,
                    json.dumps(params, ensure_ascii=False),
                    json.dumps(metrics or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return version

    def activate_params(self, model_id: str, version: int, *, min_improvement: float = 0.03) -> bool:
        """candidate 优于 active 时切换。"""
        with self._connect() as conn:
            active = conn.execute(
                """
                SELECT version, metrics_json FROM model_params
                WHERE model_id = ? AND status = 'active'
                ORDER BY version DESC LIMIT 1
                """,
                (model_id,),
            ).fetchone()
            cand = conn.execute(
                """
                SELECT version, metrics_json FROM model_params
                WHERE model_id = ? AND version = ? AND status = 'candidate'
                """,
                (model_id, version),
            ).fetchone()
            if cand is None:
                return False

            def _score(metrics_json: str | None) -> float:
                if not metrics_json:
                    return 0.0
                try:
                    m = json.loads(metrics_json)
                    return float(m.get("combined_score") or 0.0)
                except (json.JSONDecodeError, TypeError):
                    return 0.0

            old_score = _score(active["metrics_json"]) if active else 0.0
            new_score = _score(cand["metrics_json"])
            if active and new_score < old_score * (1.0 + min_improvement):
                return False

            conn.execute(
                "UPDATE model_params SET status = 'retired' WHERE model_id = ? AND status = 'active'",
                (model_id,),
            )
            conn.execute(
                "UPDATE model_params SET status = 'active' WHERE model_id = ? AND version = ?",
                (model_id, version),
            )
            return True

    def scores_joined_recent(
        self,
        *,
        symbol: str = "",
        window_days: int = 30,
    ) -> list[dict[str, Any]]:
        """打分记录联表标注，供 rollup / calibrator 使用。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT j.id, j.symbol, j.recorded_at, j.market_context_json,
                       s.model_id, s.score_type, s.total_score
                FROM human_regime_judgment j
                JOIN model_judgment_scores s ON s.judgment_id = j.id
                WHERE j.recorded_at >= datetime('now', ?)
                  AND s.model_id != '_human'
                ORDER BY j.recorded_at DESC
                """,
                (f"-{window_days} days",),
            ).fetchall()

        out: list[dict[str, Any]] = []
        for r in rows:
            if symbol and r["symbol"] != symbol:
                continue
            ctx = {}
            if r["market_context_json"]:
                try:
                    ctx = json.loads(r["market_context_json"])
                except json.JSONDecodeError:
                    pass
            out.append(
                {
                    "judgment_id": r["id"],
                    "symbol": r["symbol"],
                    "segment_primary": ctx.get("segment_primary", "global"),
                    "model_id": r["model_id"],
                    "score_type": r["score_type"],
                    "total_score": r["total_score"],
                }
            )
        return out

    def forward_scored_judgments(
        self,
        *,
        symbol: str = "",
        window_days: int = 30,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """已 forward 打分、含 realized regime 的标注。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, recorded_at, symbol, human_regime, human_trend,
                       human_notes, model_predictions_json, bar_close,
                       market_context_json, bar_timestamp, forward_scored_at,
                       realized_regime_json
                FROM human_regime_judgment
                WHERE forward_scored_at IS NOT NULL
                  AND realized_regime_json IS NOT NULL
                  AND recorded_at >= datetime('now', ?)
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (f"-{window_days} days", limit),
            ).fetchall()
        out = [self._row_judgment(r) for r in rows]
        if symbol:
            out = [j for j in out if j["symbol"] == symbol]
        return out
