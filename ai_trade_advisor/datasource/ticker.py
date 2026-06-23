from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange, resolve_exchange_id
from ai_trade_advisor.datasource.http_client import get_json


@dataclass
class LiveTickerSnapshot:
    last: float
    change_pct_24h: float | None
    as_of: str
    bid: float | None = None
    ask: float | None = None
    source: str = ""


def _symbol_to_binance_futures(symbol: str) -> str:
    """BTC/USDT:USDT -> BTCUSDT"""
    base = symbol.split("/")[0]
    quote = symbol.split("/")[1].split(":")[0]
    return f"{base}{quote}"


def _as_of_from_ticker(ticker: dict[str, Any]) -> str:
    ts = ticker.get("timestamp") or ticker.get("datetime")
    if ts is not None:
        try:
            return datetime.fromtimestamp(
                float(ts) / 1000, tz=timezone.utc
            ).isoformat()
        except (TypeError, ValueError, OSError):
            pass
    return datetime.now(timezone.utc).isoformat()


def _pct_from_ticker(ticker: dict[str, Any]) -> float | None:
    pct = ticker.get("percentage")
    if pct is not None:
        try:
            return round(float(pct), 3)
        except (TypeError, ValueError):
            pass
    last = ticker.get("last") or ticker.get("close")
    open_ = ticker.get("open") or ticker.get("info", {}).get("openPrice")
    if last is not None and open_ is not None:
        try:
            o = float(open_)
            if o:
                return round((float(last) - o) / o * 100, 3)
        except (TypeError, ValueError):
            pass
    return None


def _binance_fapi_base(cfg: AdvisorConfig) -> str:
    bn = cfg.binance_futures()
    if bn is not None:
        return bn.base_url.rstrip("/")
    return "https://fapi.binance.com"


def _fetch_binance_futures_ticker_direct(
    symbol: str,
    *,
    base_url: str = "https://fapi.binance.com",
) -> dict[str, Any]:
    """Binance USD-M 24h ticker（无需 load_markets）。"""
    sym = _symbol_to_binance_futures(symbol)
    root = base_url.rstrip("/")
    raw = get_json(
        f"{root}/fapi/v1/ticker/24hr",
        params={"symbol": sym},
        timeout=15.0,
    )
    last = float(raw["lastPrice"])
    open_ = float(raw.get("openPrice") or 0)
    pct = ((last - open_) / open_ * 100) if open_ else None
    return {
        "last": last,
        "bid": float(raw["bidPrice"]) if raw.get("bidPrice") else None,
        "ask": float(raw["askPrice"]) if raw.get("askPrice") else None,
        "percentage": pct,
        "timestamp": int(raw.get("closeTime") or raw.get("time") or 0),
    }


def fetch_live_ticker(cfg: AdvisorConfig) -> LiveTickerSnapshot:
    """拉取交易所实时 ticker（最新价 + 24h 涨跌幅）。"""
    resolved = resolve_exchange_id(cfg.exchange, market_type="swap")
    bn = cfg.binance_futures() if resolved == "binanceusdm" else None

    if resolved == "binanceusdm":
        base_url = _binance_fapi_base(cfg)
        source = bn.ticker_source if bn else "binance:fapi"
        try:
            ticker = _fetch_binance_futures_ticker_direct(
                cfg.symbol,
                base_url=base_url,
            )
            return LiveTickerSnapshot(
                last=float(ticker["last"]),
                change_pct_24h=_pct_from_ticker(ticker),
                as_of=_as_of_from_ticker(ticker),
                bid=ticker.get("bid"),
                ask=ticker.get("ask"),
                source=source,
            )
        except Exception:
            pass

    exchange = make_exchange(
        cfg.exchange,
        market_type="swap",
        binance=bn,
    )
    exchange.load_markets()
    ticker = exchange.fetch_ticker(cfg.symbol)
    last = float(ticker.get("last") or ticker.get("close") or 0)
    if last <= 0:
        raise RuntimeError(f"无效 ticker: {cfg.symbol} @ {cfg.exchange}")

    bid = ticker.get("bid")
    ask = ticker.get("ask")
    return LiveTickerSnapshot(
        last=last,
        change_pct_24h=_pct_from_ticker(ticker),
        as_of=_as_of_from_ticker(ticker),
        bid=float(bid) if bid is not None else None,
        ask=float(ask) if ask is not None else None,
        source=f"{resolved}:ccxt",
    )
