from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from ai_trade_advisor.regime.engines.vendor_paths import JAYD_VENDOR

REGIME_NAMES = {0: "Trending Up", 1: "Trending Down", 2: "Sideways"}
HMM_STATE_NAMES = {0: "Low Volatility", 1: "High Volatility"}


@dataclass
class JaydRegimeAnalysis:
    dt_regime: str
    dt_confidence: float
    hmm_state: str
    hmm_confidence: float
    raw_trend: str
    vol_bucket: str
    next_regime_label: str | None = None
    transition_matrix: list[list[float]] | None = None
    state_probs: dict[str, float] | None = None
    drivers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    out = df.copy()
    for src, dst in col_map.items():
        if src in out.columns and dst not in out.columns:
            out = out.rename(columns={src: dst})

    for col in ("open", "high", "low", "close", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "close" not in out.columns:
        raise ValueError("OHLCV requires close column")
    if "volume" not in out.columns:
        out["volume"] = 1.0
    if "high" not in out.columns:
        out["high"] = out["close"]
    if "low" not in out.columns:
        out["low"] = out["close"]
    if "open" not in out.columns:
        out["open"] = out["close"]
    return out.dropna(subset=["close"]).reset_index(drop=True)


def engineer_features(ohlcv: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """jayd-bit 特征工程（market-regime-feature-engineering）。"""
    df = _normalize_ohlcv(ohlcv)

    df["price_change"] = df["close"].pct_change()
    df["price_momentum"] = df["close"].rolling(window=5).mean().pct_change()
    df["price_volatility"] = df["close"].rolling(window=5).std()
    df["volume_change"] = df["volume"].pct_change()
    df["volume_momentum"] = df["volume"].rolling(window=5).mean().pct_change()
    df["consec_higher_highs"] = (df["high"] > df["high"].shift(1)).rolling(window=3).sum()
    df["consec_lower_lows"] = (df["low"] < df["low"].shift(1)).rolling(window=3).sum()
    df = df.dropna().reset_index(drop=True)

    feature_cols = [
        "price_change",
        "price_momentum",
        "price_volatility",
        "volume_change",
        "volume_momentum",
        "consec_higher_highs",
        "consec_lower_lows",
    ]
    scaler = StandardScaler()
    features = scaler.fit_transform(df[feature_cols])
    return features, df


def label_regimes(df: pd.DataFrame) -> np.ndarray:
    """基于价格/成交量规则生成训练标签。"""
    labels = []
    for i in range(len(df)):
        if i == 0:
            labels.append(2)
            continue
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if row["high"] > prev["high"] and row["volume"] > prev["volume"]:
            labels.append(0)
        elif row["low"] < prev["low"] and row["volume"] > prev["volume"]:
            labels.append(1)
        else:
            labels.append(2)
    return np.array(labels, dtype=int)


def _prepare_hmm_features(df: pd.DataFrame) -> np.ndarray:
    feat = pd.DataFrame(
        {
            "log_returns": np.log(df["close"] / df["close"].shift(1)),
            "volatility": df["close"].rolling(window=5).std(),
            "volume_normalized": df["volume"] / df["volume"].rolling(window=5).mean(),
        }
    ).dropna()
    scaler = StandardScaler()
    return scaler.fit_transform(feat), feat.index


def _dt_to_trend(label: int) -> tuple[str, str]:
    if label == 0:
        return "uptrend", "low_vol"
    if label == 1:
        return "downtrend", "mid_vol"
    return "range", "mid_vol"


def _hmm_to_vol(state: int) -> str:
    return "high_vol" if state == 1 else "low_vol"


def analyze_jayd_regime(df: pd.DataFrame) -> JaydRegimeAnalysis:
    """
    使用 vendor/Market-Regime-Modeling-and-Rates-Prediction-Analysis 逻辑：
    Decision Tree 分类 + Gaussian HMM 隐状态推断。
    """
    if not JAYD_VENDOR.exists():
        return JaydRegimeAnalysis(
            dt_regime="Unknown",
            dt_confidence=0.0,
            hmm_state="Unknown",
            hmm_confidence=0.0,
            raw_trend="range",
            vol_bucket="mid_vol",
            error=f"vendor repo missing: {JAYD_VENDOR}",
        )

    try:
        if len(df) < 80:
            raise ValueError("need at least 80 bars for jayd regime analysis")

        features, processed = engineer_features(df)
        labels = label_regimes(processed)

        split = max(int(len(features) * 0.7), 40)
        X_train, X_test = features[:split], features[split:]
        y_train, y_test = labels[:split], labels[split:]

        dt_model = DecisionTreeClassifier(
            max_depth=5,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
        )
        dt_model.fit(X_train, y_train)
        dt_probs = dt_model.predict_proba(X_test if len(X_test) else X_train)
        dt_pred = int(dt_model.classes_[int(np.argmax(dt_probs[-1]))])
        dt_conf = float(np.max(dt_probs[-1]))

        hmm_features, hmm_idx = _prepare_hmm_features(processed)
        hmm_model = hmm.GaussianHMM(
            n_components=2,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        hmm_model.fit(hmm_features)
        hmm_states = hmm_model.predict(hmm_features)
        hmm_post = hmm_model.predict_proba(hmm_features)[-1]
        hmm_state = int(hmm_states[-1])
        hmm_conf = float(np.max(hmm_post))

        dt_name = REGIME_NAMES.get(dt_pred, f"State_{dt_pred}")
        hmm_name = HMM_STATE_NAMES.get(hmm_state, f"HMM_{hmm_state}")

        raw_trend, vol_from_dt = _dt_to_trend(dt_pred)
        vol_bucket = _hmm_to_vol(hmm_state) if hmm_state == 1 else vol_from_dt

        trans = hmm_model.transmat_.tolist()
        next_state = int(np.argmax(trans[hmm_state]))
        next_hmm_name = HMM_STATE_NAMES.get(next_state, f"HMM_{next_state}")

        state_probs = {
            HMM_STATE_NAMES.get(i, f"HMM_{i}"): round(float(p), 4)
            for i, p in enumerate(hmm_post)
        }

        drivers = [
            f"DT · {dt_name} ({dt_conf:.0%})",
            f"HMM · {hmm_name} ({hmm_conf:.0%})",
            f"特征: 动量/波动/成交量/连续高低点",
            f"vendor: Market-Regime-Modeling-and-Rates-Prediction-Analysis",
        ]

        return JaydRegimeAnalysis(
            dt_regime=dt_name,
            dt_confidence=dt_conf,
            hmm_state=hmm_name,
            hmm_confidence=hmm_conf,
            raw_trend=raw_trend,
            vol_bucket=vol_bucket,
            next_regime_label=next_hmm_name if next_hmm_name != hmm_name else None,
            transition_matrix=trans,
            state_probs=state_probs,
            drivers=drivers,
            metadata={
                "engine": "jayd_pipeline",
                "dt_class": dt_pred,
                "hmm_state": hmm_state,
                "bars_used": len(processed),
                "vendor": str(JAYD_VENDOR),
            },
        )
    except Exception as exc:
        return JaydRegimeAnalysis(
            dt_regime="Unknown",
            dt_confidence=0.0,
            hmm_state="Unknown",
            hmm_confidence=0.0,
            raw_trend="range",
            vol_bucket="mid_vol",
            error=str(exc),
            drivers=[f"jayd pipeline 失败: {exc}"],
        )
