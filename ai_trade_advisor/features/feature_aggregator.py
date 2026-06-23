from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.signal.debouncer import DebouncerState
from ai_trade_advisor.models import GexLevel, LiquidityLevel, MarketContext, PriceZone, SmcSnapshot


@dataclass
class FeatureSnapshot:
    """
    原子快照：在 AI 输出建议瞬间锁定所有维度，并将绝对价格转为相对现价百分比。
    """

    locked_at: str
    spot_price: float
    relative: dict[str, float | None] = field(default_factory=dict)
    macro_hazard: MacroHazardState | None = None
    gex_engine: GexEngineResult | None = None
    liquidation: LiquidationGridState | None = None
    debouncer: DebouncerState | None = None
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "locked_at": self.locked_at,
            "spot_price": self.spot_price,
            "relative": {k: (round(v, 4) if v is not None else None) for k, v in self.relative.items()},
            "macro_hazard": self.macro_hazard.to_dict() if self.macro_hazard else None,
            "gex_engine": self.gex_engine.to_dict() if self.gex_engine else None,
            "liquidation": self.liquidation.to_dict() if self.liquidation else None,
            "debouncer": self.debouncer.to_dict() if self.debouncer else None,
            "alerts": self.alerts,
        }


def pct_dist(price: float | None, spot: float) -> float | None:
    if price is None or spot <= 0:
        return None
    return (price - spot) / spot * 100.0


def build_feature_snapshot(
    ctx: MarketContext,
    *,
    macro: MacroHazardState | None = None,
    gex_engine: GexEngineResult | None = None,
    liquidation: LiquidationGridState | None = None,
    debouncer: DebouncerState | None = None,
) -> FeatureSnapshot:
    spot = ctx.last_price
    locked_at = datetime.now(timezone.utc).isoformat()

    relative: dict[str, float | None] = {
        "dist_to_call_wall_pct": None,
        "dist_to_put_wall_pct": None,
        "dist_to_pain_liq_pct": None,
        "nearest_ob_dist_pct": None,
        "nearest_fvg_dist_pct": None,
        "nearest_resistance_pct": None,
        "nearest_support_pct": None,
    }

    if gex_engine:
        relative["dist_to_call_wall_pct"] = pct_dist(gex_engine.gamma_wall_call, spot)
        relative["dist_to_put_wall_pct"] = pct_dist(gex_engine.gamma_wall_put, spot)

    if liquidation and liquidation.pain_price:
        relative["dist_to_pain_liq_pct"] = pct_dist(liquidation.pain_price, spot)

    if ctx.smc.nearest_ob:
        relative["nearest_ob_dist_pct"] = pct_dist(ctx.smc.nearest_ob.mid(), spot)
    if ctx.smc.nearest_fvg:
        relative["nearest_fvg_dist_pct"] = pct_dist(ctx.smc.nearest_fvg.mid(), spot)

    res, sup = _nearest_gex_walls(ctx.gex_levels, spot)
    relative["nearest_resistance_pct"] = pct_dist(res, spot)
    relative["nearest_support_pct"] = pct_dist(sup, spot)

    for lv in ctx.liquidity_levels:
        key = f"liq_{lv.side}_dist_pct"
        dist = pct_dist(lv.price, spot)
        if dist is not None:
            relative[key] = dist

    alerts: list[str] = []
    if macro and macro.macro_hazard_flag:
        alerts.append("宏观熔断：CPI/FOMC/NFP 窗口内，微观技术面信号降权")
    if gex_engine:
        alerts.extend(gex_engine.alerts)
    if debouncer and debouncer.cooldown_active:
        alerts.append(f"信号冷却中，剩余 {debouncer.cooldown_remaining_sec // 60} 分钟")

    return FeatureSnapshot(
        locked_at=locked_at,
        spot_price=spot,
        relative=relative,
        macro_hazard=macro,
        gex_engine=gex_engine,
        liquidation=liquidation,
        debouncer=debouncer,
        alerts=alerts,
    )


def _nearest_gex_walls(levels: list[GexLevel], spot: float) -> tuple[float | None, float | None]:
    res = sup = None
    for lv in levels:
        if lv.price > spot and (res is None or lv.price < res):
            if lv.level_type in ("resistance", "magnet"):
                res = lv.price
        if lv.price < spot and (sup is None or lv.price > sup):
            if lv.level_type in ("support", "magnet"):
                sup = lv.price
    return res, sup
