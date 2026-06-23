from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VENDOR_ROOT = PROJECT_ROOT / "vendor"
AKASH_VENDOR = VENDOR_ROOT / "CryptoMarket_Regime_Classifier"
JAYD_VENDOR = VENDOR_ROOT / "Market-Regime-Modeling-and-Rates-Prediction-Analysis"

AKASH_MODEL_DIR = AKASH_VENDOR / "models"
AKASH_LSTM_MODEL = AKASH_MODEL_DIR / "lstm_regime_model.keras"
AKASH_SCALER = AKASH_MODEL_DIR / "scaler.joblib"
AKASH_METADATA = AKASH_MODEL_DIR / "lstm_model_metadata.json"
_hmm_candidates = sorted(AKASH_MODEL_DIR.glob("hmm_BTCUSDT_*_states6.joblib")) if AKASH_MODEL_DIR.exists() else []
AKASH_HMM_BUNDLE = _hmm_candidates[-1] if _hmm_candidates else None
