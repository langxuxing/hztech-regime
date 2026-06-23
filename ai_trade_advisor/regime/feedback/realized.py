from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.features.indicators import compute_atr


def compute_realized_regime(
    df: pd.DataFrame,
    bar_idx: int,
    *,
    forward_bars: int = 6,
    adx_threshold: float = 28.0,
) -> dict[str, Any] | None:
    """N 根 K 线后从价格推导 realized regime。"""
    if bar_idx < 0 or bar_idx + forward_bars >= len(df):
        return None

    close = df["close"].astype(float)
    c0 = float(close.iloc[bar_idx])
    c1 = float(close.iloc[bar_idx + forward_bars])
    if c0 <= 0:
        return None

    forward_return = float(np.log(c1 / c0))
    sub0 = df.iloc[: bar_idx + 1]
    sub1 = df.iloc[: bar_idx + forward_bars + 1]
    atr0 = float(compute_atr(sub0, period=14).iloc[-1])
    atr1 = float(compute_atr(sub1, period=14).iloc[-1])
    forward_vol_ratio = atr1 / (atr0 + 1e-8) if atr0 > 0 else 1.0

    high_vol = forward_vol_ratio >= 1.25 or abs(forward_return) >= 0.015

    if forward_return > 0.004:
        realized_trend = "uptrend"
        realized_dashboard = "trend_up" if not high_vol else "high_vol"
    elif forward_return < -0.004:
        realized_trend = "downtrend"
        realized_dashboard = "trend_down" if not high_vol else "high_vol"
    else:
        realized_trend = "range"
        realized_dashboard = "high_vol" if high_vol else "range"

    return {
        "forward_bars": forward_bars,
        "forward_return": round(forward_return, 6),
        "forward_vol_ratio": round(forward_vol_ratio, 4),
        "realized_trend": realized_trend,
        "realized_dashboard": realized_dashboard,
        "realized_regime": realized_dashboard,
        "adx_threshold_ref": adx_threshold,
    }


def find_bar_index(df: pd.DataFrame, *, bar_close: float | None, recorded_at: str | None) -> int:
    """尽量定位标注对应 K 线索引。"""
    close = df["close"].astype(float)
    if bar_close is not None:
        diffs = (close - bar_close).abs()
        idx = int(diffs.values.argmin())
        if float(diffs.iloc[idx]) / max(bar_close, 1.0) < 0.002:
            return idx
    return len(df) - 1
