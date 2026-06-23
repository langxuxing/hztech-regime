"""L2 状态识别与推理分类层编排。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.layers.l2_inference.correction import (
    apply_slow_variable_correction,
    verify_cvd_breakout,
)
from ai_trade_advisor.layers.l2_inference.rules import apply_hard_rules
from ai_trade_advisor.layers.types import InferenceResult, IngestionBundle
from ai_trade_advisor.regime.engine import analyze_btc_regime


def run_inference(cfg: AdvisorConfig, ingestion: IngestionBundle) -> InferenceResult:
    """数学模型 + 硬规则 + 慢变量纠偏 + CVD 验证。"""
    asset = cfg.symbol.split("/")[0].upper()
    if asset != "BTC":
        return InferenceResult(
            raw=None,
            regime_id="mid_vol_range",
            regime_label="非 BTC 标的 · 默认震荡",
            confidence=0.50,
            corrections=["仅 BTC 主链启用完整 Regime 引擎"],
        )

    raw = analyze_btc_regime(
        cfg,
        ingestion.ctx,
        df=ingestion.transform.df_confirmed,
        macro=ingestion.macro,
        cvd=ingestion.microstructure.get("cvd"),
        deriv=ingestion.microstructure.get("derivatives"),
    )
    ingestion.ctx.btc_regime = raw.to_dict()

    model_probs = None
    if raw.triad and raw.triad.get("hmm"):
        hmm = raw.triad["hmm"]
        if isinstance(hmm, dict) and hmm.get("state_probs"):
            model_probs = hmm["state_probs"]

    inference = InferenceResult(
        raw=raw,
        regime_id=raw.regime_id,
        regime_label=raw.regime_label,
        confidence=raw.confidence,
        model_probs=model_probs,
        in_transition=raw.in_regime_transition,
    )

    inference = apply_hard_rules(inference, ingestion)
    if inference.hard_rule_triggered not in ("macro_hazard", "liquidation_pulse"):
        inference = apply_slow_variable_correction(inference, ingestion)
        inference = verify_cvd_breakout(inference, ingestion)

    if inference.raw and inference.regime_id != inference.raw.regime_id:
        inference.raw.regime_id = inference.regime_id
        inference.raw.regime_label = inference.regime_label
        inference.raw.confidence = inference.confidence
        ingestion.ctx.btc_regime = inference.raw.to_dict()

    return inference
