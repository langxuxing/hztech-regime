from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.http_client import get_json

Side = Literal["long", "short"]

DEFAULT_HALF_LIFE_HOURS = 3.0
_MIN_EVENT_WEIGHT_USD = 1.0


@dataclass
class _LiqEvent:
    event_id: str
    price: float
    notional_usd: float
    side: Side
    ts: float


@dataclass
class LiquidationGridState:
    cells: list[dict[str, Any]]
    spot_price: float
    dominant_side: Side | None
    pain_price: float | None
    half_life_hours: float
    total_weight: float
    as_of: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": self.cells,
            "spot_price": self.spot_price,
            "dominant_side": self.dominant_side,
            "pain_price": self.pain_price,
            "half_life_hours": self.half_life_hours,
            "total_weight": round(self.total_weight, 2),
            "as_of": self.as_of,
        }


class LiquidationGrid:
    """强平网格：逐笔事件 + 半衰期权重，避免重复 poll 叠加与错误衰减。"""

    def __init__(self, *, half_life_hours: float = DEFAULT_HALF_LIFE_HOURS) -> None:
        self.half_life_hours = half_life_hours
        self._events: dict[str, _LiqEvent] = {}
        self._lock = threading.Lock()

    def ingest(
        self,
        event_id: str,
        price: float,
        notional_usd: float,
        side: Side,
        *,
        ts: float,
    ) -> bool:
        """写入单笔强平；已存在 event_id 则跳过（去重）。"""
        if not event_id or price <= 0 or notional_usd <= 0:
            return False
        with self._lock:
            if event_id in self._events:
                return False
            self._events[event_id] = _LiqEvent(
                event_id=event_id,
                price=price,
                notional_usd=notional_usd,
                side=side,
                ts=ts,
            )
            return True

    def _event_weight(self, ev: _LiqEvent, now: float) -> float:
        half_life_sec = self.half_life_hours * 3600
        if half_life_sec <= 0:
            return ev.notional_usd
        age = max(0.0, now - ev.ts)
        return ev.notional_usd * math.pow(0.5, age / half_life_sec)

    def _prune(self, now: float) -> None:
        dead = [eid for eid, ev in self._events.items() if self._event_weight(ev, now) < _MIN_EVENT_WEIGHT_USD]
        for eid in dead:
            del self._events[eid]

    def snapshot(self, spot_price: float, *, top_n: int = 8, now: float | None = None) -> LiquidationGridState:
        now = now or time.time()
        with self._lock:
            self._prune(now)
            bins: dict[int, dict[str, float]] = {}
            total_weight = 0.0
            for ev in self._events.values():
                w = self._event_weight(ev, now)
                if w < _MIN_EVENT_WEIGHT_USD:
                    continue
                total_weight += w
                key = int(round(ev.price, 0))
                cell = bins.setdefault(key, {"long_usd": 0.0, "short_usd": 0.0, "price": float(key)})
                if ev.side == "long":
                    cell["long_usd"] += w
                else:
                    cell["short_usd"] += w

            ranked = sorted(
                bins.values(),
                key=lambda c: c["long_usd"] + c["short_usd"],
                reverse=True,
            )
            cells = [
                {
                    "price": round(c["price"], 2),
                    "long_usd": round(c["long_usd"], 2),
                    "short_usd": round(c["short_usd"], 2),
                    "total_usd": round(c["long_usd"] + c["short_usd"], 2),
                }
                for c in ranked[:top_n]
            ]
            pain = ranked[0] if ranked else None
            dominant: Side | None = None
            pain_price = None
            if pain:
                dominant = "long" if pain["long_usd"] >= pain["short_usd"] else "short"
                pain_price = pain["price"]

        return LiquidationGridState(
            cells=cells,
            spot_price=spot_price,
            dominant_side=dominant,
            pain_price=pain_price,
            half_life_hours=self.half_life_hours,
            total_weight=total_weight,
            as_of=datetime.now(timezone.utc).isoformat(),
        )


class BinanceLiquidationListener:
    """收集 Binance 强平，按 event_id 去重，使用真实成交时间戳。"""

    def __init__(self, grid: LiquidationGrid, symbol: str = "BTCUSDT") -> None:
        self.grid = grid
        self.symbol = symbol.replace("/", "").replace(":USDT", "").upper()
        if not self.symbol.endswith("USDT"):
            self.symbol = f"{self.symbol}USDT"

    def poll_once(self, cfg: AdvisorConfig | None = None) -> int:
        cfg = cfg or AdvisorConfig.from_env()
        return self._ingest_coinglass(cfg) + self._ingest_binance_force_orders()

    def _ingest_coinglass(self, cfg: AdvisorConfig) -> int:
        if not cfg.coinglass_api_key:
            return 0
        try:
            data = get_json(
                "https://open-api-v4.coinglass.com/api/futures/liquidation/order",
                params={"symbol": "BTC", "exchange": "Binance", "limit": 50},
                headers={"CG-API-KEY": cfg.coinglass_api_key},
            )
            rows = (data.get("data") or []) if isinstance(data, dict) else []
        except Exception:
            return 0

        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            price = float(row.get("price") or row.get("avgPrice") or 0)
            amount = float(row.get("usdValue") or row.get("volUsd") or row.get("amount") or 0)
            side_raw = str(row.get("side") or row.get("type") or "").lower()
            if price <= 0 or amount <= 0:
                continue
            # 强平：SELL 平多 → long；BUY 平空 → short
            side: Side = "long" if side_raw in ("sell", "short", "2") else "short"
            ts = _row_ts(row, keys=("time", "createTime", "timestamp", "ts"))
            eid = str(row.get("id") or row.get("orderId") or "")
            if not eid:
                eid = _hash_event("cg", price, amount, side, ts)
            if self.grid.ingest(f"cg:{eid}", price, amount, side, ts=ts):
                count += 1
        return count

    def _ingest_binance_force_orders(self) -> int:
        try:
            rows = get_json(
                "https://fapi.binance.com/fapi/v1/allForceOrders",
                params={"symbol": self.symbol, "limit": 50},
            )
        except Exception:
            return 0
        if not isinstance(rows, list):
            return 0

        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            price = float(row.get("price") or row.get("avgPrice") or 0)
            qty = float(row.get("origQty") or row.get("executedQty") or 0)
            if price <= 0 or qty <= 0:
                continue
            notional = price * qty
            side: Side = "long" if str(row.get("side", "")).upper() == "SELL" else "short"
            ts = _row_ts(row, keys=("time", "updateTime", "workingTime"))
            eid = str(row.get("orderId") or row.get("id") or "")
            if not eid:
                eid = _hash_event("bn", price, qty, side, ts)
            if self.grid.ingest(f"bn:{eid}", price, notional, side, ts=ts):
                count += 1
        return count


_grids: dict[str, LiquidationGrid] = {}
_grid_lock = threading.Lock()


def _row_ts(row: dict, *, keys: tuple[str, ...]) -> float:
    for key in keys:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
            return val / 1000.0 if val > 1e12 else val
        except (TypeError, ValueError):
            continue
    return time.time()


def _hash_event(prefix: str, *parts: Any) -> str:
    blob = "|".join(str(p) for p in parts)
    return f"{prefix}:{hashlib.sha1(blob.encode()).hexdigest()[:16]}"


def get_liquidation_grid(
    symbol: str = "BTC",
    *,
    half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
) -> LiquidationGrid:
    key = symbol.upper()
    with _grid_lock:
        grid = _grids.get(key)
        if grid is None:
            grid = LiquidationGrid(half_life_hours=half_life_hours)
            _grids[key] = grid
        elif abs(grid.half_life_hours - half_life_hours) > 1e-6:
            grid.half_life_hours = half_life_hours
        return grid


def build_liquidation_map(
    spot_price: float,
    cfg: AdvisorConfig | None = None,
    *,
    half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
) -> LiquidationGridState:
    cfg = cfg or AdvisorConfig.from_env()
    asset = cfg.symbol.split("/")[0].upper()
    grid = get_liquidation_grid(asset, half_life_hours=half_life_hours)
    listener = BinanceLiquidationListener(grid, symbol=cfg.symbol)
    listener.poll_once(cfg)
    return grid.snapshot(spot_price)
