"""L1 微观市场结构与杠杆特征。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.derivatives_trend import analyze_derivatives_trend
from ai_trade_advisor.datasource.orderbook import fetch_orderbook
from ai_trade_advisor.datasource.spot_cvd import analyze_spot_cvd
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState, build_liquidation_map


def build_microstructure_features(
    cfg: AdvisorConfig,
    df: pd.DataFrame,
    *,
    price: float,
    skip_orderbook: bool = False,
) -> tuple[dict[str, Any], LiquidationGridState, Any]:
    """OI、资金费率、强平流、Spot CVD、订单簿。"""
    cvd = analyze_spot_cvd(cfg, price)
    deriv = analyze_derivatives_trend(cfg, df, cvd=cvd)
    liquidation = build_liquidation_map(
        price,
        cfg,
        half_life_hours=cfg.liquidation_half_life_hours,
    )
    ob = None if skip_orderbook else fetch_orderbook(cfg)

    liq_pulse = _liquidation_pulse(liquidation, price)

    return {
        "spot_cvd": cvd.get("spot_cvd"),
        "spot_cvd_breakout": bool(cvd.get("spot_cvd_breakout")),
        "cvd_bullish_divergence": bool(cvd.get("cvd_bullish_divergence")),
        "cvd_trend": cvd.get("cvd_trend"),
        "funding_rate": deriv.get("funding_rate"),
        "funding_bias": deriv.get("funding_bias"),
        "open_interest": deriv.get("open_interest"),
        "oi_change_pct": deriv.get("oi_change_pct"),
        "oi_price_sync": deriv.get("oi_price_sync"),
        "liquidation_pulse": liq_pulse,
        "orderbook_imbalance": ob.imbalance if ob else None,
        "derivatives": deriv,
        "cvd": cvd,
    }, liquidation, ob


def _liquidation_pulse(liquidation: LiquidationGridState, price: float) -> dict[str, Any]:
    """秒级强平爆仓脉冲检测（硬规则触发输入）。"""
    cells = liquidation.cells or []
    near = [c for c in cells if abs(float(c.get("price", 0)) - price) / max(price, 1) < 0.02]
    total_notional = sum(abs(float(c.get("weight_usd", 0) or 0)) for c in near)
    extreme = total_notional > 5_000_000 or liquidation.total_weight > 10_000_000
    return {
        "near_clusters": len(near),
        "near_notional_usd": round(total_notional, 0),
        "total_weight": liquidation.total_weight,
        "extreme_pulse": extreme,
    }
