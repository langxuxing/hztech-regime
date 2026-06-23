from __future__ import annotations

from typing import Any

from ai_trade_advisor.models import (
    BoardInsights,
    CapitalFlowsSnapshot,
    EtfFlowDay,
    EtfFlowSnapshot,
    EtfFlowWeek,
    ExchangeWalletFlow,
    FlowPeriod,
    GexLevel,
    LiquidityLevel,
    MarketContext,
    MarketFundFlow,
    OnChainTransferFlow,
    OrderBookSnapshot,
    PriceZone,
    SmcSnapshot,
    TradeAdvice,
)


def _zone(z: PriceZone | None) -> dict[str, Any] | None:
    if z is None:
        return None
    return {"low": z.low, "high": z.high, "label": z.label, "kind": z.kind}


def _smc(smc: SmcSnapshot) -> dict[str, Any]:
    return {
        "trend": smc.trend,
        "mss_or_choch": smc.mss_or_choch,
        "mss_direction": smc.mss_direction,
        "nearest_ob": _zone(smc.nearest_ob),
        "nearest_fvg": _zone(smc.nearest_fvg),
        "unfilled_fvgs": [_zone(z) for z in smc.unfilled_fvgs],
        "active_obs": [_zone(z) for z in smc.active_obs],
        "structure_notes": smc.structure_notes,
    }


def _liquidity(levels: list[LiquidityLevel]) -> list[dict[str, Any]]:
    return [
        {
            "price": lv.price,
            "side": lv.side,
            "swept": lv.swept,
            "sweep_time": lv.sweep_time,
            "strength": lv.strength,
        }
        for lv in levels
    ]


def _gex(levels: list[GexLevel]) -> list[dict[str, Any]]:
    return [
        {
            "price": lv.price,
            "gex_notional_proxy": lv.gex_notional_proxy,
            "level_type": lv.level_type,
            "source": lv.source,
        }
        for lv in levels
    ]


def _orderbook(ob: OrderBookSnapshot | None) -> dict[str, Any] | None:
    if ob is None:
        return None
    return {
        "best_bid": ob.best_bid,
        "best_ask": ob.best_ask,
        "spread_bps": ob.spread_bps,
        "bid_depth_usdt": ob.bid_depth_usdt,
        "ask_depth_usdt": ob.ask_depth_usdt,
        "imbalance": ob.imbalance,
        "walls": ob.walls,
    }


def _flow_period(p: FlowPeriod) -> dict[str, Any]:
    return {
        "period": p.period,
        "inflow_usd": p.inflow_usd,
        "outflow_usd": p.outflow_usd,
        "netflow_usd": p.netflow_usd,
        "change_pct": p.change_pct,
    }


def _market_flow(mf: MarketFundFlow) -> dict[str, Any]:
    return {
        "asset": mf.asset,
        "market": mf.market,
        "periods": [_flow_period(p) for p in mf.periods],
        "source": mf.source,
    }


def _exchange_wallet(w: ExchangeWalletFlow | None) -> dict[str, Any] | None:
    if w is None:
        return None
    return {
        "asset": w.asset,
        "net_to_exchange_1d": w.net_to_exchange_1d,
        "net_to_exchange_7d": w.net_to_exchange_7d,
        "net_to_exchange_30d": w.net_to_exchange_30d,
        "top_exchanges": w.top_exchanges,
        "source": w.source,
    }


def _onchain(o: OnChainTransferFlow | None) -> dict[str, Any] | None:
    if o is None:
        return None
    return {
        "asset": o.asset,
        "chain_volume_24h_usd": o.chain_volume_24h_usd,
        "transactions_24h": o.transactions_24h,
        "volume_change_7d_pct": o.volume_change_7d_pct,
        "volume_change_30d_pct": o.volume_change_30d_pct,
        "tx_change_7d_pct": o.tx_change_7d_pct,
        "largest_tx_24h_usd": o.largest_tx_24h_usd,
        "interpretation": o.interpretation,
        "source": o.source,
        "extra": o.extra,
    }


def _etf_day(d: EtfFlowDay) -> dict[str, Any]:
    return {
        "date": d.date,
        "flow_usd": d.flow_usd,
        "price_usd": d.price_usd,
        "tickers": [{"ticker": t.ticker, "flow_usd": t.flow_usd} for t in d.tickers],
    }


def _etf_week(w: EtfFlowWeek) -> dict[str, Any]:
    return {
        "week_start": w.week_start,
        "week_end": w.week_end,
        "flow_usd": w.flow_usd,
        "label": w.label,
        "days_count": w.days_count,
    }


def _etf_snapshot(e: EtfFlowSnapshot | None) -> dict[str, Any] | None:
    if e is None:
        return None
    return {
        "asset": e.asset,
        "latest": _etf_day(e.latest) if e.latest else None,
        "history": [_etf_day(d) for d in e.history],
        "weekly_history": [_etf_week(w) for w in e.weekly_history],
        "total_7d_usd": e.total_7d_usd,
        "total_30d_usd": e.total_30d_usd,
        "total_13w_usd": e.total_13w_usd,
        "interpretation": e.interpretation,
        "source": e.source,
    }


def _capital_flows(cf: CapitalFlowsSnapshot | None) -> dict[str, Any] | None:
    if cf is None:
        return None
    return {
        "data_quality": cf.data_quality,
        "notes": cf.notes,
        "btc_market_flows": [_market_flow(m) for m in cf.btc_market_flows],
        "eth_market_flows": [_market_flow(m) for m in cf.eth_market_flows],
        "btc_exchange_wallet": _exchange_wallet(cf.btc_exchange_wallet),
        "eth_exchange_wallet": _exchange_wallet(cf.eth_exchange_wallet),
        "btc_onchain": _onchain(cf.btc_onchain),
        "eth_onchain": _onchain(cf.eth_onchain),
        "btc_etf": _etf_snapshot(cf.btc_etf),
        "eth_etf": _etf_snapshot(cf.eth_etf),
    }


def market_context_to_dict(ctx: MarketContext) -> dict[str, Any]:
    return {
        "symbol": ctx.symbol,
        "exchange": ctx.exchange,
        "timeframe": ctx.timeframe,
        "as_of": ctx.as_of,
        "last_price": ctx.last_price,
        "ohlcv_summary": ctx.ohlcv_summary,
        "smc": _smc(ctx.smc),
        "liquidity_levels": _liquidity(ctx.liquidity_levels),
        "gex_levels": _gex(ctx.gex_levels),
        "orderbook": _orderbook(ctx.orderbook),
        "vol_ratio": ctx.vol_ratio,
        "vol_status": ctx.vol_status,
        "capital_flows": _capital_flows(ctx.capital_flows),
        "btc_regime": ctx.btc_regime,
        "feature_snapshot": ctx.feature_snapshot,
        "macro_hazard_flag": ctx.macro_hazard_flag,
        "obi_smoothed": ctx.obi_smoothed,
        "quant_state": ctx.quant_state,
        "pipeline": ctx.pipeline,
        "black_swan_alert": ctx.black_swan_alert,
        "regime_confirmation": ctx.regime_confirmation,
        "unified_events": ctx.unified_events or [],
        "chart": ctx.chart,
        "trading_brief": ctx.trading_brief,
    }


from ai_trade_advisor.features.board_insights import build_board_insights


def dashboard_payload(
    ctx: MarketContext,
    advice: TradeAdvice,
    *,
    mode: str,
    board: BoardInsights | None = None,
) -> dict[str, Any]:
    insights = board or build_board_insights(ctx, advice)
    return {
        **market_context_to_dict(ctx),
        "advice": advice.to_dict(),
        "mode": mode,
        "board": insights.to_dict(),
    }
