from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AdvisorConfig:
    exchange: str = "binance"
    symbol: str = "BTC/USDT:USDT"
    bar_minutes: int = 30
    lookback_bars: int = 720
    swing_length: int = 20
    orderbook_limit: int = 50
    ai_api_base: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    data_dir: Path | None = None
    pepedata_dir: Path | None = None
    etfdata_dir: Path | None = None
    use_local_pepe: bool = False
    temperature: float = 0.2
    coinglass_api_key: str = ""
    coinglass_exchange_list: str = "Binance,OKX,Bybit,Bitget,Gate"
    fund_flow_assets: list[str] = field(default_factory=lambda: ["BTC", "ETH"])
    x_bearer_token: str = ""
    x_search_query: str = ""
    x_max_results: int = 30
    event_demo_mode: bool = False
    event_min_btc_relevance: float = 0.35
    event_poll_interval_sec: int = 300
    event_llm_max_calls: int = 3
    use_deribit_gex: bool = True
    liquidation_half_life_hours: float = 3.0
    signal_cooldown_min_sec: int = 900
    signal_cooldown_max_sec: int = 1800
    macro_hazard_window_min: int = 120
    regime_min_dwell_bars: int = 2
    regime_transition_penalty: float = 0.35
    regime_forward_bars: int = 6
    regime_forward_min_samples: int = 20
    regime_rollup_window_days: int = 30
    regime_use_recommendation: bool = True
    regime_calibration_interval_hours: int = 24
    hmm_disagree_confidence_cap: float = 0.55
    hmm_low_confidence_cap: float = 0.60
    hmm_low_confidence_threshold: float = 0.50
    consensus_opposing_confidence_cap: float = 0.55
    trend_health_regime_flip_threshold: int = 6
    readiness_cache_ttl_sec: int = 60
    black_swan_liq_pulse_usd: float = 5_000_000.0
    black_swan_liq_total_usd: float = 10_000_000.0
    black_swan_changepoint_threshold: float = 0.7
    black_swan_range_watch_bars: int = 24
    black_swan_range_warn_bars: int = 48
    black_swan_funding_extreme_pct: float = 0.0003
    use_taker_cvd: bool = True
    taker_cvd_exchange: str = "binance"
    binance_config_path: Path | None = None
    allow_coinglass_scrape_fallback: bool = False
    allow_ccxt_ohlcv_fallback: bool = False
    snapshot_poll_interval_sec: int = 120
    snapshot_stale_sec: int = 300
    snapshot_warmup_on_start: bool = True
    api_key: str = ""
    # data scheduler intervals (seconds)
    sched_btc_1m_sec: int = 300
    sched_events_sec: int = 300
    sched_sync_hour: int = 8
    sched_sync_minute: int = 0
    sched_sync_timezone: str = "Asia/Shanghai"

    def binance_futures(self):
        from ai_trade_advisor.datasource.binance_config import load_binance_config

        return load_binance_config(self.binance_config_path)

    @classmethod
    def from_env(cls) -> AdvisorConfig:
        from ai_trade_advisor.datasource.paths import get_data_root, get_etf_root

        data_dir = os.getenv("DATA_DIR", "").strip()
        pepedata = os.getenv("PEPEDATA_DIR", "").strip()
        etfdata = os.getenv("ETFDATA_DIR", "").strip()
        binance_cfg = os.getenv("BINANCE_CONFIG_PATH", "").strip()
        return cls(
            exchange=os.getenv("EXCHANGE", "binance").strip().lower(),
            symbol=os.getenv("SYMBOL", "BTC/USDT:USDT").strip(),
            bar_minutes=int(os.getenv("BAR_MINUTES", "30")),
            lookback_bars=int(os.getenv("LOOKBACK_BARS", "720")),
            swing_length=int(os.getenv("SWING_LENGTH", "20")),
            orderbook_limit=int(os.getenv("ORDERBOOK_LIMIT", "50")),
            ai_api_base=os.getenv("AI_API_BASE", "https://api.openai.com/v1").strip(),
            ai_api_key=os.getenv("AI_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
            ai_model=os.getenv("AI_MODEL", "gpt-4o-mini").strip(),
            data_dir=Path(data_dir) if data_dir else get_data_root(),
            pepedata_dir=Path(pepedata) if pepedata else None,
            etfdata_dir=Path(etfdata) if etfdata else get_etf_root(),
            use_local_pepe=os.getenv("USE_LOCAL_PEPE", "").lower() in ("1", "true", "yes"),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.2")),
            coinglass_api_key=os.getenv("COINGLASS_API_KEY", "").strip(),
            coinglass_exchange_list=os.getenv(
                "COINGLASS_EXCHANGE_LIST",
                "Binance,OKX,Bybit,Bitget,Gate",
            ).strip(),
            fund_flow_assets=[
                a.strip().upper()
                for a in os.getenv("FUND_FLOW_ASSETS", "BTC,ETH").split(",")
                if a.strip()
            ],
            x_bearer_token=os.getenv("X_BEARER_TOKEN", os.getenv("TWITTER_BEARER_TOKEN", "")).strip(),
            x_search_query=os.getenv("X_SEARCH_QUERY", "").strip(),
            x_max_results=int(os.getenv("X_MAX_RESULTS", "30")),
            event_demo_mode=os.getenv("EVENT_DEMO_MODE", "false").lower() in ("1", "true", "yes"),
            event_min_btc_relevance=float(os.getenv("EVENT_MIN_BTC_RELEVANCE", "0.35")),
            event_poll_interval_sec=int(os.getenv("EVENT_POLL_INTERVAL_SEC", "300")),
            event_llm_max_calls=int(os.getenv("EVENT_LLM_MAX_CALLS", "3")),
            use_deribit_gex=os.getenv("USE_DERIBIT_GEX", "true").lower() in ("1", "true", "yes"),
            liquidation_half_life_hours=float(os.getenv("LIQUIDATION_HALF_LIFE_HOURS", "3")),
            signal_cooldown_min_sec=int(os.getenv("SIGNAL_COOLDOWN_MIN_SEC", "900")),
            signal_cooldown_max_sec=int(os.getenv("SIGNAL_COOLDOWN_MAX_SEC", "1800")),
            macro_hazard_window_min=int(os.getenv("MACRO_HAZARD_WINDOW_MIN", "120")),
            regime_min_dwell_bars=int(os.getenv("REGIME_MIN_DWELL_BARS", "2")),
            regime_transition_penalty=float(os.getenv("REGIME_TRANSITION_PENALTY", "0.35")),
            regime_forward_bars=int(os.getenv("REGIME_FORWARD_BARS", "6")),
            regime_forward_min_samples=int(os.getenv("REGIME_FORWARD_MIN_SAMPLES", "20")),
            regime_rollup_window_days=int(os.getenv("REGIME_ROLLUP_WINDOW_DAYS", "30")),
            regime_use_recommendation=os.getenv("REGIME_USE_RECOMMENDATION", "true").lower()
            in ("1", "true", "yes"),
            regime_calibration_interval_hours=int(os.getenv("REGIME_CALIBRATION_INTERVAL_HOURS", "24")),
            hmm_disagree_confidence_cap=float(os.getenv("HMM_DISAGREE_CONFIDENCE_CAP", "0.55")),
            hmm_low_confidence_cap=float(os.getenv("HMM_LOW_CONFIDENCE_CAP", "0.60")),
            hmm_low_confidence_threshold=float(os.getenv("HMM_LOW_CONFIDENCE_THRESHOLD", "0.50")),
            consensus_opposing_confidence_cap=float(
                os.getenv("CONSENSUS_OPPOSING_CONFIDENCE_CAP", "0.55")
            ),
            trend_health_regime_flip_threshold=int(
                os.getenv("TREND_HEALTH_REGIME_FLIP_THRESHOLD", "6")
            ),
            readiness_cache_ttl_sec=int(os.getenv("READINESS_CACHE_TTL_SEC", "60")),
            black_swan_liq_pulse_usd=float(os.getenv("BLACK_SWAN_LIQ_PULSE_USD", "5000000")),
            black_swan_liq_total_usd=float(os.getenv("BLACK_SWAN_LIQ_TOTAL_USD", "10000000")),
            black_swan_changepoint_threshold=float(os.getenv("BLACK_SWAN_CHANGEPOINT_THRESHOLD", "0.7")),
            black_swan_range_watch_bars=int(os.getenv("BLACK_SWAN_RANGE_WATCH_BARS", "24")),
            black_swan_range_warn_bars=int(os.getenv("BLACK_SWAN_RANGE_WARN_BARS", "48")),
            black_swan_funding_extreme_pct=float(os.getenv("BLACK_SWAN_FUNDING_EXTREME_PCT", "0.0003")),
            use_taker_cvd=os.getenv("USE_TAKER_CVD", "true").lower() in ("1", "true", "yes"),
            taker_cvd_exchange=os.getenv("TAKER_CVD_EXCHANGE", "binance").strip().lower(),
            binance_config_path=Path(binance_cfg) if binance_cfg else None,
            allow_coinglass_scrape_fallback=os.getenv(
                "ALLOW_COINGLASS_SCRAPE_FALLBACK", "false"
            ).lower() in ("1", "true", "yes"),
            allow_ccxt_ohlcv_fallback=os.getenv(
                "ALLOW_CCXT_OHLCV_FALLBACK", "false"
            ).lower() in ("1", "true", "yes"),
            snapshot_poll_interval_sec=int(os.getenv("SNAPSHOT_POLL_INTERVAL_SEC", "120")),
            snapshot_stale_sec=int(os.getenv("SNAPSHOT_STALE_SEC", "300")),
            snapshot_warmup_on_start=os.getenv("SNAPSHOT_WARMUP_ON_START", "true").lower()
            in ("1", "true", "yes"),
            api_key=os.getenv("API_KEY", "").strip(),
            sched_btc_1m_sec=int(os.getenv("SCHED_BTC_1M_SEC", os.getenv("BTC_1M_INTERVAL_SEC", "300"))),
            sched_events_sec=int(os.getenv("SCHED_EVENTS_SEC", os.getenv("EVENT_POLL_INTERVAL_SEC", "300"))),
            sched_sync_hour=int(os.getenv("SCHED_SYNC_HOUR", os.getenv("SYNC_HOUR", "8"))),
            sched_sync_minute=int(os.getenv("SCHED_SYNC_MINUTE", os.getenv("SYNC_MINUTE", "0"))),
            sched_sync_timezone=os.getenv(
                "SCHED_SYNC_TIMEZONE", os.getenv("SYNC_TIMEZONE", "Asia/Shanghai")
            ).strip(),
        )
