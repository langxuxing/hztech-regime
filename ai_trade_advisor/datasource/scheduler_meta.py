from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_trade_advisor.datasource.paths import ensure_data_layout


class SchedulerMetaStore:
    """任务元数据：data/cache/scheduler_meta.json"""

    def __init__(self, path: Path | None = None) -> None:
        layout = ensure_data_layout()
        self._path = path or layout["cache"] / "scheduler_meta.json"
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"tasks": {}}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("tasks", {})
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"tasks": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

    def record(
        self,
        task: str,
        *,
        ok: bool,
        duration_ms: int | None = None,
        detail: str = "",
        error: str | None = None,
    ) -> None:
        data = self._read()
        now = datetime.now(timezone.utc).isoformat()
        entry: dict[str, Any] = {
            "last_run_at": now,
            "last_ok": ok,
            "duration_ms": duration_ms,
            "detail": detail,
        }
        if ok:
            entry["last_ok_at"] = now
            entry["last_error"] = None
        else:
            entry["last_error"] = error or detail or "unknown error"
        data["tasks"][task] = entry
        data["updated_at"] = now
        self._write(data)

    def all_tasks(self) -> dict[str, Any]:
        return self._read().get("tasks", {})

    def status(self) -> dict[str, Any]:
        data = self._read()
        tasks = data.get("tasks", {})
        ok_count = sum(1 for t in tasks.values() if t.get("last_ok"))
        return {
            "updated_at": data.get("updated_at"),
            "task_count": len(tasks),
            "tasks_ok": ok_count,
            "tasks": tasks,
        }
