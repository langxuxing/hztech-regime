"""HMM 作为第二意见：趋势分歧时修正置信度，不覆盖主趋势信号。"""

from __future__ import annotations

from typing import Any, Protocol

_HMM_DISAGREE_CAP = 0.55
_HMM_LOW_CONF_CAP = 0.60
_HMM_LOW_CONF_THRESHOLD = 0.50


class _TrendAnalysis(Protocol):
    raw_trend: str
    regime_id: str
    confidence: float
    drivers: list[str]
    hmm_disagrees: bool


def apply_hmm_confidence_modifier(
    analysis: _TrendAnalysis,
    models: dict[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    """
    规则引擎趋势为主；HMM 分歧时降低置信度并标记 hmm_disagrees。

    不修改 raw_trend / regime_id / in_regime_transition。
    """
    meta: dict[str, Any] = {
        "applied": False,
        "disagrees": False,
        "reason": None,
        "hmm_trend": None,
        "rule_trend": analysis.raw_trend,
        "hmm_confidence": None,
        "confidence_before": round(analysis.confidence, 3),
        "confidence_after": round(analysis.confidence, 3),
    }

    hmm = (models or {}).get("hmm")
    if not isinstance(hmm, dict) or hmm.get("error"):
        return analysis, meta

    hmm_trend = str(hmm.get("raw_trend") or "range")
    hmm_conf = float(hmm.get("confidence") or 0.0)
    meta["hmm_trend"] = hmm_trend
    meta["hmm_confidence"] = round(hmm_conf, 3)

    before = analysis.confidence
    note: str | None = None

    if hmm_trend != analysis.raw_trend:
        analysis.confidence = min(analysis.confidence, _HMM_DISAGREE_CAP)
        analysis.hmm_disagrees = True
        meta["applied"] = True
        meta["disagrees"] = True
        meta["reason"] = "trend_disagreement"
        note = f"HMM 趋势分歧: 规则={analysis.raw_trend}, HMM={hmm_trend} → 置信度上限 {_HMM_DISAGREE_CAP:.0%}"
    elif hmm_conf < _HMM_LOW_CONF_THRESHOLD:
        analysis.confidence = min(analysis.confidence, _HMM_LOW_CONF_CAP)
        meta["applied"] = True
        meta["reason"] = "hmm_low_confidence"
        note = f"HMM 置信度偏低 ({hmm_conf:.0%}) → 置信度上限 {_HMM_LOW_CONF_CAP:.0%}"

    if note:
        drivers = list(analysis.drivers)
        if note not in drivers:
            drivers.append(note)
        analysis.drivers = drivers[:14]

    meta["confidence_after"] = round(analysis.confidence, 3)
    meta["note"] = note
    meta["delta"] = round(analysis.confidence - before, 3)
    return analysis, meta
