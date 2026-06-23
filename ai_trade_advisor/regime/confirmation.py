"""L3 Regime 信号防抖：df_confirmed 隔离 + 转置惩罚 + 最小驻留。"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from ai_trade_advisor.layers.types import CombinedRegimeStatus, ConfirmationState
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis
from ai_trade_advisor.signal.debouncer import DebouncerState

_REGIME_LABELS: dict[str, str] = {
    "macro_frozen_range": "宏观熔断 · 强制观望",
    "high_vol_uptrend": "高波上涨 · 现货 CVD 确认",
    "fake_breakout_wash": "假突破洗盘 · 缺现货买盘",
    "high_vol_downtrend": "高波下跌 · 趋势延续",
    "high_vol_self_heal_range": "高波自愈区间 · CVD 底背离",
    "low_vol_uptrend": "低波上行 · 趋势延续",
    "mid_vol_uptrend": "中波上行 · 趋势延续",
    "low_vol_downtrend": "低波下行 · 趋势延续",
    "low_vol_range": "低波死寂 · 震荡",
    "mid_vol_range": "中波震荡 · 等待突破",
    "high_vol_range": "高波震荡 · 事件驱动",
}


@dataclass
class _RegimeDwellState:
    published_regime_id: str
    pending_regime_id: str | None
    dwell_bars: int = 0
    last_hmm_state: int = -1


_regime_states: dict[str, _RegimeDwellState] = {}
_lock = threading.Lock()


def apply_transition_penalty(
    state_probs: list[float],
    prev_state_idx: int,
    *,
    penalty: float = 0.35,
) -> tuple[list[float], bool]:
    """
    转置矩阵惩罚：降低非当前 HMM 状态的概率，抑制毛刺切换。

    返回 (调整后概率, 是否应用了惩罚)。
    """
    if prev_state_idx < 0 or not state_probs or len(state_probs) < 2:
        return state_probs, False
    if prev_state_idx >= len(state_probs):
        return state_probs, False

    adjusted = list(state_probs)
    for i in range(len(adjusted)):
        if i != prev_state_idx:
            adjusted[i] *= max(0.0, 1.0 - penalty)

    total = sum(adjusted)
    if total <= 0:
        return state_probs, False
    return [p / total for p in adjusted], True


def confirm_regime_state(
    *,
    symbol_key: str,
    live: BtcRegimeAnalysis,
    confirmed: BtcRegimeAnalysis,
    min_dwell_bars: int = 2,
    transition_penalty: float = 0.35,
    debouncer: DebouncerState | None = None,
) -> ConfirmationState:
    """
    将 live（含未收盘 K）与 confirmed（df_confirmed）双轨合并为稳定输出。

    - confirmed 信号作为切换候选
    - 需连续 min_dwell_bars 次 confirmed 与 published 不同才切换
    - HMM 状态概率经 transition_penalty 平滑
    """
    live_id = live.regime_id
    confirmed_id = confirmed.regime_id
    notes: list[str] = []

    hmm_probs = None
    penalty_applied = False
    triad = live.triad or {}
    hmm_block = triad.get("hmm") or {}
    raw_probs = hmm_block.get("state_probs")
    prev_state = _get_prev_hmm_state(symbol_key)

    if isinstance(raw_probs, list) and raw_probs:
        hmm_probs, penalty_applied = apply_transition_penalty(
            raw_probs,
            prev_state,
            penalty=transition_penalty,
        )
        if penalty_applied:
            notes.append(f"转置惩罚 {transition_penalty:.0%} 已应用于 HMM 状态概率")
        current_state = int(hmm_block.get("current_state", -1))
        _store_hmm_state(symbol_key, current_state)

    published_id, dwell, switched = _update_dwell(
        symbol_key,
        confirmed_id,
        min_dwell_bars=min_dwell_bars,
    )

    if switched:
        notes.append(f"Regime 切换: {published_id}（驻留 {dwell} 根 confirmed K）")
    elif confirmed_id != published_id:
        notes.append(
            f"防抖拦截: confirmed={confirmed_id}，维持 published={published_id} "
            f"({dwell}/{min_dwell_bars} 根)"
        )
    else:
        notes.append(f"Regime 稳定: {published_id}")

    label = _REGIME_LABELS.get(published_id, published_id)
    confidence = confirmed.confidence
    if penalty_applied and hmm_probs:
        max_prob = max(hmm_probs)
        confidence = min(confidence, max(0.35, max_prob))

    if live.in_regime_transition:
        confidence = min(confidence, 0.55)
        notes.append("BOCPD 变点期 → 置信度上限 55%")

    dashboard = live.dashboard_regime
    if published_id != live_id:
        dashboard = confirmed.dashboard_regime

    combined = CombinedRegimeStatus(
        live_regime_id=live_id,
        confirmed_regime_id=published_id,
        regime_label=label,
        confidence=confidence,
        dashboard_regime=dashboard,
        drivers=list(dict.fromkeys(list(live.drivers) + list(confirmed.drivers)))[:12],
    )

    return ConfirmationState(
        combined=combined,
        transition_penalty_applied=penalty_applied,
        dwell_bars=dwell,
        min_dwell_bars=min_dwell_bars,
        regime_switched=switched,
        debouncer=debouncer,
        advice_locked=bool(debouncer and debouncer.cooldown_active),
        notes=notes,
    )


def merge_confirmed_into_regime_dict(
    regime: dict[str, Any],
    confirmation: ConfirmationState,
) -> dict[str, Any]:
    """将防抖后的 confirmed 状态写回 btc_regime 字典。"""
    out = dict(regime)
    combined = confirmation.combined
    out["regime_id"] = combined.confirmed_regime_id
    out["regime_label"] = combined.regime_label
    out["confidence"] = combined.confidence
    out["dashboard_regime"] = combined.dashboard_regime
    out["live_regime_id"] = combined.live_regime_id
    out["confirmation"] = confirmation.to_dict()
    if confirmation.notes:
        drivers = list(out.get("drivers") or [])
        drivers.extend(confirmation.notes[:2])
        out["drivers"] = drivers[:14]
    from ai_trade_advisor.regime.matrix import enrich_regime_dict

    return enrich_regime_dict(out)


def _update_dwell(
    symbol_key: str,
    confirmed_id: str,
    *,
    min_dwell_bars: int,
) -> tuple[str, int, bool]:
    with _lock:
        state = _regime_states.get(symbol_key)
        if state is None:
            state = _RegimeDwellState(
                published_regime_id=confirmed_id,
                pending_regime_id=None,
                dwell_bars=min_dwell_bars,
            )
            _regime_states[symbol_key] = state
            return confirmed_id, min_dwell_bars, False

        if confirmed_id == state.published_regime_id:
            state.pending_regime_id = None
            state.dwell_bars = min_dwell_bars
            return state.published_regime_id, state.dwell_bars, False

        if state.pending_regime_id != confirmed_id:
            state.pending_regime_id = confirmed_id
            state.dwell_bars = 1
            return state.published_regime_id, state.dwell_bars, False

        state.dwell_bars += 1
        if state.dwell_bars >= min_dwell_bars:
            old = state.published_regime_id
            state.published_regime_id = confirmed_id
            state.pending_regime_id = None
            state.dwell_bars = min_dwell_bars
            return state.published_regime_id, state.dwell_bars, old != confirmed_id

        return state.published_regime_id, state.dwell_bars, False


def _get_prev_hmm_state(symbol_key: str) -> int:
    with _lock:
        state = _regime_states.get(symbol_key)
        return state.last_hmm_state if state else -1


def _store_hmm_state(symbol_key: str, state_idx: int) -> None:
    with _lock:
        dwell = _regime_states.get(symbol_key)
        if dwell is None:
            _regime_states[symbol_key] = _RegimeDwellState(
                published_regime_id="low_vol_range",
                pending_regime_id=None,
            )
            dwell = _regime_states[symbol_key]
        dwell.last_hmm_state = state_idx


def reset_regime_debouncer(symbol_key: str | None = None) -> None:
    """测试辅助：清空防抖状态。"""
    with _lock:
        if symbol_key is None:
            _regime_states.clear()
        else:
            _regime_states.pop(symbol_key, None)
