"""L1 特征变频清洗：一阶差分 / 变化率，剔除未收盘 K 线。"""

from __future__ import annotations

import pandas as pd

from ai_trade_advisor.layers.types import FeatureTransformResult


def split_confirmed_bars(df: pd.DataFrame, *, bar_minutes: int) -> FeatureTransformResult:
    """将 OHLCV 拆分为 df_confirmed（排除末根未收盘）与 df_live。"""
    notes: list[str] = []
    dropped = False
    df_live = df.copy()

    if len(df) < 2:
        return FeatureTransformResult(
            df_live=df_live,
            df_confirmed=df_live,
            dropped_unclosed=False,
            rate_of_change={},
            notes=["样本不足，跳过未收盘剔除"],
        )

    if "datetime" not in df.columns and "timestamp" in df.columns:
        df_live["datetime"] = pd.to_datetime(df_live["timestamp"], unit="ms", utc=True)

    now = pd.Timestamp.now(tz="UTC")
    last_ts = df_live.iloc[-1].get("datetime")
    if last_ts is not None:
        last_ts = pd.Timestamp(last_ts)
        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize("UTC")
        bar_end = last_ts + pd.Timedelta(minutes=bar_minutes)
        if now < bar_end:
            df_confirmed = df_live.iloc[:-1].copy()
            dropped = True
            notes.append(f"剔除未收盘 K 线（{bar_minutes}m 周期）")
        else:
            df_confirmed = df_live.copy()
            notes.append("末根 K 线已收盘，全量纳入 confirmed")
    else:
        df_confirmed = df_live.iloc[:-1].copy()
        dropped = True
        notes.append("无 datetime 列，保守剔除末根")

    roc = _compute_rate_of_change(df_confirmed)
    return FeatureTransformResult(
        df_live=df_live,
        df_confirmed=df_confirmed,
        dropped_unclosed=dropped,
        rate_of_change=roc,
        notes=notes,
    )


def _compute_rate_of_change(df: pd.DataFrame) -> dict[str, float | None]:
    """关键慢/快变量一阶变化率（供 HMM / 硬规则输入）。"""
    if len(df) < 2:
        return {}

    close = df["close"].astype(float)
    vol = df["volume"].astype(float) if "volume" in df.columns else None

    def _pct(series: pd.Series, periods: int) -> float | None:
        if len(series) <= periods:
            return None
        prev = float(series.iloc[-1 - periods])
        cur = float(series.iloc[-1])
        if prev == 0:
            return None
        return round((cur - prev) / abs(prev), 6)

    out: dict[str, float | None] = {
        "close_1bar_pct": _pct(close, 1),
        "close_4bar_pct": _pct(close, 4),
        "close_24bar_pct": _pct(close, min(24, len(close) - 1)),
    }
    if vol is not None:
        out["volume_4bar_pct"] = _pct(vol, min(4, len(vol) - 1))
    return out
