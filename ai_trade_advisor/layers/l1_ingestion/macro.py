"""L1 跨市场慢变量与资金流。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.capital_flows import build_capital_flows
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState, evaluate_macro_hazard
from ai_trade_advisor.models import CapitalFlowsSnapshot


def build_macro_flow_features(
    cfg: AdvisorConfig,
    *,
    skip_capital_flows: bool = False,
) -> tuple[dict[str, Any], MacroHazardState, CapitalFlowsSnapshot | None]:
    """ETF 净流入、宏观 hazard、链上资金流。"""
    macro = evaluate_macro_hazard(cfg)
    flows = None if skip_capital_flows else build_capital_flows(cfg)

    etf_z = _etf_flow_zscore(flows)
    macro_events = macro.active_events or []

    return {
        "macro_hazard": macro.macro_hazard_flag,
        "macro_events": macro_events,
        "etf_flow_zscore": etf_z,
        "etf_interpretation": flows.btc_etf.interpretation if flows and flows.btc_etf else None,
        "etf_7d_usd": flows.btc_etf.total_7d_usd if flows and flows.btc_etf else None,
        "wallet_net_1d": (
            flows.btc_exchange_wallet.net_to_exchange_1d
            if flows and flows.btc_exchange_wallet
            else None
        ),
    }, macro, flows


def _etf_flow_zscore(flows: CapitalFlowsSnapshot | None) -> float | None:
    """ETF 日净流入标准差化（慢变量纠偏因子）。"""
    if flows is None or flows.btc_etf is None:
        return None
    hist = [d.flow_usd for d in flows.btc_etf.history if d.flow_usd is not None]
    if len(hist) < 5:
        return None
    import statistics

    mean = statistics.mean(hist)
    stdev = statistics.stdev(hist) if len(hist) > 1 else 1.0
    latest = flows.btc_etf.latest.flow_usd if flows.btc_etf.latest else None
    if latest is None or stdev == 0:
        return None
    return round((latest - mean) / stdev, 3)
