from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

# HMM label -> trend direction for prediction scoring
_LABEL_TREND = {
    "bull": "uptrend",
    "bear": "downtrend",
    "crisis": "downtrend",
    "range": "range",
    "uptrend": "uptrend",
    "downtrend": "downtrend",
}

_REGIME_COMPAT: dict[str, set[str]] = {
    "trend_up": {"trend_up", "high_vol_uptrend", "low_vol_uptrend", "mid_vol_uptrend"},
    "trend_down": {"trend_down", "high_vol_downtrend", "low_vol_downtrend"},
    "range": {"range", "low_vol_range", "mid_vol_range", "high_vol_range", "macro_frozen_range"},
    "high_vol": {"high_vol", "high_vol_range", "fake_breakout_wash", "high_vol_self_heal"},
    "transition": {"transition", "fake_breakout_wash"},
}


def _trend_score(pred: str | None, truth: str | None) -> float:
    p = (pred or "range").lower()
    t = (truth or "range").lower()
    if p == t:
        return 1.0
    trend_set = {"uptrend", "downtrend"}
    if p in trend_set and t in trend_set:
        return 0.0
    if p == "range" or t == "range":
        return 0.3
    return 0.0


def _regime_score(pred_dashboard: str | None, truth_regime: str | None) -> float:
    p = (pred_dashboard or "transition").lower()
    t = (truth_regime or "range").lower()
    if p == t:
        return 1.0
    compat = _REGIME_COMPAT.get(t, {t})
    if p in compat:
        return 0.85
    for key, vals in _REGIME_COMPAT.items():
        if t in vals and p in vals:
            return 0.7
    return 0.0


def _pred_score(next_label: str | None, human_trend: str | None) -> float | None:
    if not next_label:
        return None
    pred_trend = _LABEL_TREND.get(next_label.lower(), "range")
    return _trend_score(pred_trend, human_trend)


def score_model_against_truth(
    model: dict[str, Any],
    *,
    human_regime: str,
    human_trend: str | None,
    truth_regime: str | None = None,
    truth_trend: str | None = None,
) -> dict[str, Any]:
    """单模型对比真值（人工或 realized）。"""
    regime_truth = truth_regime or human_regime
    trend_truth = truth_trend or human_trend or _human_regime_to_trend(human_regime)

    t_score = _trend_score(model.get("raw_trend"), trend_truth)
    r_score = _regime_score(model.get("dashboard_regime"), regime_truth)
    p_score = _pred_score(model.get("next_regime_label"), trend_truth)

    weights = [0.45, 0.35, 0.20]
    scores = [t_score, r_score]
    if p_score is not None:
        scores.append(p_score)
    else:
        weights = [0.55, 0.45]

    w_sum = sum(weights)
    weighted = sum(s * w / w_sum for s, w in zip(scores, weights, strict=False))

    conf = float(model.get("confidence") or 0.5)
    wrong = weighted < 0.5
    penalty = 0.85 if wrong and conf > 0.7 else 1.0
    total = round(weighted * penalty, 4)

    return {
        "trend_score": round(t_score, 4),
        "regime_score": round(r_score, 4),
        "pred_score": round(p_score, 4) if p_score is not None else None,
        "total_score": total,
        "confidence_penalty": penalty,
        "details": {
            "model_trend": model.get("raw_trend"),
            "truth_trend": trend_truth,
            "model_regime": model.get("dashboard_regime"),
            "truth_regime": regime_truth,
        },
    }


def _human_regime_to_trend(human_regime: str) -> str:
    r = human_regime.lower()
    if r in ("trend_up", "high_vol"):
        return "uptrend"
    if r == "trend_down":
        return "downtrend"
    return "range"


_BIAS_TREND = {
    "long": "uptrend",
    "short": "downtrend",
    "neutral": "range",
}


def advice_to_scorable_model(
    advice: dict[str, Any],
    *,
    board_regime: str | None = None,
) -> dict[str, Any]:
    """将 TradeAdvice JSON 转为可打分的伪模型结构。"""
    bias = (advice.get("bias") or "neutral").lower()
    return {
        "raw_trend": _BIAS_TREND.get(bias, "range"),
        "dashboard_regime": board_regime or "transition",
        "confidence": float(advice.get("confidence") or 0.5),
        "next_regime_label": None,
    }


def score_judgment_instant(judgment: dict[str, Any]) -> list[dict[str, Any]]:
    """对一条人工标注的全部模型快照做即时打分。"""
    preds = judgment.get("model_predictions") or {}
    models = preds.get("models")
    if not isinstance(models, dict):
        models = {}

    human_regime = judgment["human_regime"]
    human_trend = judgment.get("human_trend")
    now = datetime.now(timezone.utc).isoformat()
    out: list[dict[str, Any]] = []

    for model_id, model in models.items():
        if not isinstance(model, dict) or model.get("error"):
            continue
        scored = score_model_against_truth(
            model,
            human_regime=human_regime,
            human_trend=human_trend,
        )
        out.append(
            {
                "judgment_id": judgment["id"],
                "model_id": model_id,
                "score_type": "instant",
                "scored_at": now,
                **scored,
            }
        )

    advice = preds.get("advice")
    board_regime = preds.get("board_regime")
    if isinstance(advice, dict):
        advice_model = advice_to_scorable_model(advice, board_regime=board_regime)
        scored = score_model_against_truth(
            advice_model,
            human_regime=human_regime,
            human_trend=human_trend,
        )
        out.append(
            {
                "judgment_id": judgment["id"],
                "model_id": "trade_advice",
                "score_type": "instant",
                "scored_at": now,
                **scored,
            }
        )
    return out


def score_judgment_forward(
    judgment: dict[str, Any],
    realized: dict[str, Any],
) -> list[dict[str, Any]]:
    """延迟校验：模型快照 vs realized regime。"""
    preds = judgment.get("model_predictions") or {}
    models = preds.get("models")
    if not isinstance(models, dict):
        models = {}

    truth_regime = realized.get("realized_dashboard") or realized.get("realized_regime")
    truth_trend = realized.get("realized_trend")
    now = datetime.now(timezone.utc).isoformat()
    out: list[dict[str, Any]] = []

    for model_id, model in models.items():
        if not isinstance(model, dict) or model.get("error"):
            continue
        scored = score_model_against_truth(
            model,
            human_regime=truth_regime or "range",
            human_trend=truth_trend,
            truth_regime=truth_regime,
            truth_trend=truth_trend,
        )
        out.append(
            {
                "judgment_id": judgment["id"],
                "model_id": model_id,
                "score_type": "forward",
                "scored_at": now,
                **scored,
            }
        )

    human_scored = score_model_against_truth(
        {
            "raw_trend": judgment.get("human_trend") or _human_regime_to_trend(judgment["human_regime"]),
            "dashboard_regime": judgment["human_regime"],
            "confidence": 1.0,
        },
        human_regime=truth_regime or "range",
        human_trend=truth_trend,
        truth_regime=truth_regime,
        truth_trend=truth_trend,
    )
    out.append(
        {
            "judgment_id": judgment["id"],
            "model_id": "_human",
            "score_type": "forward",
            "scored_at": now,
            **human_scored,
            "details": {**(human_scored.get("details") or {}), "meta": "human_forward_score"},
        }
    )

    advice = preds.get("advice")
    if isinstance(advice, dict):
        advice_model = advice_to_scorable_model(
            advice,
            board_regime=preds.get("board_regime"),
        )
        advice_scored = score_model_against_truth(
            advice_model,
            human_regime=truth_regime or "range",
            human_trend=truth_trend,
            truth_regime=truth_regime,
            truth_trend=truth_trend,
        )
        out.append(
            {
                "judgment_id": judgment["id"],
                "model_id": "trade_advice",
                "score_type": "forward",
                "scored_at": now,
                **advice_scored,
            }
        )
    return out
