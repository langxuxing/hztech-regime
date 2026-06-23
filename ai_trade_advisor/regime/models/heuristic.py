from __future__ import annotations

from typing import Any

from ai_trade_advisor.regime.models.base import (
    MODEL_CATALOG,
    RegimeModelResult,
    trend_to_dashboard,
)


def run_heuristic_model(rule: dict[str, Any]) -> RegimeModelResult:
    raw_trend = rule.get("raw_trend") or "range"
    vol_bucket = rule.get("vol_bucket") or "mid_vol"
    regime_id = rule.get("regime_id")
    label = rule.get("regime_label") or regime_id or "未知"
    dashboard = rule.get("dashboard_regime") or trend_to_dashboard(raw_trend, vol_bucket)
    conf = float(rule.get("confidence") or 0.6)

    drivers = [
        "KAMA + 唐奇安通道趋势判定",
        f"波动桶: {vol_bucket}",
        f"融合趋势: {raw_trend}",
    ]
    if rule.get("spot_cvd_breakout"):
        drivers.append("现货 CVD 突破确认")
    if rule.get("cvd_bullish_divergence"):
        drivers.append("CVD 底背离")

    return RegimeModelResult(
        model_id="heuristic",
        model_name=MODEL_CATALOG["heuristic"],
        regime_label=str(label),
        regime_id=regime_id,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        dashboard_regime=dashboard,
        confidence=conf,
        drivers=drivers,
        metadata={"source": "kama_donchian_cvd"},
    )
