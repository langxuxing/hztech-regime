from __future__ import annotations

from typing import Any

from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.models import CapitalFlowsSnapshot, MarketContext


def _clamp_score(value: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(value))))


def score_macro(
    ctx: MarketContext,
    *,
    macro: MacroHazardState | None = None,
) -> tuple[int, list[str]]:
    """
    半年期宏观分 [-1, 0, +1]。
    代理：BTC Regime 趋势 + ETF 7d 流向 + 宏观熔断窗口。
    """
    drivers: list[str] = []
    points = 0.0

    if macro and macro.macro_hazard_flag:
        drivers.append("宏观公布窗口 → 政策真空期，宏观分归零")
        return 0, drivers

    regime = ctx.btc_regime or {}
    raw_trend = regime.get("raw_trend") or "range"
    if raw_trend == "uptrend":
        points += 1.0
        drivers.append("KAMA+唐奇安多头结构 → 扩张倾向")
    elif raw_trend == "downtrend":
        points -= 1.0
        drivers.append("KAMA+唐奇安空头结构 → 紧缩倾向")

    etf_7d = _etf_7d(ctx.capital_flows)
    if etf_7d is not None:
        if etf_7d > 50_000_000:
            points += 0.75
            drivers.append(f"BTC ETF 7d 净流入 ${etf_7d / 1e6:.0f}M")
        elif etf_7d < -50_000_000:
            points -= 0.75
            drivers.append(f"BTC ETF 7d 净流出 ${abs(etf_7d) / 1e6:.0f}M")

    if ctx.vol_status in ("danger", "high", "elevated", "extreme"):
        points -= 0.5
        drivers.append(f"波动状态 {ctx.vol_status} → 偏紧")

    if points >= 0.75:
        return 1, drivers
    if points <= -0.75:
        return -1, drivers
    return 0, drivers


def score_flow(ctx: MarketContext) -> tuple[int, list[str]]:
    """
    周度筹码动能 $Flow [-2, +2]。
    组合：ETF 日/7d、交易所钱包净流入、市场 taker netflow、现货 CVD。
    """
    drivers: list[str] = []
    points = 0.0
    flows = ctx.capital_flows
    regime = ctx.btc_regime or {}

    etf_day = _etf_latest(flows)
    etf_7d = _etf_7d(flows)
    if etf_day is not None:
        if etf_day > 100_000_000:
            points += 1.5
            drivers.append(f"ETF 单日极端净流入 ${etf_day / 1e6:.0f}M")
        elif etf_day > 20_000_000:
            points += 0.75
            drivers.append(f"ETF 单日净流入 ${etf_day / 1e6:.0f}M")
        elif etf_day < -100_000_000:
            points -= 1.5
            drivers.append(f"ETF 单日极端净流出 ${abs(etf_day) / 1e6:.0f}M")
        elif etf_day < -20_000_000:
            points -= 0.75
            drivers.append(f"ETF 单日净流出 ${abs(etf_day) / 1e6:.0f}M")

    if etf_7d is not None:
        if etf_7d > 200_000_000:
            points += 0.5
        elif etf_7d < -200_000_000:
            points -= 0.5

    wallet = flows.btc_exchange_wallet if flows else None
    if wallet and wallet.net_to_exchange_1d is not None:
        net = wallet.net_to_exchange_1d
        if net > 0:
            points -= 0.75
            drivers.append("链上净流入交易所（大户充值现货）→ 抛压信号")
        elif net < 0:
            points += 0.75
            drivers.append("链上净流出交易所（提币/囤货）→ 积累信号")

    taker_net = _btc_taker_netflow(flows)
    if taker_net is not None:
        if taker_net > 0:
            points += 0.5
            drivers.append("市场 taker 净买入")
        elif taker_net < 0:
            points -= 0.5
            drivers.append("市场 taker 净卖出")

    if regime.get("spot_cvd_breakout"):
        points += 0.75
        drivers.append("现货 CVD 突破确认")
    if regime.get("cvd_bullish_divergence"):
        points += 0.5
        drivers.append("5m CVD 底背离")

    cvd_trend = regime.get("cvd_trend")
    if cvd_trend == "bullish":
        points += 0.5
        drivers.append("CVD 斜率看多")
    elif cvd_trend == "bearish":
        points -= 0.5
        drivers.append("CVD 斜率看空")

    funding_bias = regime.get("funding_bias")
    if funding_bias == "bullish":
        points += 0.35
        drivers.append("资金费率偏多")
    elif funding_bias == "bearish":
        points -= 0.35
        drivers.append("资金费率偏空/拥挤")

    oi_sync = regime.get("oi_price_sync")
    if oi_sync == "long_build":
        points += 0.5
        drivers.append("OI 增仓 + 价格上涨")
    elif oi_sync == "short_build":
        points -= 0.5
        drivers.append("OI 增仓 + 价格下跌")
    elif oi_sync == "unwind":
        drivers.append("OI 减仓，趋势动能减弱")

    return _clamp_score(points, -2, 2), drivers


def score_gex(
    ctx: MarketContext,
    *,
    gex_engine: GexEngineResult | None = None,
    feature_relative: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    """
    短期波动分 $Gex [-2, +2]。
  正 Gamma 压制波动；极端负 Gamma 放大波动。
    """
    drivers: list[str] = []
    rel = feature_relative or {}
    points = 0.0

    net_gex = _net_gex_near_spot(ctx.gex_levels, ctx.last_price)
    if net_gex is not None:
        if net_gex > 0:
            points += 1.0
            drivers.append("近端 GEX 净正 → 波动压制")
        else:
            points -= 1.0
            drivers.append("近端 GEX 净负 → 波动放大风险")

    if gex_engine and gex_engine.source == "deribit":
        call_wall = gex_engine.gamma_wall_call
        put_wall = gex_engine.gamma_wall_put
        spot = ctx.last_price
        if call_wall and put_wall and spot > 0:
            call_dist = (call_wall - spot) / spot * 100
            put_dist = (spot - put_wall) / spot * 100
            if call_dist < 3 and put_dist > 5:
                points += 0.75
                drivers.append(f"Call 墙距现价 {call_dist:.1f}% → 正 Gamma 压制")
            if put_dist < 3 and call_dist > 5:
                points -= 0.75
                drivers.append(f"Put 墙距现价 {put_dist:.1f}% → 负 Gamma 踩踏风险")

    if ctx.vol_ratio is not None:
        if ctx.vol_ratio >= 0.20:
            points -= 1.0
            drivers.append(f"VR={ctx.vol_ratio:.2f} 高波 → 负 Gamma 环境")
        elif ctx.vol_ratio <= 0.04:
            points += 0.5
            drivers.append(f"VR={ctx.vol_ratio:.2f} 低波 → 正 Gamma 环境")

    dist_pain = rel.get("dist_to_pain_liq_pct")
    if dist_pain is not None and dist_pain > -3 and dist_pain < 0:
        points -= 0.5
        drivers.append(f"清算密集区距现价 {dist_pain:.1f}% → 踩踏风险")

    return _clamp_score(points, -2, 2), drivers


def score_event_risk(
    macro: MacroHazardState | None,
    *,
    upcoming_high_impact: int = 0,
) -> tuple[str, int, list[str]]:
    """
    月度事件风险 [High/Med/Low] → 分数 [+1, 0, -1]。
    """
    drivers: list[str] = []
    if macro and macro.macro_hazard_flag:
        drivers.append("宏观公布窗口内 → 高危")
        return "high", 1, drivers

    if macro and macro.minutes_to_next is not None:
        mins = macro.minutes_to_next
        if 0 < mins <= 180:
            drivers.append(f"数据公布前 {mins}min → 前夕降波")
            return "low", -1, drivers

    if upcoming_high_impact >= 3:
        drivers.append(f"本月 {upcoming_high_impact} 个高影响事件 → 高危事件月")
        return "high", 1, drivers

    if upcoming_high_impact >= 1:
        drivers.append("存在待公布高影响事件 → 平稳过渡")
        return "medium", 0, drivers

    drivers.append("近期无重大宏观事件 → 常规暴露")
    return "medium", 0, drivers


def _etf_7d(flows: CapitalFlowsSnapshot | None) -> float | None:
    if flows and flows.btc_etf:
        return flows.btc_etf.total_7d_usd
    return None


def _etf_latest(flows: CapitalFlowsSnapshot | None) -> float | None:
    if flows and flows.btc_etf and flows.btc_etf.latest:
        return flows.btc_etf.latest.flow_usd
    return None


def _btc_taker_netflow(flows: CapitalFlowsSnapshot | None) -> float | None:
    if not flows:
        return None
    for mf in flows.btc_market_flows:
        for p in mf.periods:
            if p.period in ("24h", "1d") and p.netflow_usd is not None:
                return p.netflow_usd
    return None


def _net_gex_near_spot(levels: list, spot: float, *, band_pct: float = 5.0) -> float | None:
    if not levels or spot <= 0:
        return None
    total = 0.0
    count = 0
    for lv in levels:
        dist = abs(lv.price - spot) / spot * 100
        if dist > band_pct:
            continue
        sign = 1.0 if lv.level_type in ("support", "magnet") and lv.price <= spot else -1.0
        if lv.level_type == "resistance":
            sign = -1.0 if lv.price >= spot else 1.0
        total += lv.gex_notional_proxy * sign
        count += 1
    return total if count else None


def compute_boundaries(
    ctx: MarketContext,
    *,
    gex_engine: GexEngineResult | None = None,
    liquidation: LiquidationGridState | None = None,
    feature_relative: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GEX 阻力墙 + 清算流动性池上下边界。"""
    spot = ctx.last_price
    rel = feature_relative or {}
    upper = lower = None
    upper_label = "GEX 阻力墙"
    lower_label = "清算流动性池"

    if gex_engine and gex_engine.gamma_wall_call:
        upper = gex_engine.gamma_wall_call
    if not upper:
        for lv in ctx.gex_levels:
            if lv.price > spot and lv.level_type in ("resistance", "magnet"):
                upper = lv.price
                break

    if liquidation and liquidation.pain_price:
        lower = liquidation.pain_price
    if not lower:
        for lv in ctx.liquidity_levels:
            if lv.price < spot and lv.side == "buy_side":
                lower = lv.price
                break
        if not lower and rel.get("dist_to_pain_liq_pct") is not None:
            dist = rel["dist_to_pain_liq_pct"]
            lower = spot * (1 + dist / 100)

    range_pct = None
    if upper and lower and spot > 0:
        range_pct = round((upper - lower) / spot * 100, 2)

    return {
        "upper_price": upper,
        "lower_price": lower,
        "upper_label": upper_label,
        "lower_label": lower_label,
        "range_pct": range_pct,
        "dist_to_upper_pct": rel.get("dist_to_call_wall_pct") or rel.get("nearest_resistance_pct"),
        "dist_to_lower_pct": rel.get("dist_to_pain_liq_pct") or rel.get("nearest_support_pct"),
    }
