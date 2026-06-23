from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.http_client import get_json

_CACHE_TTL_SEC = 60.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, "FundingSnapshot"]] = {}


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _direction(score: float) -> str:
    if score > 0.12:
        return "up"
    if score < -0.12:
        return "down"
    return "neutral"


def _symbol_to_binance_futures(symbol: str) -> str:
    base = symbol.split("/")[0]
    quote = symbol.split("/")[1].split(":")[0]
    return f"{base}{quote}"


@dataclass
class FundingSnapshot:
    """统一资金费率快照：Binance 为主源，CoinGlass 跨所均值为补充。"""

    symbol: str
    rate: float
    mark_price: float | None
    history: list[float]
    cross_exchange_avg: float | None
    cross_exchange_count: int
    primary_source: str
    as_of: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "rate": self.rate,
            "mark_price": self.mark_price,
            "history": self.history,
            "cross_exchange_avg": self.cross_exchange_avg,
            "cross_exchange_count": self.cross_exchange_count,
            "primary_source": self.primary_source,
            "as_of": self.as_of,
            "raw": self.raw,
        }


def fetch_funding_snapshot(
    cfg: AdvisorConfig,
    *,
    coinglass_api_key: str = "",
    force: bool = False,
) -> FundingSnapshot:
    """拉取并缓存统一 funding 快照（默认 TTL 60s）。"""
    key = f"{cfg.exchange}:{cfg.symbol}"
    now = time.monotonic()
    if not force:
        with _lock:
            hit = _cache.get(key)
            if hit and now - hit[0] < _CACHE_TTL_SEC:
                return hit[1]

    snap = _fetch_fresh(cfg, coinglass_api_key=coinglass_api_key)
    with _lock:
        _cache[key] = (now, snap)
    return snap


def _fetch_fresh(cfg: AdvisorConfig, *, coinglass_api_key: str) -> FundingSnapshot:
    sym = _symbol_to_binance_futures(cfg.symbol)
    premium = get_json(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        params={"symbol": sym},
        timeout=15.0,
    )
    rate = float(premium["lastFundingRate"])
    mark = float(premium.get("markPrice") or 0) or None

    history_rows = get_json(
        "https://fapi.binance.com/fapi/v1/fundingRate",
        params={"symbol": sym, "limit": 12},
        timeout=15.0,
    )
    history: list[float] = []
    if isinstance(history_rows, list):
        history = [
            float(r["fundingRate"])
            for r in history_rows
            if isinstance(r, dict) and r.get("fundingRate") is not None
        ]
    if not history:
        history = [rate]

    cross_avg: float | None = None
    cross_n = 0
    if coinglass_api_key:
        cross_avg, cross_n = _fetch_coinglass_cross_avg(coinglass_api_key)

    return FundingSnapshot(
        symbol=cfg.symbol,
        rate=rate,
        mark_price=mark,
        history=history,
        cross_exchange_avg=cross_avg,
        cross_exchange_count=cross_n,
        primary_source="binance_fapi",
        as_of=datetime.now(timezone.utc).isoformat(),
        raw={"premium": premium, "history_count": len(history)},
    )


def _fetch_coinglass_cross_avg(api_key: str) -> tuple[float | None, int]:
    try:
        data = get_json(
            "https://open-api-v4.coinglass.com/api/futures/funding-rate/exchange-list",
            params={"symbol": "BTC"},
            headers={"CG-API-KEY": api_key},
            timeout=15.0,
        )
        if str(data.get("code")) not in ("0", "200", "success"):
            return None, 0
        items = (data.get("data") or [])[:12]
        rates: list[float] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("rate") is not None:
                rates.append(float(item["rate"]))
            elif item.get("fundingRate") is not None:
                rates.append(float(item["fundingRate"]))
        if not rates:
            return None, 0
        return sum(rates) / len(rates), len(rates)
    except Exception:
        return None, 0


def funding_to_prediction_signal(snap: FundingSnapshot):
    """将统一 funding 快照转为趋势共识信号（单一 funding 源）。"""
    from ai_trade_advisor.forecast.models import PredictionSignal

    rate = snap.rate
    score = _clamp(rate * 8000)
    conf = 0.45 + min(0.35, abs(rate) * 12000)
    if snap.cross_exchange_avg is not None:
        conf = min(0.92, conf + 0.05)
    pct = rate * 100
    label = f"资金费率 {pct:.4f}%"
    if snap.cross_exchange_avg is not None:
        label += f" · 跨所均 {snap.cross_exchange_avg * 100:.4f}%"
    return PredictionSignal(
        source="funding_snapshot",
        category="derivatives",
        direction=_direction(score),
        score=score,
        confidence=conf,
        horizon="8h",
        label=label,
        raw=snap.to_dict(),
    )
