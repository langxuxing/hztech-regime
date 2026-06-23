from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange
from ai_trade_advisor.models import OrderBookSnapshot


def fetch_orderbook(cfg: AdvisorConfig) -> OrderBookSnapshot:
    exchange = make_exchange(
        cfg.exchange,
        market_type="swap",
        binance=cfg.binance_futures(),
    )
    exchange.load_markets()
    ob = exchange.fetch_order_book(cfg.symbol, limit=cfg.orderbook_limit)
    bids = ob.get("bids") or []
    asks = ob.get("asks") or []
    if not bids or not asks:
        raise RuntimeError("订单簿为空")

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / mid * 10000 if mid else 0.0

    bid_depth = sum(_level_notional(level) for level in bids)
    ask_depth = sum(_level_notional(level) for level in asks)
    total = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total if total else 0.0

    walls = _detect_walls(bids, asks, mid)
    return OrderBookSnapshot(
        best_bid=best_bid,
        best_ask=best_ask,
        spread_bps=round(spread_bps, 2),
        bid_depth_usdt=round(bid_depth, 2),
        ask_depth_usdt=round(ask_depth, 2),
        imbalance=round(imbalance, 4),
        walls=walls,
    )


def _level_notional(level: list) -> float:
    """ccxt 通常为 [price, amount]；OKX 等可能附带额外字段。"""
    return float(level[0]) * float(level[1])


def _detect_walls(
    bids: list[list[float]],
    asks: list[list[float]],
    mid: float,
    *,
    min_notional_ratio: float = 0.08,
) -> list[dict[str, Any]]:
    """识别相对异常的大单墙（相对前 5 档均值）。"""
    walls: list[dict[str, Any]] = []

    def _scan(side: str, levels: list[list[float]]) -> None:
        if len(levels) < 3:
            return
        notionals = [_level_notional(level) for level in levels[:10]]
        avg = sum(notionals) / len(notionals) if notionals else 0
        if avg <= 0:
            return
        for level, n in zip(levels[:15], notionals):
            p = float(level[0])
            if n >= avg * (1 + min_notional_ratio * 10):
                walls.append(
                    {
                        "side": side,
                        "price": p,
                        "notional_usdt": round(n, 2),
                        "distance_bps": round((p - mid) / mid * 10000, 1),
                    }
                )

    _scan("bid", bids)
    _scan("ask", asks)
    walls.sort(key=lambda w: abs(w["distance_bps"]))
    return walls[:6]
