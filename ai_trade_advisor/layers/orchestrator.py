"""四层 Regime 引擎编排入口。"""

from __future__ import annotations

from ai_trade_advisor.ai.advisor import generate_advice
from ai_trade_advisor.black_swan.engine import evaluate_black_swan_alert
from ai_trade_advisor.black_swan.pipeline import (
    apply_black_swan_after_confirmation,
    evaluate_black_swan_fast,
)
from ai_trade_advisor.bigevent.engine import load_pipeline_event_context
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.context.builder import build_structured_context
from ai_trade_advisor.features.board_insights import build_board_insights
from ai_trade_advisor.features.chart_payload import build_chart_payload
from ai_trade_advisor.features.feature_aggregator import build_feature_snapshot
from ai_trade_advisor.features.trading_brief import build_trading_brief
from ai_trade_advisor.features.unified_events import build_unified_events
from ai_trade_advisor.layers.l1_ingestion.bundle import run_ingestion
from ai_trade_advisor.layers.l2_inference.inference import run_inference
from ai_trade_advisor.layers.l3_confirmation.engine import run_l3_pipeline
from ai_trade_advisor.layers.l4_execution.execution import run_execution
from ai_trade_advisor.layers.types import PipelineMetadata, RegimePipelineResult
from ai_trade_advisor.models import BoardInsights, MarketContext, TradeAdvice
from ai_trade_advisor.regime.matrix import enrich_regime_dict
from ai_trade_advisor.signal.debouncer import compute_orderbook_obi, smooth_obi


def run_regime_pipeline(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> tuple[RegimePipelineResult, MarketContext, TradeAdvice, str, BoardInsights]:
    """完整四层流水线：L1 输入 → L2 推理 → L3 防抖 → L4 路由 + 黑天鹅预警。"""
    ingestion = run_ingestion(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    ctx = ingestion.ctx
    ctx.chart = build_chart_payload(
        ingestion.transform.df_confirmed,
        ingestion.market,
        ctx,
    )

    upcoming_count, upcoming_events = load_pipeline_event_context()

    live_inf, confirmed_inf = run_inference(cfg, ingestion)
    live_raw = live_inf.raw
    confirmed_raw = confirmed_inf.raw

    asset = cfg.symbol.split("/")[0].upper()
    sym_key = f"{cfg.exchange}:{cfg.symbol}"
    asset_is_btc = asset == "BTC" and live_raw is not None and confirmed_raw is not None

    if asset_is_btc:
        ctx.btc_regime = enrich_regime_dict(live_raw.to_dict())
        fast_alert = evaluate_black_swan_fast(
            cfg,
            ingestion,
            live_raw=live_raw,
            upcoming_high_impact=upcoming_count,
        )
        if fast_alert.suspended:
            ctx.macro_hazard_flag = True
    else:
        fast_alert = evaluate_black_swan_alert(
            macro=ingestion.macro,
            liquidation=ingestion.liquidation,
        )
        ctx.black_swan_alert = fast_alert.to_dict()

    obi_state = None
    if ctx.orderbook:
        raw_obi = compute_orderbook_obi(ctx.orderbook)
        obi_state = smooth_obi(raw_obi, symbol_key=sym_key)
        ctx.obi_smoothed = obi_state.smoothed

    raw_advice = generate_advice(cfg, ctx)
    if ctx.macro_hazard_flag or fast_alert.suspended:
        raw_advice = _apply_hazard_lock(raw_advice, fast_alert)

    ctx.trading_brief = build_trading_brief(ctx, raw_advice)

    confirmation, advice = run_l3_pipeline(
        cfg,
        ingestion,
        live_raw=live_raw if asset_is_btc else None,
        confirmed_raw=confirmed_raw if asset_is_btc else None,
        raw_advice=raw_advice,
        symbol_key=sym_key,
        obi_state=obi_state,
        asset_is_btc=asset_is_btc,
    )

    if asset_is_btc:
        alert = apply_black_swan_after_confirmation(
            cfg,
            ctx,
            ingestion,
            confirmation,
            live_regime=ctx.btc_regime,
            live_raw=live_raw,
            fast_alert=fast_alert,
            upcoming_high_impact=upcoming_count,
        )
    else:
        alert = fast_alert

    ctx.trading_brief = build_trading_brief(ctx, advice)

    snapshot = build_feature_snapshot(
        ctx,
        macro=ingestion.macro,
        gex_engine=ingestion.gex_engine,
        liquidation=ingestion.liquidation,
        debouncer=confirmation.debouncer,
    )
    ctx.feature_snapshot = snapshot.to_dict()

    execution = run_execution(
        cfg,
        ingestion,
        confirmation,
        alert,
        advice=advice,
        feature_snapshot=snapshot,
        upcoming_high_impact=upcoming_count,
    )
    ctx.quant_state = execution.quant_state.to_dict()
    if ctx.black_swan_alert:
        ctx.quant_state["black_swan"] = ctx.black_swan_alert

    metadata = PipelineMetadata(
        stage="production",
        flow=[
            "L1 多源数据输入",
            "L1 特征变频 / df_confirmed",
            "L2 HMM + 硬规则推理",
            "L2.5a 快变量黑天鹅（宏观/强平/变点）",
            "L3 转置惩罚 + 驻留防抖",
            "L2.5b 确认后实用策略 + 熔断",
            "L4 策略路由 / 参数微调",
        ],
        layers={
            "ingestion": ingestion.to_dict(),
            "inference_live": live_inf.to_dict(),
            "inference_confirmed": confirmed_inf.to_dict(),
            "confirmation": confirmation.to_dict(),
            "black_swan_fast": fast_alert.to_dict(),
            "black_swan": alert.to_dict(),
            "execution": execution.to_dict(),
        },
    )

    result = RegimePipelineResult(
        ingestion=ingestion,
        inference=live_inf,
        confirmation=confirmation,
        execution=execution,
        advice=advice,
        metadata=metadata,
    )

    structured = build_structured_context(ctx)
    board = build_board_insights(ctx, advice, cfg=cfg)
    ctx.unified_events = build_unified_events(board.major_events, upcoming_events)
    ctx.pipeline = metadata.to_dict()
    return result, ctx, advice, structured, board


def run_advisor_from_pipeline(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> tuple[MarketContext, TradeAdvice, str, BoardInsights, RegimePipelineResult]:
    """run_advisor 使用的完整流水线包装。"""
    result, ctx, advice, structured, board = run_regime_pipeline(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    return ctx, advice, structured, board, result


def _apply_hazard_lock(advice: TradeAdvice, alert) -> TradeAdvice:
    from ai_trade_advisor.models import TradeAdvice as TA

    reason = alert.suspend_reason or "宏观/黑天鹅熔断窗口"
    risks = list(advice.risks) + [f"熔断: {reason}"]
    return TA(
        bias="neutral",
        confidence=min(advice.confidence, 0.3),
        entry_zone=None,
        stop_loss=None,
        take_profit=[],
        time_horizon=advice.time_horizon,
        reasoning="熔断窗口内不建议开仓。",
        risks=risks,
        confluence_score=min(advice.confluence_score, 0.25),
        raw_llm=advice.raw_llm,
        rule_based=advice.rule_based,
    )
