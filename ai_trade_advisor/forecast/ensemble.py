from __future__ import annotations

from datetime import datetime, timezone

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.macro_calendar_engine import evaluate_macro_hazard
from ai_trade_advisor.forecast.models import PredictionDirection, PredictionSignal, TrendConsensus
from ai_trade_advisor.datasource.forecast_sources import DEFAULT_FETCHERS, funding_to_prediction_signal
from ai_trade_advisor.datasource.funding_snapshot import fetch_funding_snapshot

_DIRECTION_LABELS: dict[PredictionDirection, str] = {
    "up": "集成偏多",
    "down": "集成偏空",
    "neutral": "集成中性",
}

# 来源权重：预测市场与主动流短周期权重略高
_SOURCE_WEIGHTS: dict[str, float] = {
    "polymarket_15m": 0.5,
    "binance_taker": 1.1,
    "binance_top_trader": 1.0,
    "binance_global": 0.9,
    "okx_account_ratio": 0.95,
    "funding_snapshot": 0.9,
    "alternative.me": 0.75,
}


def fetch_trend_consensus(
    asset: str = "BTC",
    *,
    coinglass_api_key: str = "",
    cfg: AdvisorConfig | None = None,
) -> TrendConsensus:
    cfg = cfg or AdvisorConfig.from_env()
    macro = evaluate_macro_hazard(cfg)
    if macro.macro_hazard_flag:
        return _macro_hazard_consensus(asset, macro)

    signals: list[PredictionSignal] = []
    for _name, fetcher in DEFAULT_FETCHERS:
        signals.append(fetcher())

    try:
        snap = fetch_funding_snapshot(cfg, coinglass_api_key=cfg.coinglass_api_key)
        signals.append(funding_to_prediction_signal(snap))
    except Exception:
        pass

    return aggregate_signals(signals, asset=asset, macro_hazard=False)


def _macro_hazard_consensus(asset: str, macro) -> TrendConsensus:
    as_of = datetime.now(timezone.utc).isoformat()
    events = "；".join(macro.active_events) if macro.active_events else "宏观数据公布窗口"
    return TrendConsensus(
        as_of=as_of,
        asset=asset,
        direction="neutral",
        label="宏观熔断 · 观望",
        score=0.0,
        confidence=0.25,
        agreement=1.0,
        bullish_count=0,
        bearish_count=0,
        neutral_count=0,
        sources_ok=0,
        sources_failed=0,
        summary=f"macro_hazard_flag=True：{events}。微观技术面与筹码面信号已截断。",
        signals=[],
        macro_hazard_flag=True,
    )


def aggregate_signals(
    signals: list[PredictionSignal],
    *,
    asset: str = "BTC",
    macro_hazard: bool = False,
) -> TrendConsensus:
    as_of = datetime.now(timezone.utc).isoformat()
    ok = [s for s in signals if not s.error]
    failed = [s for s in signals if s.error]

    if not ok:
        return TrendConsensus(
            as_of=as_of,
            asset=asset,
            direction="neutral",
            label="无可用信号",
            score=0.0,
            confidence=0.0,
            agreement=0.0,
            bullish_count=0,
            bearish_count=0,
            neutral_count=len(signals),
            sources_ok=0,
            sources_failed=len(failed),
            summary="所有外部数据源均不可用，无法形成集成判断。",
            signals=signals,
        )

    weighted_sum = 0.0
    weight_total = 0.0
    for s in ok:
        w = _SOURCE_WEIGHTS.get(s.source, 1.0) * s.confidence
        weighted_sum += s.score * w
        weight_total += w

    score = weighted_sum / weight_total if weight_total else 0.0
    direction: PredictionDirection
    if score >= 0.12:
        direction = "up"
    elif score <= -0.12:
        direction = "down"
    else:
        direction = "neutral"

    bullish = sum(1 for s in ok if s.direction == "up")
    bearish = sum(1 for s in ok if s.direction == "down")
    neutral = sum(1 for s in ok if s.direction == "neutral")
    majority = max(bullish, bearish, neutral)
    agreement = majority / len(ok)

    avg_conf = sum(s.confidence for s in ok) / len(ok)
    confidence = min(0.92, avg_conf * (0.55 + agreement * 0.45))

    by_cat: dict[str, list[PredictionSignal]] = {}
    for s in ok:
        by_cat.setdefault(s.category, []).append(s)

    cat_bits = []
    for cat, items in sorted(by_cat.items()):
        cat_score = sum(i.score for i in items) / len(items)
        cat_bits.append(f"{cat}={cat_score:+.2f}")

    summary = (
        f"共 {len(ok)}/{len(signals)} 个来源可用；"
        f"看多 {bullish} / 看空 {bearish} / 中性 {neutral}；"
        f"集成得分 {score:+.3f}（{'、'.join(cat_bits)}）。"
    )

    return TrendConsensus(
        as_of=as_of,
        asset=asset,
        direction=direction,
        label=_DIRECTION_LABELS[direction],
        score=score,
        confidence=confidence,
        agreement=agreement,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        sources_ok=len(ok),
        sources_failed=len(failed),
        summary=summary,
        signals=signals,
        macro_hazard_flag=macro_hazard,
    )


def fetch_from_config(cfg: AdvisorConfig | None = None) -> TrendConsensus:
    cfg = cfg or AdvisorConfig.from_env()
    return fetch_trend_consensus(coinglass_api_key=cfg.coinglass_api_key, cfg=cfg)
