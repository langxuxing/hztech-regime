from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange
from ai_trade_advisor.models import GexLevel


def build_gex_proxy(
    cfg: AdvisorConfig,
    df: pd.DataFrame,
) -> list[GexLevel]:
    """
    Crypto GEX 代理层。

    传统 GEX 来自期权 Gamma；永续合约无直接 GEX，此处组合：
    1. 交易所 Open Interest 变化 + 价格聚类 → 「磁吸/支撑/阻力」价位
    2. 高成交量节点 (volume profile proxy)
    3. Funding rate 极端时的 mean-reversion 磁吸位

    完整 GEX 可后续接入 Deribit options chain。
    """
    levels: list[GexLevel] = []
    price = float(df.iloc[-1]["close"])
    levels.extend(_volume_nodes(df, price))
    levels.extend(_fetch_oi_magnet_levels(cfg, price))
    return _merge_gex_levels(levels, price)[:8]


def _volume_nodes(df: pd.DataFrame, price: float) -> list[GexLevel]:
    sub = df.tail(60)
    if sub.empty:
        return []
    typical = (sub["high"] + sub["low"] + sub["close"]) / 3.0
    vol = sub["volume"].astype(float)
    bins = np.linspace(float(sub["low"].min()), float(sub["high"].max()), 12)
    if len(bins) < 3:
        return []
    idx = np.digitize(typical, bins)
    acc: dict[int, float] = {}
    for i, v in zip(idx, vol):
        acc[i] = acc.get(int(i), 0.0) + float(v)
    top_bins = sorted(acc.items(), key=lambda x: x[1], reverse=True)[:3]
    out: list[GexLevel] = []
    for bin_i, v in top_bins:
        lo = bins[max(bin_i - 1, 0)]
        hi = bins[min(bin_i, len(bins) - 1)]
        mid = (lo + hi) / 2.0
        level_type = "magnet" if abs(mid - price) / price < 0.01 else (
            "support" if mid < price else "resistance"
        )
        out.append(
            GexLevel(
                price=mid,
                gex_notional_proxy=float(v),
                level_type=level_type,
                source="volume_node",
            )
        )
    return out


def _fetch_oi_magnet_levels(cfg: AdvisorConfig, price: float) -> list[GexLevel]:
    try:
        exchange = make_exchange(
            cfg.exchange,
            market_type="swap",
            binance=cfg.binance_futures(),
        )
        exchange.load_markets()
        oi = exchange.fetch_open_interest(cfg.symbol)
        funding = exchange.fetch_funding_rate(cfg.symbol)
    except Exception:
        return []

    oi_val = float((oi or {}).get("openInterestAmount") or (oi or {}).get("openInterest") or 0)
    fund = float((funding or {}).get("fundingRate") or 0)
    if oi_val <= 0:
        return []

    # OI 磁吸：假设大量未平仓集中在 mark 附近 ± 小偏移
    mark = float((oi or {}).get("markPrice") or price)
    offsets = [-0.005, -0.002, 0.002, 0.005]
    out: list[GexLevel] = []
    for off in offsets:
        lvl = mark * (1 + off)
        if fund > 0.0003:
            t = "resistance" if off > 0 else "support"
        elif fund < -0.0003:
            t = "support" if off > 0 else "resistance"
        else:
            t = "magnet"
        out.append(
            GexLevel(
                price=lvl,
                gex_notional_proxy=oi_val * abs(off) * 100,
                level_type=t,
                source=f"oi_funding(f={fund:.6f})",
            )
        )
    return out


def _merge_gex_levels(levels: list[GexLevel], price: float) -> list[GexLevel]:
    if not levels:
        return []
    levels.sort(key=lambda x: x.price)
    merged: list[GexLevel] = []
    for lv in levels:
        if merged and abs(lv.price - merged[-1].price) / price < 0.003:
            merged[-1].gex_notional_proxy += lv.gex_notional_proxy
        else:
            merged.append(lv)
    merged.sort(key=lambda x: x.gex_notional_proxy, reverse=True)
    return merged
