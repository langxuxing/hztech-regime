from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.regime.triad.bocpd import BocpdResult, detect_changepoint
from ai_trade_advisor.regime.triad.hmm_regime import (
    HmmRegimeResult,
    TransitionForecast,
    fit_hmm_regime,
    forecast_transition,
)


@dataclass
class TriadRegimeFusion:
    bocpd: BocpdResult
    hmm: HmmRegimeResult
    transition: TransitionForecast
    fused_trend: str
    fused_vol: str
    fused_dashboard: str
    fusion_confidence: float
    agreement: float
    in_transition: bool
    summary: str
    drivers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bocpd": self.bocpd.to_dict(),
            "hmm": self.hmm.to_dict(),
            "transition": self.transition.to_dict(),
            "fused_trend": self.fused_trend,
            "fused_vol": self.fused_vol,
            "fused_dashboard": self.fused_dashboard,
            "fusion_confidence": round(self.fusion_confidence, 4),
            "agreement": round(self.agreement, 4),
            "in_transition": self.in_transition,
            "summary": self.summary,
            "drivers": self.drivers,
        }


def triad_from_dataframe(df: pd.DataFrame, *, n_states: int = 4, hazard_lambda: float = 80.0) -> TriadRegimeFusion:
    close = df["close"].astype(float)
    ret = np.log(close / close.shift(1)).dropna().to_numpy()

    bocpd = detect_changepoint(ret, hazard_lambda=hazard_lambda)

    try:
        hmm, trans, labels = fit_hmm_regime(df, n_states=n_states)
        transition = forecast_transition(hmm, trans, labels, horizon=3)
        hmm_error = None
    except Exception as exc:
        hmm = HmmRegimeResult(
            n_states=0,
            current_state=-1,
            current_label="unknown",
            state_probs=[],
            state_labels=[],
            raw_trend_hint="range",
            vol_hint="mid_vol",
            confidence=0.0,
            model="none",
            error=str(exc),
        )
        transition = TransitionForecast(
            horizon_bars=3,
            next_label="unknown",
            next_probs={},
            persistence=0.0,
            switch_risk=1.0,
            label="HMM 不可用",
        )
        hmm_error = str(exc)

    return _fuse_triad_only(bocpd, hmm, transition, hmm_error=hmm_error)


def fuse_regime_triad(
    df: pd.DataFrame,
    rule: dict[str, Any],
    *,
    n_states: int = 4,
    hazard_lambda: float = 80.0,
) -> TriadRegimeFusion:
    triad = triad_from_dataframe(df, n_states=n_states, hazard_lambda=hazard_lambda)
    return _apply_rule_overlay(triad, rule)


def _fuse_triad_only(
    bocpd: BocpdResult,
    hmm: HmmRegimeResult,
    transition: TransitionForecast,
    *,
    hmm_error: str | None = None,
) -> TriadRegimeFusion:
    drivers = [
        f"BOCPD: {bocpd.label}",
        f"HMM({hmm.model}): {hmm.current_label} conf={hmm.confidence:.0%}",
        transition.label,
    ]
    if hmm_error:
        drivers.append(f"HMM 降级: {hmm_error}")

    fused_trend = hmm.raw_trend_hint
    fused_vol = hmm.vol_hint
    agreement = hmm.confidence

    if bocpd.in_transition:
        fused_dashboard = "transition"
        fusion_conf = max(0.25, hmm.confidence * 0.55)
    else:
        fused_dashboard = _trend_to_dashboard(fused_trend, fused_vol)
        fusion_conf = min(0.88, hmm.confidence * 0.65 + (1.0 - bocpd.changepoint_prob) * 0.25)

    summary = (
        f"三型融合：HMM→{hmm.current_label}，"
        f"变点概率 {bocpd.changepoint_prob:.0%}，"
        f"3bar 预测→{transition.next_label}。"
    )

    return TriadRegimeFusion(
        bocpd=bocpd,
        hmm=hmm,
        transition=transition,
        fused_trend=fused_trend,
        fused_vol=fused_vol,
        fused_dashboard=fused_dashboard,
        fusion_confidence=fusion_conf,
        agreement=agreement,
        in_transition=bocpd.in_transition or transition.switch_risk > 0.45,
        summary=summary,
        drivers=drivers,
    )


def _apply_rule_overlay(triad: TriadRegimeFusion, rule: dict[str, Any]) -> TriadRegimeFusion:
    """规则引擎 (KAMA/CVD) 与三型 ML 投票融合。"""
    rule_trend = rule.get("raw_trend") or "range"
    rule_vol = rule.get("vol_bucket") or "mid_vol"
    rule_id = rule.get("regime_id") or ""
    rule_conf = float(rule.get("confidence") or 0.6)
    rule_dashboard = rule.get("dashboard_regime") or "transition"

    hmm_trend = triad.hmm.raw_trend_hint
    votes_trend = [rule_trend, _hint_to_raw(hmm_trend)]
    agree_trend = votes_trend[0] == votes_trend[1] or votes_trend[1] == "range"

    drivers = list(triad.drivers)
    drivers.append(f"规则引擎: {rule_id} ({rule_trend}/{rule_vol})")

    in_transition = triad.in_transition or rule_dashboard == "transition"
    if not agree_trend and not in_transition:
        in_transition = True
        drivers.append("规则与 HMM 趋势分歧 → 标记 transition")

    if rule_id == "macro_frozen_range":
        fused_dashboard = "range"
        fusion_conf = max(rule_conf, triad.fusion_confidence * 0.5)
    elif in_transition:
        fused_dashboard = "transition"
        fusion_conf = min(rule_conf, triad.fusion_confidence) * 0.78
    elif agree_trend:
        fused_dashboard = rule_dashboard
        fusion_conf = min(0.92, rule_conf * 0.55 + triad.fusion_confidence * 0.45)
    else:
        fused_dashboard = triad.fused_dashboard
        fusion_conf = (rule_conf + triad.fusion_confidence) / 2.0 * 0.85

    fused_trend = rule_trend if rule_conf >= triad.hmm.confidence else hmm_trend
    fused_vol = rule_vol if rule_vol != "mid_vol" else triad.fused_vol

    agreement = (
        (1.0 if agree_trend else 0.45)
        * (1.0 - triad.bocpd.changepoint_prob * 0.5)
        * max(triad.hmm.confidence, 0.3)
    )

    summary = (
        f"{triad.summary} "
        f"规则={rule_id}；融合 dashboard={fused_dashboard}，置信 {fusion_conf:.0%}。"
    )

    return TriadRegimeFusion(
        bocpd=triad.bocpd,
        hmm=triad.hmm,
        transition=triad.transition,
        fused_trend=fused_trend,
        fused_vol=fused_vol,
        fused_dashboard=fused_dashboard,
        fusion_confidence=fusion_conf,
        agreement=agreement,
        in_transition=in_transition,
        summary=summary,
        drivers=drivers[:10],
    )


def _trend_to_dashboard(trend: str, vol: str) -> str:
    if vol == "high_vol":
        if trend == "uptrend":
            return "trend_up"
        if trend == "downtrend":
            return "trend_down"
        return "high_vol"
    if trend == "uptrend":
        return "trend_up"
    if trend == "downtrend":
        return "trend_down"
    return "range"


def _hint_to_raw(hint: str) -> str:
    return {"uptrend": "uptrend", "downtrend": "downtrend"}.get(hint, "range")
