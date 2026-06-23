from __future__ import annotations

from typing import Any

from ai_trade_advisor.datasource.http_client import get_json
from ai_trade_advisor.models import OnChainTransferFlow

BLOCKCHAIR = {
    "BTC": "https://api.blockchair.com/bitcoin/stats",
    "ETH": "https://api.blockchair.com/ethereum/stats",
}

BLOCKCHAIN_CHARTS = {
    "BTC": {
        "volume": "estimated-transaction-volume-usd",
        "tx": "n-transactions",
    },
}


def fetch_onchain_flow(asset: str) -> OnChainTransferFlow | None:
    asset = asset.upper()
    try:
        if asset == "BTC":
            return _fetch_btc_onchain()
        if asset == "ETH":
            return _fetch_eth_onchain()
    except Exception:
        return None
    return None


def _fetch_btc_onchain() -> OnChainTransferFlow:
    stats = get_json(BLOCKCHAIR["BTC"]).get("data") or {}
    vol_24h = _sat_to_btc_usd(stats.get("volume_24h"), stats.get("market_price_usd"))
    tx_24h = _int(stats.get("transactions_24h"))
    largest = stats.get("largest_transaction_24h") or {}
    largest_usd = _float(largest.get("value_usd"))

    vol_trends = _blockchain_chart_trends(BLOCKCHAIN_CHARTS["BTC"]["volume"])
    tx_trends = _blockchain_chart_trends(BLOCKCHAIN_CHARTS["BTC"]["tx"])
    has_trends = any(
        v is not None
        for v in (
            vol_trends.get("change_7d_pct"),
            vol_trends.get("change_30d_pct"),
            tx_trends.get("change_7d_pct"),
        )
    )

    return OnChainTransferFlow(
        asset="BTC",
        chain_volume_24h_usd=vol_24h,
        transactions_24h=tx_24h,
        volume_change_7d_pct=vol_trends.get("change_7d_pct"),
        volume_change_30d_pct=vol_trends.get("change_30d_pct"),
        tx_change_7d_pct=tx_trends.get("change_7d_pct"),
        largest_tx_24h_usd=largest_usd,
        interpretation=_interpret_onchain(
            vol_trends.get("change_7d_pct"),
            tx_trends.get("change_7d_pct"),
        ),
        source="blockchair+blockchain.com" if has_trends else "blockchair",
    )


def _fetch_eth_onchain() -> OnChainTransferFlow:
    stats = get_json(BLOCKCHAIR["ETH"]).get("data") or {}
    price = _float(stats.get("market_price_usd")) or 0.0
    vol_raw = _float(stats.get("volume_24h_approximate"))
    vol_24h = (vol_raw / 1e18 * price) if vol_raw and price else None
    tx_24h = _int(stats.get("transactions_24h"))
    largest = stats.get("largest_transaction_24h") or {}
    largest_usd = _float(largest.get("value_usd"))

    erc20 = ((stats.get("layer_2") or {}).get("erc_20") or {})
    erc20_tx_24h = _int(erc20.get("transactions_24h"))

    return OnChainTransferFlow(
        asset="ETH",
        chain_volume_24h_usd=vol_24h,
        transactions_24h=tx_24h,
        volume_change_7d_pct=None,
        volume_change_30d_pct=None,
        tx_change_7d_pct=None,
        largest_tx_24h_usd=largest_usd,
        interpretation=_interpret_eth(tx_24h, erc20_tx_24h),
        source="blockchair",
        extra={"erc20_transactions_24h": erc20_tx_24h},
    )


def _blockchain_chart_trends(chart_name: str) -> dict[str, float | None]:
    """7d/30d trends from blockchain.com charts; returns empty on network/API failure."""
    url = f"https://api.blockchain.info/charts/{chart_name}?timespan=30days&format=json"
    try:
        payload = get_json(url, timeout=12.0)
    except Exception:
        return {"change_7d_pct": None, "change_30d_pct": None}
    values = payload.get("values") or []
    ys = [float(v["y"]) for v in values if v.get("y") is not None]
    if len(ys) < 8:
        return {"change_7d_pct": None, "change_30d_pct": None}
    return {
        "change_7d_pct": _pct_change(ys[-1], ys[-8]),
        "change_30d_pct": _pct_change(ys[-1], ys[0]),
    }


def _interpret_onchain(vol_7d: float | None, tx_7d: float | None) -> str:
    parts: list[str] = []
    if vol_7d is not None:
        parts.append(f"链上成交额 7d {'+' if vol_7d >= 0 else ''}{vol_7d:.1f}%")
    if tx_7d is not None:
        parts.append(f"链上交易笔数 7d {'+' if tx_7d >= 0 else ''}{tx_7d:.1f}%")
    if not parts:
        return "链上活跃度数据有限"
    rising = (vol_7d or 0) > 5 or (tx_7d or 0) > 5
    falling = (vol_7d or 0) < -5 or (tx_7d or 0) < -5
    if rising:
        parts.append("→ 链上活动升温，关注大额转账方向")
    elif falling:
        parts.append("→ 链上活动降温")
    else:
        parts.append("→ 链上活动相对平稳")
    return "；".join(parts)


def _interpret_eth(tx_24h: int | None, erc20_tx_24h: int | None) -> str:
    parts: list[str] = []
    if tx_24h:
        parts.append(f"L1 交易 {tx_24h:,} 笔/24h")
    if erc20_tx_24h:
        parts.append(f"ERC20 交易 {erc20_tx_24h:,} 笔/24h")
    parts.append("→ ETH 链上流量需结合交易所钱包净流入/流出判断方向")
    return "；".join(parts)


def _pct_change(current: float, base: float) -> float | None:
    if base == 0:
        return None
    return (current - base) / base * 100.0


def _sat_to_btc_usd(sats: Any, price_usd: Any) -> float | None:
    s = _float(sats)
    p = _float(price_usd)
    if s is None or p is None:
        return None
    return s / 1e8 * p


def _float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
