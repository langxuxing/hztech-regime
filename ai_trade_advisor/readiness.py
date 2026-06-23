"""生产就绪度检查：API Key、本地数据、调度器依赖。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.capital_flows import build_capital_flows
from ai_trade_advisor.datasource.paths import get_data_root, get_ohlcv_dir, get_macro_root
from ai_trade_advisor.datasource.ohlcv import _MIN_LOCAL_BARS, load_local_btc_1m_csvs, resample_from_1m


@dataclass
class ReadinessReport:
    tier: str  # production | degraded | demo
    checks: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    capital_flows_quality: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "checks": self.checks,
            "notes": self.notes,
            "capital_flows_quality": self.capital_flows_quality,
        }


def check_readiness(cfg: AdvisorConfig | None = None) -> ReadinessReport:
    """评估当前环境是否满足各业务层最低数据要求。"""
    cfg = cfg or AdvisorConfig.from_env()
    notes: list[str] = []
    checks: dict[str, bool] = {}

    checks["coinglass_api_key"] = bool(cfg.coinglass_api_key)
    checks["x_bearer_token"] = bool(cfg.x_bearer_token)
    checks["ai_api_key"] = bool(cfg.ai_api_key)
    checks["binance_config"] = bool(cfg.binance_config_path) or bool(
        os.getenv("BINANCE_API_KEY", "").strip()
    )

    btc_dir = get_ohlcv_dir("Btc")
    df_1m = load_local_btc_1m_csvs()
    local_btc_ok = False
    if df_1m is not None and len(df_1m) >= 500:
        resampled = resample_from_1m(df_1m, cfg.bar_minutes)
        local_btc_ok = len(resampled) >= _MIN_LOCAL_BARS
    checks["local_btc_1m"] = local_btc_ok
    checks["btc_1m_files"] = bool(list(btc_dir.glob("btc_usdt_swap_mark_1m_*.csv")))

    macro_root = get_macro_root()
    checks["macro_layout"] = macro_root.is_dir() and any(macro_root.iterdir())
    etf_root = cfg.etfdata_dir or (get_data_root() / "ETF")
    checks["etf_data"] = bool(list(etf_root.rglob("*.csv"))) if etf_root.exists() else False

    try:
        flows = build_capital_flows(cfg)
        cf_quality = flows.data_quality
    except Exception as exc:
        cf_quality = f"error: {exc}"
        notes.append(str(exc))

    if not checks["local_btc_1m"]:
        notes.append(
            "本地 BTC 1m 不足：运行 ./scripts/download_btc.sh 或 start-data-scheduler.sh"
        )
    if not checks["coinglass_api_key"]:
        notes.append("未配置 COINGLASS_API_KEY：资金流/日历降级")
    if not checks["x_bearer_token"] and not cfg.event_demo_mode:
        notes.append("未配置 X_BEARER_TOKEN：突发事件监控跳过")
    if not checks["ai_api_key"]:
        notes.append("未配置 AI_API_KEY：LLM 建议将走规则兜底")

    tier = "production"
    if not checks["coinglass_api_key"] or cf_quality in ("partial", "free_only"):
        tier = "degraded"
    if cfg.event_demo_mode or (not checks["x_bearer_token"] and not checks["coinglass_api_key"]):
        tier = "demo"
    if not checks["local_btc_1m"] and not cfg.allow_ccxt_ohlcv_fallback:
        notes.append("ALLOW_CCXT_OHLCV_FALLBACK=false 且本地数据不足 → pipeline 将失败")
        tier = "demo"

    return ReadinessReport(
        tier=tier,
        checks=checks,
        notes=notes,
        capital_flows_quality=str(cf_quality),
    )
