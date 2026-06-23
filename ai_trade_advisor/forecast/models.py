from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PredictionDirection = Literal["up", "down", "neutral"]


@dataclass
class PredictionSignal:
    source: str
    category: str
    direction: PredictionDirection
    score: float
    confidence: float
    horizon: str
    label: str
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "category": self.category,
            "direction": self.direction,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "horizon": self.horizon,
            "label": self.label,
            "raw": self.raw,
            "error": self.error,
        }


@dataclass
class TrendConsensus:
    as_of: str
    asset: str
    direction: PredictionDirection
    label: str
    score: float
    confidence: float
    agreement: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    sources_ok: int
    sources_failed: int
    summary: str
    signals: list[PredictionSignal] = field(default_factory=list)
    macro_hazard_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "asset": self.asset,
            "direction": self.direction,
            "label": self.label,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "agreement": round(self.agreement, 4),
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "sources_ok": self.sources_ok,
            "sources_failed": self.sources_failed,
            "summary": self.summary,
            "signals": [s.to_dict() for s in self.signals],
            "macro_hazard_flag": self.macro_hazard_flag,
        }
