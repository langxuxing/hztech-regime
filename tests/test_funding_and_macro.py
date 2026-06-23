"""Funding snapshot 与制造业宏观指标测试。"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.funding_snapshot import (
    FundingSnapshot,
    fetch_funding_snapshot,
)
from ai_trade_advisor.datasource.forecast_sources import funding_to_prediction_signal
from ai_trade_advisor.datasource.macro_fetch import fetch_manufacturing_activity


def test_funding_to_prediction_signal():
    snap = FundingSnapshot(
        symbol="BTC/USDT:USDT",
        rate=0.0001,
        mark_price=100000.0,
        history=[0.00008, 0.00009, 0.0001],
        cross_exchange_avg=0.00012,
        cross_exchange_count=5,
        primary_source="binance_fapi",
        as_of="2026-01-01T00:00:00+00:00",
    )
    sig = funding_to_prediction_signal(snap)
    assert sig.source == "funding_snapshot"
    assert sig.error is None
    assert "跨所均" in sig.label


def test_fetch_funding_snapshot_uses_binance_primary():
    cfg = AdvisorConfig(symbol="BTC/USDT:USDT")

    def fake_get(url, **kwargs):
        if "premiumIndex" in url:
            return {"lastFundingRate": "0.0002", "markPrice": "90000"}
        if "fundingRate" in url:
            return [{"fundingRate": "0.0001"}, {"fundingRate": "0.0002"}]
        raise AssertionError(url)

    with patch("ai_trade_advisor.datasource.funding_snapshot.get_json", side_effect=fake_get):
        snap = fetch_funding_snapshot(cfg, force=True)
    assert snap.rate == 0.0002
    assert snap.primary_source == "binance_fapi"
    assert len(snap.history) == 2


def test_fetch_manufacturing_activity_parses_fred_csv():
    csv_text = (
        "observation_date,IPMAN\n"
        "2024-01-01,100.0\n"
        "2024-02-01,101.0\n"
        "2024-03-01,102.0\n"
    )

    with patch(
        "ai_trade_advisor.datasource.macro_fetch._download_text",
        return_value=csv_text,
    ):
        df = fetch_manufacturing_activity(timeout=5.0)

    assert len(df) == 3
    assert "mom_pct" in df.columns
    assert float(df.iloc[-1]["value"]) == 102.0
