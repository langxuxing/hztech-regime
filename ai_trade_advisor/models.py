from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Bias = Literal["long", "short", "neutral"]
EventSeverity = Literal["high", "medium", "low"]
EventImpact = Literal["bullish", "bearish", "neutral"]
RegimeType = Literal[
    "trend_up",
    "trend_down",
    "range",
    "high_vol",
    "transition",
    "macro_frozen_range",
    "fake_breakout_wash",
    "high_vol_self_heal",
]
TrendDirection = Literal["up", "down", "sideways", "correction"]


@dataclass
class PriceZone:
    low: float
    high: float
    label: str = ""
    kind: str = ""

    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    def width_pct(self, price: float) -> float:
        if price <= 0:
            return 0.0
        return abs(self.mid() - price) / price * 100.0


@dataclass
class LiquidityLevel:
    price: float
    side: Literal["buy_side", "sell_side"]
    swept: bool
    sweep_time: str | None = None
    strength: float = 1.0


@dataclass
class GexLevel:
    price: float
    gex_notional_proxy: float
    level_type: Literal["support", "resistance", "magnet"]
    source: str = "oi_cluster"


@dataclass
class OrderBookSnapshot:
    best_bid: float
    best_ask: float
    spread_bps: float
    bid_depth_usdt: float
    ask_depth_usdt: float
    imbalance: float
    walls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SmcSnapshot:
    trend: str
    mss_or_choch: str | None
    mss_direction: int
    nearest_ob: PriceZone | None
    nearest_fvg: PriceZone | None
    unfilled_fvgs: list[PriceZone] = field(default_factory=list)
    active_obs: list[PriceZone] = field(default_factory=list)
    structure_notes: list[str] = field(default_factory=list)


@dataclass
class FlowPeriod:
    period: str
    inflow_usd: float | None = None
    outflow_usd: float | None = None
    netflow_usd: float | None = None
    change_pct: float | None = None


@dataclass
class MarketFundFlow:
    asset: str
    market: str
    periods: list[FlowPeriod] = field(default_factory=list)
    source: str = ""


@dataclass
class ExchangeWalletFlow:
    """链上转入/转出交易所（钱包余额变化代理）。"""

    asset: str
    net_to_exchange_1d: float | None
    net_to_exchange_7d: float | None
    net_to_exchange_30d: float | None
    top_exchanges: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""


@dataclass
class OnChainTransferFlow:
    """链上全网活跃度（成交量/笔数），非交易所钱包净流入。"""

    asset: str
    chain_volume_24h_usd: float | None
    transactions_24h: int | None
    volume_change_7d_pct: float | None
    volume_change_30d_pct: float | None
    tx_change_7d_pct: float | None
    largest_tx_24h_usd: float | None
    interpretation: str
    source: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EtfTickerFlow:
    ticker: str
    flow_usd: float


@dataclass
class EtfFlowDay:
    date: str
    flow_usd: float
    price_usd: float | None = None
    tickers: list[EtfTickerFlow] = field(default_factory=list)


@dataclass
class EtfFlowWeek:
    week_start: str
    week_end: str
    flow_usd: float
    label: str = ""
    days_count: int = 0


@dataclass
class EtfFlowSnapshot:
    asset: str
    latest: EtfFlowDay | None = None
    history: list[EtfFlowDay] = field(default_factory=list)
    weekly_history: list[EtfFlowWeek] = field(default_factory=list)
    total_7d_usd: float | None = None
    total_30d_usd: float | None = None
    total_13w_usd: float | None = None
    interpretation: str = ""
    source: str = ""


@dataclass
class CapitalFlowsSnapshot:
    btc_market_flows: list[MarketFundFlow] = field(default_factory=list)
    eth_market_flows: list[MarketFundFlow] = field(default_factory=list)
    btc_exchange_wallet: ExchangeWalletFlow | None = None
    eth_exchange_wallet: ExchangeWalletFlow | None = None
    btc_onchain: OnChainTransferFlow | None = None
    eth_onchain: OnChainTransferFlow | None = None
    btc_etf: EtfFlowSnapshot | None = None
    eth_etf: EtfFlowSnapshot | None = None
    data_quality: str = "partial"
    notes: list[str] = field(default_factory=list)


@dataclass
class RegimeJudgment:
    regime: RegimeType
    label: str
    confidence: float
    summary: str
    vol_regime: str
    structure_regime: str
    flow_regime: str | None
    drivers: list[str] = field(default_factory=list)
    regime_id: str | None = None
    raw_trend: str | None = None
    vol_bucket: str | None = None
    next_regime_label: str | None = None
    changepoint_prob: float | None = None
    in_regime_transition: bool = False
    triad_summary: str | None = None
    tech_trend: str | None = None
    derivatives: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "summary": self.summary,
            "vol_regime": self.vol_regime,
            "structure_regime": self.structure_regime,
            "flow_regime": self.flow_regime,
            "drivers": self.drivers,
            "regime_id": self.regime_id,
            "raw_trend": self.raw_trend,
            "tech_trend": self.tech_trend,
            "vol_bucket": self.vol_bucket,
            "next_regime_label": self.next_regime_label,
            "changepoint_prob": self.changepoint_prob,
            "in_regime_transition": self.in_regime_transition,
            "triad_summary": self.triad_summary,
            "derivatives": self.derivatives,
        }


@dataclass
class MajorEvent:
    id: str
    category: str
    title: str
    description: str
    severity: EventSeverity
    impact: EventImpact
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "impact": self.impact,
            "timestamp": self.timestamp,
        }


@dataclass
class TrendJudgment:
    direction: TrendDirection
    label: str
    confidence: float
    short_term: str
    medium_term: str
    summary: str
    key_levels: dict[str, float | None] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "short_term": self.short_term,
            "medium_term": self.medium_term,
            "summary": self.summary,
            "key_levels": self.key_levels,
            "signals": self.signals,
        }


@dataclass
class MarketContext:
    symbol: str
    exchange: str
    timeframe: str
    as_of: str
    last_price: float
    ohlcv_summary: dict[str, Any]
    smc: SmcSnapshot
    liquidity_levels: list[LiquidityLevel]
    gex_levels: list[GexLevel]
    orderbook: OrderBookSnapshot | None
    vol_ratio: float | None = None
    vol_status: str | None = None
    capital_flows: CapitalFlowsSnapshot | None = None
    feature_snapshot: dict[str, Any] | None = None
    macro_hazard_flag: bool = False
    obi_smoothed: float | None = None
    btc_regime: dict[str, Any] | None = None
    quant_state: dict[str, Any] | None = None
    black_swan_alert: dict[str, Any] | None = None
    regime_confirmation: dict[str, Any] | None = None
    pipeline: dict[str, Any] | None = None
    unified_events: list[dict[str, Any]] | None = None
    chart: dict[str, Any] | None = None
    trading_brief: dict[str, Any] | None = None


@dataclass
class TradeAdvice:
    bias: Bias
    confidence: float
    entry_zone: tuple[float, float] | None
    stop_loss: float | None
    take_profit: list[float]
    time_horizon: str
    reasoning: str
    risks: list[str]
    confluence_score: float
    raw_llm: str | None = None
    rule_based: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "bias": self.bias,
            "confidence": round(self.confidence, 3),
            "entry_zone": list(self.entry_zone) if self.entry_zone else None,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "time_horizon": self.time_horizon,
            "reasoning": self.reasoning,
            "risks": self.risks,
            "confluence_score": round(self.confluence_score, 3),
            "rule_based": self.rule_based,
        }


@dataclass
class BoardInsights:
    regime: RegimeJudgment
    major_events: list[MajorEvent]
    trend: TrendJudgment

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.to_dict(),
            "major_events": [e.to_dict() for e in self.major_events],
            "trend": self.trend.to_dict(),
        }
