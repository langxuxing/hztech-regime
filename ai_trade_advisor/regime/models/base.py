from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MODEL_CATALOG: dict[str, str] = {
    "heuristic": "启发式规则 · KAMA/唐奇安/CVD",
    "hmm": "隐马尔可夫模型 · HMM",
    "clustering": "聚类 · K-Means / GMM",
    "msar": "马尔可夫转换自回归 · MS-AR",
    "heuristic_advanced": "传统启发式 · 挤压/ADX/均线",
    "hybrid": "组合模型 · HMM + 序列转移",
    "crypto_lstm": "akash LSTM · CryptoMarket_Regime_Classifier",
    "jayd_regime": "jayd DT+HMM · Market-Regime-Modeling",
    "trade_advice": "LLM/规则交易建议",
}


@dataclass
class RegimeModelResult:
    model_id: str
    model_name: str
    regime_label: str
    regime_id: str | None
    raw_trend: str
    vol_bucket: str
    dashboard_regime: str
    confidence: float
    state_probs: dict[str, float] | None = None
    next_regime_label: str | None = None
    changepoint_prob: float | None = None
    drivers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "regime_label": self.regime_label,
            "regime_id": self.regime_id,
            "raw_trend": self.raw_trend,
            "vol_bucket": self.vol_bucket,
            "dashboard_regime": self.dashboard_regime,
            "confidence": round(self.confidence, 4),
            "state_probs": self.state_probs,
            "next_regime_label": self.next_regime_label,
            "changepoint_prob": self.changepoint_prob,
            "drivers": self.drivers,
            "metadata": self.metadata,
            "error": self.error,
        }


def trend_to_dashboard(trend: str, vol: str) -> str:
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


def vol_from_label(label: str) -> str:
    if label in ("crisis", "high_vol_squeeze"):
        return "high_vol"
    if label in ("bear", "bull"):
        return "low_vol"
    return "mid_vol"


def trend_from_label(label: str) -> str:
    if label in ("bull", "low_vol_uptrend", "uptrend", "bull_ma"):
        return "uptrend"
    if label in ("bear", "crisis", "downtrend", "bear_ma"):
        return "downtrend"
    return "range"
