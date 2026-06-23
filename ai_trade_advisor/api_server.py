#!/usr/bin/env python3
"""本地看板 API（Flask）：为 Flutter 前端提供 JSON 数据。"""

from __future__ import annotations

import argparse
import threading
import time

from flask import Flask, jsonify, request

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import ensure_data_layout
from ai_trade_advisor.bigevent.engine import run_event_analysis
from ai_trade_advisor.bigevent.models import EventAnalysisSnapshot
from ai_trade_advisor.bigevent.store import EventStore
from ai_trade_advisor.regime.history import RegimeHistoryStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.models import MODEL_CATALOG
from ai_trade_advisor.regime.feedback.service import record_human_judgment_with_scoring
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.feedback.recommender import recommend_model
from ai_trade_advisor.regime.feedback.market_context import build_market_context
from ai_trade_advisor.regime.feedback.calibrator import run_calibration
from ai_trade_advisor.regime.feedback.worker import run_forward_scoring_batch
from ai_trade_advisor.datasource.capabilities import assess_data_capabilities
from ai_trade_advisor.datasource.scheduler_meta import SchedulerMetaStore
from ai_trade_advisor.forecast.ensemble import fetch_from_config
from ai_trade_advisor.snapshot.bundle import load_snapshot, refresh_snapshot, warmup_snapshot
from ai_trade_advisor.snapshot.store import SnapshotStore
from ai_trade_advisor.api_auth import register_api_auth

app = Flask(__name__)

_event_cache: EventAnalysisSnapshot | None = None
_event_lock = threading.Lock()
_poll_thread: threading.Thread | None = None
_feedback_thread: threading.Thread | None = None
_snapshot_thread: threading.Thread | None = None
_skip_orderbook = False
_skip_capital_flows = False
_regime_store = RegimeHistoryStore()
_judgment_store = HumanJudgmentStore()
_feedback_store = FeedbackStore()
_snapshot_store = SnapshotStore()


def _live_requested() -> bool:
    return request.args.get("live", "false").lower() in ("1", "true", "yes")


def _refresh_requested() -> bool:
    return request.args.get("refresh", "false").lower() in ("1", "true", "yes")


def _load_bundle(cfg: AdvisorConfig) -> tuple[dict, bool]:
    live = _live_requested() or _refresh_requested()
    return load_snapshot(
        cfg,
        _snapshot_store,
        max_age_sec=cfg.snapshot_stale_sec,
        live=live,
        skip_orderbook=_skip_orderbook,
        skip_capital_flows=_skip_capital_flows,
    )


@app.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, Authorization"
    return response


@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    cfg = AdvisorConfig.from_env()
    key = f"{cfg.exchange}_{cfg.symbol.replace('/', '_').replace(':', '_')}"
    age = _snapshot_store.age_seconds(key)
    return jsonify(
        {
            "status": "ok",
            "snapshot_age_sec": age,
            "snapshot_stale_sec": cfg.snapshot_stale_sec,
        }
    )


@app.route("/api/radar", methods=["GET", "OPTIONS"])
def radar():
    """聚合雷达快照（单次拉取，带 version / snapshot_id）。"""
    cfg = _cfg_from_query()
    try:
        bundle, from_cache = _load_bundle(cfg)
        bundle["from_cache"] = from_cache
        return jsonify(bundle)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/scheduler/status", methods=["GET", "OPTIONS"])
def scheduler_status():
    """数据调度任务与各模块能力层级。"""
    cfg = AdvisorConfig.from_env()
    try:
        return jsonify(
            {
                "scheduler": SchedulerMetaStore().status(),
                "capabilities": assess_data_capabilities(cfg),
                "snapshot_age_sec": _snapshot_store.age_seconds(
                    f"{cfg.exchange}_{cfg.symbol.replace('/', '_').replace(':', '_')}"
                ),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/trend-consensus", methods=["GET", "OPTIONS"])
def trend_consensus():
    cfg = _cfg_from_query()
    try:
        bundle, _ = _load_bundle(cfg)
        if bundle.get("consensus") and not _live_requested():
            return jsonify(bundle["consensus"])
        consensus = fetch_from_config(cfg)
        return jsonify(consensus.to_dict())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/history", methods=["GET", "OPTIONS"])
def regime_history():
    symbol = request.args.get("symbol", "BTC/USDT:USDT").strip()
    try:
        limit = int(request.args.get("limit", "30"))
    except ValueError:
        limit = 30
    try:
        cfg = _cfg_from_query()
        if symbol == cfg.symbol and not _live_requested():
            bundle, _ = _load_bundle(cfg)
            hist = bundle.get("regime_history")
            if hist:
                rows = hist.get("history") or []
                return jsonify({"symbol": symbol, "history": rows[:limit]})
        rows = _regime_store.recent(symbol=symbol, limit=max(1, min(limit, 100)))
        return jsonify({"symbol": symbol, "history": rows})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/models", methods=["GET", "OPTIONS"])
def regime_models():
    cfg = _cfg_from_query()
    try:
        bundle, from_cache = _load_bundle(cfg)
        models = bundle.get("models") or {}
        models["from_cache"] = from_cache
        models["version"] = bundle.get("version")
        return jsonify(models)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/human-judgment", methods=["GET", "POST", "OPTIONS"])
def human_judgment():
    symbol = request.args.get("symbol", "BTC/USDT:USDT").strip()

    if request.method == "GET":
        try:
            limit = int(request.args.get("limit", "20"))
        except ValueError:
            limit = 20
        try:
            rows = _judgment_store.recent(
                symbol=symbol, limit=max(1, min(limit, 100)), with_scores=True
            )
            latest = _judgment_store.latest(symbol)
            if latest:
                latest["scores"] = _feedback_store.scores_for_judgment(latest["id"])
            return jsonify({"symbol": symbol, "latest": latest, "history": rows})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    body = request.get_json(silent=True) or {}
    human_regime = (body.get("human_regime") or "").strip()
    if not human_regime:
        return jsonify({"error": "human_regime is required"}), 400

    cfg = _cfg_from_query()
    try:
        bundle, _ = _load_bundle(cfg)
        dash = bundle.get("dashboard") or {}
        btc = dash.get("btc_regime") or {}
        advice = dash.get("advice")
        board = dash.get("board") or {}
        board_regime = (board.get("regime") or {}).get("regime")
        result = record_human_judgment_with_scoring(
            cfg.symbol,
            human_regime=human_regime,
            human_trend=(body.get("human_trend") or "").strip() or None,
            human_notes=(body.get("human_notes") or "").strip() or None,
            btc_regime=btc,
            advice=advice,
            board_regime=board_regime,
            as_of=dash.get("as_of"),
            judgment_store=_judgment_store,
            feedback_store=_feedback_store,
        )
        return jsonify({"ok": True, "symbol": cfg.symbol, **result})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/model-scores", methods=["GET", "OPTIONS"])
def regime_model_scores():
    try:
        judgment_id = int(request.args.get("judgment_id", "0"))
    except ValueError:
        return jsonify({"error": "judgment_id required"}), 400
    try:
        scores = _feedback_store.scores_for_judgment(judgment_id)
        return jsonify({"judgment_id": judgment_id, "scores": scores})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/model-leaderboard", methods=["GET", "OPTIONS"])
def regime_model_leaderboard():
    symbol = request.args.get("symbol", "").strip()
    segment = request.args.get("segment", "").strip()
    try:
        window_days = int(request.args.get("window_days", "30"))
    except ValueError:
        window_days = 30
    try:
        rows = _feedback_store.leaderboard(
            symbol=symbol, segment=segment, window_days=window_days
        )
        return jsonify(
            {"symbol": symbol or None, "segment": segment or None, "leaderboard": rows}
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/recommended-model", methods=["GET", "OPTIONS"])
def regime_recommended_model():
    cfg = _cfg_from_query()
    try:
        bundle, from_cache = _load_bundle(cfg)
        models = bundle.get("models") or {}
        rec = models.get("recommendation")
        if rec is None:
            btc = (bundle.get("dashboard") or {}).get("btc_regime") or {}
            mctx = build_market_context(btc)
            rec = recommend_model(
                mctx,
                symbol=bundle.get("symbol", cfg.symbol),
                window_days=cfg.regime_rollup_window_days,
            )
        return jsonify(
            {
                "symbol": bundle.get("symbol", cfg.symbol),
                "as_of": bundle.get("as_of"),
                "recommendation": rec,
                "from_cache": from_cache,
                "version": bundle.get("version"),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/regime/calibrate", methods=["POST", "OPTIONS"])
def regime_calibrate():
    cfg = _cfg_from_query()
    try:
        fwd = run_forward_scoring_batch(cfg, store=_feedback_store)
        cal = run_calibration(cfg, store=_feedback_store)
        return jsonify({"forward": fwd, "calibration": cal})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/state-machine", methods=["GET", "OPTIONS"])
def state_machine():
    cfg = _cfg_from_query()
    try:
        bundle, from_cache = _load_bundle(cfg)
        payload = bundle.get("state_machine") or {}
        payload["from_cache"] = from_cache
        payload["version"] = bundle.get("version")
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/dashboard", methods=["GET", "OPTIONS"])
def dashboard():
    cfg = _cfg_from_query()
    try:
        bundle, from_cache = _load_bundle(cfg)
        dash = dict(bundle.get("dashboard") or {})
        dash["snapshot_id"] = bundle.get("snapshot_id")
        dash["version"] = bundle.get("version")
        dash["computed_at"] = bundle.get("computed_at")
        dash["from_cache"] = from_cache
        return jsonify(dash)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/events", methods=["GET", "OPTIONS"])
@app.route("/api/events/scan", methods=["GET", "OPTIONS"])
@app.route("/api/events/calendar", methods=["GET", "OPTIONS"])
def events():
    return _handle_events(force_scan=request.path == "/api/events/scan")


def _cfg_from_query() -> AdvisorConfig:
    cfg = AdvisorConfig.from_env()
    if exchange := request.args.get("exchange", "").strip():
        cfg.exchange = exchange
    if symbol := request.args.get("symbol", "").strip():
        cfg.symbol = symbol
    if bar := request.args.get("bar_minutes", "").strip():
        try:
            cfg.bar_minutes = int(bar)
        except ValueError:
            pass
    if request.args.get("use_local_pepe", "false").lower() in ("1", "true", "yes"):
        cfg.use_local_pepe = True
    return cfg


def _handle_events(*, force_scan: bool):
    global _event_cache
    cfg = AdvisorConfig.from_env()
    refresh = request.args.get("refresh", "false").lower() in ("1", "true", "yes")
    path = request.path

    try:
        if not force_scan and not refresh:
            bundle, _ = _load_bundle(_cfg_from_query())
            if bundle.get("events"):
                payload = bundle["events"]
                if path == "/api/events/calendar":
                    payload = {
                        "as_of": payload["as_of"],
                        "calendar_events": payload["calendar_events"],
                        "upcoming_high_impact": payload["upcoming_high_impact"],
                        "summary": payload["summary"],
                    }
                payload["version"] = bundle.get("version")
                return jsonify(payload)

        with _event_lock:
            if force_scan or refresh or _event_cache is None:
                _event_cache = run_event_analysis(cfg, store=EventStore())
            snap = _event_cache

        payload = snap.to_dict()
        if path == "/api/events/calendar":
            payload = {
                "as_of": payload["as_of"],
                "calendar_events": payload["calendar_events"],
                "upcoming_high_impact": payload["upcoming_high_impact"],
                "summary": payload["summary"],
            }
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _start_feedback_poller(interval_hours: int) -> None:
    def _loop() -> None:
        while True:
            try:
                cfg = AdvisorConfig.from_env()
                fwd = run_forward_scoring_batch(cfg, store=_feedback_store)
                cal = run_calibration(cfg, store=_feedback_store)
                print(
                    f"[feedback-poller] forward={fwd.get('processed')} "
                    f"calibrated={cal.get('activated')}"
                )
            except Exception as exc:
                print(f"[feedback-poller] 错误: {exc}")
            time.sleep(max(interval_hours, 1) * 3600)

    t = threading.Thread(target=_loop, daemon=True, name="feedback-poller")
    t.start()
    global _feedback_thread
    _feedback_thread = t


def _start_event_poller(interval_sec: int) -> None:
    def _loop() -> None:
        global _event_cache
        while True:
            try:
                cfg = AdvisorConfig.from_env()
                with _event_lock:
                    _event_cache = run_event_analysis(cfg, store=EventStore())
                    snap = _event_cache
                print(f"[event-poller] 扫描完成，突发 {len(snap.breaking_events)} 条")
            except Exception as exc:
                print(f"[event-poller] 错误: {exc}")
            time.sleep(max(interval_sec, 60))

    t = threading.Thread(target=_loop, daemon=True, name="event-poller")
    t.start()
    global _poll_thread
    _poll_thread = t


def _start_snapshot_poller(interval_sec: int) -> None:
    def _loop() -> None:
        while True:
            try:
                cfg = AdvisorConfig.from_env()
                bundle = refresh_snapshot(
                    cfg,
                    _snapshot_store,
                    skip_orderbook=_skip_orderbook,
                    skip_capital_flows=_skip_capital_flows,
                )
                print(
                    f"[snapshot-poller] v={bundle.get('version')} "
                    f"as_of={bundle.get('as_of')}"
                )
            except Exception as exc:
                print(f"[snapshot-poller] 错误: {exc}")
            time.sleep(max(interval_sec, 30))

    t = threading.Thread(target=_loop, daemon=True, name="snapshot-poller")
    t.start()
    global _snapshot_thread
    _snapshot_thread = t


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regime & Trend 看板 API (Flask)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-orderbook", action="store_true")
    parser.add_argument("--skip-capital-flows", action="store_true", help="跳过 ETF/链上/资金流抓取")
    parser.add_argument("--with-capital-flows", action="store_true", help="(已默认开启) 抓取 ETF/链上/资金流")
    parser.add_argument("--poll-feedback", action="store_true", help="后台定时延迟打分与校准")
    parser.add_argument("--poll-events", action="store_true", help="后台定时扫描事件")
    parser.add_argument(
        "--poll-snapshots",
        action="store_true",
        help="后台定时刷新看板快照",
    )
    parser.add_argument(
        "--no-poll-snapshots",
        action="store_true",
        help="禁用后台快照轮询",
    )
    parser.add_argument(
        "--warmup-snapshot",
        action="store_true",
        help="启动前同步预热快照（覆盖 SNAPSHOT_WARMUP_ON_START=false）",
    )
    parser.add_argument(
        "--no-warmup-snapshot",
        action="store_true",
        help="跳过启动预热",
    )
    args = parser.parse_args(argv)

    layout = ensure_data_layout()
    print(f"数据目录: {layout['root']}")
    print(f"  SQLite: {layout['db'] / 'events.db'}")
    print(f"  Regime: {layout['db'] / 'regime_history.db'}")
    print(f"  缓存:   {layout['cache']}")
    print(f"  快照:   {layout['cache'] / 'snapshots'}")
    print(f"  导出:   {layout['exports']}")
    print(f"  日志:   {layout['logs']}")

    global _skip_orderbook, _skip_capital_flows
    _skip_orderbook = args.skip_orderbook
    _skip_capital_flows = args.skip_capital_flows
    EventStore()

    cfg = AdvisorConfig.from_env()
    register_api_auth(app, cfg.api_key)
    if cfg.api_key:
        print("API Key 鉴权已启用（/health 除外）")

    warmup = (cfg.snapshot_warmup_on_start or args.warmup_snapshot) and not args.no_warmup_snapshot
    if warmup:
        try:
            print("[snapshot-warmup] 预热快照...")
            bundle = warmup_snapshot(
                cfg,
                _snapshot_store,
                skip_orderbook=_skip_orderbook,
                skip_capital_flows=_skip_capital_flows,
            )
            print(f"[snapshot-warmup] 完成 v={bundle.get('version')}")
        except Exception as exc:
            print(f"[snapshot-warmup] 失败（API 仍将启动）: {exc}")

    poll_snapshots = args.poll_snapshots and not args.no_poll_snapshots
    if poll_snapshots:
        _start_snapshot_poller(cfg.snapshot_poll_interval_sec)
        print(f"快照轮询已启动，间隔 {cfg.snapshot_poll_interval_sec}s")

    if args.poll_events:
        _start_event_poller(cfg.event_poll_interval_sec)
        print(f"事件轮询已启动，间隔 {cfg.event_poll_interval_sec}s")

    if args.poll_feedback:
        _start_feedback_poller(cfg.regime_calibration_interval_hours)
        print(f"反馈闭环轮询已启动，间隔 {cfg.regime_calibration_interval_hours}h")

    print(f"看板 API 运行于 http://{args.host}:{args.port}")
    print("  雷达聚合: /api/radar")
    print("  交易看板: /api/dashboard")
    print("  趋势集成: /api/trend-consensus")
    print("  状态机:   /api/state-machine")
    print("  Regime 历史: /api/regime/history")
    print("  多模型对比: /api/regime/models")
    print("  人工判断:   /api/regime/human-judgment (GET/POST)")
    print("  模型打分:   /api/regime/model-scores")
    print("  Leaderboard: /api/regime/model-leaderboard")
    print("  推荐模型:   /api/regime/recommended-model")
    print("  手动校准:   POST /api/regime/calibrate")
    print("  强制重算:   任意端点加 ?live=true")
    print("  调度状态:   /api/scheduler/status")

    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
