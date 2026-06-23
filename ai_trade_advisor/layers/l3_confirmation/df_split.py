"""L3 已确认 vs 实时概率隔离。"""

from __future__ import annotations

from ai_trade_advisor.layers.types import ConfirmationState, InferenceResult, IngestionBundle


def apply_df_confirmation(
    confirmation: ConfirmationState,
    inference: InferenceResult,
    ingestion: IngestionBundle,
) -> ConfirmationState:
    """
    df_confirmed 机制：confirmed_regime 仅基于已收盘 K 线推理；
    live_regime_id 保留秒级/末根概率供监控。
    """
    notes = list(confirmation.notes)
    if ingestion.transform.dropped_unclosed:
        notes.append("confirmed 基于剔除末根后的 df_confirmed")
    else:
        notes.append("末根已收盘，live 与 confirmed 同源")

    if inference.model_probs:
        notes.append(f"HMM 实时概率：{inference.model_probs}")

    return ConfirmationState(
        combined=confirmation.combined,
        transition_penalty_applied=confirmation.transition_penalty_applied,
        dwell_bars=confirmation.dwell_bars,
        min_dwell_bars=confirmation.min_dwell_bars,
        regime_switched=confirmation.regime_switched,
        debouncer=confirmation.debouncer,
        advice_locked=confirmation.advice_locked,
        notes=notes,
    )
