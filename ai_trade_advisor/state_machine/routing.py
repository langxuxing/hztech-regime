from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteResult:
    diagnosis_id: str
    diagnosis: str
    system_commands: list[str]
    matrix_quadrant: str | None = None
    match_type: str = "default"


@dataclass
class WeeklyPolicy:
    """SOP 1 — 每周战略定调。"""
    var_limit_pct: float
    var_adjustment: str
    cta_mode: str
    grid_mode: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "var_limit_pct": self.var_limit_pct,
            "var_adjustment": self.var_adjustment,
            "cta_mode": "enhanced" if self.cta_mode == "enhanced" else self.cta_mode,
            "grid_mode": self.grid_mode,
            "notes": self.notes,
        }


@dataclass
class DailySopRule:
    """SOP 2 — 盘前 15 分钟快检触发的规则。"""
    rule_id: str
    condition: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "condition": self.condition,
            "action": self.action,
            "params": self.params,
        }


# PDF 综合路由表（得分向量 [Macro, Flow, Gex]）
_ROUTING_TABLE: list[tuple[tuple[int, int, int], str, str, list[str]]] = [
    (
        (1, 2, -2),
        "gamma_squeeze_rally",
        "Gamma 强拉升市",
        ["CTA 满仓", "解除 Trailing Stop 限制", "强制关闭网格"],
    ),
    (
        (1, 1, 2),
        "slow_bull_range",
        "慢牛震荡市",
        ["加大高频做市分配", "收紧日内止损"],
    ),
    (
        (0, -2, -2),
        "panic_washout",
        "踩踏清洗市",
        ["多头暂停", "激活清算图挂单接刀策略"],
    ),
    (
        (-1, -2, -2),
        "panic_washout",
        "踩踏清洗市",
        ["多头暂停", "激活清算图挂单接刀策略"],
    ),
    (
        (-1, -1, 2),
        "steady_bleed",
        "平稳阴跌市",
        ["现货套保 (Delta Neutral)", "网格下移"],
    ),
    (
        (1, 2, 2),
        "violent_surge",
        "狂暴拉升市",
        ["趋势策略满负荷", "解除盈利回吐限制", "关闭逆势策略"],
    ),
    (
        (-1, -1, 2),
        "steady_drift_down",
        "平稳阴跌市 (流动性匮乏)",
        ["缩紧多头仓位", "降低网格下限", "轻仓做空"],
    ),
    (
        (1, 1, 2),
        "slow_bull_oscillation",
        "慢牛震荡市 (主动买方)",
        ["放宽趋势开仓阈值", "提高做市权重", "收紧止损"],
    ),
]

# 2×2 矩阵四象限（需 Flow/Gex 达到持续强度阈值才落入）
_MATRIX_2X2: dict[tuple[str, str], tuple[str, str, list[str]]] = {
    ("positive", "outflow"): (
        "steady_drift_down",
        "平稳阴跌市",
        ["缩紧多头", "降低网格下限", "轻仓做空"],
    ),
    ("positive", "inflow"): (
        "slow_bull_oscillation",
        "慢牛震荡市",
        ["放宽趋势阈值", "提高做市权重", "收紧止损"],
    ),
    ("negative", "outflow"): (
        "panic_washout",
        "踩踏清洗市",
        ["多头收紧止损", "清算密集区挂被动买单"],
    ),
    ("negative", "inflow"): (
        "gamma_squeeze_rally",
        "狂暴拉升市",
        ["CTA 满负荷", "解除盈利回吐限制", "关闭逆势策略"],
    ),
}

# 矩阵外两种补充形态
_UNCLEAR: tuple[str, str, list[str]] = (
    "indeterminate",
    "不明确",
    ["维持标准模式", "等待得分向量确认", "降低方向性敞口"],
)
_RANGE_OSCILLATION: tuple[str, str, list[str]] = (
    "range_oscillation",
    "区间震荡",
    ["网格策略为主", "收窄趋势敞口", "区间内高抛低吸"],
)

_FLOW_SUSTAINED = 2
_GEX_EXTREME_NEG = -2
_GEX_POSITIVE = 1


def resolve_route(macro: int, flow: int, gex: int) -> RouteResult:
    """综合路由：精确匹配 → 模糊匹配 → 补充形态 → 2×2 矩阵 → 不明确兜底。"""
    key = (macro, flow, gex)
    for pattern, diag_id, diag, cmds in _ROUTING_TABLE:
        if pattern == key:
            return RouteResult(
                diagnosis_id=diag_id,
                diagnosis=diag,
                system_commands=cmds,
                match_type="exact",
            )

    fuzzy = _fuzzy_match(macro, flow, gex)
    if fuzzy:
        return fuzzy

    supplemental = _supplemental_form(flow, gex)
    if supplemental:
        return supplemental

    matrix = _matrix_match(flow, gex)
    if matrix:
        return matrix

    diag_id, diag, cmds = _UNCLEAR
    return RouteResult(
        diagnosis_id=diag_id,
        diagnosis=diag,
        system_commands=cmds,
        match_type="default",
    )


def _supplemental_form(flow: int, gex: int) -> RouteResult | None:
    """矩阵外的两种补充形态：区间震荡 / 不明确。"""
    if gex >= _GEX_POSITIVE and abs(flow) < _FLOW_SUSTAINED:
        diag_id, diag, cmds = _RANGE_OSCILLATION
        return RouteResult(
            diagnosis_id=diag_id,
            diagnosis=diag,
            system_commands=cmds,
            matrix_quadrant="positive_neutral_flow",
            match_type="supplemental",
        )

    if _is_indeterminate(flow, gex):
        diag_id, diag, cmds = _UNCLEAR
        return RouteResult(
            diagnosis_id=diag_id,
            diagnosis=diag,
            system_commands=cmds,
            match_type="supplemental",
        )
    return None


def _is_indeterminate(flow: int, gex: int) -> bool:
    """双轴信号偏弱，或方向冲突且未达象限持续强度。"""
    flow_weak = abs(flow) < _FLOW_SUSTAINED
    gex_mid = -1 < gex < _GEX_POSITIVE
    gex_weak = abs(gex) < _GEX_POSITIVE
    if flow_weak and gex_weak:
        return True
    if flow_weak and gex_mid:
        return True
    # 持续筹码流 + 非极端 GEX → 方向与波动状态不匹配
    if abs(flow) >= _FLOW_SUSTAINED and gex > _GEX_EXTREME_NEG:
        return True
    return False


def _matrix_match(flow: int, gex: int) -> RouteResult | None:
    """仅当 Flow/Gex 达到持续强度时落入四象限。"""
    sustained_outflow = flow <= -_FLOW_SUSTAINED
    sustained_inflow = flow >= _FLOW_SUSTAINED
    if not sustained_outflow and not sustained_inflow:
        return None

    if gex >= _GEX_POSITIVE:
        gex_sign = "positive"
    elif gex <= _GEX_EXTREME_NEG:
        gex_sign = "negative"
    else:
        return None

    flow_sign = "inflow" if sustained_inflow else "outflow"
    quad_key = (gex_sign, flow_sign)
    if quad_key not in _MATRIX_2X2:
        return None

    diag_id, diag, cmds = _MATRIX_2X2[quad_key]
    return RouteResult(
        diagnosis_id=diag_id,
        diagnosis=diag,
        system_commands=cmds,
        matrix_quadrant=f"{gex_sign}_{flow_sign}",
        match_type="matrix",
    )


def _fuzzy_match(macro: int, flow: int, gex: int) -> RouteResult | None:
    if macro >= 0 and flow >= 2 and gex <= -1:
        return RouteResult(
            "gamma_squeeze_rally",
            "Gamma 强拉升市",
            ["CTA 满仓", "解除 Trailing Stop", "关闭网格"],
            match_type="fuzzy",
        )
    if macro <= 0 and flow <= -2 and gex <= -1:
        return RouteResult(
            "panic_washout",
            "踩踏清洗市",
            ["多头暂停", "清算图挂单接刀"],
            match_type="fuzzy",
        )
    if macro <= -1 and flow <= -1 and gex >= 1:
        return RouteResult(
            "steady_bleed",
            "平稳阴跌市",
            ["现货套保", "网格下移"],
            match_type="fuzzy",
        )
    if macro >= 1 and flow >= 1 and gex >= 1:
        return RouteResult(
            "slow_bull_range",
            "慢牛震荡市",
            ["加大做市", "收紧日内止损"],
            match_type="fuzzy",
        )
    return None


def build_weekly_policy(
    macro: int,
    event_risk: str,
    route: RouteResult,
) -> WeeklyPolicy:
    """SOP 1：由宏观分 + 事件风险 + 路由诊断生成仓位/策略库状态。"""
    base_var = 12.0
    notes: list[str] = []

    if event_risk == "high":
        base_var = 8.0
        notes.append("高危事件月：下调 VaR 上限，提高尾部对冲")
    elif event_risk == "low":
        base_var = 9.0
        notes.append("数据公布前夕：降低隐含波动率敞口")

    if macro == 1:
        base_var = min(15.0, base_var + 2.0)
        cta_mode = "enhanced"
        grid_mode = "full_open"
        notes.append("宏观扩张：CTA 增强模式")
    elif macro == -1:
        base_var = max(6.0, base_var - 3.0)
        cta_mode = "defensive"
        grid_mode = "widen_or_pause"
        notes.append("宏观紧缩：CTA 防御，网格拓宽/暂停")
    else:
        cta_mode = "standard"
        grid_mode = "full_open"

    if route.diagnosis_id == "gamma_squeeze_rally":
        cta_mode = "enhanced"
        grid_mode = "pause"
        base_var = min(18.0, base_var + 3.0)
    elif route.diagnosis_id == "panic_washout":
        cta_mode = "defensive"
        grid_mode = "widen_or_pause"
        base_var = max(5.0, base_var - 4.0)
    elif route.diagnosis_id == "steady_bleed":
        cta_mode = "defensive"
        grid_mode = "shift_down"
    elif route.diagnosis_id == "range_oscillation":
        cta_mode = "standard"
        grid_mode = "full_open"
        notes.append("区间震荡：网格为主，趋势敞口收窄")
    elif route.diagnosis_id == "indeterminate":
        cta_mode = "standard"
        grid_mode = "widen_or_pause"
        base_var = max(6.0, base_var - 2.0)
        notes.append("形态不明确：降仓观望，等待信号确认")

    prev_var = round(base_var - 2.0, 1) if macro != 0 else base_var
    var_adj = f"总仓位 VaR 上限从 {prev_var}% 调整为 {base_var}%"

    return WeeklyPolicy(
        var_limit_pct=base_var,
        var_adjustment=var_adj,
        cta_mode=cta_mode,
        grid_mode=grid_mode,
        notes=notes,
    )


def evaluate_daily_sop(
    gex_score: int,
    flow_score: int,
    *,
    dist_to_pain_liq_pct: float | None = None,
    atr_stop_multiplier: float = 2.0,
) -> list[DailySopRule]:
    """SOP 2 — 盘前快检：返回已触发的规则列表。"""
    triggered: list[DailySopRule] = []

    if gex_score <= -2:
        triggered.append(
            DailySopRule(
                rule_id="gex_extreme_negative",
                condition="GEX 跌入极端负区",
                action="日内 ATR 止损倍数临时放大",
                params={"atr_multiplier_from": atr_stop_multiplier, "atr_multiplier_to": 2.5},
            )
        )

    if dist_to_pain_liq_pct is not None and -3 < dist_to_pain_liq_pct < 0:
        delay_pct = round(abs(dist_to_pain_liq_pct) * 0.5, 2)
        triggered.append(
            DailySopRule(
                rule_id="liq_zone_below",
                condition=f"下方清算带距现价 {dist_to_pain_liq_pct:.1f}% (<3%)",
                action="做市买单坐标向后延迟，等待针尖黄金坑",
                params={"bid_delay_pct": delay_pct},
            )
        )

    if flow_score <= -2:
        triggered.append(
            DailySopRule(
                rule_id="extreme_outflow",
                condition="ETF 极端净流出 + 巨鲸充值进所",
                action="限制 CTA 突破追多，开仓阈值上调",
                params={"cta_breakout_threshold_boost": 0.15},
            )
        )

    return triggered
