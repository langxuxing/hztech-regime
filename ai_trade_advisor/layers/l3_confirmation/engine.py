"""L3 信号防抖编排（Regime + Advice）。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.layers.l3_confirmation.df_split import apply_df_confirmation
from ai_trade_advisor.layers.l3_confirmation.regime_stabilizer import stabilize_regime
from ai_trade_advisor.layers.types import CombinedRegimeStatus, ConfirmationState, InferenceResult, IngestionBundle
from ai_trade_advisor.models import TradeAdvice
from ai_trade_advisor.regime.confirmation import confirm_regime_state
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis
from ai_trade_advisor.signal.debouncer import DebouncerState, debounce_orderbook_and_advice


def confirm_btc_regime(
    *,
    symbol_key: str,
    live: BtcRegimeAnalysis,
    confirmed: BtcRegimeAnalysis,
    min_dwell_bars: int,
    transition_penalty: float,
) -> ConfirmationState:
    """BTC 双轨 Regime 确认（live + df_confirmed）。"""
    return confirm_regime_state(
        symbol_key=symbol_key,
        live=live,
        confirmed=confirmed,
        min_dwell_bars=min_dwell_bars,
        transition_penalty=transition_penalty,
    )


def non_btc_regime_confirmation() -> ConfirmationState:
    """非 BTC 标的的占位确认状态。"""
    return ConfirmationState(
        combined=CombinedRegimeStatus(
            live_regime_id="n/a",
            confirmed_regime_id="n/a",
            regime_label="非 BTC 标的",
            confidence=0.0,
            dashboard_regime="transition",
        ),
    )


def debounce_advice(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    advice: TradeAdvice,
    *,
    symbol_key: str,
    obi_state=None,
) -> tuple[TradeAdvice, DebouncerState]:
    """Advice 信号冷却与订单簿防抖。"""
    cooldown = cfg.signal_cooldown_min_sec
    if advice.confidence >= 0.75:
        cooldown = cfg.signal_cooldown_max_sec

    return debounce_orderbook_and_advice(
        ingestion.ctx.orderbook,
        advice,
        symbol_key=symbol_key,
        cooldown_sec=cooldown,
        obi_state=obi_state,
    )


def attach_debouncer(
    confirmation: ConfirmationState,
    debouncer: DebouncerState,
) -> ConfirmationState:
    """将 Advice 防抖状态附加到 Regime 确认结果。"""
    return ConfirmationState(
        combined=confirmation.combined,
        transition_penalty_applied=confirmation.transition_penalty_applied,
        dwell_bars=confirmation.dwell_bars,
        min_dwell_bars=confirmation.min_dwell_bars,
        regime_switched=confirmation.regime_switched,
        debouncer=debouncer,
        advice_locked=debouncer.cooldown_active,
        notes=confirmation.notes,
    )


def run_l3_pipeline(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    *,
    live_raw: BtcRegimeAnalysis | None,
    confirmed_raw: BtcRegimeAnalysis | None,
    raw_advice: TradeAdvice,
    symbol_key: str,
    obi_state=None,
    asset_is_btc: bool = True,
) -> tuple[ConfirmationState, TradeAdvice]:
    """
    L3 统一入口：Regime 确认 + Advice 防抖。

    BTC 使用双轨 confirm_regime_state；非 BTC 使用占位状态。
    """
    if asset_is_btc and live_raw is not None and confirmed_raw is not None:
        confirmation = confirm_btc_regime(
            symbol_key=symbol_key,
            live=live_raw,
            confirmed=confirmed_raw,
            min_dwell_bars=cfg.regime_min_dwell_bars,
            transition_penalty=cfg.regime_transition_penalty,
        )
    else:
        confirmation = non_btc_regime_confirmation()

    advice, debouncer = debounce_advice(
        cfg,
        ingestion,
        raw_advice,
        symbol_key=symbol_key,
        obi_state=obi_state,
    )
    return attach_debouncer(confirmation, debouncer), advice


def run_confirmation(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    inference: InferenceResult,
    advice: TradeAdvice,
    *,
    symbol_key: str,
    obi_state=None,
    confirmed_inference: InferenceResult | None = None,
) -> tuple[ConfirmationState, TradeAdvice]:
    """单轨推理场景的 Regime 防抖 + Advice 冷却（回测/测试用，与生产同 confirm_regime_state）。"""
    raw = inference.raw
    confirmed_raw = (confirmed_inference.raw if confirmed_inference else None) or raw

    if raw is not None and confirmed_raw is not None:
        confirmation = confirm_regime_state(
            symbol_key=symbol_key,
            live=raw,
            confirmed=confirmed_raw,
            min_dwell_bars=cfg.regime_min_dwell_bars,
            transition_penalty=cfg.regime_transition_penalty,
        )
        confirmation = apply_df_confirmation(confirmation, inference, ingestion)
    else:
        confirmation = stabilize_regime(
            inference,
            symbol_key=symbol_key,
            bar_minutes=cfg.bar_minutes,
            min_dwell_bars=cfg.regime_min_dwell_bars,
        )
        confirmation = apply_df_confirmation(confirmation, inference, ingestion)

    locked_advice, debouncer = debounce_advice(
        cfg,
        ingestion,
        advice,
        symbol_key=symbol_key,
        obi_state=obi_state,
    )
    return attach_debouncer(confirmation, debouncer), locked_advice
