"""Advisor 编排入口 — 委托四层 Regime 引擎流水线。"""

from __future__ import annotations

from dataclasses import dataclass

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.layers.l1_ingestion import run_ingestion
from ai_trade_advisor.layers.orchestrator import run_advisor_from_pipeline, run_regime_pipeline
from ai_trade_advisor.models import BoardInsights, MarketContext, TradeAdvice

__all__ = [
    "build_market_context",
    "run_advisor",
    "run_regime_pipeline",
]


@dataclass
class _AntiNoiseBundle:
    macro: MacroHazardState
    gex_engine: GexEngineResult | None
    liquidation: LiquidationGridState


def build_market_context(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> tuple[MarketContext, _AntiNoiseBundle]:
    """L1 多源数据输入（兼容旧签名）。"""
    ing = run_ingestion(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    bundle = _AntiNoiseBundle(
        macro=ing.macro,
        gex_engine=ing.gex_engine,
        liquidation=ing.liquidation,
    )
    return ing.ctx, bundle


def run_advisor(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> tuple[MarketContext, TradeAdvice, str, BoardInsights]:
    ctx, advice, structured, board, _ = run_advisor_from_pipeline(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    return ctx, advice, structured, board
