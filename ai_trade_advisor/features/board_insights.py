from __future__ import annotations

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.engine import (
    analyze_btc_regime,
    flow_regime_from_capital,
)
from ai_trade_advisor.models import (
    BoardInsights,
    CapitalFlowsSnapshot,
    MajorEvent,
    MarketContext,
    RegimeJudgment,
    RegimeType,
    TradeAdvice,
    TrendDirection,
    TrendJudgment,
)

_LEGACY_LABELS: dict[RegimeType, str] = {
    "trend_up": "趋势上行 · Risk-On",
    "trend_down": "趋势下行 · Risk-Off",
    "range": "震荡区间",
    "high_vol": "高波动事件期",
    "transition": "Regime 转换中",
    "macro_frozen_range": "宏观熔断 · 强制观望",
    "fake_breakout_wash": "假突破洗盘",
    "high_vol_self_heal": "高波自愈区间",
}

_TREND_LABELS: dict[TrendDirection, str] = {
    "up": "偏多",
    "down": "偏空",
    "sideways": "横盘",
    "correction": "回调/修正",
}


def build_board_insights(
    ctx: MarketContext,
    advice: TradeAdvice,
    *,
    df: pd.DataFrame | None = None,
    cfg: AdvisorConfig | None = None,
) -> BoardInsights:
    asset = ctx.symbol.split("/")[0].upper()
    if asset == "BTC" and ctx.btc_regime:
        regime = _regime_from_btc_analysis(ctx)
    elif asset == "BTC" and cfg is not None:
        analysis = analyze_btc_regime(cfg, ctx, df=df)
        ctx.btc_regime = analysis.to_dict()
        regime = _regime_from_btc_analysis(ctx)
    else:
        vol_regime, structure_regime, flow_regime = _classify_sub_regimes(ctx)
        regime = _legacy_judge_regime(ctx, vol_regime, structure_regime, flow_regime)

    events = _detect_major_events(ctx)
    trend = _judge_trend(ctx, advice, regime, events)
    return BoardInsights(regime=regime, major_events=events, trend=trend)


def _regime_from_btc_analysis(ctx: MarketContext) -> RegimeJudgment:
    r = ctx.btc_regime or {}
    dashboard = r.get("dashboard_regime") or "transition"
    if r.get("in_regime_transition"):
        dashboard = "transition"
    regime_type = _coerce_regime_type(dashboard, r.get("regime_id"))
    vol_regime = {
        "low_vol": "低波动",
        "mid_vol": "中波动",
        "high_vol": "高波动",
    }.get(r.get("vol_bucket") or "", "未知")
    structure = {
        "uptrend": "KAMA+唐奇安多头",
        "downtrend": "KAMA+唐奇安空头",
        "range": "KAMA+唐奇安区间",
    }.get(r.get("raw_trend") or "", "结构不明")
    flow = flow_regime_from_capital(ctx.capital_flows)

    summary = _btc_regime_summary(r)
    triad = r.get("triad") or {}
    if triad.get("summary"):
        summary = f"{summary} {triad['summary']}"

    drivers = list(r.get("drivers") or [])[:8]
    if flow:
        drivers.append(flow)

    conf = float(r.get("confidence") or 0.6)
    if triad.get("fusion_confidence") is not None:
        conf = min(conf, float(triad["fusion_confidence"]) * 0.4 + conf * 0.6)

    return RegimeJudgment(
        regime=regime_type,
        label=r.get("regime_label") or _LEGACY_LABELS.get(regime_type, "Regime"),
        confidence=conf,
        summary=summary,
        vol_regime=vol_regime,
        structure_regime=structure,
        flow_regime=flow,
        drivers=drivers,
        regime_id=r.get("regime_id"),
        raw_trend=r.get("raw_trend"),
        tech_trend=r.get("tech_trend"),
        vol_bucket=r.get("vol_bucket"),
        next_regime_label=r.get("next_regime_label"),
        changepoint_prob=r.get("changepoint_prob"),
        in_regime_transition=bool(r.get("in_regime_transition")),
        triad_summary=triad.get("summary"),
        derivatives=_derivatives_snapshot(r),
    )


def _derivatives_snapshot(r: dict) -> dict:
    deriv = r.get("derivatives_trend") or {}
    return {
        "funding_rate": r.get("funding_rate"),
        "funding_bias": r.get("funding_bias") or deriv.get("funding_bias"),
        "open_interest": r.get("open_interest"),
        "oi_change_pct": r.get("oi_change_pct"),
        "oi_price_sync": r.get("oi_price_sync") or deriv.get("oi_price_sync"),
        "oi_bias": deriv.get("oi_bias"),
        "cvd_trend": r.get("cvd_trend") or deriv.get("cvd_trend"),
        "cvd_slope": deriv.get("cvd_slope"),
        "spot_cvd": r.get("spot_cvd"),
        "spot_cvd_breakout": r.get("spot_cvd_breakout"),
        "cvd_bullish_divergence": r.get("cvd_bullish_divergence"),
        "derivative_votes_bull": deriv.get("derivative_votes_bull"),
        "derivative_votes_bear": deriv.get("derivative_votes_bear"),
        "drivers": deriv.get("drivers") or [],
    }


def _coerce_regime_type(dashboard: str, regime_id: str | None) -> RegimeType:
    if regime_id == "macro_frozen_range":
        return "macro_frozen_range"
    if regime_id == "fake_breakout_wash":
        return "fake_breakout_wash"
    if regime_id == "high_vol_self_heal_range":
        return "high_vol_self_heal"
    if dashboard in _LEGACY_LABELS:
        return dashboard  # type: ignore[return-value]
    return "transition"


def _btc_regime_summary(r: dict) -> str:
    rid = r.get("regime_id", "")
    close = r.get("close")
    if close is None:
        return r.get("regime_label") or "BTC 多维度 Regime 分析"
    if rid == "macro_frozen_range":
        return "宏观公布窗口内强制观望，微观 SMC/CVD 信号全部降权。"
    if rid == "fake_breakout_wash":
        return f"价格突破 KAMA+唐奇安上轨（{close:.0f}），但现货 CVD 未创新高，警惕假突破洗盘。"
    if rid == "high_vol_uptrend":
        return f"高波上涨且现货 CVD 确认，BTC {close:.0f} 上方趋势有效。"
    if rid == "high_vol_self_heal_range":
        return f"虽处下跌结构，5m CVD 底背离 + 现货溢价暗示自愈反弹窗口（{close:.0f}）。"
    if rid == "high_vol_downtrend":
        return f"高波下跌 Regime，{close:.0f} 下方趋势延续，暂无 CVD 背离。"
    if rid == "low_vol_range":
        return f"低波死寂震荡，区间 [{r.get('donchian_lower'):.0f}, {r.get('donchian_upper'):.0f}]。"
    return r.get("regime_label") or "BTC 多维度 Regime 分析"


def _classify_sub_regimes(
    ctx: MarketContext,
) -> tuple[str, str, str | None]:
    vol_regime = "未知"
    if ctx.vol_status:
        status = ctx.vol_status.lower()
        if status in ("elevated", "high", "extreme", "danger"):
            vol_regime = "高波动"
        elif status in ("compressed", "low", "quiet", "normal"):
            vol_regime = "低波动" if status in ("compressed", "low", "quiet") else "正常波动"
        else:
            vol_regime = ctx.vol_status
    elif ctx.vol_ratio is not None:
        if ctx.vol_ratio >= 0.20:
            vol_regime = "高波动"
        elif ctx.vol_ratio <= 0.06:
            vol_regime = "低波动"
        else:
            vol_regime = "正常波动"

    structure_regime = {
        "bullish": "多头结构",
        "bearish": "空头结构",
        "ranging": "区间结构",
    }.get(ctx.smc.trend, "结构不明")

    flow_regime = flow_regime_from_capital(ctx.capital_flows)
    if flow_regime is None and ctx.capital_flows and ctx.capital_flows.eth_exchange_wallet:
        w = ctx.capital_flows.eth_exchange_wallet
        if w.net_to_exchange_1d is not None:
            flow_regime = "ETH 链上净流入交易所" if w.net_to_exchange_1d > 0 else "ETH 链上净流出交易所"
    return vol_regime, structure_regime, flow_regime


def _legacy_judge_regime(
    ctx: MarketContext,
    vol_regime: str,
    structure_regime: str,
    flow_regime: str | None,
) -> RegimeJudgment:
    drivers: list[str] = []
    score_up = score_down = score_range = score_high_vol = 0.0

    if ctx.smc.trend == "bullish":
        score_up += 0.35
        drivers.append("30m 结构呈 Higher High / Higher Low")
    elif ctx.smc.trend == "bearish":
        score_down += 0.35
        drivers.append("30m 结构呈 Lower High / Lower Low")
    else:
        score_range += 0.35
        drivers.append("价格在 20bar 区间内反复，无明显趋势")

    if vol_regime == "高波动":
        score_high_vol += 0.4
        drivers.append(f"波动率状态: {ctx.vol_status or ctx.vol_ratio}")
    elif vol_regime == "低波动":
        score_range += 0.2
        drivers.append("波动率压缩，可能酝酿突破")

    if ctx.smc.mss_or_choch:
        if ctx.smc.mss_direction > 0:
            score_up += 0.2
            drivers.append(f"最新出现 {ctx.smc.mss_or_choch} 看涨")
        elif ctx.smc.mss_direction < 0:
            score_down += 0.2
            drivers.append(f"最新出现 {ctx.smc.mss_or_choch} 看跌")

    if flow_regime and "净流入" in flow_regime:
        score_down += 0.1
        drivers.append("链上/交易所资金净流入（潜在卖压）")
    elif flow_regime and "净流出" in flow_regime:
        score_up += 0.1
        drivers.append("链上/交易所资金净流出（潜在囤币）")

    scores = {
        "trend_up": score_up,
        "trend_down": score_down,
        "range": score_range,
        "high_vol": score_high_vol,
    }
    top = max(scores, key=scores.get)  # type: ignore[arg-type]
    runner = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    confidence = runner[0][1]
    if len(runner) > 1 and abs(runner[0][1] - runner[1][1]) < 0.12:
        top = "transition"
        confidence = 0.45
        drivers.append("多维度信号分歧，Regime 处于切换窗口")

    confidence = min(0.92, max(0.35, confidence + 0.25))
    regime_type: RegimeType = top  # type: ignore[assignment]
    return RegimeJudgment(
        regime=regime_type,
        label=_LEGACY_LABELS[regime_type],
        confidence=confidence,
        summary=_legacy_summary(regime_type, ctx, vol_regime, structure_regime),
        vol_regime=vol_regime,
        structure_regime=structure_regime,
        flow_regime=flow_regime,
        drivers=drivers[:6],
    )


def _legacy_summary(
    regime: RegimeType,
    ctx: MarketContext,
    vol_regime: str,
    structure_regime: str,
) -> str:
    price = ctx.last_price
    if regime == "trend_up":
        return f"当前处于趋势上行 Regime：{structure_regime}，{vol_regime}。价格 {price:.2g} 上方结构占优。"
    if regime == "trend_down":
        return f"当前处于趋势下行 Regime：{structure_regime}，{vol_regime}。价格 {price:.2g} 下方结构占优。"
    if regime == "range":
        hi = ctx.ohlcv_summary.get("range_20bar_high")
        lo = ctx.ohlcv_summary.get("range_20bar_low")
        return f"震荡 Regime：{structure_regime}。关注区间 [{lo}, {hi}] 边界突破。"
    if regime == "high_vol":
        return f"高波动 Regime：{vol_regime}，事件驱动特征明显，趋势信号需降权。"
    return f"Regime 转换期：{structure_regime} 与 {vol_regime} 信号不一致，等待确认。"


def _detect_major_events(ctx: MarketContext) -> list[MajorEvent]:
    events: list[MajorEvent] = []
    idx = 0

    br = ctx.btc_regime or {}
    if br.get("regime_id") == "fake_breakout_wash":
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="regime",
                title="假突破洗盘预警",
                description=br.get("regime_label") or "高波突破但现货 CVD 未确认",
                severity="high",
                impact="bearish",
                timestamp=ctx.as_of,
            )
        )
        idx += 1
    elif br.get("regime_id") == "high_vol_self_heal_range":
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="regime",
                title="CVD 底背离 · 自愈信号",
                description="5m 现货 CVD 底背离，关注反弹",
                severity="medium",
                impact="bullish",
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    if ctx.smc.mss_or_choch:
        impact = "bullish" if ctx.smc.mss_direction > 0 else "bearish" if ctx.smc.mss_direction < 0 else "neutral"
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="structure",
                title=f"{ctx.smc.mss_or_choch} 结构突破",
                description=ctx.smc.structure_notes[0] if ctx.smc.structure_notes else "市场结构发生变化",
                severity="high",
                impact=impact,  # type: ignore[arg-type]
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    recent_sweeps = [lv for lv in ctx.liquidity_levels if lv.swept][-3:]
    for lv in recent_sweeps:
        side_label = "上方流动性" if lv.side == "sell_side" else "下方流动性"
        impact = "bearish" if lv.side == "sell_side" else "bullish"
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="liquidity",
                title=f"{side_label} 清洗",
                description=f"价格 {lv.price:.6g} 附近发生 sweep，强度 {lv.strength:.2f}",
                severity="medium" if lv.strength < 1.5 else "high",
                impact=impact,  # type: ignore[arg-type]
                timestamp=lv.sweep_time,
            )
        )
        idx += 1

    if ctx.macro_hazard_flag:
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="macro",
                title="宏观熔断窗口",
                description="CPI/FOMC/NFP 公布 ±120min，强制观望",
                severity="high",
                impact="neutral",
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    events.extend(_flow_and_onchain_events(ctx, start_idx=idx))

    if not events:
        events.append(
            MajorEvent(
                id="evt-0",
                category="market",
                title="暂无重大事件",
                description="近期无显著结构突破、流动性清洗或链上异动",
                severity="low",
                impact="neutral",
                timestamp=ctx.as_of,
            )
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: severity_rank.get(e.severity, 9))
    return events[:10]


def _flow_and_onchain_events(ctx: MarketContext, *, start_idx: int) -> list[MajorEvent]:
    cf = ctx.capital_flows
    if cf is None:
        return []

    events: list[MajorEvent] = []
    idx = start_idx
    price = ctx.last_price or 0.0

    for oc, asset in ((cf.btc_onchain, "BTC"), (cf.eth_onchain, "ETH")):
        if oc is None or not oc.largest_tx_24h_usd:
            continue
        usd = oc.largest_tx_24h_usd
        if usd < 30_000_000:
            continue
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="onchain",
                title=f"{asset} 大额链上转账",
                description=f"24h 最大单笔约 ${usd / 1e6:.0f}M；{oc.interpretation}",
                severity="high" if usd >= 100_000_000 else "medium",
                impact="neutral",
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    for wallet, asset, ref_price in (
        (cf.btc_exchange_wallet, "BTC", price),
        (cf.eth_exchange_wallet, "ETH", price if ctx.symbol.startswith("ETH") else None),
    ):
        if wallet is None or wallet.net_to_exchange_1d is None:
            continue
        net = wallet.net_to_exchange_1d
        usd_est = abs(net) * ref_price if ref_price else abs(net)
        if asset == "ETH" and ref_price is None:
            usd_est = abs(net) * 3000
        if usd_est < 20_000_000 and abs(net) < 500:
            continue
        inbound = net > 0
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="flow",
                title=f"{asset} 交易所钱包{'净流入' if inbound else '净流出'}",
                description=(
                    f"1d 净{'流入' if inbound else '流出'} {abs(net):,.0f} {asset}"
                    f"（≈ ${usd_est / 1e6:.0f}M），潜在{'卖压' if inbound else '积累'}"
                ),
                severity="high" if usd_est >= 80_000_000 else "medium",
                impact="bearish" if inbound else "bullish",
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    for etf in (cf.btc_etf, cf.eth_etf):
        if etf is None or etf.latest is None:
            continue
        flow = etf.latest.flow_usd
        if abs(flow) < 80_000_000:
            continue
        bullish = flow > 0
        events.append(
            MajorEvent(
                id=f"evt-{idx}",
                category="etf",
                title=f"{etf.asset} Spot ETF {'净流入' if bullish else '净流出'}",
                description=(
                    f"{etf.latest.date} 净流 ${flow / 1e6:+.0f}M；"
                    f"7d 累计 ${(etf.total_7d_usd or 0) / 1e6:+.0f}M"
                ),
                severity="high" if abs(flow) >= 300_000_000 else "medium",
                impact="bullish" if bullish else "bearish",
                timestamp=ctx.as_of,
            )
        )
        idx += 1

    return events


def _judge_trend(
    ctx: MarketContext,
    advice: TradeAdvice,
    regime: RegimeJudgment,
    events: list[MajorEvent],
) -> TrendJudgment:
    if ctx.macro_hazard_flag or regime.regime == "macro_frozen_range":
        snap = ctx.feature_snapshot or {}
        macro = snap.get("macro_hazard") or {}
        active = macro.get("active_events") or []
        return TrendJudgment(
            direction="sideways",
            label="宏观熔断 · 观望",
            confidence=0.25,
            short_term="宏观窗口内横盘",
            medium_term="等待 CPI/FOMC/NFP 落地",
            summary="macro_hazard_flag=True，趋势预测已截断，系统强制观望。",
            key_levels=_levels_from_snapshot(ctx),
            signals=[f"宏观熔断：{e}" for e in active[:3]] or ["宏观数据公布窗口"],
        )

    signals: list[str] = []
    bull = bear = 0.0

    br = ctx.btc_regime or {}
    if br.get("regime_id") == "high_vol_uptrend":
        bull += 1.2
        signals.append("Regime: 高波上涨 + CVD 确认")
    elif br.get("regime_id") == "fake_breakout_wash":
        bear += 0.8
        signals.append("Regime: 假突破洗盘")
    elif br.get("regime_id") == "high_vol_self_heal_range":
        bull += 0.9
        signals.append("Regime: CVD 底背离自愈")
    elif br.get("regime_id") == "high_vol_downtrend":
        bear += 1.0
        signals.append("Regime: 高波下跌")
    elif br.get("raw_trend") == "uptrend":
        bull += 0.7
        signals.append("KAMA+唐奇安偏多")
    elif br.get("raw_trend") == "downtrend":
        bear += 0.7
        signals.append("KAMA+唐奇安偏空")

    if ctx.smc.mss_direction > 0:
        bull += 0.5
    elif ctx.smc.mss_direction < 0:
        bear += 0.5

    for ev in events[:3]:
        if ev.impact == "bullish":
            bull += 0.3
        elif ev.impact == "bearish":
            bear += 0.3

    if advice.bias == "long":
        bull += 0.5
    elif advice.bias == "short":
        bear += 0.5

    if regime.in_regime_transition:
        signals.append(
            f"三型切换窗口：变点 {regime.changepoint_prob or 0:.0%} → 3bar {regime.next_regime_label or '?'}"
        )
        if regime.next_regime_label in ("bull", "crisis"):
            bull += 0.15 if regime.next_regime_label == "bull" else -0.1
        elif regime.next_regime_label == "bear":
            bear += 0.15
    elif regime.next_regime_label:
        signals.append(f"HMM 3bar 预测 → {regime.next_regime_label}")

    hi = float(ctx.ohlcv_summary.get("range_20bar_high") or ctx.last_price * 1.02)
    lo = float(ctx.ohlcv_summary.get("range_20bar_low") or ctx.last_price * 0.98)
    invalidation = advice.stop_loss
    resistance = br.get("donchian_upper") or hi
    support = br.get("donchian_lower") or lo

    net = bull - bear
    if regime.regime in ("range", "macro_frozen_range", "high_vol_self_heal") and abs(net) < 0.8:
        direction: TrendDirection = "sideways"
    elif regime.regime == "high_vol" and abs(net) < 1.2:
        direction = "correction"
    elif net >= 0.8:
        direction = "up"
    elif net <= -0.8:
        direction = "down"
    elif net > 0:
        direction = "correction" if br.get("raw_trend") == "downtrend" else "up"
    else:
        direction = "correction" if br.get("raw_trend") == "uptrend" else "down"

    confidence = min(0.9, max(0.3, advice.confidence * 0.5 + abs(net) * 0.15 + regime.confidence * 0.2))
    if regime.in_regime_transition:
        confidence *= 0.82
    short_term = _horizon_label(direction, "short")
    medium_term = _horizon_label(direction, "medium", regime.regime)
    if regime.in_regime_transition and regime.next_regime_label:
        medium_term = f"切换中，3bar 或转 {regime.next_regime_label}"

    return TrendJudgment(
        direction=direction,
        label=_TREND_LABELS[direction],
        confidence=confidence,
        short_term=short_term,
        medium_term=medium_term,
        summary=(
            f"短周期{short_term}，中周期{medium_term}。"
            f"Regime「{regime.label}」，综合 {len(signals)} 项信号。"
        ),
        key_levels={
            "support": float(support) if support else lo,
            "resistance": float(resistance) if resistance else hi,
            "invalidation": invalidation,
            "kama": br.get("kama"),
        },
        signals=signals[:5],
    )


def _horizon_label(direction: TrendDirection, horizon: str, regime: RegimeType | None = None) -> str:
    if horizon == "short":
        return {
            "up": "延续上攻",
            "down": "延续下探",
            "sideways": "区间内震荡",
            "correction": "短线修正",
        }[direction]
    if regime in ("transition", "macro_frozen_range", "fake_breakout_wash"):
        return "方向待确认"
    return {
        "up": "中期偏多",
        "down": "中期偏空",
        "sideways": "中期盘整",
        "correction": "中期修正后看 Regime",
    }[direction]
