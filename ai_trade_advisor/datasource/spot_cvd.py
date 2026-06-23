from __future__ import annotations

from typing import Any

import ccxt
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.taker_cvd import (
    build_taker_cvd_series,
    fetch_binance_taker_history,
    fetch_taker_klines,
)
from ai_trade_advisor.datasource.derivatives_trend import cvd_trend_bias
from ai_trade_advisor.features.indicators import bar_volume_delta


def _spot_symbol(perp_symbol: str) -> str:
    base = perp_symbol.split("/")[0]
    return f"{base}/USDT"


def fetch_spot_ohlcv(
    cfg: AdvisorConfig,
    *,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    ex_cls = getattr(ccxt, cfg.exchange)
    exchange = ex_cls({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    exchange.load_markets()
    symbol = _spot_symbol(cfg.symbol)
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.assign(datetime=pd.to_datetime(df["timestamp"], unit="ms", utc=True))
    return df.sort_values("timestamp").reset_index(drop=True)


def build_spot_cvd_series(df: pd.DataFrame) -> pd.Series:
    if "cvd_delta" in df.columns:
        return build_taker_cvd_series(df)
    return bar_volume_delta(df).cumsum()


def spot_cvd_breakout(cvd: pd.Series, *, lookback: int = 14) -> bool:
    if len(cvd) < lookback + 1:
        return False
    current = float(cvd.iloc[-1])
    prior_max = float(cvd.iloc[-(lookback + 1) : -1].max())
    return current > prior_max


def spot_premium_bps(cfg: AdvisorConfig, perp_price: float) -> float | None:
    try:
        spot_df = fetch_spot_ohlcv(cfg, timeframe="1m", limit=2)
        spot = float(spot_df.iloc[-1]["close"])
        if spot <= 0:
            return None
        return (perp_price - spot) / spot * 10000
    except Exception:
        return None


def analyze_spot_cvd(cfg: AdvisorConfig, perp_price: float) -> dict[str, Any]:
    if cfg.use_taker_cvd:
        try:
            return _analyze_taker_cvd(cfg, perp_price)
        except Exception:
            pass
    return _unavailable_cvd(cfg)


def _unavailable_cvd(cfg: AdvisorConfig) -> dict[str, Any]:
    """Taker CVD 不可用时返回空信号，不使用 OHLCV 代理估算。"""
    return {
        "spot_cvd": None,
        "spot_cvd_breakout": False,
        "cvd_bullish_divergence": False,
        "cvd_trend": "neutral",
        "cvd_slope": None,
        "spot_premium_bps": None,
        "spot_premium_positive": False,
        "source": "unavailable",
        "unavailable": True,
        "note": "Binance taker CVD 拉取失败；已禁用 ohlcv_proxy 低质量兜底",
    }


def _attach_cvd_trend(out: dict[str, Any], cvd_30m: pd.Series) -> None:
    trend, slope = cvd_trend_bias(cvd_30m, lookback=14)
    out["cvd_trend"] = trend
    out["cvd_slope"] = slope


def analyze_spot_cvd_from_frames(
    *,
    df_30m: pd.DataFrame,
    df_5m: pd.DataFrame,
    perp_price: float,
    source: str,
) -> dict[str, Any]:
    cvd_30m = build_spot_cvd_series(df_30m)
    out: dict[str, Any] = {
        "spot_cvd": float(cvd_30m.iloc[-1]) if len(cvd_30m) else None,
        "spot_cvd_breakout": spot_cvd_breakout(cvd_30m, lookback=14) if len(cvd_30m) >= 15 else False,
        "cvd_bullish_divergence": _micro_cvd_v_bottom(df_5m),
        "spot_premium_bps": None,
        "spot_premium_positive": False,
        "source": source,
    }
    if len(cvd_30m) >= 15:
        _attach_cvd_trend(out, cvd_30m)
    if len(df_30m):
        spot = float(df_30m.iloc[-1]["close"])
        if spot > 0:
            out["spot_premium_bps"] = (perp_price - spot) / spot * 10000
            out["spot_premium_positive"] = out["spot_premium_bps"] > 0
    if out["cvd_bullish_divergence"] and out["spot_premium_positive"]:
        out["divergence_confirmed"] = True
    return out


def load_taker_history_for_backtest(
    cfg: AdvisorConfig,
    *,
    bars_30m: int,
    bars_5m: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spot = _spot_symbol(cfg.symbol)
    return (
        fetch_binance_taker_history(spot, timeframe="30m", bars=bars_30m),
        fetch_binance_taker_history(spot, timeframe="5m", bars=bars_5m),
    )


def _analyze_taker_cvd(cfg: AdvisorConfig, perp_price: float) -> dict[str, Any]:
    df_30m, src_30 = fetch_taker_klines(cfg, timeframe="30m", limit=120)
    df_5m, _src_5 = fetch_taker_klines(cfg, timeframe="5m", limit=120)
    cvd_30m = build_taker_cvd_series(df_30m)
    out: dict[str, Any] = {
        "spot_cvd": float(cvd_30m.iloc[-1]),
        "spot_cvd_breakout": spot_cvd_breakout(cvd_30m, lookback=14),
        "cvd_bullish_divergence": _micro_cvd_v_bottom(df_5m),
        "spot_premium_bps": None,
        "spot_premium_positive": False,
        "source": src_30,
        "taker_buy_last_30m": float(df_30m.iloc[-1]["taker_buy_volume"]) if len(df_30m) else None,
        "taker_sell_last_30m": float(df_30m.iloc[-1]["taker_sell_volume"]) if len(df_30m) else None,
    }
    _attach_cvd_trend(out, cvd_30m)
    prem = spot_premium_bps(cfg, perp_price)
    out["spot_premium_bps"] = prem
    out["spot_premium_positive"] = prem is not None and prem > 0
    if out["cvd_bullish_divergence"] and out["spot_premium_positive"]:
        out["divergence_confirmed"] = True
    return out


def _micro_cvd_v_bottom(df: pd.DataFrame, lookback: int = 48) -> bool:
    sub = df.tail(lookback).reset_index(drop=True)
    if len(sub) < 20:
        return False
    cvd = build_spot_cvd_series(sub)
    price = sub["low"].astype(float)
    mid = len(sub) // 2
    p1, p2 = float(price.iloc[:mid].min()), float(price.iloc[mid:].min())
    c1, c2 = float(cvd.iloc[:mid].min()), float(cvd.iloc[mid:].min())
    return p2 < p1 * 0.998 and c2 > c1
