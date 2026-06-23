from __future__ import annotations

import pandas as pd

from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard
from algorithm.hmm import fit_hmm_regime, forecast_transition


def run_hmm_model(df: pd.DataFrame, *, n_states: int = 4) -> RegimeModelResult:
    hmm, trans, state_labels = fit_hmm_regime(df, n_states=n_states)
    transition = forecast_transition(hmm, trans, state_labels, horizon=3)

    label_map = {
        "bull": "低波动上涨",
        "bear": "高波动下跌",
        "range": "平稳震荡",
        "crisis": "危机/极端波动",
    }
    regime_label = f"HMM · {label_map.get(hmm.current_label, hmm.current_label)}"
    state_probs = {
        state_labels[i]: round(float(p), 4)
        for i, p in enumerate(hmm.state_probs)
        if i < len(state_labels)
    }

    drivers = [
        f"隐状态: {hmm.current_label} (conf {hmm.confidence:.0%})",
        f"发射特征: 对数收益 + 滚动波动率 + 动量",
        transition.label,
    ]
    if hmm.error:
        drivers.append(f"降级: {hmm.error}")

    return RegimeModelResult(
        model_id="hmm",
        model_name=MODEL_CATALOG["hmm"],
        regime_label=regime_label,
        regime_id=f"hmm_{hmm.current_label}",
        raw_trend=hmm.raw_trend_hint,
        vol_bucket=hmm.vol_hint,
        dashboard_regime=trend_to_dashboard(hmm.raw_trend_hint, hmm.vol_hint),
        confidence=hmm.confidence,
        state_probs=state_probs,
        next_regime_label=transition.next_label,
        drivers=drivers,
        metadata={
            "n_states": hmm.n_states,
            "model": hmm.model,
            "state_labels": state_labels,
            "transition": transition.to_dict(),
        },
        error=hmm.error,
    )
