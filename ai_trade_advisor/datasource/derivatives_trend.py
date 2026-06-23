from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange

TrendBias = Literal["bullish", "bearish", "neutral"]
OiSync = Literal["long_build", "short_build", "unwind", "neutral"]


def cvd_trend_bias(cvd: pd.Series, *, lookback: int = 14) -> tuple[TrendBias, float | None]:
    """CVD 斜率趋势：近 lookback 根累计增量方向。"""
    if len(cvd) < lookback + 1:
        return "neutral", None
    window = cvd.iloc[-(lookback + 1) :]
    slope = float(window.iloc[-1] - window.iloc[0]) / lookback
    if slope > 0:
        return "bullish", slope
    if slope < 0:
        return "bearish", slope
    return "neutral", slope


def _funding_bias(current: float, history: list[float]) -> tuple[TrendBias, str]:
    """资金费率趋势：正费率多头付费；结合近期变化判断拥挤方向。"""
    pct = current * 100
    rising = len(history) >= 3 and history[-1] > history[-3]
    falling = len(history) >= 3 and history[-1] < history[-3]

    if current > 0.0008:
        note = f"资金费率 {pct:.4f}% 极端正 → 多头拥挤"
        return "bearish", note
    if current < -0.0003:
        note = f"资金费率 {pct:.4f}% 负 → 空头付费/空头拥挤"
        return "bearish", note
    if current > 0.00005:
        note = f"资金费率 {pct:.4f}% 正"
        if rising:
            note += " 且上升 → 多头动能"
            return "bullish", note
        return "bullish", note + " → 多头占优"
    if current < -0.00005:
        note = f"资金费率 {pct:.4f}% 负"
        if falling:
            note += " 且走低 → 空头动能"
            return "bearish", note
        return "bearish", note
    return "neutral", f"资金费率 {pct:.4f}% 中性"


def _oi_sync(price_change_pct: float, oi_change_pct: float) -> tuple[TrendBias, OiSync, str]:
    """OI + 价格联动：增仓上行/增仓下行/减仓。"""
    if abs(oi_change_pct) < 1.0:
        return "neutral", "neutral", f"OI 变化 {oi_change_pct:+.1f}% 平淡"

    if oi_change_pct > 0:
        if price_change_pct > 0.5:
            return "bullish", "long_build", (
                f"OI +{oi_change_pct:.1f}% + 价格 +{price_change_pct:.1f}% → 多头增仓"
            )
        if price_change_pct < -0.5:
            return "bearish", "short_build", (
                f"OI +{oi_change_pct:.1f}% + 价格 {price_change_pct:.1f}% → 空头增仓"
            )
        return "neutral", "neutral", f"OI +{oi_change_pct:.1f}% 但价格横盘"

    sync: OiSync = "unwind"
    if price_change_pct > 0.5:
        note = f"OI {oi_change_pct:.1f}% + 价格 +{price_change_pct:.1f}% → 空头平仓反弹"
        return "bullish", sync, note
    if price_change_pct < -0.5:
        note = f"OI {oi_change_pct:.1f}% + 价格 {price_change_pct:.1f}% → 多头止损离场"
        return "bearish", sync, note
    return "neutral", sync, f"OI {oi_change_pct:.1f}% 减仓，趋势减弱"


def _fetch_funding(cfg: AdvisorConfig) -> tuple[float | None, list[float]]:
    try:
        exchange = make_exchange(
            cfg.exchange,
            market_type="swap",
            binance=cfg.binance_futures(),
        )
        exchange.load_markets()
        current = exchange.fetch_funding_rate(cfg.symbol)
        rate = float((current or {}).get("fundingRate") or 0)
        history_rows: list[dict[str, Any]] = []
        if exchange.has.get("fetchFundingRateHistory"):
            history_rows = exchange.fetch_funding_rate_history(cfg.symbol, limit=12) or []
        rates = [float(r.get("fundingRate") or 0) for r in history_rows if r.get("fundingRate") is not None]
        if not rates:
            rates = [rate]
        return rate, rates
    except Exception:
        return None, []


def _fetch_oi_history(cfg: AdvisorConfig) -> list[dict[str, Any]]:
    try:
        exchange = make_exchange(
            cfg.exchange,
            market_type="swap",
            binance=cfg.binance_futures(),
        )
        exchange.load_markets()
        if not exchange.has.get("fetchOpenInterestHistory"):
            return []
        return exchange.fetch_open_interest_history(cfg.symbol, timeframe="1h", limit=48) or []
    except Exception:
        return []


def _oi_values(rows: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        val = row.get("openInterestAmount") or row.get("openInterestValue") or row.get("openInterest")
        if val is not None:
            out.append(float(val))
    return out


def analyze_derivatives_trend(
    cfg: AdvisorConfig,
    df: pd.DataFrame,
    *,
    cvd: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    衍生品趋势三要素：Funding + OI + CVD。
    返回各维度 bias 及综合投票，供 Regime 趋势融合。
    """
    out: dict[str, Any] = {
        "funding_rate": None,
        "funding_bias": "neutral",
        "open_interest": None,
        "oi_change_pct": None,
        "oi_price_sync": "neutral",
        "oi_bias": "neutral",
        "cvd_trend": "neutral",
        "cvd_slope": None,
        "derivative_votes_bull": 0,
        "derivative_votes_bear": 0,
        "drivers": [],
        "source": cfg.exchange,
    }

    fund_rate, fund_hist = _fetch_funding(cfg)
    if fund_rate is not None:
        out["funding_rate"] = fund_rate
        bias, note = _funding_bias(fund_rate, fund_hist)
        out["funding_bias"] = bias
        out["drivers"].append(note)

    oi_rows = _fetch_oi_history(cfg)
    oi_vals = _oi_values(oi_rows)
    if oi_vals:
        out["open_interest"] = oi_vals[-1]
        lookback = min(24, len(oi_vals) - 1)
        if lookback > 0 and oi_vals[-lookback - 1] > 0:
            oi_chg = (oi_vals[-1] - oi_vals[-lookback - 1]) / oi_vals[-lookback - 1] * 100
            out["oi_change_pct"] = round(oi_chg, 2)

            closes = df["close"].astype(float)
            price_lookback = min(lookback * 2, len(closes) - 1)
            price_chg = 0.0
            if price_lookback > 0 and closes.iloc[-price_lookback - 1] > 0:
                price_chg = (float(closes.iloc[-1]) - float(closes.iloc[-price_lookback - 1])) / float(
                    closes.iloc[-price_lookback - 1]
                ) * 100

            oi_bias, sync, note = _oi_sync(price_chg, oi_chg)
            out["oi_bias"] = oi_bias
            out["oi_price_sync"] = sync
            out["drivers"].append(note)

    if cvd and not cvd.get("unavailable"):
        trend = cvd.get("cvd_trend")
        slope = cvd.get("cvd_slope")
        if trend:
            out["cvd_trend"] = trend
            out["cvd_slope"] = slope
            if trend == "bullish":
                out["drivers"].append("CVD 斜率向上 → 主动买盘")
            elif trend == "bearish":
                out["drivers"].append("CVD 斜率向下 → 主动卖盘")
        elif cvd.get("spot_cvd_breakout"):
            out["cvd_trend"] = "bullish"
            out["drivers"].append("现货 CVD 突破 → 买盘确认")
        elif cvd.get("cvd_bullish_divergence"):
            out["cvd_trend"] = "bullish"
            out["drivers"].append("5m CVD 底背离 → 买盘潜伏")

    for key in ("funding_bias", "oi_bias", "cvd_trend"):
        bias = out.get(key)
        if bias == "bullish":
            out["derivative_votes_bull"] += 1
        elif bias == "bearish":
            out["derivative_votes_bear"] += 1

    return out


def resolve_trend_with_derivatives(
    tech_trend: str,
    deriv: dict[str, Any],
    drivers: list[str],
) -> str:
    """
    技术面趋势 + 衍生品三票融合。
    - 技术趋势与 ≥2 票衍生品背离 → 降级为 range
    - 技术 range + ≥2 票同向 → 升级为对应趋势
    """
    bull = int(deriv.get("derivative_votes_bull") or 0)
    bear = int(deriv.get("derivative_votes_bear") or 0)

    if tech_trend == "uptrend":
        if bear >= 2:
            drivers.append("技术面多头但 Funding/OI/CVD 两项看空 → 趋势降级为区间")
            return "range"
        if bull >= 2:
            drivers.append("技术面多头 + 衍生品共振确认")
        return "uptrend"

    if tech_trend == "downtrend":
        if bull >= 2:
            drivers.append("技术面空头但 Funding/OI/CVD 两项看多 → 趋势降级为区间")
            return "range"
        if bear >= 2:
            drivers.append("技术面空头 + 衍生品共振确认")
        return "downtrend"

    if bull >= 2:
        drivers.append("区间震荡 + Funding/OI/CVD 多头共振 → 上行倾向")
        return "uptrend"
    if bear >= 2:
        drivers.append("区间震荡 + Funding/OI/CVD 空头共振 → 下行倾向")
        return "downtrend"
    return "range"
