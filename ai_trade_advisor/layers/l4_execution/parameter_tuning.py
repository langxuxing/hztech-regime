"""L4 参数动态自适应：按 Regime 微调策略内部参数。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.layers.types import CombinedRegimeStatus


def tune_parameters(regime: CombinedRegimeStatus) -> dict[str, Any]:
    """低波挤压调低突破阈值；高波拉宽止损、减半仓位。"""
    rid = regime.confirmed_regime_id
    base: dict[str, Any] = {
        "position_scale": 1.0,
        "stop_loss_multiplier": 1.0,
        "breakout_threshold_scale": 1.0,
        "grid_enabled": True,
        "cta_enabled": True,
        "notes": [],
    }

    if rid in ("low_vol_range", "mid_vol_range"):
        base["breakout_threshold_scale"] = 0.85
        base["grid_enabled"] = True
        base["cta_enabled"] = False
        base["notes"].append("低波挤压：突破阈值降低 15%，优先网格")

    elif rid in ("high_vol_uptrend", "high_vol_downtrend", "high_vol_range"):
        base["position_scale"] = 0.5
        base["stop_loss_multiplier"] = 1.5
        base["grid_enabled"] = False
        base["cta_enabled"] = True
        base["notes"].append("高波状态：仓位减半，止损拉宽 50%，关闭网格")

    elif rid == "fake_breakout_wash":
        base["position_scale"] = 0.33
        base["cta_enabled"] = False
        base["notes"].append("假突破：仓位降至 1/3，暂停趋势追单")

    elif rid == "macro_frozen_range":
        base["position_scale"] = 0.0
        base["grid_enabled"] = False
        base["cta_enabled"] = False
        base["notes"].append("宏观熔断：全策略挂起")

    elif rid.endswith("_uptrend"):
        base["cta_enabled"] = True
        base["grid_enabled"] = False
        base["notes"].append("趋势上行：开启 CTA，关闭网格")

    elif rid.endswith("_downtrend"):
        base["cta_enabled"] = True
        base["position_scale"] = 0.67
        base["notes"].append("趋势下行：CTA 做空偏好，仓位 2/3")

    return base
