from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.models import LiquidityLevel


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    *,
    swing_window: int = 5,
    lookback: int = 80,
) -> list[LiquidityLevel]:
    """
    ICT 流动性清洗地图：识别 swing high/low 被刺破后收回的结构。
    - sell_side liquidity: swing high 上方被 sweep（诱多后回落）
    - buy_side liquidity: swing low 下方被 sweep（诱空后反弹）
    """
    if len(df) < swing_window * 2 + 5:
        return []

    sub = df.tail(lookback).reset_index(drop=True)
    levels: list[LiquidityLevel] = []
    highs = sub["high"].values
    lows = sub["low"].values
    closes = sub["close"].values
    times = sub["datetime"].astype(str).values if "datetime" in sub.columns else [""] * len(sub)

    for i in range(swing_window, len(sub) - swing_window):
        win_h = highs[i - swing_window : i + swing_window + 1]
        win_l = lows[i - swing_window : i + swing_window + 1]
        if highs[i] == win_h.max():
            swing_high = float(highs[i])
            for j in range(i + 1, min(i + 15, len(sub))):
                swept = highs[j] > swing_high and closes[j] < swing_high
                if swept:
                    levels.append(
                        LiquidityLevel(
                            price=swing_high,
                            side="sell_side",
                            swept=True,
                            sweep_time=str(times[j]),
                            strength=1.0 + (highs[j] - swing_high) / swing_high * 100,
                        )
                    )
                    break
        if lows[i] == win_l.min():
            swing_low = float(lows[i])
            for j in range(i + 1, min(i + 15, len(sub))):
                swept = lows[j] < swing_low and closes[j] > swing_low
                if swept:
                    levels.append(
                        LiquidityLevel(
                            price=swing_low,
                            side="buy_side",
                            swept=True,
                            sweep_time=str(times[j]),
                            strength=1.0 + (swing_low - lows[j]) / swing_low * 100,
                        )
                    )
                    break

    # 未清洗的 pending liquidity（最近 swing 高低点）
    pending = _pending_liquidity(sub, swing_window)
    levels.extend(pending)
    levels.sort(key=lambda x: x.price)
    return _dedupe_levels(levels)[-12:]


def _pending_liquidity(df: pd.DataFrame, swing_window: int) -> list[LiquidityLevel]:
    out: list[LiquidityLevel] = []
    sub = df.tail(40).reset_index(drop=True)
    highs = sub["high"].values
    lows = sub["low"].values
    for i in range(swing_window, len(sub) - swing_window):
        if highs[i] == highs[i - swing_window : i + swing_window + 1].max():
            out.append(LiquidityLevel(price=float(highs[i]), side="sell_side", swept=False))
        if lows[i] == lows[i - swing_window : i + swing_window + 1].min():
            out.append(LiquidityLevel(price=float(lows[i]), side="buy_side", swept=False))
    return out[-4:]


def _dedupe_levels(levels: list[LiquidityLevel]) -> list[LiquidityLevel]:
    seen: dict[tuple[str, int], LiquidityLevel] = {}
    for lv in levels:
        key = (lv.side, int(lv.price * 1e4))
        if key not in seen or lv.swept:
            seen[key] = lv
    return list(seen.values())
