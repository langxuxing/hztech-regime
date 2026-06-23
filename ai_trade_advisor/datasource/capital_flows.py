from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.etf_flow import fetch_etf_flows
from ai_trade_advisor.datasource.fund_flow import fetch_exchange_wallet_flow, fetch_market_fund_flows
from ai_trade_advisor.datasource.onchain import fetch_onchain_flow
from ai_trade_advisor.models import CapitalFlowsSnapshot


def build_capital_flows(cfg: AdvisorConfig) -> CapitalFlowsSnapshot:
    notes: list[str] = []
    btc_market: list = []
    eth_market: list = []
    btc_wallet = eth_wallet = None
    btc_onchain = eth_onchain = None
    btc_etf = eth_etf = None

    for asset in cfg.fund_flow_assets:
        if asset == "BTC":
            btc_market = fetch_market_fund_flows(cfg, "BTC")
            btc_wallet = fetch_exchange_wallet_flow(cfg, "BTC")
            btc_onchain = fetch_onchain_flow("BTC")
            btc_etf = fetch_etf_flows(cfg, "BTC")
        elif asset == "ETH":
            eth_market = fetch_market_fund_flows(cfg, "ETH")
            eth_wallet = fetch_exchange_wallet_flow(cfg, "ETH")
            eth_onchain = fetch_onchain_flow("ETH")
            eth_etf = fetch_etf_flows(cfg, "ETH")

    if btc_etf and btc_etf.source.startswith("farside"):
        notes.append("BTC Spot ETF：Farside 爬虫（日度 + 近 3 个月周度聚合）")
    elif btc_etf and btc_etf.source.startswith("local"):
        notes.append("BTC Spot ETF：本地 CSV（data/ETF/Btc/）")
    if cfg.coinglass_api_key:
        notes.append("CoinGlass: 市场 netflow + 交易所钱包已启用")
        if eth_etf:
            notes.append("ETH Spot ETF：CoinGlass API")
    elif eth_etf or (btc_etf and btc_etf.source.startswith("coinglass")):
        notes.append("使用本地 Spot ETF CSV（data/ETF/）；市场 netflow/交易所钱包仍需 COINGLASS_API_KEY")
    elif not btc_etf:
        notes.append("未配置 COINGLASS_API_KEY：市场 netflow/交易所钱包需 Hobbyist+ Key")
        notes.append("BTC ETF 可走 Farside 爬虫；ETH ETF 需 CoinGlass Key 或本地 CSV")
    if btc_onchain or eth_onchain:
        notes.append(
            "链上活跃度（Blockchair）：全网成交额/笔数，不等于交易所净流入；"
            "交易所流向见 exchange_wallet"
        )

    quality = "full" if cfg.coinglass_api_key and (btc_market or btc_etf) else "partial"
    if not cfg.coinglass_api_key and (btc_etf or eth_etf):
        quality = "partial"
    if btc_etf and btc_etf.source.startswith("farside") and not cfg.coinglass_api_key:
        quality = "partial"
    if not cfg.coinglass_api_key and (btc_onchain or eth_onchain):
        quality = "free_only"

    return CapitalFlowsSnapshot(
        btc_market_flows=btc_market,
        eth_market_flows=eth_market,
        btc_exchange_wallet=btc_wallet,
        eth_exchange_wallet=eth_wallet,
        btc_onchain=btc_onchain,
        eth_onchain=eth_onchain,
        btc_etf=btc_etf,
        eth_etf=eth_etf,
        data_quality=quality,
        notes=notes,
    )
