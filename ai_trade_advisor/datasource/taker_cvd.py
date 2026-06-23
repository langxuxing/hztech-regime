from __future__ import annotations

import time
from typing import Any

import ccxt
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig

# Binance spot kline: taker buy base volume @ index 9
_BINANCE_INTERVAL = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def _binance_symbol(spot_symbol: str) -> str:
    """BTC/USDT -> BTCUSDT"""
    base, quote = spot_symbol.split("/")
    return f"{base}{quote}"


def _parse_binance_rows(rows: list) -> pd.DataFrame:
    parsed = []
    for row in rows:
        parsed.append(
            {
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "taker_buy_volume": float(row[9]),
            }
        )
    df = pd.DataFrame(parsed)
    if df.empty:
        return df
    df = df.assign(
        taker_sell_volume=(df["volume"] - df["taker_buy_volume"]).clip(lower=0.0),
    )
    df = df.assign(
        cvd_delta=df["taker_buy_volume"] - df["taker_sell_volume"],
        datetime=pd.to_datetime(df["timestamp"], unit="ms", utc=True),
    )
    return df.sort_values("timestamp").reset_index(drop=True)


def fetch_binance_taker_klines(
    spot_symbol: str,
    *,
    timeframe: str,
    limit: int = 500,
    since_ms: int | None = None,
) -> pd.DataFrame:
    """拉取 Binance 现货 K 线 + taker buy volume（真实 CVD 来源）。"""
    interval = _BINANCE_INTERVAL.get(timeframe, timeframe)
    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    ex.load_markets()
    symbol = _binance_symbol(spot_symbol)
    params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
    if since_ms is not None:
        params["startTime"] = since_ms
    rows = ex.publicGetKlines(params)
    return _parse_binance_rows(rows)


def fetch_binance_taker_history(
    spot_symbol: str,
    *,
    timeframe: str,
    bars: int,
) -> pd.DataFrame:
    """分页拉取更长历史（回测用，从 endTime 向前覆盖 bars 根）。"""
    interval = _BINANCE_INTERVAL.get(timeframe, timeframe)
    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    ex.load_markets()
    symbol = _binance_symbol(spot_symbol)

    tf_ms = {
        "1m": 60_000,
        "5m": 300_000,
        "30m": 1_800_000,
        "1h": 3_600_000,
    }.get(timeframe, 1_800_000)

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - bars * tf_ms
    since = start_ms
    chunks: list[pd.DataFrame] = []

    while since < end_ms:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "startTime": since,
        }
        rows = ex.publicGetKlines(params)
        if not rows:
            break
        part = _parse_binance_rows(rows)
        chunks.append(part)
        since = int(part.iloc[-1]["timestamp"]) + tf_ms
        if len(part) < 1000 or since >= end_ms:
            break
        time.sleep(ex.rateLimit / 1000 if ex.rateLimit else 0.2)

    if not chunks:
        return pd.DataFrame()
    out = pd.concat(chunks, ignore_index=True)
    out = out.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    out = out[out["timestamp"] <= end_ms]
    return out.tail(bars).reset_index(drop=True)


def build_taker_cvd_series(df: pd.DataFrame) -> pd.Series:
    if "cvd_delta" in df.columns:
        return df["cvd_delta"].astype(float).cumsum()
    raise ValueError("缺少 cvd_delta，请使用 fetch_binance_taker_klines")


def fetch_taker_klines(
    cfg: AdvisorConfig,
    *,
    timeframe: str,
    limit: int,
) -> tuple[pd.DataFrame, str]:
    """
    按配置拉取 taker K 线。
    OKX 现货 candle 无 taker 拆分，BTC/ETH 统一走 Binance spot 参考流。
    """
    spot = _spot_symbol(cfg.symbol)
    source_exchange = (cfg.taker_cvd_exchange or "binance").lower()
    if source_exchange != "binance":
        source_exchange = "binance"
    df = fetch_binance_taker_klines(spot, timeframe=timeframe, limit=limit)
    return df, f"binance_spot_taker:{timeframe}"


def _spot_symbol(perp_symbol: str) -> str:
    base = perp_symbol.split("/")[0]
    return f"{base}/USDT"
