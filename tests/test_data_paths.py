from __future__ import annotations

from pathlib import Path

from ai_trade_advisor.datasource.paths import (
    REPO_ROOT,
    get_data_root,
    get_etf_root,
    get_ohlcv_dir,
)


def test_data_root_sibling_to_algorithm() -> None:
    algo = REPO_ROOT / "algorithm"
    data = get_data_root()
    assert algo.is_dir(), f"expected algorithm/ at {algo}"
    assert data == REPO_ROOT / "data"
    assert data.parent == algo.parent


def test_etf_and_ohlcv_under_data() -> None:
    assert get_etf_root() == get_data_root() / "ETF"
    assert get_ohlcv_dir("Btc") == get_data_root() / "OHLCV" / "Btc"
