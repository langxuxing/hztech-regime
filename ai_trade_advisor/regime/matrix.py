"""Regime 2×3 矩阵与 HMM 概率序列化。"""

from __future__ import annotations

from typing import Any


def _cell_from_axes(raw_trend: str | None, vol_bucket: str | None) -> str:
    trend = (raw_trend or "range").lower()
    vol = (vol_bucket or "mid_vol").lower()
    high_vol = vol in ("high_vol", "mid_vol")

    if trend == "uptrend":
        return "high_vol_uptrend" if high_vol else "low_vol_uptrend"
    if trend == "downtrend":
        return "high_vol_downtrend" if high_vol else "low_vol_downtrend"
    return "high_vol_range" if high_vol else "low_vol_range"


def build_regime_matrix(regime: dict[str, Any]) -> dict[str, Any]:
    """从 btc_regime 字典构建矩阵 payload。"""
    live_id = regime.get("live_regime_id") or regime.get("regime_id") or ""
    confirmed = (
        regime.get("confirmation", {})
        .get("combined", {})
        .get("confirmed_regime_id")
    ) or live_id

    raw_trend = regime.get("raw_trend")
    vol_bucket = regime.get("vol_bucket")
    current_cell = live_id or _cell_from_axes(raw_trend, vol_bucket)
    confirmed_cell = confirmed or _cell_from_axes(raw_trend, vol_bucket)

    history: list[dict[str, Any]] = []
    if raw_trend and vol_bucket:
        history.append(
            {
                "cell": current_cell,
                "trend": _trend_coord(raw_trend),
                "vol": _vol_coord(vol_bucket),
            }
        )

    return {
        "current_cell": current_cell,
        "confirmed_cell": confirmed_cell,
        "live_coords": {
            "trend": _trend_coord(raw_trend),
            "vol": _vol_coord(vol_bucket),
        },
        "history_points": history,
    }


def build_hmm_probs(regime: dict[str, Any]) -> dict[str, float]:
    """将 Triad HMM 状态概率映射到 6 象限 regime_id。"""
    triad = regime.get("triad") or {}
    hmm = triad.get("hmm") or {}
    probs = hmm.get("state_probs") or []
    labels = hmm.get("state_labels") or []
    vol_hint = (hmm.get("vol_hint") or regime.get("vol_bucket") or "mid_vol").lower()

    if not probs or not labels:
        rid = regime.get("regime_id")
        if rid:
            return {rid: float(regime.get("confidence") or 0.5)}
        return {}

    mapping: dict[str, float] = {}
    for label, p in zip(labels, probs, strict=False):
        cell = _hmm_label_to_cell(str(label), vol_hint)
        mapping[cell] = mapping.get(cell, 0.0) + float(p)

    total = sum(mapping.values())
    if total > 0:
        mapping = {k: round(v / total, 4) for k, v in mapping.items()}
    return mapping


def enrich_regime_dict(regime: dict[str, Any]) -> dict[str, Any]:
    out = dict(regime)
    out["matrix"] = build_regime_matrix(out)
    out["hmm_probs"] = build_hmm_probs(out)
    return out


def _trend_coord(raw_trend: str | None) -> float:
    return {"uptrend": 0.8, "downtrend": -0.8, "range": 0.0}.get(
        (raw_trend or "range").lower(), 0.0
    )


def _vol_coord(vol_bucket: str | None) -> float:
    return {"low_vol": 0.25, "mid_vol": 0.55, "high_vol": 0.85}.get(
        (vol_bucket or "mid_vol").lower(), 0.55
    )


def _hmm_label_to_cell(label: str, vol_hint: str) -> str:
    high = vol_hint in ("high_vol", "mid_vol")
    return {
        "bull": "high_vol_uptrend" if high else "low_vol_uptrend",
        "bear": "high_vol_downtrend" if high else "low_vol_downtrend",
        "range": "high_vol_range" if high else "low_vol_range",
        "crisis": "high_vol_range",
    }.get(label.lower(), "mid_vol_range")
