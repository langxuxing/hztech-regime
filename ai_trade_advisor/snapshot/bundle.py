from __future__ import annotations

import threading
from typing import Any

from ai_trade_advisor.bigevent.engine import run_event_analysis
from ai_trade_advisor.bigevent.store import EventStore
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.forecast.ensemble import fetch_from_config
from ai_trade_advisor.pipeline import run_advisor
from ai_trade_advisor.readiness import get_cached_readiness_tier
from ai_trade_advisor.regime.feedback.market_context import build_market_context
from ai_trade_advisor.regime.feedback.recommender import recommend_model
from ai_trade_advisor.regime.history import RegimeHistoryStore
from ai_trade_advisor.regime.models import MODEL_CATALOG
from ai_trade_advisor.regime.trend_judgment import build_trend_judgment
from ai_trade_advisor.serialize import dashboard_payload
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key

_refresh_locks: dict[str, threading.Lock] = {}
_refresh_guard = threading.Lock()


def _refresh_lock(key: str) -> threading.Lock:
    with _refresh_guard:
        if key not in _refresh_locks:
            _refresh_locks[key] = threading.Lock()
        return _refresh_locks[key]


def compute_dashboard_snapshot(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
    regime_store: RegimeHistoryStore | None = None,
) -> dict[str, Any]:
    """运行完整 pipeline 并返回 dashboard payload + 元数据。"""
    store = regime_store or RegimeHistoryStore()
    ctx, advice, _, board = run_advisor(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    store.record_if_changed(ctx.symbol, board.regime, as_of=ctx.as_of)
    mode = "rule_based" if advice.rule_based else "llm"
    meta = SnapshotStore.new_version()
    btc = ctx.btc_regime or {}
    mctx = build_market_context(btc)
    recommendation = None
    if btc:
        try:
            recommendation = recommend_model(
                mctx,
                symbol=ctx.symbol,
                window_days=cfg.regime_rollup_window_days,
            )
        except Exception:
            recommendation = None

    return {
        **meta,
        "exchange": cfg.exchange,
        "symbol": ctx.symbol,
        "as_of": ctx.as_of,
        "dashboard": dashboard_payload(ctx, advice, mode=mode, board=board),
        "state_machine": {
            "symbol": ctx.symbol,
            "as_of": ctx.as_of,
            **(ctx.quant_state or {}),
        },
        "models": {
            "symbol": ctx.symbol,
            "as_of": ctx.as_of,
            "catalog": MODEL_CATALOG,
            "models": btc.get("models") or {},
            "comparison": btc.get("model_comparison") or {},
            "close": btc.get("close"),
            "recommendation": recommendation,
        },
    }


def build_radar_bundle(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
    deep_scan_events: bool = False,
    regime_store: RegimeHistoryStore | None = None,
    event_store: EventStore | None = None,
) -> dict[str, Any]:
    """构建带版本号的雷达聚合快照（dashboard + events + consensus + history）。"""
    store = regime_store or RegimeHistoryStore()
    ev_store = event_store or EventStore()
    errors: list[str] = []

    core = compute_dashboard_snapshot(
        cfg,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
        regime_store=store,
    )
    symbol = core["symbol"]

    try:
        events_snap = run_event_analysis(cfg, store=ev_store)
        events = events_snap.to_dict()
    except Exception as exc:
        errors.append(f"events: {exc}")
        events = None

    try:
        consensus = fetch_from_config(cfg).to_dict()
    except Exception as exc:
        errors.append(f"consensus: {exc}")
        consensus = None

    try:
        history_rows = store.recent(symbol=symbol, limit=30)
        regime_history = {"symbol": symbol, "history": history_rows}
    except Exception as exc:
        errors.append(f"regime_history: {exc}")
        regime_history = None

    readiness_tier = "unknown"
    try:
        readiness_tier = get_cached_readiness_tier(cfg)
    except Exception as exc:
        errors.append(f"readiness: {exc}")

    dash = core.get("dashboard") or {}
    btc = dash.get("btc_regime") or {}
    trend_judgment = build_trend_judgment(
        btc,
        regime_confirmation=dash.get("regime_confirmation"),
        consensus=consensus,
        data_tier=readiness_tier,
        hmm_modifier=btc.get("hmm_modifier") or btc.get("hmm_confidence_modifier"),
        consensus_cap=cfg.consensus_opposing_confidence_cap,
    )

    return {
        "snapshot_id": core["snapshot_id"],
        "version": core["version"],
        "computed_at": core["computed_at"],
        "exchange": core["exchange"],
        "symbol": symbol,
        "as_of": core["as_of"],
        "dashboard": core["dashboard"],
        "state_machine": core["state_machine"],
        "models": core["models"],
        "events": events,
        "consensus": consensus,
        "regime_history": regime_history,
        "trend_judgment": trend_judgment,
        "readiness_tier": readiness_tier,
        "errors": errors,
        "deep_scan_events": deep_scan_events,
    }


def refresh_snapshot(
    cfg: AdvisorConfig,
    store: SnapshotStore,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> dict[str, Any]:
    """计算并持久化雷达快照（同 key 串行，避免并发重算）。"""
    key = snapshot_key(cfg)
    lock = _refresh_lock(key)
    with lock:
        cached = store.get(key)
        if cached and not store.is_stale(key, max_age_sec=30):
            return cached
        bundle = build_radar_bundle(
            cfg,
            skip_orderbook=skip_orderbook,
            skip_capital_flows=skip_capital_flows,
        )
        store.save(key, bundle)
        return bundle


def warmup_snapshot(
    cfg: AdvisorConfig,
    store: SnapshotStore,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> dict[str, Any]:
    """启动时同步预热（若无缓存或已过期则重算）。"""
    key = snapshot_key(cfg)
    cached = store.get(key)
    if cached and not store.is_stale(key, max_age_sec=cfg.snapshot_stale_sec):
        return cached
    return refresh_snapshot(
        cfg,
        store,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )


def load_snapshot(
    cfg: AdvisorConfig,
    store: SnapshotStore,
    *,
    max_age_sec: int,
    live: bool = False,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> tuple[dict[str, Any], bool]:
    """
    读取快照；若缺失/过期或 live=True 则重新计算。

    返回 (bundle, from_cache)。
    """
    key = snapshot_key(cfg)
    if not live:
        cached = store.get(key)
        if cached and not store.is_stale(key, max_age_sec):
            return cached, True

    bundle = refresh_snapshot(
        cfg,
        store,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    return bundle, False
