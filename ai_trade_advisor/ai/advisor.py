from __future__ import annotations

from ai_trade_advisor.ai.client import call_llm, parse_advice_json
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.context.builder import build_structured_context
from ai_trade_advisor.models import Bias, MarketContext, TradeAdvice


def generate_advice(cfg: AdvisorConfig, ctx: MarketContext) -> TradeAdvice:
    if ctx.macro_hazard_flag or (ctx.btc_regime or {}).get("regime_id") == "macro_frozen_range":
        return _macro_hazard_advice(ctx)
    prompt = build_structured_context(ctx)
    if cfg.ai_api_key:
        raw = call_llm(cfg, prompt)
        data = parse_advice_json(raw)
        return _from_llm(data, raw_llm=raw)
    return _rule_based_advice(ctx)


def _macro_hazard_advice(ctx: MarketContext) -> TradeAdvice:
    return TradeAdvice(
        bias="neutral",
        confidence=0.3,
        entry_zone=None,
        stop_loss=None,
        take_profit=[],
        time_horizon="4h-24h",
        reasoning="宏观熔断窗口，Regime=macro_frozen_range，强制观望。",
        risks=["宏观 hazard 窗口"],
        confluence_score=0.2,
        rule_based=True,
    )


def _from_llm(data: dict, *, raw_llm: str) -> TradeAdvice:
    bias = str(data.get("bias", "neutral")).lower()
    if bias not in ("long", "short", "neutral"):
        bias = "neutral"
    entry = data.get("entry_zone")
    entry_zone = tuple(entry) if isinstance(entry, (list, tuple)) and len(entry) == 2 else None
    tp = data.get("take_profit") or []
    if not isinstance(tp, list):
        tp = [tp] if tp else []
    risks = data.get("risks") or []
    if not isinstance(risks, list):
        risks = [str(risks)]
    return TradeAdvice(
        bias=bias,  # type: ignore[arg-type]
        confidence=float(data.get("confidence", 0.5)),
        entry_zone=entry_zone,  # type: ignore[arg-type]
        stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
        take_profit=[float(x) for x in tp],
        time_horizon=str(data.get("time_horizon", "intraday")),
        reasoning=str(data.get("reasoning", "")),
        risks=[str(r) for r in risks],
        confluence_score=float(data.get("confluence_score", 0.5)),
        raw_llm=raw_llm,
        rule_based=False,
    )


def _rule_based_advice(ctx: MarketContext) -> TradeAdvice:
    """无 API Key 时的确定性规则引擎，便于本地验证特征管道。"""
    score = 0.0
    risks: list[str] = []
    price = ctx.last_price

    if ctx.smc.mss_direction > 0:
        score += 0.25
    elif ctx.smc.mss_direction < 0:
        score -= 0.25

    if ctx.smc.trend == "bullish":
        score += 0.15
    elif ctx.smc.trend == "bearish":
        score -= 0.15

    recent_sweeps = [lv for lv in ctx.liquidity_levels if lv.swept]
    for lv in recent_sweeps[-3:]:
        if lv.side == "sell_side" and lv.swept:
            score -= 0.1
            risks.append(f"上方 sell-side 流动性已清洗 @ {lv.price:.6g}")
        if lv.side == "buy_side" and lv.swept:
            score += 0.1
            risks.append(f"下方 buy-side 流动性已清洗 @ {lv.price:.6g}")

    if ctx.orderbook:
        if ctx.obi_smoothed is not None:
            score += ctx.obi_smoothed * 0.12
        elif ctx.orderbook.imbalance > 0.15:
            score += 0.1
        elif ctx.orderbook.imbalance < -0.15:
            score -= 0.1
        if ctx.orderbook.spread_bps > 5:
            risks.append(f"价差偏大 {ctx.orderbook.spread_bps}bps")

    if _is_elevated_vol(ctx.vol_status, ctx.vol_ratio):
        risks.append(f"波动率偏高 ({ctx.vol_status or ctx.vol_ratio})，建议缩小仓位")
        score *= 0.7

    score += _capital_flow_score(ctx, risks)
    score += _btc_regime_score(ctx, risks)
    br = ctx.btc_regime or {}
    if br.get("regime_id") in ("low_vol_range", "mid_vol_range", "high_vol_range"):
        score *= 0.85

    if ctx.macro_hazard_flag or (ctx.btc_regime or {}).get("regime_id") == "macro_frozen_range":
        return _macro_hazard_advice(ctx)

    if score > 0.2:
        bias: Bias = "long"
    elif score < -0.2:
        bias = "short"
    else:
        bias = "neutral"

    confidence = min(abs(score) + 0.3, 0.85)
    atr_proxy = (ctx.ohlcv_summary.get("range_20bar_high", price) - ctx.ohlcv_summary.get("range_20bar_low", price)) / 2
    atr_proxy = atr_proxy if atr_proxy > 0 else price * 0.005

    if bias == "long":
        entry = (price - atr_proxy * 0.3, price)
        sl = price - atr_proxy * 1.2
        tp = [price + atr_proxy * 1.5, price + atr_proxy * 2.5]
    elif bias == "short":
        entry = (price, price + atr_proxy * 0.3)
        sl = price + atr_proxy * 1.2
        tp = [price - atr_proxy * 1.5, price - atr_proxy * 2.5]
    else:
        entry = None
        sl = None
        tp = []

    reasoning_parts = [
        f"SMC 趋势={ctx.smc.trend}",
        f"MSS/CHoCH={ctx.smc.mss_or_choch or '无'}",
    ]
    if ctx.orderbook:
        reasoning_parts.append(f"订单簿 imbalance={ctx.orderbook.imbalance:+.3f}")
    if ctx.capital_flows:
        reasoning_parts.append(_capital_flow_summary(ctx.capital_flows))
    if ctx.btc_regime:
        reasoning_parts.append(
            f"BTC Regime={ctx.btc_regime.get('regime_id')} ({ctx.btc_regime.get('regime_label')})"
        )
    reasoning = "；".join(reasoning_parts) + "。（规则引擎模式，配置 AI_API_KEY 可启用 LLM）"

    return TradeAdvice(
        bias=bias,
        confidence=confidence,
        entry_zone=entry,
        stop_loss=sl,
        take_profit=tp,
        time_horizon="4h-24h",
        reasoning=reasoning,
        risks=risks or ["规则引擎仅供参考，非投资建议"],
        confluence_score=min(abs(score), 1.0),
        rule_based=True,
    )


def _capital_flow_score(ctx: MarketContext, risks: list[str]) -> float:
    cf = ctx.capital_flows
    if not cf:
        return 0.0
    score = 0.0
    base = ctx.symbol.split("/")[0].upper()

    for wallet in (cf.btc_exchange_wallet, cf.eth_exchange_wallet):
        if not wallet or wallet.asset != base:
            continue
        if wallet.net_to_exchange_1d is not None:
            if wallet.net_to_exchange_1d > 0:
                score -= 0.08
                risks.append(f"{wallet.asset} 24h 净流入交易所 {wallet.net_to_exchange_1d:+.2f}（卖压）")
            elif wallet.net_to_exchange_1d < 0:
                score += 0.08
                risks.append(f"{wallet.asset} 24h 净流出交易所 {wallet.net_to_exchange_1d:+.2f}（提币/积累）")

    flows = cf.btc_market_flows if base == "BTC" else cf.eth_market_flows if base == "ETH" else []
    for mf in flows:
        for p in mf.periods:
            if p.period == "24h" and p.netflow_usd is not None:
                if p.netflow_usd > 0:
                    score += 0.06
                elif p.netflow_usd < 0:
                    score -= 0.06
    return score


def _capital_flow_summary(cf) -> str:
    parts: list[str] = []
    for wallet in (cf.btc_exchange_wallet, cf.eth_exchange_wallet):
        if wallet and wallet.net_to_exchange_1d is not None:
            parts.append(f"{wallet.asset}交易所链上1d={wallet.net_to_exchange_1d:+.2f}")
    if cf.btc_onchain and cf.btc_onchain.volume_change_7d_pct is not None:
        parts.append(f"BTC链上量7d={cf.btc_onchain.volume_change_7d_pct:+.1f}%")
    return "资金流:" + ",".join(parts) if parts else "资金流:见上下文"


def _btc_regime_score(ctx: MarketContext, risks: list[str]) -> float:
    br = ctx.btc_regime or {}
    rid = br.get("regime_id")
    score = 0.0
    if rid == "high_vol_uptrend":
        score += 0.25
    elif rid == "fake_breakout_wash":
        score -= 0.2
        risks.append("假突破洗盘：高波突破但现货 CVD 未确认")
    elif rid == "high_vol_downtrend":
        score -= 0.22
    elif rid == "high_vol_self_heal_range":
        score += 0.18
        risks.append("CVD 底背离自愈窗口，可轻仓试多")
    elif rid == "low_vol_uptrend":
        score += 0.12
    elif rid == "low_vol_downtrend":
        score -= 0.12
    elif rid == "mid_vol_uptrend":
        score += 0.14
    return score


def _is_elevated_vol(vol_status: str | None, vol_ratio: float | None) -> bool:
    status = (vol_status or "").lower()
    if status in ("danger", "high", "elevated", "extreme"):
        return True
    if vol_ratio is not None and vol_ratio >= 0.20:
        return True
    return False
