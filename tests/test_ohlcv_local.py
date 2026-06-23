"""OHLCV 本地加载与 resample 测试。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import (
    LocalBtcDataError,
    get_last_ohlcv_source,
    load_local_btc_1m_csvs,
    load_ohlcv,
    resample_from_1m,
)


def _write_1m_csv(path: Path, timestamps: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, ts in enumerate(timestamps):
        price = 100.0 + i * 0.01
        rows.append(f"{ts},{price},{price+1},{price-1},{price},0,1")
    path.write_text("ts,open,high,low,close,volume,confirm\n" + "\n".join(rows), encoding="utf-8")


def test_resample_from_1m_aggregates_30m(tmp_path: Path) -> None:
    ts0 = 1_700_000_000_000
    stamps = [ts0 + i * 60_000 for i in range(60)]
    df = pd.read_csv(
        pd.io.common.StringIO(
            "timestamp,open,high,low,close,volume\n"
            + "\n".join(f"{t},1,2,0.5,1.5,10" for t in stamps)
        )
    )
    out = resample_from_1m(df, 30)
    assert len(out) >= 2
    assert float(out.iloc[-1]["close"]) == 1.5


def test_load_local_btc_1m_csvs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_trade_advisor.datasource.ohlcv.get_ohlcv_dir",
        lambda asset="Btc": tmp_path,
    )
    ts0 = 1_700_000_000_000
    stamps = [ts0 + i * 60_000 for i in range(120)]
    _write_1m_csv(tmp_path / "btc_usdt_swap_mark_1m_2024-01-01.csv", stamps)
    df = load_local_btc_1m_csvs()
    assert df is not None
    assert len(df) == 120


def test_load_ohlcv_prefers_local_btc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_trade_advisor.datasource.ohlcv.get_ohlcv_dir",
        lambda asset="Btc": tmp_path,
    )

    ts0 = 1_700_000_000_000
    # 3 days of 1m bars → enough for 30m resample
    stamps = [ts0 + i * 60_000 for i in range(3 * 24 * 60)]
    _write_1m_csv(tmp_path / "btc_usdt_swap_mark_1m_2024-06-01.csv", stamps[: 24 * 60])
    _write_1m_csv(
        tmp_path / "btc_usdt_swap_mark_1m_2024-06-02.csv",
        stamps[24 * 60 : 2 * 24 * 60],
    )
    _write_1m_csv(
        tmp_path / "btc_usdt_swap_mark_1m_2024-06-03.csv",
        stamps[2 * 24 * 60 :],
    )

    cfg = AdvisorConfig(
        symbol="BTC/USDT:USDT",
        bar_minutes=30,
        lookback_bars=100,
    )
    df = load_ohlcv(cfg)
    assert len(df) >= 50
    assert get_last_ohlcv_source() == "local_btc_1m_resample"


def test_load_ohlcv_btc_raises_without_local_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ai_trade_advisor.datasource.ohlcv.get_ohlcv_dir",
        lambda asset="Btc": tmp_path,
    )
    cfg = AdvisorConfig(symbol="BTC/USDT:USDT", bar_minutes=30, lookback_bars=100)
    with pytest.raises(LocalBtcDataError):
        load_ohlcv(cfg)


def test_load_ohlcv_btc_allows_ccxt_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ai_trade_advisor.datasource.ohlcv.get_ohlcv_dir",
        lambda asset="Btc": tmp_path,
    )

    def _fake_ccxt(cfg, *, limit=None):
        ts0 = 1_700_000_000_000
        rows = [
            {
                "timestamp": ts0 + i * 1_800_000,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            }
            for i in range(60)
        ]
        import pandas as pd

        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    monkeypatch.setattr(
        "ai_trade_advisor.datasource.ohlcv.fetch_ohlcv_ccxt",
        _fake_ccxt,
    )
    cfg = AdvisorConfig(
        symbol="BTC/USDT:USDT",
        bar_minutes=30,
        lookback_bars=50,
        allow_ccxt_ohlcv_fallback=True,
    )
    df = load_ohlcv(cfg)
    assert len(df) == 60
    assert get_last_ohlcv_source() == "ccxt_live"


def test_spot_cvd_unavailable_on_taker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_trade_advisor.datasource.spot_cvd import analyze_spot_cvd

    def _boom(*_a, **_k):
        raise RuntimeError("network")

    monkeypatch.setattr(
        "ai_trade_advisor.datasource.spot_cvd._analyze_taker_cvd",
        _boom,
    )
    cfg = AdvisorConfig(use_taker_cvd=True)
    out = analyze_spot_cvd(cfg, 100.0)
    assert out["unavailable"] is True
    assert out["source"] == "unavailable"
