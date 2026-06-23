from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import product
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import fetch_ohlcv_ccxt
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.regime.feedback.params_store import ModelParamsCache, _DEFAULT_PARAMS
from ai_trade_advisor.regime.feedback.replay import replay_param_grid
from ai_trade_advisor.regime.feedback.rollup import refresh_rollup
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.models.base import MODEL_CATALOG

_SEARCH_GRIDS: dict[str, dict[str, list[Any]]] = {
    "hmm": {"n_states": [3, 4, 5], "hazard_lambda": [40.0, 80.0, 120.0]},
    "clustering": {"n_clusters": [3, 4, 5, 6], "dtw_window": [12, 24, 48]},
    "msar": {"n_states": [2, 3, 4]},
    "heuristic_advanced": {"adx_trend_threshold": [22.0, 28.0, 35.0], "squeeze_overlap_min": [0.6, 0.75, 0.9]},
    "hybrid": {
        "seq_decay": [0.75, 0.85, 0.95],
        "markov_weight": [0.40, 0.45, 0.50],
        "seq_weight": [0.30, 0.35, 0.40],
        "hmm_weight": [0.15, 0.20, 0.25],
    },
}

_VENDOR_THRESHOLDS = [0.35, 0.45, 0.55, 0.65, 0.75]


def _grid_combos(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid.keys())
    if not keys:
        return [{}]
    vals = [grid[k] for k in keys]
    return [dict(zip(keys, combo, strict=True)) for combo in product(*vals)]


def _normalize_weights(scores: dict[str, float], *, floor: float = 0.15) -> dict[str, float]:
    if not scores:
        return dict(_DEFAULT_PARAMS["ensemble"]["weights"])
    keys = list(MODEL_CATALOG.keys())
    raw = {k: max(scores.get(k, 0.0), floor) for k in keys}
    total = sum(raw.values()) or 1.0
    return {k: round(v / total, 4) for k, v in raw.items()}


def _calibrate_ensemble_weights(store: FeedbackStore, window_days: int) -> tuple[dict[str, Any], float, dict]:
    board = store.leaderboard(segment="global", window_days=window_days)
    if not board:
        board = store.leaderboard(window_days=window_days)
    scores = {
        r["model_id"]: float(r.get("combined_score") or 0.0)
        for r in board
        if r.get("model_id") and not r.get("low_confidence")
    }
    weights = _normalize_weights(scores)
    avg = sum(scores.values()) / max(len(scores), 1) if scores else 0.5
    segment_weights: dict[str, dict[str, float]] = {}
    for seg in {r.get("segment_primary") for r in board if r.get("segment_primary")}:
        if not seg or seg == "global":
            continue
        seg_rows = [r for r in board if r.get("segment_primary") == seg and not r.get("low_confidence")]
        if len(seg_rows) < 3:
            continue
        seg_scores = {r["model_id"]: float(r.get("combined_score") or 0.0) for r in seg_rows}
        segment_weights[str(seg)] = _normalize_weights(seg_scores)
    params = {"weights": weights, "segment_weights": segment_weights}
    return params, avg, {"global_scores": scores, "segment_count": len(segment_weights)}


def _calibrate_vendor_from_rollup(
    store: FeedbackStore,
    model_id: str,
    window_days: int,
) -> tuple[dict[str, Any], float]:
    """用 Leaderboard forward 均值选择 vendor 置信度阈值（无需重跑）。"""
    board = [r for r in store.leaderboard(window_days=window_days) if r.get("model_id") == model_id]
    if not board:
        return dict(_DEFAULT_PARAMS.get(model_id, {})), 0.5
    best_row = max(board, key=lambda r: float(r.get("combined_score") or 0))
    forward_avg = float(best_row.get("forward_avg") or best_row.get("combined_score") or 0.5)
    base = dict(_DEFAULT_PARAMS.get(model_id, {"enabled": True, "confidence_threshold": 0.5}))
    # 高 forward 表现 → 可放低阈值纳入更多预测；低表现 → 提高阈值
    if forward_avg >= 0.75:
        threshold = 0.45
    elif forward_avg >= 0.6:
        threshold = 0.55
    else:
        threshold = 0.65
    base["confidence_threshold"] = threshold
    base["enabled"] = True
    return base, forward_avg


def run_calibration(
    cfg: AdvisorConfig | None = None,
    *,
    store: FeedbackStore | None = None,
    window_days: int | None = None,
    symbol: str = "",
) -> dict[str, Any]:
    """基于 forward 样本：K 线回放调参 + Leaderboard 调 ensemble/vendor。"""
    cfg = cfg or AdvisorConfig.from_env()
    store = store or FeedbackStore()
    window = window_days or cfg.regime_rollup_window_days

    refresh_rollup(store, symbol=symbol, window_days=window)
    rows = store.scores_joined_recent(symbol=symbol, window_days=window)
    forward_rows = [r for r in rows if r["score_type"] == "forward"]
    judgments = store.forward_scored_judgments(symbol=symbol, window_days=window)

    report: dict[str, Any] = {
        "ok": True,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window,
        "forward_samples": len(forward_rows),
        "replay_judgments": len(judgments),
        "models": {},
        "activated": [],
        "method": "replay+rollup",
    }

    if len(forward_rows) < max(3, cfg.regime_forward_min_samples // 4):
        report["ok"] = False
        report["reason"] = (
            f"forward 样本偏少 ({len(forward_rows)}), 仅更新 ensemble/vendor 权重"
        )

    df = None
    if judgments:
        try:
            sym_cfg = AdvisorConfig.from_env()
            sym_cfg.symbol = symbol or sym_cfg.symbol
            df = fetch_ohlcv_ccxt(sym_cfg, limit=max(sym_cfg.lookback_bars, 1500))
        except Exception as exc:
            report["replay_error"] = str(exc)

    for model_id, grid in _SEARCH_GRIDS.items():
        combos = _grid_combos(grid)
        base_params = dict(_DEFAULT_PARAMS.get(model_id, {}))
        replay_score = 0.0
        method = "rollup_fallback"

        if df is not None and len(judgments) >= 3:
            best, replay_score = replay_param_grid(df, judgments, model_id, combos)
            if replay_score > 0:
                best_params = {**base_params, **best}
                method = "walk_forward_replay"
            else:
                best_params = base_params
        else:
            by_model = [r for r in forward_rows if r["model_id"] == model_id]
            baseline = sum(float(r["total_score"] or 0) for r in by_model) / max(len(by_model), 1)
            best_params = base_params
            replay_score = baseline if by_model else 0.0
            method = "forward_mean"

        version = store.save_params_candidate(
            model_id,
            best_params,
            metrics={
                "combined_score": replay_score,
                "sample_count": len(judgments) or len(forward_rows),
                "method": method,
            },
        )
        min_imp = 0.03 if replay_score > 0 else 0.0
        activated = store.activate_params(model_id, version, min_improvement=min_imp)
        report["models"][model_id] = {
            "version": version,
            "params": best_params,
            "score": replay_score,
            "activated": activated,
            "method": method,
        }
        if activated:
            report["activated"].append(model_id)

    for vendor_id in ("crypto_lstm", "jayd_regime"):
        vparams, vscore = _calibrate_vendor_from_rollup(store, vendor_id, window)
        version = store.save_params_candidate(
            vendor_id,
            vparams,
            metrics={"combined_score": vscore, "method": "rollup_threshold"},
        )
        activated = store.activate_params(vendor_id, version, min_improvement=0.0)
        report["models"][vendor_id] = {
            "version": version,
            "params": vparams,
            "score": vscore,
            "activated": activated,
            "method": "rollup_threshold",
        }
        if activated:
            report["activated"].append(vendor_id)

    ens_params, ens_score, ens_meta = _calibrate_ensemble_weights(store, window)
    version = store.save_params_candidate(
        "ensemble",
        ens_params,
        metrics={"combined_score": ens_score, **ens_meta, "method": "leaderboard_weights"},
    )
    activated = store.activate_params("ensemble", version, min_improvement=0.0)
    report["models"]["ensemble"] = {
        "version": version,
        "params": ens_params,
        "score": ens_score,
        "activated": activated,
        "method": "leaderboard_weights",
        "meta": ens_meta,
    }
    if activated:
        report["activated"].append("ensemble")

    ModelParamsCache.get().reload()

    export_dir = get_data_root() / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = export_dir / f"regime_calibration_{date}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["export_path"] = str(path)
    return report
