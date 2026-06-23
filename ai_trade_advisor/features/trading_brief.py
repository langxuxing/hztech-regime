"""短期预测与操作建议聚合（规则 + AI advice 融合）。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.models import MarketContext, TradeAdvice


def build_trading_brief(ctx: MarketContext, advice: TradeAdvice) -> dict[str, Any]:
    """1–4h 操作简报：整合 SMC、流动性、GEX、衍生品、资金流与 AI 建议。"""
    price = ctx.last_price
    smc = ctx.smc
    btc = ctx.btc_regime or {}
    micro = _micro_from_pipeline(ctx)
    flows = _flow_summary(ctx)

    bull_scenario, bear_scenario, base_scenario = _scenarios(ctx, advice, price)
    smc_action = _smc_action(smc)
    liq_note = _liquidity_note(ctx.liquidity_levels, price)
    gex_note = _gex_note(ctx.gex_levels, price)
    deriv_note = _derivatives_note(btc, micro)
    flow_note = flows.get("summary", "")

    catalysts: list[str] = []
    if smc.mss_or_choch:
        catalysts.append(f"{smc.mss_or_choch} 结构信号")
    if ctx.macro_hazard_flag:
        catalysts.append("宏观熔断窗口")
    if btc.get("spot_cvd_breakout"):
        catalysts.append("现货 CVD 突破确认")
    elif btc.get("cvd_bullish_divergence"):
        catalysts.append("CVD 底背离")
    if flows.get("etf_signal"):
        catalysts.append(flows["etf_signal"])

    key_levels = _key_levels(ctx, advice, price)
    horizon = advice.time_horizon if advice.time_horizon else "1h-4h"

    ai_note = advice.reasoning
    if advice.raw_llm:
        ai_note = advice.reasoning

    return {
        "horizon": horizon,
        "bias": advice.bias,
        "confidence": advice.confidence,
        "confluence_score": advice.confluence_score,
        "scenario_bull": bull_scenario,
        "scenario_bear": bear_scenario,
        "scenario_base": base_scenario,
        "smc_action": smc_action,
        "liquidity_note": liq_note,
        "gex_note": gex_note,
        "derivatives_note": deriv_note,
        "flow_note": flow_note,
        "catalysts": catalysts,
        "key_levels": key_levels,
        "operation_plan": _operation_plan(advice, key_levels),
        "ai_enhanced": not advice.rule_based and bool(getattr(advice, "raw_llm", None)),
        "ai_mode": "llm" if not advice.rule_based else "rule_based",
        "ai_summary": ai_note,
        "risks": advice.risks,
        "derivatives": {
            "oi_change_pct": micro.get("oi_change_pct") or btc.get("oi_change_pct"),
            "funding_rate": micro.get("funding_rate") or btc.get("funding_rate"),
            "funding_bias": micro.get("funding_bias") or btc.get("funding_bias"),
            "cvd_trend": micro.get("cvd_trend") or btc.get("cvd_trend"),
            "spot_cvd_breakout": btc.get("spot_cvd_breakout"),
        },
        "flows": flows,
    }


def _micro_from_pipeline(ctx: MarketContext) -> dict[str, Any]:
    layers = (ctx.pipeline or {}).get("layers") or {}
    ing = layers.get("ingestion") or {}
    return ing.get("microstructure") or {}


def _scenarios(ctx: MarketContext, advice: TradeAdvice, price: float) -> tuple[str, str, str]:
    hi = ctx.ohlcv_summary.get("range_20bar_high", price * 1.02)
    lo = ctx.ohlcv_summary.get("range_20bar_low", price * 0.98)
    bull = f"突破 {float(hi):.0f} 且 CVD/结构确认 → 延续上攻至下一 GEX 阻力"
    bear = f"跌破 {float(lo):.0f} 或流动性下方清洗 → 下探买盘 OB/FVG"
    base = f"区间 {float(lo):.0f}–{float(hi):.0f} 震荡；当前偏向 {advice.bias}"
    return bull, bear, base


def _smc_action(smc) -> str:
    parts = [f"趋势={smc.trend}"]
    if smc.mss_or_choch:
        parts.append(f"{smc.mss_or_choch}({'多' if smc.mss_direction > 0 else '空'})")
    if smc.nearest_ob:
        parts.append(f"关注 OB {smc.nearest_ob.low:.0f}-{smc.nearest_ob.high:.0f}")
    if smc.unfilled_fvgs:
        parts.append(f"未回补 FVG {len(smc.unfilled_fvgs)} 处")
    return " · ".join(parts)


def _liquidity_note(levels, price: float) -> str:
    if not levels:
        return "无明显流动性池"
    pending = [lv for lv in levels if not lv.swept]
    if not pending:
        return "近期流动性已清洗，关注结构延续"
    nearest = min(pending, key=lambda lv: abs(lv.price - price))
    side = "下方" if nearest.price < price else "上方"
    return f"最近待清洗位 {side} {nearest.price:.0f} (strength {nearest.strength:.1f})"


def _gex_note(levels, price: float) -> str:
    if not levels:
        return "GEX 数据不可用"
    magnets = sorted(levels, key=lambda g: abs(g.price - price))[:2]
    parts = [f"{g.level_type}@{g.price:.0f}" for g in magnets]
    return "磁吸/墙位: " + ", ".join(parts)


def _derivatives_note(btc: dict, micro: dict) -> str:
    oi = micro.get("oi_change_pct") or btc.get("oi_change_pct")
    fund = micro.get("funding_rate") or btc.get("funding_rate")
    cvd = micro.get("cvd_trend") or btc.get("cvd_trend")
    bits = []
    if oi is not None:
        bits.append(f"OI {oi:+.1f}%")
    if fund is not None:
        bits.append(f"费率 {float(fund):.4f}")
    if cvd:
        bits.append(f"CVD {cvd}")
    return " · ".join(bits) if bits else "衍生品数据待更新"


def _flow_summary(ctx: MarketContext) -> dict[str, Any]:
    cf = ctx.capital_flows
    if cf is None:
        return {"summary": "资金流数据未加载"}
    etf = cf.btc_etf
    parts: list[str] = []
    etf_signal = ""
    if etf and etf.latest:
        flow = etf.latest.flow_usd
        parts.append(f"ETF 日流 ${flow / 1e6:+.1f}M")
        etf_signal = "ETF 净流入" if flow > 0 else "ETF 净流出"
    w = cf.btc_exchange_wallet
    if w and w.net_to_exchange_1d is not None:
        parts.append(f"链上净{'入' if w.net_to_exchange_1d >= 0 else '出'}所 {w.net_to_exchange_1d:+.0f} BTC")
    return {
        "summary": " · ".join(parts) if parts else "资金流中性",
        "etf_signal": etf_signal,
        "etf_7d": etf.total_7d_usd if etf else None,
    }


def _key_levels(ctx: MarketContext, advice: TradeAdvice, price: float) -> dict[str, float | None]:
    levels: dict[str, float | None] = {
        "current": price,
        "support": ctx.ohlcv_summary.get("range_20bar_low"),
        "resistance": ctx.ohlcv_summary.get("range_20bar_high"),
        "stop_loss": advice.stop_loss,
    }
    if advice.entry_zone:
        levels["entry_low"] = advice.entry_zone[0]
        levels["entry_high"] = advice.entry_zone[1]
    if advice.take_profit:
        levels["take_profit_1"] = advice.take_profit[0]
        if len(advice.take_profit) > 1:
            levels["take_profit_2"] = advice.take_profit[1]
    btc = ctx.btc_regime or {}
    if btc.get("donchian_upper"):
        levels["donchian_upper"] = float(btc["donchian_upper"])
    if btc.get("donchian_lower"):
        levels["donchian_lower"] = float(btc["donchian_lower"])
    return levels


def _operation_plan(advice: TradeAdvice, levels: dict[str, Any]) -> list[str]:
    plan: list[str] = []
    bias_label = {"long": "做多", "short": "做空", "neutral": "观望"}.get(advice.bias, advice.bias)
    plan.append(f"方向: {bias_label} (置信 {(advice.confidence * 100):.0f}%)")
    if advice.entry_zone:
        plan.append(f"入场区 {advice.entry_zone[0]:.0f}–{advice.entry_zone[1]:.0f}")
    if advice.stop_loss:
        plan.append(f"止损 {advice.stop_loss:.0f}")
    if advice.take_profit:
        plan.append(f"止盈 {' / '.join(f'{t:.0f}' for t in advice.take_profit)}")
    if advice.bias == "neutral":
        plan.append("熔断/信号冲突：仅观察，不开新仓")
    return plan
