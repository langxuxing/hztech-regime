from __future__ import annotations

import threading
import time
from typing import Any

from ai_trade_advisor.regime.feedback.store import FeedbackStore

_DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "hmm": {"n_states": 4, "hazard_lambda": 80.0},
    "clustering": {"n_clusters": 4, "dtw_window": 24},
    "msar": {"n_states": 3},
    "heuristic_advanced": {"adx_trend_threshold": 28.0, "squeeze_overlap_min": 0.6},
    "hybrid": {"seq_decay": 0.85, "markov_weight": 0.45, "seq_weight": 0.35, "hmm_weight": 0.20},
    "ensemble": {
        "weights": {
            "heuristic": 1.0,
            "hmm": 1.0,
            "clustering": 1.0,
            "msar": 1.0,
            "heuristic_advanced": 1.0,
            "hybrid": 1.0,
            "crypto_lstm": 1.0,
            "jayd_regime": 1.0,
        },
        "segment_weights": {},
    },
    "crypto_lstm": {"enabled": True, "confidence_threshold": 0.5},
    "jayd_regime": {"enabled": True, "confidence_threshold": 0.5},
}


class ModelParamsCache:
    """进程内参数缓存，支持热更新。"""

    _instance: ModelParamsCache | None = None
    _lock = threading.Lock()

    def __init__(self, store: FeedbackStore | None = None) -> None:
        self._store = store or FeedbackStore()
        self._cache: dict[str, dict[str, Any]] = dict(_DEFAULT_PARAMS)
        self._last_load = 0.0
        self._poll_sec = 60.0
        self.reload()

    @classmethod
    def get(cls) -> ModelParamsCache:
        with cls._lock:
            if cls._instance is None:
                cls._instance = ModelParamsCache()
            return cls._instance

    def reload(self) -> None:
        merged = dict(_DEFAULT_PARAMS)
        active = self._store.active_params()
        for model_id, entry in active.items():
            merged[model_id] = {**merged.get(model_id, {}), **entry.get("params", {})}
        self._cache = merged
        self._last_load = time.time()

    def maybe_reload(self) -> None:
        if time.time() - self._last_load >= self._poll_sec:
            self.reload()

    def get_params(self, model_id: str) -> dict[str, Any]:
        self.maybe_reload()
        return dict(self._cache.get(model_id, _DEFAULT_PARAMS.get(model_id, {})))

    def all_params(self) -> dict[str, dict[str, Any]]:
        self.maybe_reload()
        return dict(self._cache)

    def ensemble_weights(self, segment: str | None = None) -> dict[str, float]:
        ens = self.get_params("ensemble")
        if segment:
            seg_weights = (ens.get("segment_weights") or {}).get(segment)
            if isinstance(seg_weights, dict) and seg_weights:
                return dict(seg_weights)
        return dict(ens.get("weights") or _DEFAULT_PARAMS["ensemble"]["weights"])

    def active_versions(self) -> dict[str, int]:
        self.maybe_reload()
        active = self._store.active_params()
        return {mid: int(entry.get("version", 0)) for mid, entry in active.items()}
