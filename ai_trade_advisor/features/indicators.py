from __future__ import annotations

import numpy as np
import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def compute_kama(close: pd.Series, *, period: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average。"""
    s = close.astype(float).reset_index(drop=True)
    n = len(s)
    if n == 0:
        return pd.Series(dtype=float)
    if n <= period:
        return s.copy()

    change = (s - s.shift(period)).abs()
    volatility = (s - s.shift(1)).abs().rolling(period).sum()
    er = change / volatility.replace(0, np.nan)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    out = np.full(n, np.nan)
    out[period - 1] = float(s.iloc[period - 1])
    for i in range(period, n):
        sci = sc.iloc[i]
        if not np.isfinite(sci):
            sci = slow_sc ** 2
        out[i] = out[i - 1] + sci * (float(s.iloc[i]) - out[i - 1])

    result = pd.Series(out, index=close.index)
    return result.ffill().bfill()


def kama_rails(
    df: pd.DataFrame,
    *,
    kama_period: int = 10,
    atr_period: int = 14,
    rail_mult: float = 1.5,
) -> tuple[float, float, float]:
    close = df["close"].astype(float)
    kama = compute_kama(close, period=kama_period)
    atr = compute_atr(df, period=atr_period)
    last_kama = float(kama.iloc[-1])
    last_atr = float(atr.iloc[-1]) if np.isfinite(atr.iloc[-1]) else float(close.iloc[-1]) * 0.005
    return last_kama, last_kama + rail_mult * last_atr, last_kama - rail_mult * last_atr


def donchian_14d(df: pd.DataFrame) -> tuple[float, float]:
    """14 日唐奇安通道（由 30m/任意周期重采样为日线）。"""
    d = df.copy()
    if "datetime" not in d.columns:
        d["datetime"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
    daily = (
        d.set_index("datetime")
        .resample("1D", label="right", closed="right")
        .agg({"high": "max", "low": "min", "close": "last"})
        .dropna(subset=["close"])
    )
    if len(daily) < 14:
        hi = float(df["high"].max())
        lo = float(df["low"].min())
        return hi, lo
    upper = float(daily["high"].tail(14).max())
    lower = float(daily["low"].tail(14).min())
    return upper, lower


def bar_volume_delta(df: pd.DataFrame) -> pd.Series:
    """Bar 级 CVD 增量代理：阳线计 +volume，阴线计 -volume。"""
    o = df["open"].astype(float)
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    sign = np.where(c >= o, 1.0, -1.0)
    return pd.Series(v.values * sign, index=df.index)
