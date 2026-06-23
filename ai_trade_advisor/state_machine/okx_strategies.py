from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ai_trade_advisor.state_machine.routing import RouteResult, WeeklyPolicy

GridDirection = Literal["long", "short", "neutral", "single"]
MartingaleDirection = Literal["long", "short", "neutral", "single"]
GridMode = Literal["arithmetic", "geometric"]

_DIRECTION_LABELS: dict[str, str] = {
    "long": "多向",
    "short": "空向",
    "neutral": "双向",
    "single": "单向",
}


@dataclass
class GridParams:
    """OKX 合约/现货网格建议参数。"""

    enabled: bool
    direction: GridDirection
    direction_label: str
    lower_price: float
    upper_price: float
    grid_count: int
    mode: GridMode
    leverage: int
    profit_per_grid_pct: float
    total_investment_usdt: float | None = None
    stop_loss_pct: float | None = None
    trigger_price: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "direction": self.direction,
            "direction_label": self.direction_label,
            "lower_price": round(self.lower_price, 2),
            "upper_price": round(self.upper_price, 2),
            "grid_count": self.grid_count,
            "mode": self.mode,
            "leverage": self.leverage,
            "profit_per_grid_pct": self.profit_per_grid_pct,
            "total_investment_usdt": self.total_investment_usdt,
            "stop_loss_pct": self.stop_loss_pct,
            "trigger_price": round(self.trigger_price, 2) if self.trigger_price else None,
            "notes": self.notes,
        }


@dataclass
class MartingaleParams:
    """OKX 马丁格尔策略建议参数。"""

    enabled: bool
    direction: MartingaleDirection
    direction_label: str
    initial_order_usdt: float
    multiplier: float
    max_additions: int
    take_profit_pct: float
    stop_loss_pct: float
    leverage: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "direction": self.direction,
            "direction_label": self.direction_label,
            "initial_order_usdt": self.initial_order_usdt,
            "multiplier": self.multiplier,
            "max_additions": self.max_additions,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "leverage": self.leverage,
            "notes": self.notes,
        }


@dataclass
class OkxOtherTool:
    tool_id: str
    name: str
    action: str
    priority: Literal["primary", "secondary", "avoid"] = "secondary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "action": self.action,
            "priority": self.priority,
        }


@dataclass
class OkxStrategyPlan:
    diagnosis_id: str
    diagnosis: str
    summary: str
    primary_tool: str
    grid: GridParams
    martingale: MartingaleParams
    other_tools: list[OkxOtherTool] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "diagnosis": self.diagnosis,
            "summary": self.summary,
            "primary_tool": self.primary_tool,
            "grid": self.grid.to_dict(),
            "martingale": self.martingale.to_dict(),
            "other_tools": [t.to_dict() for t in self.other_tools],
            "cautions": self.cautions,
        }


def build_okx_strategy_plan(
    route: RouteResult,
    *,
    spot: float,
    boundaries: dict[str, Any],
    weekly_policy: WeeklyPolicy,
    event_risk: str = "medium",
) -> OkxStrategyPlan:
    """按市场形态生成 OKX 策略工具与网格/马丁参数建议。"""
    builder = _STRATEGY_BUILDERS.get(route.diagnosis_id, _build_indeterminate)
    return builder(
        route=route,
        spot=spot,
        boundaries=boundaries,
        weekly_policy=weekly_policy,
        event_risk=event_risk,
    )


def _grid_direction_label(direction: GridDirection) -> str:
    return _DIRECTION_LABELS[direction]


def _grid_context(kw: dict[str, Any]) -> tuple[float, dict[str, Any], WeeklyPolicy]:
    return kw["spot"], kw["boundaries"], kw["weekly_policy"]


def _resolve_price_band(
    spot: float,
    boundaries: dict[str, Any],
    *,
    lower_pct: float,
    upper_pct: float,
) -> tuple[float, float]:
    lower = boundaries.get("lower_price") or spot * (1 - lower_pct / 100)
    upper = boundaries.get("upper_price") or spot * (1 + upper_pct / 100)
    if lower >= upper:
        lower = spot * (1 - lower_pct / 100)
        upper = spot * (1 + upper_pct / 100)
    if lower > spot:
        lower = spot * (1 - lower_pct / 100)
    if upper < spot:
        upper = spot * (1 + upper_pct / 100)
    return float(lower), float(upper)


def _grid_count(range_pct: float | None, *, dense: bool = False) -> int:
    if range_pct is None or range_pct <= 0:
        return 20 if dense else 12
    per_grid = 0.35 if dense else 0.55
    return max(6, min(30, int(range_pct / per_grid)))


def _base_grid(
    *,
    enabled: bool,
    direction: GridDirection,
    spot: float,
    boundaries: dict[str, Any],
    weekly_policy: WeeklyPolicy,
    lower_pct: float,
    upper_pct: float,
    dense: bool = False,
    leverage: int = 3,
    profit_pct: float = 0.45,
    notes: list[str] | None = None,
) -> GridParams:
    lower, upper = _resolve_price_band(spot, boundaries, lower_pct=lower_pct, upper_pct=upper_pct)
    range_pct = boundaries.get("range_pct")
    if range_pct is None and spot > 0:
        range_pct = (upper - lower) / spot * 100

    grid_count = _grid_count(range_pct, dense=dense)
    mode: GridMode = "geometric" if (range_pct or 0) >= 4 else "arithmetic"

    if weekly_policy.grid_mode == "shift_down":
        upper = min(upper, spot * 1.015)
        notes = (notes or []) + ["网格整体下移，上沿贴近现价"]
    elif weekly_policy.grid_mode == "widen_or_pause":
        span = (upper - lower) / spot * 100
        lower = spot * (1 - (span * 1.25) / 200)
        upper = spot * (1 + (span * 1.25) / 200)
        grid_count = max(6, grid_count - 4)
        notes = (notes or []) + ["拓宽区间、减少格数，降低频繁成交"]
    elif weekly_policy.grid_mode == "pause":
        enabled = False
        notes = (notes or []) + ["趋势/极端波动期暂停网格"]

    stop_loss = None
    if direction == "long":
        stop_loss = round((spot - lower) / spot * 100 * 1.1, 2)
    elif direction == "short":
        stop_loss = round((upper - spot) / spot * 100 * 1.1, 2)

    return GridParams(
        enabled=enabled,
        direction=direction,
        direction_label=_grid_direction_label(direction),
        lower_price=lower,
        upper_price=upper,
        grid_count=grid_count,
        mode=mode,
        leverage=leverage,
        profit_per_grid_pct=profit_pct,
        total_investment_usdt=None,
        stop_loss_pct=stop_loss,
        trigger_price=spot,
        notes=notes or [],
    )


def _base_martingale(
    *,
    enabled: bool,
    direction: MartingaleDirection,
    leverage: int = 2,
    initial_usdt: float = 50.0,
    multiplier: float = 1.5,
    max_additions: int = 4,
    take_profit_pct: float = 0.8,
    stop_loss_pct: float = 3.0,
    notes: list[str] | None = None,
) -> MartingaleParams:
    return MartingaleParams(
        enabled=enabled,
        direction=direction,
        direction_label=_grid_direction_label(direction),
        initial_order_usdt=initial_usdt,
        multiplier=multiplier,
        max_additions=max_additions,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        leverage=leverage,
        notes=notes or [],
    )


def _build_range_oscillation(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    spot, boundaries, weekly_policy = _grid_context(kw)
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="正 Gamma 压制波动、筹码无持续方向：双向网格吃区间，马丁轻仓辅助。",
        primary_tool="grid_neutral",
        grid=_base_grid(
            enabled=True,
            direction="neutral",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            dense=True,
            lower_pct=2.5,
            upper_pct=2.5,
            leverage=3,
            profit_pct=0.4,
            notes=["OKX 合约网格 → 双向", "区间中枢放现价，均匀布格"],
        ),
        martingale=_base_martingale(
            enabled=False,
            direction="neutral",
            notes=["震荡市不做马丁，避免单边突破加仓失控"],
        ),
        other_tools=[
            OkxOtherTool("spot_dca", "现货定投", "小仓位定投攒币，网格主策略", "secondary"),
        ],
        cautions=["突破上下沿需手动暂停网格并复核形态"],
    )


def _build_slow_bull(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    spot, boundaries, weekly_policy = _grid_context(kw)
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="主动买方 + 正 Gamma：偏多网格做市，马丁仅多向轻仓。",
        primary_tool="grid_long",
        grid=_base_grid(
            enabled=True,
            direction="long",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            lower_pct=2.0,
            upper_pct=4.5,
            leverage=3,
            profit_pct=0.5,
            notes=["OKX 合约网格 → 多向", "下沿放宽承接回调，上沿贴近阻力"],
        ),
        martingale=_base_martingale(
            enabled=True,
            direction="long",
            initial_usdt=40.0,
            multiplier=1.4,
            max_additions=3,
            take_profit_pct=1.0,
            stop_loss_pct=2.5,
            notes=["仅回调加仓，禁止追突破加仓"],
        ),
        other_tools=[
            OkxOtherTool("signal_bot", "信号策略", "放宽趋势开仓阈值，顺势加仓", "secondary"),
            OkxOtherTool("recurring_buy", "现货定投", "慢牛背景小额定投", "secondary"),
        ],
        cautions=["收紧日内止损，防范假突破"],
    )


def _build_steady_drift_down(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    spot, boundaries, weekly_policy = _grid_context(kw)
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="阴跌 + 正 Gamma：空向网格下移，多头网格缩窄或关闭。",
        primary_tool="grid_short",
        grid=_base_grid(
            enabled=True,
            direction="short",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            lower_pct=4.0,
            upper_pct=1.5,
            leverage=2,
            profit_pct=0.55,
            notes=["OKX 合约网格 → 空向", "降低网格下限，上沿不宜过高"],
        ),
        martingale=_base_martingale(
            enabled=True,
            direction="short",
            initial_usdt=35.0,
            multiplier=1.35,
            max_additions=3,
            take_profit_pct=0.9,
            stop_loss_pct=2.0,
            notes=["反弹加仓做空，总层数≤3"],
        ),
        other_tools=[
            OkxOtherTool("delta_neutral", "现货套保", "现货多头 + 合约空向对冲", "primary"),
            OkxOtherTool("iceberg", "冰山策略", "反弹分批挂空", "secondary"),
        ],
        cautions=["缩紧多头仓位，勿在流动性匮乏时重仓抄底"],
    )


def _build_panic_washout(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    spot, boundaries, weekly_policy = _grid_context(kw)
    lower = boundaries.get("lower_price") or spot * 0.94
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="极端负 Gamma + 净流出：空网格暂停，清算密集区多向接刀网格。",
        primary_tool="grid_long",
        grid=_base_grid(
            enabled=True,
            direction="long",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            lower_pct=6.0,
            upper_pct=1.0,
            leverage=2,
            profit_pct=0.65,
            notes=[
                "OKX 合约网格 → 多向（接刀专用）",
                f"下沿锚定清算池 ≈ {lower:.0f}",
                "买单向后延迟，等针尖黄金坑",
            ],
        ),
        martingale=_base_martingale(
            enabled=True,
            direction="long",
            initial_usdt=30.0,
            multiplier=1.3,
            max_additions=2,
            take_profit_pct=1.5,
            stop_loss_pct=4.0,
            notes=["仅清算带附近启用，最多加仓 2 层"],
        ),
        other_tools=[
            OkxOtherTool("limit_ladder", "限价分批", "爆仓密集区挂被动买单", "primary"),
            OkxOtherTool("grid_short", "空向网格", "暂停 — 踩踏期不做空网格", "avoid"),
        ],
        cautions=["多头全线收紧止损；勿在瀑布中段盲目马丁"],
    )


def _build_gamma_squeeze(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    spot, boundaries, weekly_policy = _grid_context(kw)
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="Gamma 挤压/轧空：趋势满负荷，关闭逆势网格与马丁。",
        primary_tool="trend_cta",
        grid=_base_grid(
            enabled=False,
            direction="single",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            lower_pct=1.5,
            upper_pct=1.5,
            leverage=5,
            profit_pct=0.3,
            notes=["强制关闭网格 — 单边行情网格易被扫"],
        ),
        martingale=_base_martingale(
            enabled=False,
            direction="long",
            notes=["轧空行情禁止马丁 — 回撤即爆仓"],
        ),
        other_tools=[
            OkxOtherTool("signal_bot", "信号策略/CTA", "趋势策略满负荷，顺势追多", "primary"),
            OkxOtherTool("trailing_stop", "追踪止损", "解除盈利回吐限制，移动止盈", "primary"),
            OkxOtherTool("grid_neutral", "双向网格", "关闭", "avoid"),
        ],
        cautions=["关闭逆势策略；高杠杆仅用于趋势腿"],
    )


def _build_indeterminate(**kw: Any) -> OkxStrategyPlan:
    route: RouteResult = kw["route"]
    event_risk: str = kw.get("event_risk", "medium")
    spot, boundaries, weekly_policy = _grid_context(kw)
    grid_enabled = event_risk != "high"
    return OkxStrategyPlan(
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        summary="形态不明确：轻仓双向网格或暂停，等待得分向量确认。",
        primary_tool="grid_neutral" if grid_enabled else "wait",
        grid=_base_grid(
            enabled=grid_enabled,
            direction="neutral",
            spot=spot,
            boundaries=boundaries,
            weekly_policy=weekly_policy,
            lower_pct=1.8,
            upper_pct=1.8,
            leverage=2,
            profit_pct=0.35,
            dense=False,
            notes=["OKX 合约网格 → 双向（观察仓）", "缩窄仓位，格距放宽"],
        ),
        martingale=_base_martingale(
            enabled=False,
            direction="neutral",
            notes=["信号未确认前禁用马丁"],
        ),
        other_tools=[
            OkxOtherTool("wait", "观望", "维持标准模式，降低方向性敞口", "primary"),
            OkxOtherTool("recurring_buy", "现货定投", "仅保留极小定额定投", "secondary"),
        ],
        cautions=["双轴得分确认前勿加大仓位"],
    )


_STRATEGY_BUILDERS = {
    "range_oscillation": _build_range_oscillation,
    "slow_bull_oscillation": _build_slow_bull,
    "slow_bull_range": _build_slow_bull,
    "steady_drift_down": _build_steady_drift_down,
    "steady_bleed": _build_steady_drift_down,
    "panic_washout": _build_panic_washout,
    "gamma_squeeze_rally": _build_gamma_squeeze,
    "violent_surge": _build_gamma_squeeze,
    "indeterminate": _build_indeterminate,
}
