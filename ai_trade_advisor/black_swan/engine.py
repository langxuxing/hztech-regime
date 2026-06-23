from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.models import CapitalFlowsSnapshot

AlertLevel = Literal[0, 1, 2, 3]

ALERT_LABELS: dict[int, str] = {
    0: "normal",
    1: "watch",
    2: "warn",
    3: "halt",
}

_LEVEL_ACTIONS: dict[int, dict[str, Any]] = {
    0: {
        "position_scale": 1.0,
        "allow_new_orders": True,
        "widen_stop_multiplier": 1.0,
        "confidence_multiplier": 1.0,
    },
    1: {
        "position_scale": 0.85,
        "allow_new_orders": True,
        "widen_stop_multiplier": 1.1,
        "confidence_multiplier": 0.7,
    },
    2: {
        "position_scale": 0.5,
        "allow_new_orders": False,
        "widen_stop_multiplier": 1.5,
        "confidence_multiplier": 0.5,
    },
    3: {
        "position_scale": 0.0,
        "allow_new_orders": False,
        "widen_stop_multiplier": 2.0,
        "confidence_multiplier": 0.2,
    },
}


@dataclass
class BlackSwanAlert:
    """分级预警输出，可直接序列化为实盘熔断 JSON。"""

    level: AlertLevel
    level_label: str
    suspended: bool
    triggers: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)
    circuit_breaker_active: bool = False
    suspend_reason: str | None = None
    strategies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "level_label": self.level_label,
            "suspended": self.suspended,
            "triggers": self.triggers,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "actions": self.actions,
            "circuit_breaker_active": self.circuit_breaker_active,
            "suspend_reason": self.suspend_reason,
            "strategies": self.strategies,
        }


def evaluate_black_swan_alert(
    *,
    macro: MacroHazardState | None = None,
    liquidation: LiquidationGridState | None = None,
    liquidation_pulse: dict[str, Any] | None = None,
    changepoint_prob: float | None = None,
    dvol_leads_gk: bool | None = None,
    vol_status: str | None = None,
    oi_change_pct: float | None = None,
    funding_bias: str | None = None,
    capital_flows: CapitalFlowsSnapshot | None = None,
    liq_pulse_threshold_usd: float = 5_000_000.0,
    liq_total_threshold_usd: float = 10_000_000.0,
    changepoint_warn_threshold: float = 0.7,
    upcoming_high_impact: int = 0,
    practical_signals: dict[str, Any] | None = None,
) -> BlackSwanAlert:
    """
    黑天鹅预警最小闭环：多源打分 → 分级 → 熔断动作。

    0=Normal  1=Watch  2=Warn  3=Halt
    """
    triggers: list[str] = []
    scores: dict[str, float] = {
        "macro_hazard": 0.0,
        "liq_pulse": 0.0,
        "changepoint": 0.0,
        "dvol_lead": 0.0,
        "etf_deriv_divergence": 0.0,
    }

    macro_hazard = bool(macro and macro.macro_hazard_flag)
    if macro_hazard:
        scores["macro_hazard"] = 1.0
        triggers.append("宏观公布窗口 ±120min → 硬熔断")
    elif upcoming_high_impact >= 1:
        scores["macro_hazard"] = min(0.6, 0.2 * upcoming_high_impact)
        triggers.append(f"高影响事件临近 ({upcoming_high_impact}) → 事件预警")

    pulse = liquidation_pulse or {}
    if not pulse and liquidation is not None:
        pulse = {
            "near_notional_usd": sum(
                abs(float(c.get("weight_usd", 0) or 0))
                for c in (liquidation.cells or [])
            ),
            "total_weight": liquidation.total_weight,
            "extreme_pulse": liquidation.total_weight > liq_total_threshold_usd,
        }

    near_notional = float(pulse.get("near_notional_usd") or 0)
    total_weight = float(pulse.get("total_weight") or 0)
    extreme_pulse = bool(pulse.get("extreme_pulse"))
    oi_shock = oi_change_pct is not None and oi_change_pct <= -3.0

    if near_notional >= liq_pulse_threshold_usd or total_weight >= liq_total_threshold_usd:
        scores["liq_pulse"] = min(1.0, max(near_notional, total_weight) / liq_total_threshold_usd)
        triggers.append(
            f"强平脉冲: 近端 ${near_notional:,.0f} / 网格权重 ${total_weight:,.0f}"
        )
        if oi_shock:
            triggers.append(f"OI 骤降 {oi_change_pct:.1f}% 伴随强平脉冲")

    cp = changepoint_prob if changepoint_prob is not None else 0.0
    if cp >= changepoint_warn_threshold:
        scores["changepoint"] = min(1.0, cp)
        triggers.append(f"BOCPD 变点概率 {cp:.0%} → 结构突变预警")

    if dvol_leads_gk:
        scores["dvol_lead"] = 0.8
        triggers.append("前瞻波动率领先实现波动率 → 高波预警")

    etf_day = _etf_day_flow(capital_flows)
    deriv_dead = _derivatives_dead(oi_change_pct, funding_bias)
    if etf_day is not None and etf_day > 50_000_000 and deriv_dead:
        scores["etf_deriv_divergence"] = 0.7
        triggers.append(
            f"ETF 单日净流入 ${etf_day / 1e6:.0f}M 但衍生品 OI/费率死寂 → 慢变量纠偏"
        )

    if vol_status in ("danger", "extreme"):
        scores["dvol_lead"] = max(scores["dvol_lead"], 0.6)
        if "极端波动状态" not in " ".join(triggers):
            triggers.append(f"波动状态 {vol_status} → 高危")

    practical = practical_signals or {}
    practical_scores = practical.get("scores") or {}
    strategy_list = list(practical.get("strategies") or [])
    max_strategy_hint = int(practical.get("max_level_hint") or 0)

    for key, val in practical_scores.items():
        if key not in scores:
            scores[key] = float(val)
        else:
            scores[key] = max(scores[key], float(val))

    for s in strategy_list:
        t = s.get("trigger")
        if t and t not in triggers:
            triggers.append(t)

    level = _resolve_level(
        scores=scores,
        macro_hazard=macro_hazard,
        extreme_pulse=extreme_pulse,
        oi_shock=oi_shock,
        cp=cp,
        changepoint_warn_threshold=changepoint_warn_threshold,
        max_strategy_hint=max_strategy_hint,
    )

    actions = dict(_LEVEL_ACTIONS[level])
    suspended = level >= 3
    circuit_breaker_active = level >= 2
    suspend_reason = triggers[0] if suspended and triggers else None

    return BlackSwanAlert(
        level=level,
        level_label=ALERT_LABELS[level],
        suspended=suspended,
        triggers=triggers,
        scores=scores,
        actions=actions,
        circuit_breaker_active=circuit_breaker_active,
        suspend_reason=suspend_reason,
        strategies=strategy_list,
    )


def apply_circuit_breaker_to_regime(
    regime: dict[str, Any],
    alert: BlackSwanAlert,
) -> dict[str, Any]:
    """将熔断指令合并进 btc_regime 输出。"""
    out = dict(regime)
    out["black_swan"] = alert.to_dict()

    if alert.level >= 3:
        out["regime_id"] = "macro_frozen_range"
        out["regime_label"] = "黑天鹅熔断 · 全策略挂起"
        out["macro_hazard"] = True
        out["confidence"] = min(float(out.get("confidence") or 1.0), 0.25)
        out["dashboard_regime"] = "range"
        drivers = list(out.get("drivers") or [])
        drivers.insert(0, f"黑天鹅 Halt: {alert.suspend_reason or '极端风险'}")
        out["drivers"] = drivers[:14]
    elif alert.level == 2:
        out["confidence"] = min(
            float(out.get("confidence") or 1.0),
            float(out.get("confidence") or 1.0) * alert.actions["confidence_multiplier"],
        )
        drivers = list(out.get("drivers") or [])
        drivers.insert(0, "黑天鹅 Warn: 禁止新开仓，仓位减半")
        out["drivers"] = drivers[:14]
    elif alert.level == 1:
        out["confidence"] = float(out.get("confidence") or 1.0) * alert.actions["confidence_multiplier"]
        drivers = list(out.get("drivers") or [])
        drivers.append("黑天鹅 Watch: 置信度下调，慢变量纠偏生效")
        out["drivers"] = drivers[:14]

    return out


def _resolve_level(
    *,
    scores: dict[str, float],
    macro_hazard: bool,
    extreme_pulse: bool,
    oi_shock: bool,
    cp: float,
    changepoint_warn_threshold: float,
    max_strategy_hint: int = 0,
) -> AlertLevel:
    if macro_hazard:
        return 3
    if extreme_pulse and oi_shock:
        return 3
    if (
        cp >= changepoint_warn_threshold
        or extreme_pulse
        or scores.get("dvol_lead", 0) >= 0.8
        or max_strategy_hint >= 2
        or (
            scores.get("range_squeeze", 0) >= 0.85
            and scores.get("vol_squeeze", 0) >= 0.55
        )
        or scores.get("oi_divergence", 0) >= 0.85
    ):
        return 2
    if (
        scores.get("etf_deriv_divergence", 0) >= 0.5
        or scores.get("dvol_lead", 0) >= 0.5
        or max_strategy_hint >= 1
        or scores.get("range_squeeze", 0) >= 0.55
        or scores.get("funding_extreme", 0) >= 0.6
        or scores.get("failed_breakout", 0) >= 0.5
        or scores.get("macro_hazard", 0) >= 0.4
        or scores.get("donchian_edge", 0) >= 0.35
    ):
        return 1
    return 0


def _etf_day_flow(flows: CapitalFlowsSnapshot | None) -> float | None:
    if flows and flows.btc_etf and flows.btc_etf.latest:
        return flows.btc_etf.latest.flow_usd
    return None


def _derivatives_dead(oi_change_pct: float | None, funding_bias: str | None) -> bool:
    oi_flat = oi_change_pct is None or abs(oi_change_pct) < 0.5
    funding_neutral = (funding_bias or "neutral") == "neutral"
    return oi_flat and funding_neutral
