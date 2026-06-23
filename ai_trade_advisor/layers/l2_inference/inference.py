"""L2 状态识别与推理分类层。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.layers.types import InferenceResult, IngestionBundle
from ai_trade_advisor.layers.l2_inference.correction import (
    apply_slow_variable_correction,
    verify_cvd_breakout,
)
from ai_trade_advisor.layers.l2_inference.rules import apply_hard_rules
from ai_trade_advisor.regime.engine import analyze_btc_regime


def _apply_corrections(
    inference: InferenceResult,
    ingestion: IngestionBundle,
) -> InferenceResult:
    out = apply_hard_rules(inference, ingestion)
    if out.hard_rule_triggered in ("macro_hazard", "liquidation_pulse"):
        return out
    out = apply_slow_variable_correction(out, ingestion)
    return verify_cvd_breakout(out, ingestion)


def run_inference(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    *,
    skip_triad: bool = False,
) -> tuple[InferenceResult, InferenceResult]:
    """
    双轨推理：live（含末根）与 confirmed（df_confirmed）。

    返回 (live_inference, confirmed_inference)。
    """
    ctx = ingestion.ctx
    macro = ingestion.macro
    micro = ingestion.microstructure
    cvd = micro.get("cvd")
    deriv = micro.get("derivatives")

    live_raw = analyze_btc_regime(
        cfg,
        ctx,
        df=ingestion.transform.df_live,
        macro=macro,
        cvd=cvd,
        deriv=deriv,
        skip_triad=skip_triad,
    )

    confirmed_raw = analyze_btc_regime(
        cfg,
        ctx,
        df=ingestion.transform.df_confirmed,
        macro=macro,
        cvd=cvd,
        deriv=deriv,
        skip_triad=True,
    )

    live = _to_inference(live_raw, hard_rule=None)
    confirmed = _to_inference(confirmed_raw, hard_rule=None)
    live = _apply_corrections(live, ingestion)
    confirmed = _apply_corrections(confirmed, ingestion)

    if macro.macro_hazard_flag:
        live.hard_rule_triggered = "macro_hazard"
        confirmed.hard_rule_triggered = "macro_hazard"

    liq_pulse = micro.get("liquidation_pulse") or {}
    if liq_pulse.get("extreme_pulse"):
        live.hard_rule_triggered = live.hard_rule_triggered or "liquidation_pulse"
        live.corrections.append("强平脉冲极端 → 硬规则标记")

    return live, confirmed


def _to_inference(raw, *, hard_rule: str | None) -> InferenceResult:
    model_probs = None
    triad = raw.triad or {}
    hmm = triad.get("hmm") or {}
    probs = hmm.get("state_probs")
    labels = hmm.get("state_labels") or []
    if isinstance(probs, list) and labels:
        model_probs = {
            str(labels[i]): float(probs[i])
            for i in range(min(len(probs), len(labels)))
        }

    return InferenceResult(
        raw=raw,
        regime_id=raw.regime_id,
        regime_label=raw.regime_label,
        confidence=raw.confidence,
        model_probs=model_probs,
        hard_rule_triggered=hard_rule,
        in_transition=raw.in_regime_transition,
    )
