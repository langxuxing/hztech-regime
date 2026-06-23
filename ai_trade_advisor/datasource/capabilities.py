from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import get_last_ohlcv_source, load_local_btc_1m_csvs
from ai_trade_advisor.datasource.paths import get_ohlcv_dir
from ai_trade_advisor.regime.optional_deps import optional_dependency_status
from ai_trade_advisor.regime.engines.vendor_paths import AKASH_LSTM_MODEL


def assess_data_capabilities(cfg: AdvisorConfig | None = None) -> dict[str, Any]:
    """按部署配置评估数据源可用层级。"""
    cfg = cfg or AdvisorConfig.from_env()
    has_cg = bool(cfg.coinglass_api_key)
    has_x = bool(cfg.x_bearer_token)
    local_1m = load_local_btc_1m_csvs()
    local_bars = len(local_1m) if local_1m is not None else 0

    tier = "free"
    if has_cg:
        tier = "coinglass"
    if has_cg and has_x:
        tier = "full"

    modules: dict[str, dict[str, Any]] = {
        "ohlcv": {
            "status": "ok" if local_bars >= 50 else "degraded",
            "source": get_last_ohlcv_source() or "local_btc_1m_resample",
            "local_1m_bars": local_bars,
            "note": "主路径：OKX 1m 本地 resample；BTC 禁止 ccxt fallback",
        },
        "ticker_orderbook": {"status": "ok", "note": "交易所 REST/ccxt"},
        "spot_cvd": {
            "status": "ok" if cfg.use_taker_cvd else "disabled",
            "note": "Binance taker；失败时不使用 ohlcv 代理",
        },
        "derivatives": {"status": "ok", "note": "Funding/OI via ccxt；主 funding 源"},
        "etf_btc": {
            "status": "ok" if has_cg or local_bars else "partial",
            "note": "本地 CSV / Farside / CoinGlass API",
        },
        "etf_eth": {
            "status": "ok" if has_cg else "missing_key",
            "note": "需 COINGLASS_API_KEY 或本地 CSV",
        },
        "fund_flow": {
            "status": "ok" if has_cg else "missing_key",
            "note": "CoinGlass netflow + exchange wallet",
        },
        "chain_activity": {
            "status": "ok",
            "note": "Blockchair 全网活跃度（非交易所净流入）",
        },
        "events_calendar": {
            "status": "ok" if has_cg else "degraded",
            "note": "CoinGlass API" if has_cg else "无 Key 时不启用 HTML scrape",
        },
        "events_x": {
            "status": "ok" if has_x else ("demo" if cfg.event_demo_mode else "missing_key"),
            "note": "X_BEARER_TOKEN" if has_x else "演示模式或跳过",
        },
        "macro_fred": {"status": "ok", "note": "FRED 日度同步"},
        "macro_ism": {"status": "fragile", "note": "Investing.com 非官方 API，建议替换"},
        "forecast_consensus": {"status": "ok", "note": "Binance/OKX 公开端点 + 恐惧贪婪"},
    }

    opt = optional_dependency_status()
    lstm_ok = opt["tensorflow"]["available"] and AKASH_LSTM_MODEL.exists()
    modules["regime_crypto_lstm"] = {
        "status": "ok" if lstm_ok else "missing_optional",
        "tensorflow": opt["tensorflow"]["available"],
        "model_artifacts": AKASH_LSTM_MODEL.exists(),
        "note": "已就绪" if lstm_ok else opt["tensorflow"]["install"],
    }
    modules["regime_heuristic_advanced"] = {
        "status": "ok" if opt["pandas_ta"]["available"] else "missing_optional",
        "note": opt["pandas_ta"]["install"] if not opt["pandas_ta"]["available"] else "pandas-ta 已安装",
    }

    return {
        "tier": tier,
        "coinglass_api_key": has_cg,
        "x_bearer_token": has_x,
        "event_demo_mode": cfg.event_demo_mode,
        "funding_primary_source": "binance_fapi",
        "modules": modules,
        "optional_dependencies": opt,
        "ohlcv_dir": str(get_ohlcv_dir("Btc")),
    }
