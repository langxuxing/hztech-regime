from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import ensure_data_layout


def snapshot_key(cfg: AdvisorConfig) -> str:
    sym = cfg.symbol.replace("/", "_").replace(":", "_")
    return f"{cfg.exchange}_{sym}"


class SnapshotStore:
    """文件型快照存储（data/cache/snapshots/）。"""

    def __init__(self, root: Path | None = None) -> None:
        layout = ensure_data_layout()
        self._dir = (root or layout["cache"]) / "snapshots"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def path_for(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self._dir / f"{safe}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        try:
            with self._lock:
                return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self.path_for(key)
        with self._lock:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        return payload

    def age_seconds(self, key: str) -> float | None:
        snap = self.get(key)
        if not snap:
            return None
        computed = snap.get("computed_at")
        if not computed:
            return None
        try:
            ts = datetime.fromisoformat(str(computed).replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - ts).total_seconds()
        except ValueError:
            return None

    def is_stale(self, key: str, max_age_sec: int) -> bool:
        age = self.age_seconds(key)
        if age is None:
            return True
        return age > max_age_sec

    @staticmethod
    def new_version() -> dict[str, str]:
        now = datetime.now(timezone.utc)
        return {
            "snapshot_id": uuid4().hex,
            "version": now.strftime("%Y%m%dT%H%M%SZ"),
            "computed_at": now.isoformat(),
        }
