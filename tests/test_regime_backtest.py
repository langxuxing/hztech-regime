from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.backtest.regime_backtest import run_regime_backtest
from ai_trade_advisor.config import AdvisorConfig


def _synthetic_taker_df(n: int, *, tf_ms: int, base: float = 100.0) -> pd.DataFrame:
    ts = np.arange(n) * tf_ms + 1_700_000_000_000
    close = base + np.sin(np.linspace(0, 8 * np.pi, n)) * 5
    high = close + 1.0
    low = close - 1.0
    buy = np.full(n, 6.0)
    sell = np.full(n, 5.0)
    return pd.DataFrame(
        {
            "timestamp": ts.astype(int),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": buy + sell,
            "taker_buy_volume": buy,
            "taker_sell_volume": sell,
            "cvd_delta": buy - sell,
            "datetime": pd.to_datetime(ts, unit="ms", utc=True),
        }
    )


def test_regime_backtest_walk_forward_offline():
    cfg = AdvisorConfig.from_env()
    cfg.symbol = "BTC/USDT:USDT"
    df_30 = _synthetic_taker_df(320, tf_ms=1_800_000)
    df_5 = _synthetic_taker_df(320 * 6, tf_ms=300_000)

    result = run_regime_backtest(
        cfg,
        bars=320,
        warmup=200,
        horizons=(1, 4),
        df_30m=df_30,
        df_5m=df_5,
        skip_macro=True,
    )

    assert result.bars_evaluated > 0
    assert sum(result.regime_counts.values()) == result.bars_evaluated
    assert "binance_spot_taker" in result.cvd_source
    for rid, stats in result.forward_returns.items():
        assert "h1" in stats or "h4" in stats
