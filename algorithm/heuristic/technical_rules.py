from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class HeuristicRegimeResult:
    regime_label: str
    regime_id: str
    raw_trend: str
    vol_bucket: str
    confidence: float
    drivers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _atr_pandas_ta(df: pd.DataFrame, period: int = 14) -> pd.Series | None:
    try:
        import pandas_ta as ta

        atr = ta.atr(df["high"], df["low"], df["close"], length=period)
        return atr if atr is not None else None
    except Exception:
        return None


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    ta_atr = _atr_pandas_ta(df, period)
    if ta_atr is not None and not ta_atr.isna().all():
        return ta_atr

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def _adx_pandas_ta(df: pd.DataFrame, period: int = 14) -> float | None:
    try:
        import pandas_ta as ta

        adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
        if adx_df is not None and f"ADX_{period}" in adx_df.columns:
            val = adx_df[f"ADX_{period}"].iloc[-1]
            if not pd.isna(val):
                return float(val)
    except Exception:
        pass
    return None


def _adx(df: pd.DataFrame, period: int = 14) -> float:
    ta_val = _adx_pandas_ta(df, period)
    if ta_val is not None:
        return ta_val

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    atr = _atr(df, period)
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).sum() / (atr * period + 1e-8)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).sum() / (atr * period + 1e-8)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-8) * 100
    adx = dx.rolling(period, min_periods=period).mean()
    val = adx.iloc[-1]
    if pd.isna(val):
        return 0.0
    return float(val)


def _bollinger_keltner_squeeze(df: pd.DataFrame) -> tuple[bool, float]:
    close = df["close"].astype(float)
    try:
        import pandas_ta as ta

        bb = ta.bbands(close, length=20, std=2)
        kc = ta.kc(df["high"], df["low"], close, length=20, scalar=1.5)
        if bb is not None and kc is not None:
            bb_u = bb.iloc[:, -2]
            bb_l = bb.iloc[:, -3]
            kc_u = kc.iloc[:, 0]
            kc_l = kc.iloc[:, 2]
            squeeze = (bb_u.iloc[-1] < kc_u.iloc[-1]) and (bb_l.iloc[-1] > kc_l.iloc[-1])
            mid = close.rolling(20).mean().iloc[-1]
            bb_width = float((bb_u.iloc[-1] - bb_l.iloc[-1]) / (mid + 1e-8))
            kc_width = float((kc_u.iloc[-1] - kc_l.iloc[-1]) / (kc.iloc[:, 1].iloc[-1] + 1e-8))
            overlap = 1.0 - min(bb_width / (kc_width + 1e-8), 1.0)
            return bool(squeeze), overlap
    except Exception:
        pass

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    bb_upper = mid + 2 * std
    bb_lower = mid - 2 * std
    ema20 = _ema(close, 20)
    atr = _atr(df, 20)
    kc_upper = ema20 + 1.5 * atr
    kc_lower = ema20 - 1.5 * atr
    squeeze = (bb_upper.iloc[-1] < kc_upper.iloc[-1]) and (bb_lower.iloc[-1] > kc_lower.iloc[-1])
    bb_width = float((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / (mid.iloc[-1] + 1e-8))
    kc_width = float((kc_upper.iloc[-1] - kc_lower.iloc[-1]) / (ema20.iloc[-1] + 1e-8))
    overlap = 1.0 - min(bb_width / (kc_width + 1e-8), 1.0)
    return bool(squeeze), overlap


def fit_heuristic_regime(
    df: pd.DataFrame,
    *,
    adx_trend_threshold: float = 28.0,
    squeeze_overlap_min: float = 0.6,
) -> HeuristicRegimeResult:
    """布林带挤压 / ADX 趋势强度 / 多周期均线 (pandas-ta 优先)。"""
    close = df["close"].astype(float)
    price = float(close.iloc[-1])

    ma200 = close.rolling(200, min_periods=50).mean().iloc[-1]
    ma50 = close.rolling(50, min_periods=20).mean().iloc[-1]
    squeeze, overlap = _bollinger_keltner_squeeze(df)
    adx = _adx(df)

    bull_ma = price > float(ma200) if not pd.isna(ma200) else False
    bull_short = price > float(ma50) if not pd.isna(ma50) else False

    drivers: list[str] = []
    if squeeze and overlap >= squeeze_overlap_min:
        drivers.append("布林带⊂肯特纳 → 极度压缩 (Squeeze)")
        raw_trend = "range"
        vol_bucket = "low_vol"
        regime_label = "启发式 · 波动挤压 · 待突破"
        regime_id = "squeeze_compression"
        conf = 0.72 + overlap * 0.15
    elif adx >= adx_trend_threshold:
        if bull_short and bull_ma:
            raw_trend = "uptrend"
            vol_bucket = "mid_vol"
            regime_label = f"启发式 · ADX={adx:.0f} 强趋势上行"
            regime_id = "adx_strong_uptrend"
            conf = min(0.9, 0.65 + adx / 100)
        elif not bull_short and not bull_ma:
            raw_trend = "downtrend"
            vol_bucket = "mid_vol"
            regime_label = f"启发式 · ADX={adx:.0f} 强趋势下行"
            regime_id = "adx_strong_downtrend"
            conf = min(0.9, 0.65 + adx / 100)
        else:
            raw_trend = "range"
            vol_bucket = "mid_vol"
            regime_label = f"启发式 · ADX={adx:.0f} 趋势分歧"
            regime_id = "adx_mixed"
            conf = 0.58
        drivers.append(f"ADX={adx:.1f} (趋势强度)")
    else:
        if bull_ma and bull_short:
            raw_trend = "uptrend"
            vol_bucket = "low_vol"
            regime_label = "启发式 · 200MA 上方牛市结构"
            regime_id = "ma_bull"
            conf = 0.7
        elif not bull_ma and not bull_short:
            raw_trend = "downtrend"
            vol_bucket = "low_vol"
            regime_label = "启发式 · 200MA 下方熊市结构"
            regime_id = "ma_bear"
            conf = 0.7
        else:
            raw_trend = "range"
            vol_bucket = "mid_vol"
            regime_label = "启发式 · 均线缠绕震荡"
            regime_id = "ma_range"
            conf = 0.62
        drivers.append(f"ADX={adx:.1f} (弱趋势)")

    if not pd.isna(ma200):
        drivers.append(f"价格 vs MA200: {'上方' if bull_ma else '下方'}")
    if squeeze:
        drivers.append(f"挤压重合度 {overlap:.0%}")

    return HeuristicRegimeResult(
        regime_label=regime_label,
        regime_id=regime_id,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        confidence=float(conf),
        drivers=drivers,
        metadata={
            "adx": round(adx, 2),
            "squeeze": squeeze,
            "squeeze_overlap": round(overlap, 4),
            "above_ma200": bull_ma,
            "above_ma50": bull_short,
        },
    )
