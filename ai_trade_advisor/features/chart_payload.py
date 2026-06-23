"""K 线序列与叠加层，供前端图表渲染。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ai_trade_advisor.features.indicators import donchian_14d, kama_rails
from ai_trade_advisor.models import MarketContext


def build_chart_payload(
    df: pd.DataFrame,
    market: dict[str, Any],
    ctx: MarketContext,
    *,
    max_bars: int = 120,
) -> dict[str, Any]:
    """构建 OHLCV bars + KAMA/唐奇安/流动性/GEX 水平线。"""
    if df is None or len(df) < 2:
        return {"bars": [], "overlays": [], "timeframe": ctx.timeframe}

    sub = df.tail(max_bars).reset_index(drop=True)
    kama_series, k_upper_series, k_lower_series = _kama_series(sub)
    bars: list[dict[str, Any]] = []

    for i, row in sub.iterrows():
        ts = row.get("datetime")
        iso = ts.isoformat() if hasattr(ts, "isoformat") else str(row.get("timestamp", ""))
        bars.append(
            {
                "t": iso,
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(float(row["close"]), 4),
                "v": round(float(row.get("volume", 0) or 0), 2),
                "kama": round(float(kama_series.iloc[i]), 4) if i < len(kama_series) else None,
            }
        )

    kama, k_up, k_lo = kama_rails(sub)
    d_up, d_lo = donchian_14d(sub)
    price = ctx.last_price

    overlays: list[dict[str, Any]] = [
        {"kind": "kama", "price": kama, "label": "KAMA", "color": "accent"},
        {"kind": "kama_upper", "price": k_up, "label": "KAMA上", "color": "long"},
        {"kind": "kama_lower", "price": k_lo, "label": "KAMA下", "color": "short"},
        {"kind": "donchian_upper", "price": d_up, "label": "唐奇安上", "color": "neutral"},
        {"kind": "donchian_lower", "price": d_lo, "label": "唐奇安下", "color": "neutral"},
    ]

    for lv in ctx.liquidity_levels[:8]:
        overlays.append(
            {
                "kind": "liquidity",
                "price": lv.price,
                "label": f"流动性 {lv.side}",
                "color": "long" if lv.side == "buy_side" else "short",
                "swept": lv.swept,
                "strength": lv.strength,
            }
        )

    for g in ctx.gex_levels[:6]:
        overlays.append(
            {
                "kind": "gex",
                "price": g.price,
                "label": f"GEX {g.level_type}",
                "color": _gex_color(g.level_type),
                "notional": g.gex_notional_proxy,
            }
        )

    if ctx.smc.nearest_ob:
        z = ctx.smc.nearest_ob
        overlays.append(
            {"kind": "ob", "price_low": z.low, "price_high": z.high, "label": "OB", "color": "accent"}
        )
    if ctx.smc.nearest_fvg:
        z = ctx.smc.nearest_fvg
        overlays.append(
            {"kind": "fvg", "price_low": z.low, "price_high": z.high, "label": "FVG", "color": "magnet"}
        )

    return {
        "timeframe": ctx.timeframe,
        "bars": bars,
        "overlays": overlays,
        "last_price": price,
        "smc_trend": ctx.smc.trend,
        "change_pct_24h": market.get("ticker", {}).get("change_pct_24h"),
    }


def _kama_series(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """逐 bar KAMA（简化：复用 rails 末值作为水平线时，序列用滚动 close EMA 代理）。"""
    close = df["close"].astype(float)
    kama = close.ewm(span=10, adjust=False).mean()
    atr = (df["high"] - df["low"]).astype(float).rolling(14, min_periods=1).mean()
    return kama, kama + atr, kama - atr


def _gex_color(level_type: str) -> str:
    return {"support": "long", "resistance": "short"}.get(level_type, "magnet")
