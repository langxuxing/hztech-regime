from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_trade_advisor.forecast.ensemble import fetch_trend_consensus as fetch_trend_consensus

__all__ = ["fetch_trend_consensus"]


def __getattr__(name: str):
    if name == "fetch_trend_consensus":
        from ai_trade_advisor.forecast.ensemble import fetch_trend_consensus

        return fetch_trend_consensus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
