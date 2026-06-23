from __future__ import annotations

import numpy as np
import pandas as pd


def build_regime_features(df: pd.DataFrame, *, vol_window: int = 12) -> np.ndarray:
    """HMM / Hybrid 发射特征：对数收益 + 滚动波动率 z-score + 动量。"""
    close = df["close"].astype(float)
    ret = np.log(close / close.shift(1))
    vol = ret.rolling(vol_window, min_periods=3).std()
    vol_z = (vol - vol.rolling(48, min_periods=8).mean()) / (vol.rolling(48, min_periods=8).std() + 1e-8)
    mom = close.pct_change(6)
    feat = pd.DataFrame({"ret": ret, "vol_z": vol_z, "mom": mom}).dropna()
    if len(feat) < 30:
        raise ValueError("insufficient bars for HMM features")
    x = feat.to_numpy(dtype=float)
    return normalize_features(x)


def build_cluster_features(df: pd.DataFrame, *, vol_window: int = 12) -> pd.DataFrame:
    """聚类多维特征：收益率、波动率、成交量、振幅、动量。"""
    close = df["close"].astype(float)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

    ret = np.log(close / close.shift(1))
    vol = ret.rolling(vol_window, min_periods=3).std()
    vol_z = (vol - vol.rolling(48, min_periods=8).mean()) / (vol.rolling(48, min_periods=8).std() + 1e-8)
    amplitude = (high - low) / (close + 1e-8)
    amp_z = (amplitude - amplitude.rolling(48, min_periods=8).mean()) / (
        amplitude.rolling(48, min_periods=8).std() + 1e-8
    )
    vol_zscore = (volume - volume.rolling(48, min_periods=8).mean()) / (
        volume.rolling(48, min_periods=8).std() + 1e-8
    )
    mom = close.pct_change(6)

    feat = pd.DataFrame(
        {
            "ret": ret,
            "vol_z": vol_z,
            "amplitude_z": amp_z,
            "volume_z": vol_zscore,
            "mom": mom,
        }
    ).dropna()
    if len(feat) < 30:
        raise ValueError("insufficient bars for clustering features")
    return feat


def normalize_features(x: np.ndarray) -> np.ndarray:
    return (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-8)


def recent_return_window(df: pd.DataFrame, *, window: int = 24) -> np.ndarray:
    close = df["close"].astype(float)
    ret = np.log(close / close.shift(1)).dropna().to_numpy()
    if len(ret) < window:
        raise ValueError("insufficient bars for DTW window")
    w = ret[-window:]
    return (w - w.mean()) / (w.std() + 1e-8)
