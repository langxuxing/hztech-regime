from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from ai_trade_advisor.datasource.http_client import get_json
from ai_trade_advisor.forecast.models import PredictionDirection, PredictionSignal

SourceFetcher = Callable[[], PredictionSignal | None]

_NEUTRAL_BAND = 0.12


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _direction(score: float) -> PredictionDirection:
    if score >= _NEUTRAL_BAND:
        return "up"
    if score <= -_NEUTRAL_BAND:
        return "down"
    return "neutral"


def _signal(
    *,
    source: str,
    category: str,
    score: float,
    confidence: float,
    horizon: str,
    label: str,
    raw: dict[str, Any] | None = None,
) -> PredictionSignal:
    score = _clamp(score)
    confidence = _clamp(confidence, 0.0, 1.0)
    return PredictionSignal(
        source=source,
        category=category,
        direction=_direction(score),
        score=score,
        confidence=confidence,
        horizon=horizon,
        label=label,
        raw=raw or {},
    )


def _failed(source: str, category: str, horizon: str, error: str) -> PredictionSignal:
    return PredictionSignal(
        source=source,
        category=category,
        direction="neutral",
        score=0.0,
        confidence=0.0,
        horizon=horizon,
        label="数据不可用",
        error=error,
    )


def fetch_fear_greed() -> PredictionSignal:
    """Alternative.me 恐惧贪婪指数 — 情绪/逆向指标。"""
    try:
        data = get_json("https://api.alternative.me/fng/", params={"limit": 1})
        row = (data.get("data") or [{}])[0]
        value = float(row.get("value", 50))
        classification = str(row.get("value_classification", ""))
        score = (value - 50) / 50
        if value <= 24:
            conf = 0.75
            note = f"极度恐惧({value})，情绪偏空"
        elif value >= 75:
            conf = 0.75
            note = f"极度贪婪({value})，情绪偏多"
        else:
            conf = 0.45 + abs(value - 50) / 100
            note = f"{classification}({value})"
        return _signal(
            source="alternative.me",
            category="sentiment",
            score=score,
            confidence=conf,
            horizon="1d-7d",
            label=note,
            raw={
                "value": value,
                "classification": classification,
                "contrarian_hint": "极度恐惧常被视为逆向买入区" if value <= 24 else (
                    "极度贪婪常被视为逆向卖出区" if value >= 75 else None
                ),
            },
        )
    except Exception as exc:
        return _failed("alternative.me", "sentiment", "1d-7d", str(exc))


def fetch_binance_top_trader_ls() -> PredictionSignal:
    """Binance 大户账户多空比 — 顶级 20% 保证金用户。"""
    try:
        rows = get_json(
            "https://fapi.binance.com/futures/data/topLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
        )
        row = rows[0]
        ratio = float(row["longShortRatio"])
        long_pct = float(row["longAccount"])
        score = _clamp((ratio - 1.0) * 0.8)
        conf = 0.55 + min(0.25, abs(long_pct - 0.5))
        return _signal(
            source="binance_top_trader",
            category="positioning",
            score=score,
            confidence=conf,
            horizon="1h-4h",
            label=f"大户多空比 {ratio:.2f}（多 {long_pct:.0%}）",
            raw=row,
        )
    except Exception as exc:
        return _failed("binance_top_trader", "positioning", "1h-4h", str(exc))


def fetch_binance_global_ls() -> PredictionSignal:
    """Binance 全市场账户多空比。"""
    try:
        rows = get_json(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
        )
        row = rows[0]
        ratio = float(row["longShortRatio"])
        long_pct = float(row["longAccount"])
        score = _clamp((ratio - 1.0) * 0.7)
        conf = 0.5 + min(0.2, abs(long_pct - 0.5))
        return _signal(
            source="binance_global",
            category="positioning",
            score=score,
            confidence=conf,
            horizon="1h-4h",
            label=f"全市场多空比 {ratio:.2f}（多 {long_pct:.0%}）",
            raw=row,
        )
    except Exception as exc:
        return _failed("binance_global", "positioning", "1h-4h", str(exc))


def fetch_binance_taker_flow() -> PredictionSignal:
    """Binance 主动买卖量比 — 短周期资金流向。"""
    try:
        rows = get_json(
            "https://fapi.binance.com/futures/data/takerlongshortRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
        )
        row = rows[0]
        ratio = float(row["buySellRatio"])
        buy_vol = float(row.get("buyVol", 0))
        sell_vol = float(row.get("sellVol", 0))
        score = _clamp((ratio - 1.0) * 1.2)
        total = buy_vol + sell_vol
        conf = 0.5 + min(0.3, total / 10000) if total else 0.45
        return _signal(
            source="binance_taker",
            category="flow",
            score=score,
            confidence=conf,
            horizon="1h",
            label=f"主动买卖比 {ratio:.2f}",
            raw=row,
        )
    except Exception as exc:
        return _failed("binance_taker", "flow", "1h", str(exc))


def fetch_binance_funding() -> PredictionSignal:
    """Binance 永续资金费率 — 杠杆方向与拥挤度。"""
    try:
        row = get_json(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            params={"symbol": "BTCUSDT"},
        )
        rate = float(row["lastFundingRate"])
        mark = float(row.get("markPrice", 0))
        # 正费率：多头拥挤；负费率：空头拥挤
        score = _clamp(rate * 8000)
        conf = 0.45 + min(0.35, abs(rate) * 12000)
        pct = rate * 100
        return _signal(
            source="binance_funding",
            category="derivatives",
            score=score,
            confidence=conf,
            horizon="8h",
            label=f"资金费率 {pct:.4f}%",
            raw={"lastFundingRate": rate, "markPrice": mark},
        )
    except Exception as exc:
        return _failed("binance_funding", "derivatives", "8h", str(exc))


def fetch_okx_ls_ratio() -> PredictionSignal:
    """OKX 合约账户多空比。"""
    try:
        data = get_json(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC", "period": "1H"},
            headers={"User-Agent": "RegimeTrend/1.0"},
        )
        if str(data.get("code")) != "0":
            raise RuntimeError(data.get("msg", "okx error"))
        rows = data.get("data") or []
        if not rows:
            raise RuntimeError("empty okx ls data")
        ts, ratio_s = rows[0]
        ratio = float(ratio_s)
        score = _clamp((ratio - 1.0) * 0.75)
        conf = 0.5 + min(0.25, abs(ratio - 1.0) * 0.5)
        return _signal(
            source="okx_account_ratio",
            category="positioning",
            score=score,
            confidence=conf,
            horizon="1h-4h",
            label=f"OKX 多空比 {ratio:.2f}",
            raw={"timestamp": ts, "ratio": ratio},
        )
    except Exception as exc:
        return _failed("okx_account_ratio", "positioning", "1h-4h", str(exc))


def _parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return []


def fetch_polymarket_15m() -> PredictionSignal:
    """Polymarket 15 分钟 BTC Up/Down 预测市场隐含概率。"""
    try:
        window = (int(time.time()) // 900) * 900
        slug = f"btc-updown-15m-{window}"
        ev = get_json(f"https://gamma-api.polymarket.com/events/slug/{slug}")
        markets = ev.get("markets") or []
        if not markets:
            raise RuntimeError("no polymarket market")
        m = markets[0]
        outcomes = _parse_json_list(m.get("outcomes"))
        prices = _parse_json_list(m.get("outcomePrices"))
        up_prob = down_prob = 0.5
        for name, price in zip(outcomes, prices, strict=False):
            p = float(price)
            if str(name).lower() == "up":
                up_prob = p
            elif str(name).lower() == "down":
                down_prob = p
        score = _clamp((up_prob - down_prob) * 1.5)
        conf = 0.4 + abs(up_prob - 0.5) * 0.8
        return _signal(
            source="polymarket_15m",
            category="prediction_market",
            score=score,
            confidence=conf,
            horizon="15m",
            label=f"15m Up {up_prob:.0%} / Down {down_prob:.0%}",
            raw={"slug": slug, "title": ev.get("title"), "up_prob": up_prob, "down_prob": down_prob},
        )
    except Exception as exc:
        return _failed("polymarket_15m", "prediction_market", "15m", str(exc))


def fetch_coinglass_funding(api_key: str) -> PredictionSignal | None:
    """CoinGlass 跨所资金费率（需 API Key）。"""
    if not api_key:
        return None
    try:
        data = get_json(
            "https://open-api-v4.coinglass.com/api/futures/funding-rate/exchange-list",
            params={"symbol": "BTC"},
            headers={"CG-API-KEY": api_key},
        )
        if str(data.get("code")) not in ("0", "200", "success"):
            raise RuntimeError(data.get("msg", "coinglass error"))
        items = (data.get("data") or [])[:8]
        rates: list[float] = []
        for item in items:
            if item.get("rate") is not None:
                rates.append(float(item["rate"]))
            elif item.get("fundingRate") is not None:
                rates.append(float(item["fundingRate"]))
        if not rates:
            raise RuntimeError("no funding rates")
        avg = sum(rates) / len(rates)
        score = _clamp(avg * 6000)
        conf = 0.55 + min(0.3, abs(avg) * 8000)
        return _signal(
            source="coinglass_funding",
            category="derivatives",
            score=score,
            confidence=conf,
            horizon="8h",
            label=f"跨所平均资金费率 {avg * 100:.4f}%",
            raw={"avg_rate": avg, "exchanges": len(rates)},
        )
    except Exception as exc:
        return _failed("coinglass_funding", "derivatives", "8h", str(exc))


DEFAULT_FETCHERS: list[tuple[str, SourceFetcher]] = [
    ("alternative.me", fetch_fear_greed),
    ("binance_top_trader", fetch_binance_top_trader_ls),
    ("binance_global", fetch_binance_global_ls),
    ("binance_taker", fetch_binance_taker_flow),
    ("binance_funding", fetch_binance_funding),
    ("okx_account_ratio", fetch_okx_ls_ratio),
    ("polymarket_15m", fetch_polymarket_15m),
]
