#!/usr/bin/env python3
"""Vendor Regime 模型离线重训 / 阈值校准（crypto_lstm / jayd_regime）。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import fetch_ohlcv_ccxt
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.regime.feedback.calibrator import run_calibration
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.models.crypto_lstm import run_crypto_lstm_model
from ai_trade_advisor.regime.models.jayd_regime import run_jayd_regime_model


def _evaluate_on_bars(df, model_id: str) -> dict:
    runner = {
        "crypto_lstm": run_crypto_lstm_model,
        "jayd_regime": run_jayd_regime_model,
    }.get(model_id)
    if runner is None:
        return {}
    try:
        r = runner(df)
        return {
            "regime_label": r.regime_label,
            "confidence": r.confidence,
            "raw_trend": r.raw_trend,
            "error": r.error,
        }
    except Exception as exc:
        return {"error": str(exc)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train / calibrate vendor regime models")
    parser.add_argument("--model", choices=["crypto_lstm", "jayd_regime"], required=True)
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument(
        "--calibrate-only",
        action="store_true",
        help="仅根据 Leaderboard 校准阈值（不重训权重）",
    )
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    cfg.symbol = args.symbol
    df = fetch_ohlcv_ccxt(cfg, limit=max(cfg.lookback_bars, 720))

    artifact_root = Path(args.artifact_dir) if args.artifact_dir else get_data_root() / "exports" / "vendor_models"
    artifact_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifact_path = artifact_root / f"{args.model}_{stamp}.json"

    live_eval = _evaluate_on_bars(df, args.model)
    cal_report = run_calibration(cfg, symbol=args.symbol) if args.calibrate_only else None
    store = FeedbackStore()
    active = store.active_params(args.model)
    params = active.get("params") or {
        "enabled": True,
        "confidence_threshold": 0.5,
    }

    report = {
        "model_id": args.model,
        "symbol": args.symbol,
        "bars": len(df),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "artifact_path": str(artifact_path),
        "live_evaluation": live_eval,
        "active_params": params,
        "calibration": cal_report,
        "note": (
            "Vendor 权重重训需对接 vendor 仓库训练脚本；"
            "当前脚本导出评估报告并写入 model_params（阈值/启用状态）。"
        ),
    }
    artifact_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if not active:
        version = store.save_params_candidate(
            args.model,
            {**params, "artifact_path": str(artifact_path)},
            metrics={"combined_score": live_eval.get("confidence", 0.5), "sample_count": len(df)},
        )
        store.activate_params(args.model, version, min_improvement=0.0)
        report["activated_version"] = version

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
