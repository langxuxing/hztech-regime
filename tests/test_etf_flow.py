from __future__ import annotations

from pathlib import Path

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.etf_flow import aggregate_weekly, load_local_etf_flows, parse_etf_day_row
from ai_trade_advisor.datasource.farside_etf import parse_farside_btc_table
from ai_trade_advisor.models import EtfFlowDay


FARSIDE_SAMPLE_HTML = """
<html><body><table></table><table>
<tr><th>Date</th><th>IBIT</th><th>GBTC</th><th>Total</th></tr>
<tr><td>10 Jun 2026</td><td>100.0</td><td>(20.0)</td><td>80.0</td></tr>
<tr><td>11 Jun 2026</td><td>50.0</td><td>10.0</td><td>60.0</td></tr>
<tr><td>12 Jun 2026</td><td>(30.0)</td><td>5.0</td><td>(25.0)</td></tr>
<tr><td>16 Jun 2026</td><td>20.0</td><td>(5.0)</td><td>15.0</td></tr>
<tr><td>Total</td><td>140</td><td>(10)</td><td>130</td></tr>
</table></body></html>
"""


def test_parse_farside_table():
    days = parse_farside_btc_table(FARSIDE_SAMPLE_HTML)
    assert len(days) == 4
    assert days[0].date == "2026-06-10"
    assert days[0].flow_usd == 80_000_000
    assert days[0].tickers[0].ticker == "IBIT"
    assert days[2].flow_usd == -25_000_000


def test_aggregate_weekly():
    days = [
        EtfFlowDay(date="2026-06-10", flow_usd=80_000_000),
        EtfFlowDay(date="2026-06-11", flow_usd=60_000_000),
        EtfFlowDay(date="2026-06-12", flow_usd=-25_000_000),
        EtfFlowDay(date="2026-06-16", flow_usd=15_000_000),
    ]
    weeks = aggregate_weekly(days, weeks=2)
    assert len(weeks) == 2
    assert weeks[0].flow_usd == 115_000_000
    assert weeks[1].flow_usd == 15_000_000
    assert weeks[0].days_count == 3


def test_parse_etf_day():
    row = {
        "timestamp": 1704931200000,
        "flow_usd": 655300000,
        "price_usd": 46663,
        "etf_flows": [
            {"etf_ticker": "GBTC", "flow_usd": -95100000},
            {"etf_ticker": "IBIT", "flow_usd": 111700000},
        ],
    }
    day = parse_etf_day_row(row)
    assert day is not None
    assert day.flow_usd == 655300000
    assert day.tickers[0].ticker == "IBIT"
    assert "2024" in day.date


def test_load_local_etf_flows(tmp_path: Path) -> None:
    btc_dir = tmp_path / "Btc"
    btc_dir.mkdir()
    (btc_dir / "btc_etf_flow_daily.csv").write_text(
        "date,timestamp_ms,flow_usd,price_usd\n2025-01-02,1735776000000,100000000,95000\n",
        encoding="utf-8",
    )
    (btc_dir / "btc_etf_flow_tickers.csv").write_text(
        "date,ticker,flow_usd\n2025-01-02,IBIT,80000000\n2025-01-02,GBTC,-10000000\n",
        encoding="utf-8",
    )
    cfg = AdvisorConfig(etfdata_dir=tmp_path)
    snap = load_local_etf_flows(cfg, "BTC")
    assert snap is not None
    assert snap.latest is not None
    assert snap.latest.flow_usd == 100_000_000
    assert snap.latest.tickers[0].ticker == "IBIT"
    assert snap.source == "local:farside_csv"
