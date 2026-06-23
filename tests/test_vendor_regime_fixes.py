from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.regime.models.ensemble import run_all_regime_models


def _synthetic_ohlcv(n: int = 200, *, zero_volume: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 60_000 + np.cumsum(rng.normal(0, 50, n))
    df = pd.DataFrame(
        {
            "timestamp": np.arange(n) * 1_800_000 + 1_700_000_000_000,
            "open": close,
            "high": close + 100,
            "low": close - 100,
            "close": close,
            "volume": np.zeros(n) if zero_volume else rng.uniform(10, 100, n),
        }
    )
    return df


def test_ensemble_jayd_handles_zero_volume() -> None:
    df = _synthetic_ohlcv(200, zero_volume=True)
    rule = {
        "regime_id": "mid_vol_range",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.6,
        "dashboard_regime": "range",
    }
    out = run_all_regime_models(df, rule)
    jayd = (out.get("models") or {}).get("jayd_regime") or {}
    assert not jayd.get("error"), jayd.get("error")


def test_ensemble_vendor_models_on_synthetic() -> None:
    df = _synthetic_ohlcv(300)
    rule = {
        "regime_id": "mid_vol_range",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.6,
        "dashboard_regime": "range",
    }
    out = run_all_regime_models(df, rule)
    models = out.get("models") or {}
    jayd = models.get("jayd_regime") or {}
    assert not jayd.get("error"), jayd.get("error")
