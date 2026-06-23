"""L1 市场价格与技术特征。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import ohlcv_summary
from ai_trade_advisor.datasource.ticker import fetch_live_ticker
from ai_trade_advisor.features.indicators import donchian_14d, kama_rails
from ai_trade_advisor.features.liquidity_map import detect_liquidity_sweeps
from ai_trade_advisor.features.smc import build_smc_snapshot


def build_market_features(
    cfg: AdvisorConfig,
    df: pd.DataFrame,
    *,
    candle_price: float | None = None,
) -> dict[str, Any]:
    """K 线、KAMA、唐奇安通道、SMC 结构。"""
    close = candle_price if candle_price is not None else float(df.iloc[-1]["close"])
    ticker = fetch_live_ticker(cfg)
    kama, k_upper, k_lower = kama_rails(df)
    d_upper, d_lower = donchian_14d(df)
    smc = build_smc_snapshot(df, close)
    liquidity = detect_liquidity_sweeps(df)
    summary = ohlcv_summary(df)
    summary["candle_close"] = close
    summary["change_pct_24h"] = ticker.change_pct_24h

    return {
        "close": close,
        "ticker": {
            "last": ticker.last,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "change_pct_24h": ticker.change_pct_24h,
            "source": ticker.source,
        },
        "kama": kama,
        "kama_upper": k_upper,
        "kama_lower": k_lower,
        "donchian_upper": d_upper,
        "donchian_lower": d_lower,
        "smc_trend": smc.trend,
        "liquidity_sweeps": len(liquidity),
        "ohlcv_summary": summary,
    }
