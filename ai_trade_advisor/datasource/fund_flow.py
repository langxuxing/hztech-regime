from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.http_client import get_json
from ai_trade_advisor.models import ExchangeWalletFlow, FlowPeriod, MarketFundFlow

COINGLASS_BASE = "https://open-api-v4.coinglass.com"
DEFAULT_EXCHANGES = "Binance,OKX,Bybit,Bitget,Gate"
PERIOD_KEYS = (
    ("24h", "24h"),
    ("7d", "7d"),
    ("30d", "30d"),
)


def fetch_market_fund_flows(cfg: AdvisorConfig, asset: str) -> list[MarketFundFlow]:
    """CoinGlass 市场级资金流入/流出（taker buy/sell netflow）。"""
    if not cfg.coinglass_api_key:
        return []
    flows: list[MarketFundFlow] = []
    for market, path in (("futures", "/api/futures/coin/netflow"), ("spot", "/api/spot/coin/netflow")):
        try:
            data = _coinglass_get(cfg, path, {"symbol": asset, "exchange_list": cfg.coinglass_exchange_list})
            periods = _parse_netflow_periods(data)
            if periods:
                flows.append(
                    MarketFundFlow(
                        asset=asset,
                        market=market,
                        periods=periods,
                        source=f"coinglass:{market}",
                    )
                )
        except Exception:
            continue
    return flows


def fetch_exchange_wallet_flow(cfg: AdvisorConfig, asset: str) -> ExchangeWalletFlow | None:
    """
    链上转入/转出交易所：用各交易所钱包余额变化近似。
    balance_change > 0 → 净流入交易所（潜在卖压）
    balance_change < 0 → 净流出交易所（提币/积累）
    """
    if not cfg.coinglass_api_key:
        return None
    try:
        rows = _coinglass_get(cfg, "/api/exchange/balance/list", {"symbol": asset})
    except Exception:
        return None
    if not isinstance(rows, list) or not rows:
        return None

    def _sum(field: str) -> float:
        total = 0.0
        for row in rows:
            val = row.get(field)
            if val is not None:
                total += float(val)
        return total

    top = sorted(rows, key=lambda r: abs(float(r.get("balance_change_1d") or 0)), reverse=True)[:5]
    top_exchanges = [
        {
            "exchange": r.get("exchange_name"),
            "balance": r.get("total_balance"),
            "change_1d": r.get("balance_change_1d"),
            "change_7d": r.get("balance_change_7d"),
            "change_30d": r.get("balance_change_30d"),
            "change_pct_1d": r.get("balance_change_percent_1d"),
        }
        for r in top
    ]
    return ExchangeWalletFlow(
        asset=asset,
        net_to_exchange_1d=_sum("balance_change_1d"),
        net_to_exchange_7d=_sum("balance_change_7d"),
        net_to_exchange_30d=_sum("balance_change_30d"),
        top_exchanges=top_exchanges,
        source="coinglass:exchange_balance",
    )


def _coinglass_get(cfg: AdvisorConfig, path: str, params: dict[str, Any]) -> Any:
    payload = get_json(
        COINGLASS_BASE + path,
        headers={"CG-API-KEY": cfg.coinglass_api_key, "accept": "application/json"},
        params=params,
    )
    if not isinstance(payload, dict):
        raise ValueError("invalid coinglass response")
    if str(payload.get("code")) not in ("0", "200"):
        raise ValueError(payload.get("msg") or "coinglass error")
    return payload.get("data")


def _parse_netflow_periods(data: dict[str, Any]) -> list[FlowPeriod]:
    if not isinstance(data, dict):
        return []
    periods: list[FlowPeriod] = []
    for label, suffix in PERIOD_KEYS:
        buy = _float(data.get(f"taker_buy_volume_usd_{suffix}"))
        sell = _float(data.get(f"taker_sell_volume_usd_{suffix}"))
        net = _float(data.get(f"net_flow_usd_{suffix}"))
        chg = _float(data.get(f"net_flow_usd_change_percent_{suffix}"))
        if buy is None and sell is None and net is None:
            continue
        periods.append(
            FlowPeriod(
                period=label,
                inflow_usd=buy,
                outflow_usd=sell,
                netflow_usd=net if net is not None else ((buy or 0) - (sell or 0)),
                change_pct=chg,
            )
        )
    return periods


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
