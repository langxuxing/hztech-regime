from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-12


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / (loss + EPS)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr = _atr(high, low, close, period)
    plus_di = 100 * pd.Series(plus_dm, index=close.index).rolling(period).mean() / (atr + EPS)
    minus_di = 100 * pd.Series(minus_dm, index=close.index).rolling(period).mean() / (atr + EPS)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di + EPS) * 100
    return dx.rolling(period, min_periods=period).mean()


def _macd_hist(close: pd.Series) -> pd.Series:
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd = ema12 - ema26
    signal = _ema(macd, 9)
    return macd - signal


def _bb_width(close: pd.Series, period: int = 20) -> pd.Series:
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    return (upper - lower) / (mid + EPS)


def build_akash_features(
    merged: pd.DataFrame,
    *,
    main_tf: str = "5m",
    context_tfs: list[str] | None = None,
) -> pd.DataFrame:
    """构建与 akash LSTM metadata 一致的特征（无 TA-Lib 依赖）。"""
    context_tfs = context_tfs or ["15m"]
    df = merged.copy()
    all_tfs = [main_tf] + [tf for tf in context_tfs if tf != main_tf]

    for tf in all_tfs:
        close_col = f"close_{tf}"
        high_col = f"high_{tf}"
        low_col = f"low_{tf}"
        if not all(c in df.columns for c in (close_col, high_col, low_col)):
            continue

        close = df[close_col].astype(float)
        high = df[high_col].astype(float)
        low = df[low_col].astype(float)
        vol_col = f"volume_{tf}"
        volume = df[vol_col].astype(float) if vol_col in df.columns else pd.Series(1.0, index=df.index)

        df[f"log_ret_1_{tf}"] = np.log(close / close.shift(1) + EPS)
        ema9 = _ema(close, 9)
        ema21 = _ema(close, 21)
        df[f"ema_ratio_9_21_{tf}"] = ema9 / (ema21 + EPS)
        df[f"macd_hist_{tf}"] = _macd_hist(close)
        df[f"adx_{tf}"] = _adx(high, low, close)
        atr = _atr(high, low, close)
        df[f"atr_norm_{tf}"] = atr / (close + EPS)
        df[f"bb_width_{tf}"] = _bb_width(close)
        df[f"rsi_14_{tf}"] = _rsi(close)
        vol_mean = volume.rolling(50, min_periods=1).mean()
        vol_std = volume.rolling(50, min_periods=1).std().replace(0, EPS)
        df[f"volume_zscore_50_{tf}"] = (volume - vol_mean) / vol_std

    context_cols: list[str] = []
    for tf in context_tfs:
        suffix = f"_{tf}"
        context_cols.extend(
            c
            for c in df.columns
            if c.endswith(suffix)
            and not c.startswith(("open_", "high_", "low_", "close_", "volume_"))
        )
    if context_cols:
        df.loc[:, context_cols] = df.loc[:, context_cols].shift(1)

    return df.dropna().reset_index(drop=True)
