"""L3 转置矩阵惩罚与 Regime 防抖（最小驻留周期）。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from ai_trade_advisor.layers.types import CombinedRegimeStatus, ConfirmationState, InferenceResult

# 状态切换最小驻留 K 线数（业务防抖）
DEFAULT_MIN_DWELL_BARS = 3
# 转置惩罚：非相邻状态切换需更高置信度门槛
TRANSITION_PENALTY_CONFIDENCE = 0.78

_REGIME_ADJACENCY: dict[str, set[str]] = {
    "macro_frozen_range": {"high_vol_range", "mid_vol_range", "low_vol_range"},
    "high_vol_uptrend": {"mid_vol_uptrend", "fake_breakout_wash", "high_vol_range"},
    "fake_breakout_wash": {"high_vol_uptrend", "high_vol_range", "mid_vol_range"},
    "high_vol_downtrend": {"low_vol_downtrend", "high_vol_range", "high_vol_self_heal_range"},
    "high_vol_self_heal_range": {"high_vol_downtrend", "mid_vol_range", "low_vol_range"},
    "low_vol_uptrend": {"mid_vol_uptrend", "low_vol_range"},
    "mid_vol_uptrend": {"low_vol_uptrend", "high_vol_uptrend", "mid_vol_range"},
    "low_vol_downtrend": {"high_vol_downtrend", "low_vol_range"},
    "low_vol_range": {"mid_vol_range", "low_vol_uptrend", "low_vol_downtrend"},
    "mid_vol_range": {"low_vol_range", "high_vol_range", "mid_vol_uptrend"},
    "high_vol_range": {"mid_vol_range", "high_vol_uptrend", "high_vol_downtrend", "fake_breakout_wash"},
}


@dataclass
class _DwellState:
    regime_id: str
    locked_at: float
    dwell_bars: int = 0


_dwell_states: dict[str, _DwellState] = {}
_lock = threading.Lock()


def stabilize_regime(
    inference: InferenceResult,
    *,
    symbol_key: str = "default",
    min_dwell_bars: int = DEFAULT_MIN_DWELL_BARS,
    bar_minutes: int = 30,
) -> ConfirmationState:
    """
    df_confirmed 基础上的 Regime 防抖：
    - 转置矩阵惩罚：非相邻状态需 confidence >= TRANSITION_PENALTY_CONFIDENCE
    - 最小驻留：未达 min_dwell_bars 不切换 confirmed 状态
    """
    live_id = inference.regime_id
    live_label = inference.regime_label
    confidence = inference.confidence
    dashboard = inference.raw.dashboard_regime if inference.raw else "transition"
    drivers = list(inference.raw.drivers if inference.raw else [])

    notes: list[str] = []
    penalty_applied = False
    switched = False
    now = time.time()

    with _lock:
        st = _dwell_states.setdefault(symbol_key, _DwellState(regime_id=live_id, locked_at=now))
        elapsed_bars = int((now - st.locked_at) / max(bar_minutes * 60, 1))
        st.dwell_bars = elapsed_bars

        confirmed_id = st.regime_id
        if live_id != confirmed_id:
            adjacent = live_id in _REGIME_ADJACENCY.get(confirmed_id, set())
            needs_penalty = not adjacent
            if needs_penalty and confidence < TRANSITION_PENALTY_CONFIDENCE:
                penalty_applied = True
                notes.append(
                    f"转置惩罚：{confirmed_id}→{live_id} 需置信度≥{TRANSITION_PENALTY_CONFIDENCE}"
                )
            elif elapsed_bars < min_dwell_bars:
                notes.append(f"驻留不足：{elapsed_bars}/{min_dwell_bars} bars，维持 {confirmed_id}")
            else:
                st.regime_id = live_id
                st.locked_at = now
                st.dwell_bars = 0
                confirmed_id = live_id
                switched = True
                notes.append(f"状态切换确认：→ {live_id}")

        dwell = st.dwell_bars

    if confirmed_id != live_id:
        live_label = _label_for(confirmed_id) or live_label
        if inference.raw:
            dashboard = inference.raw.dashboard_regime

    combined = CombinedRegimeStatus(
        live_regime_id=live_id,
        confirmed_regime_id=confirmed_id,
        regime_label=live_label if confirmed_id == live_id else _label_for(confirmed_id) or live_label,
        confidence=confidence,
        dashboard_regime=dashboard,
        drivers=drivers,
    )

    return ConfirmationState(
        combined=combined,
        transition_penalty_applied=penalty_applied,
        dwell_bars=dwell,
        min_dwell_bars=min_dwell_bars,
        regime_switched=switched,
        notes=notes,
    )


def _label_for(regime_id: str) -> str | None:
    from ai_trade_advisor.regime.engine import _REGIME_LABELS

    return _REGIME_LABELS.get(regime_id)


def reset_dwell_state(symbol_key: str = "default") -> None:
    """测试用：重置防抖状态。"""
    with _lock:
        _dwell_states.pop(symbol_key, None)
