#!/usr/bin/env python3
"""对 BTC 运行两个 vendor Regime 引擎并打印结果。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as: python scripts/run_vendor_regime_engines.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import load_ohlcv
from ai_trade_advisor.regime.models.crypto_lstm import run_crypto_lstm_model
from ai_trade_advisor.regime.models.ensemble import run_all_regime_models
from ai_trade_advisor.regime.models.jayd_regime import run_jayd_regime_model


def main() -> int:
    cfg = AdvisorConfig.from_env()
    print(f"Loading BTC OHLCV from local OKX 1m ({cfg.symbol})...")
    df = load_ohlcv(cfg)
    print(f"Loaded {len(df)} bars ({cfg.bar_minutes}m)")

    print("\n=== jayd DT+HMM engine ===")
    jayd = run_jayd_regime_model(df)
    print(json.dumps(jayd.to_dict(), ensure_ascii=False, indent=2))

    print("\n=== akash LSTM engine (5m/15m via ccxt) ===")
    lstm = run_crypto_lstm_model(df)
    print(json.dumps(lstm.to_dict(), ensure_ascii=False, indent=2))

    print("\n=== full ensemble (8 models) ===")
    rule = {
        "regime_id": "mid_vol_range",
        "regime_label": "中波震荡",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.7,
        "dashboard_regime": "range",
    }
    out = run_all_regime_models(df, rule)
    for mid, m in out["models"].items():
        status = m.get("regime_label", "?")
        conf = m.get("confidence", 0)
        err = m.get("error")
        suffix = f" ERROR: {err}" if err else ""
        print(f"  {mid:20s} {status} ({conf:.0%}){suffix}")
    print(f"\nConsensus: {out['comparison']['dominant_trend']} ({out['comparison']['agreement_ratio']:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
