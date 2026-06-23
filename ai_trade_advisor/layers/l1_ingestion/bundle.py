"""L1 多源数据输入层编排。"""

from __future__ import annotations

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import load_ohlcv
from ai_trade_advisor.datasource.ticker import fetch_live_ticker
from ai_trade_advisor.layers.l1_ingestion.macro import build_macro_flow_features
from ai_trade_advisor.layers.l1_ingestion.market import build_market_features
from ai_trade_advisor.layers.l1_ingestion.microstructure import build_microstructure_features
from ai_trade_advisor.layers.l1_ingestion.transform import split_confirmed_bars
from ai_trade_advisor.layers.l1_ingestion.volatility import build_volatility_features
from ai_trade_advisor.layers.types import IngestionBundle
from ai_trade_advisor.models import MarketContext


def run_ingestion(
    cfg: AdvisorConfig,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> IngestionBundle:
    """聚合四维度数据源并变频清洗。"""
    df = load_ohlcv(cfg)
    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    transform = split_confirmed_bars(df, bar_minutes=cfg.bar_minutes)
    ticker = fetch_live_ticker(cfg)
    live_price = ticker.last
    structure_price = float(transform.df_confirmed.iloc[-1]["close"])

    market = build_market_features(
        cfg,
        transform.df_confirmed,
        candle_price=structure_price,
        ticker=ticker,
    )
    vol_feats, gex_engine, gex_levels = build_volatility_features(
        cfg, transform.df_confirmed, price=live_price, use_deribit=cfg.use_deribit_gex
    )
    micro, liquidation, ob = build_microstructure_features(
        cfg, transform.df_confirmed, price=live_price, skip_orderbook=skip_orderbook
    )
    macro_flow, macro, flows = build_macro_flow_features(
        cfg, skip_capital_flows=skip_capital_flows
    )

    from ai_trade_advisor.features.liquidity_map import detect_liquidity_sweeps
    from ai_trade_advisor.features.smc import build_smc_snapshot

    smc = build_smc_snapshot(transform.df_confirmed, structure_price)
    liquidity = detect_liquidity_sweeps(transform.df_confirmed)

    ctx = MarketContext(
        symbol=cfg.symbol,
        exchange=cfg.exchange,
        timeframe=f"{cfg.bar_minutes}m",
        as_of=ticker.as_of,
        last_price=live_price,
        ohlcv_summary=market["ohlcv_summary"],
        smc=smc,
        liquidity_levels=liquidity,
        gex_levels=gex_levels,
        orderbook=ob,
        vol_ratio=vol_feats.get("vol_ratio"),
        vol_status=vol_feats.get("vol_status"),
        capital_flows=flows,
        macro_hazard_flag=macro.macro_hazard_flag,
    )

    return IngestionBundle(
        ctx=ctx,
        df=transform.df_live,
        transform=transform,
        macro=macro,
        gex_engine=gex_engine,
        liquidation=liquidation,
        market=market,
        volatility=vol_feats,
        microstructure=micro,
        macro_flow=macro_flow,
    )
