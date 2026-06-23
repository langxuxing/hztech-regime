from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.models import Bias, OrderBookSnapshot, TradeAdvice

OBI_EMA_WINDOW_SEC = 300
COOLDOWN_MIN_SEC = 15 * 60
COOLDOWN_MAX_SEC = 30 * 60


@dataclass
class ObiSmoothed:
    raw: float
    smoothed: float
    samples: int
    as_of: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": round(self.raw, 4),
            "smoothed": round(self.smoothed, 4),
            "samples": self.samples,
            "as_of": self.as_of,
        }


@dataclass
class DebouncerState:
    obi: ObiSmoothed | None = None
    cooldown_active: bool = False
    cooldown_remaining_sec: int = 0
    locked_bias: Bias | None = None
    locked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "obi": self.obi.to_dict() if self.obi else None,
            "cooldown_active": self.cooldown_active,
            "cooldown_remaining_sec": self.cooldown_remaining_sec,
            "locked_bias": self.locked_bias,
            "locked_at": self.locked_at,
        }


@dataclass
class _ObiEmaState:
    value: float | None = None
    last_ts: float = 0.0
    samples: int = 0


@dataclass
class _CooldownState:
    advice: TradeAdvice | None = None
    locked_at: float = 0.0
    cooldown_sec: int = COOLDOWN_MIN_SEC


_obi_states: dict[str, _ObiEmaState] = {}
_cooldown_states: dict[str, _CooldownState] = {}
_lock = threading.Lock()


def compute_orderbook_obi(orderbook: OrderBookSnapshot, *, depth: int = 50) -> float:
    """前 N 档买卖盘名义价值失衡（快照深度由 orderbook_limit 控制，默认 50）。"""
    _ = depth  # 与 fetch_orderbook(limit=50) 对齐
    bid = orderbook.bid_depth_usdt
    ask = orderbook.ask_depth_usdt
    total = bid + ask
    if total <= 0:
        return orderbook.imbalance
    return (bid - ask) / total


def smooth_obi(raw_obi: float, *, symbol_key: str = "default", now: float | None = None) -> ObiSmoothed:
    now = now or time.time()
    with _lock:
        st = _obi_states.setdefault(symbol_key, _ObiEmaState())
        if st.value is None or st.last_ts <= 0:
            st.value = raw_obi
            st.samples = 1
        else:
            dt = max(0.001, now - st.last_ts)
            alpha = 1.0 - pow(0.5, dt / OBI_EMA_WINDOW_SEC)
            st.value = (1 - alpha) * st.value + alpha * raw_obi
            st.samples += 1
        st.last_ts = now
        smoothed = st.value
        samples = st.samples

    return ObiSmoothed(
        raw=raw_obi,
        smoothed=smoothed if smoothed is not None else raw_obi,
        samples=samples,
        as_of=datetime.now(timezone.utc).isoformat(),
    )


def apply_advice_cooldown(
    advice: TradeAdvice,
    *,
    symbol_key: str = "default",
    cooldown_sec: int | None = None,
    now: float | None = None,
) -> tuple[TradeAdvice, DebouncerState]:
    now = now or time.time()
    cd_sec = cooldown_sec or _pick_cooldown(advice.confidence)

    with _lock:
        st = _cooldown_states.setdefault(symbol_key, _CooldownState())
        elapsed = now - st.locked_at if st.locked_at and st.advice else cd_sec + 1
        remaining = max(0, int(st.cooldown_sec - elapsed))

        if st.advice is None or elapsed >= st.cooldown_sec:
            st.advice = advice
            st.locked_at = now
            st.cooldown_sec = cd_sec
            locked = advice
            active = False
            remaining = cd_sec
        elif advice.bias != st.advice.bias:
            locked = st.advice
            active = True
        else:
            blended = _blend_advice(st.advice, advice)
            st.advice = blended
            locked = blended
            active = remaining > 0

        state = DebouncerState(
            cooldown_active=active,
            cooldown_remaining_sec=remaining,
            locked_bias=st.advice.bias if st.advice else None,
            locked_at=datetime.fromtimestamp(st.locked_at, tz=timezone.utc).isoformat(),
        )

    if active and advice.bias != locked.bias:
        risks = list(locked.risks) + [f"信号防抖：方向翻转被冷却器拦截（原建议 {advice.bias}）"]
        locked = _clone_advice(locked, risks=risks)
    elif active:
        note = f"冷却锁定 {remaining // 60}min，bias={locked.bias}"
        risks = list(locked.risks) + [note]
        locked = _clone_advice(locked, risks=risks)

    return locked, state


def debounce_orderbook_and_advice(
    orderbook: OrderBookSnapshot | None,
    advice: TradeAdvice,
    *,
    symbol_key: str = "default",
    cooldown_sec: int | None = None,
    obi_state: ObiSmoothed | None = None,
) -> tuple[TradeAdvice, DebouncerState]:
    locked, state = apply_advice_cooldown(
        advice,
        symbol_key=symbol_key,
        cooldown_sec=cooldown_sec,
    )
    state.obi = obi_state
    return locked, state


def _pick_cooldown(confidence: float) -> int:
    if confidence >= 0.75:
        return COOLDOWN_MAX_SEC
    return COOLDOWN_MIN_SEC


def _blend_advice(prev: TradeAdvice, new: TradeAdvice) -> TradeAdvice:
    conf = max(prev.confidence, new.confidence) * 0.85 + new.confidence * 0.15
    return TradeAdvice(
        bias=prev.bias,
        confidence=conf,
        entry_zone=new.entry_zone or prev.entry_zone,
        stop_loss=new.stop_loss if new.stop_loss is not None else prev.stop_loss,
        take_profit=new.take_profit or prev.take_profit,
        time_horizon=new.time_horizon,
        reasoning=new.reasoning,
        risks=new.risks,
        confluence_score=max(prev.confluence_score, new.confluence_score),
        raw_llm=new.raw_llm or prev.raw_llm,
        rule_based=new.rule_based,
    )


def _clone_advice(
    advice: TradeAdvice,
    *,
    bias: Bias | None = None,
    confidence: float | None = None,
    risks: list[str] | None = None,
) -> TradeAdvice:
    return TradeAdvice(
        bias=bias if bias is not None else advice.bias,
        confidence=confidence if confidence is not None else advice.confidence,
        entry_zone=advice.entry_zone,
        stop_loss=advice.stop_loss,
        take_profit=advice.take_profit,
        time_horizon=advice.time_horizon,
        reasoning=advice.reasoning,
        risks=risks if risks is not None else advice.risks,
        confluence_score=advice.confluence_score,
        raw_llm=advice.raw_llm,
        rule_based=advice.rule_based,
    )
