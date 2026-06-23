from pathlib import Path
from unittest.mock import patch

from ai_trade_advisor.datasource.binance_config import (
    DEMO_FAPI_BASE_URL,
    BinanceFuturesConfig,
    load_binance_config,
    normalize_fapi_base_url,
)


def test_normalize_fapi_base_url_demo():
    assert normalize_fapi_base_url("", sandbox=True) == DEMO_FAPI_BASE_URL
    assert (
        normalize_fapi_base_url("https://demo-fapi.binance.com", sandbox=True)
        == DEMO_FAPI_BASE_URL
    )


def test_load_binance_config_from_dict(tmp_path: Path):
    cfg_file = tmp_path / "demo.json"
    cfg_file.write_text(
        """
        {
            "name": "test",
            "key": "k",
            "secret": "s",
            "base_url": "https://demo-fapi.binance.com",
            "sandbox": true
        }
        """,
        encoding="utf-8",
    )
    cfg = load_binance_config(cfg_file)
    assert cfg is not None
    assert cfg.sandbox is True
    assert cfg.base_url == DEMO_FAPI_BASE_URL
    assert cfg.ticker_source == "binance:demo-fapi"
