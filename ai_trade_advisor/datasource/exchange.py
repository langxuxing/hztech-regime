from __future__ import annotations

import ccxt

from ai_trade_advisor.datasource.binance_config import BinanceFuturesConfig


def resolve_exchange_id(exchange_id: str, *, market_type: str = "swap") -> str:
    """将配置中的交易所 id 映射为 ccxt 实现 id。"""
    ex = exchange_id.strip().lower()
    if ex == "binance":
        return "binanceusdm" if market_type == "swap" else "binance"
    return ex


def make_exchange(
    exchange_id: str,
    *,
    market_type: str = "swap",
    binance: BinanceFuturesConfig | None = None,
) -> ccxt.Exchange:
    """创建 ccxt 交易所实例。Binance sandbox 走 demo-fapi + enable_demo_trading。"""
    resolved = resolve_exchange_id(exchange_id, market_type=market_type)
    ex_cls = getattr(ccxt, resolved, None)
    if ex_cls is None:
        raise ValueError(f"不支持的交易所: {exchange_id}")

    if resolved in ("binance", "binanceusdm") and binance is not None:
        exchange = ccxt.binance(
            {
                "apiKey": binance.api_key,
                "secret": binance.api_secret,
                "enableRateLimit": True,
                "timeout": 15000,
                "options": {
                    "defaultType": "future",
                    "adjustForTimeDifference": True,
                    "fetchCurrencies": False,
                    "fetchMarkets": {"types": ["linear"]},
                },
            }
        )
        if binance.sandbox:
            exchange.enable_demo_trading(True)
        return exchange

    options: dict[str, str] = {}
    if resolved == "binance":
        options["defaultType"] = "spot"
    elif resolved in ("okx", "bybit", "bitget", "gate"):
        options["defaultType"] = "swap"

    return ex_cls({"enableRateLimit": True, "options": options})
