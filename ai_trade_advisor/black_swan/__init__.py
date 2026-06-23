"""黑天鹅发现与分级预警（Tail Risk & Early Warning）。"""

from ai_trade_advisor.black_swan.engine import (
    ALERT_LABELS,
    BlackSwanAlert,
    AlertLevel,
    apply_circuit_breaker_to_regime,
    combine_black_swan_alerts,
    evaluate_black_swan_alert,
)
from ai_trade_advisor.black_swan.strategies import build_practical_signals

__all__ = [
    "ALERT_LABELS",
    "AlertLevel",
    "BlackSwanAlert",
    "apply_black_swan_after_confirmation",
    "apply_circuit_breaker_to_regime",
    "build_practical_signals",
    "combine_black_swan_alerts",
    "evaluate_black_swan_alert",
    "evaluate_black_swan_confirmed",
    "evaluate_black_swan_fast",
]


def __getattr__(name: str):
    if name == "apply_black_swan_after_confirmation":
        from ai_trade_advisor.black_swan.pipeline import apply_black_swan_after_confirmation

        return apply_black_swan_after_confirmation
    if name == "evaluate_black_swan_confirmed":
        from ai_trade_advisor.black_swan.pipeline import evaluate_black_swan_confirmed

        return evaluate_black_swan_confirmed
    if name == "evaluate_black_swan_fast":
        from ai_trade_advisor.black_swan.pipeline import evaluate_black_swan_fast

        return evaluate_black_swan_fast
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
