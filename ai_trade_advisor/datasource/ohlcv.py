from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange
from ai_trade_advisor.datasource.paths import get_ohlcv_dir

logger = logging.getLogger(__name__)

OhlcvSource = Literal[
    "local_btc_1m_resample",
    "local_pepe_resample",
    "ccxt_live",
]

_last_ohlcv_source: OhlcvSource | None = None
_MIN_LOCAL_BARS = 50


@dataclass
class OhlcvValidationResult:
    ok: bool
    bars: int
    gap_count: int
    ohlc_violations: int
    duplicate_timestamps: int
    notes: list[str]


class LocalBtcDataError(RuntimeError):
    """本地 BTC OHLCV 数据不可用或不足。"""


def get_last_ohlcv_source() -> OhlcvSource | None:
    """最近一次 load_ohlcv 使用的数据来源。"""
    return _last_ohlcv_source


def validate_ohlcv(
    df: pd.DataFrame,
    *,
    bar_minutes: int | None = None,
    strict: bool = False,
) -> OhlcvValidationResult:
    """校验 OHLCV 完整性：重复时间戳、OHLC 逻辑、可选 gap 检测。"""
    notes: list[str] = []
    if df is None or df.empty:
        return OhlcvValidationResult(
            ok=False,
            bars=0,
            gap_count=0,
            ohlc_violations=0,
            duplicate_timestamps=0,
            notes=["empty dataframe"],
        )

    work = _normalize_1m_df(df) if "timestamp" in df.columns else df.copy()
    bars = len(work)
    dup = int(work["timestamp"].duplicated().sum()) if "timestamp" in work.columns else 0
    if dup:
        notes.append(f"duplicate timestamps: {dup}")

    bad = work[
        (work["high"] < work["low"])
        | (work["high"] < work["open"])
        | (work["high"] < work["close"])
        | (work["low"] > work["open"])
        | (work["low"] > work["close"])
    ]
    ohlc_violations = len(bad)
    if ohlc_violations:
        notes.append(f"ohlc logic violations: {ohlc_violations}")

    gap_count = 0
    if bar_minutes and "timestamp" in work.columns and len(work) > 1:
        expected_ms = bar_minutes * 60_000
        ts = work["timestamp"].astype(int).sort_values()
        deltas = ts.diff().dropna()
        gaps = deltas[deltas > expected_ms]
        gap_count = len(gaps)
        if gap_count:
            notes.append(f"time gaps (>{bar_minutes}m): {gap_count}")

    ok = ohlc_violations == 0 and (dup == 0 or not strict) and (gap_count == 0 or not strict)
    return OhlcvValidationResult(
        ok=ok,
        bars=bars,
        gap_count=gap_count,
        ohlc_violations=ohlc_violations,
        duplicate_timestamps=dup,
        notes=notes,
    )


def _apply_ohlcv_validation(
    df: pd.DataFrame,
    *,
    bar_minutes: int,
    source: str,
) -> pd.DataFrame:
    """校验并在可修复时去重；严重异常打日志。"""
    result = validate_ohlcv(df, bar_minutes=bar_minutes)
    out = df.copy()
    if result.duplicate_timestamps and "timestamp" in out.columns:
        out = out.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
        logger.warning("ohlcv[%s]: dropped %d duplicate bars", source, result.duplicate_timestamps)
    if result.ohlc_violations:
        logger.error(
            "ohlcv[%s]: %d OHLC violations (bars=%d)",
            source,
            result.ohlc_violations,
            result.bars,
        )
    if result.gap_count:
        logger.warning("ohlcv[%s]: %d time gaps detected", source, result.gap_count)
    return out.reset_index(drop=True)


def fetch_ohlcv_ccxt(
    cfg: AdvisorConfig,
    *,
    limit: int | None = None,
) -> pd.DataFrame:
    """从交易所拉取 OHLCV 并转为标准 DataFrame。"""
    exchange = make_exchange(
        cfg.exchange,
        market_type="swap",
        binance=cfg.binance_futures(),
    )
    exchange.load_markets()
    timeframe = f"{cfg.bar_minutes}m"
    bar_limit = limit or cfg.lookback_bars
    raw = exchange.fetch_ohlcv(cfg.symbol, timeframe=timeframe, limit=bar_limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.assign(datetime=pd.to_datetime(df["timestamp"], unit="ms", utc=True))
    df = df.sort_values("timestamp").reset_index(drop=True)
    return _apply_ohlcv_validation(df, bar_minutes=cfg.bar_minutes, source="ccxt_live")


def _normalize_1m_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ts" in out.columns and "timestamp" not in out.columns:
        out = out.rename(columns={"ts": "timestamp"})
    out["timestamp"] = out["timestamp"].astype(int)
    for col in ("open", "high", "low", "close"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    else:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0.0)
    out = out.dropna(subset=["open", "high", "low", "close", "timestamp"])
    return out.sort_values("timestamp").reset_index(drop=True)


def load_local_btc_1m_csvs(
    btc_dir: Path | None = None,
    *,
    lookback_days: int | None = None,
) -> pd.DataFrame | None:
    """读取 OKX mark 1m 日分 CSV（btc_usdt_swap_mark_1m_YYYY-MM-DD.csv）。"""
    base = btc_dir or get_ohlcv_dir("Btc")
    files = sorted(base.glob("btc_usdt_swap_mark_1m_*.csv"))
    if not files:
        return None

    if lookback_days is not None and lookback_days > 0:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days - 1)).isoformat()
        files = [f for f in files if f.stem.split("_")[-1] >= cutoff]
        if not files:
            files = sorted(base.glob("btc_usdt_swap_mark_1m_*.csv"))[-lookback_days:]

    frames: list[pd.DataFrame] = []
    for fp in files:
        try:
            raw = pd.read_csv(fp)
            frames.append(_normalize_1m_df(raw))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("跳过损坏的 1m CSV %s: %s", fp.name, exc)

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return merged.reset_index(drop=True)


def _try_load_local_btc(cfg: AdvisorConfig) -> pd.DataFrame | None:
    """本地 OKX 1m → resample 为 bar_minutes。"""
    if not cfg.symbol.upper().startswith("BTC"):
        return None

    warmup_days = max(14, cfg.lookback_bars * cfg.bar_minutes // 1440 + 7)
    df_1m = load_local_btc_1m_csvs(lookback_days=warmup_days)
    if df_1m is None or df_1m.empty:
        return None

    resampled = resample_from_1m(df_1m, cfg.bar_minutes)
    if len(resampled) < _MIN_LOCAL_BARS:
        return None

    out = resampled.tail(cfg.lookback_bars).reset_index(drop=True)
    return _apply_ohlcv_validation(out, bar_minutes=cfg.bar_minutes, source="local_btc_1m_resample")


def _try_load_local_pepe(cfg: AdvisorConfig) -> pd.DataFrame | None:
    """若配置了 CreativeIdeaLab 本地 PEPE 1m 数据，则 resample 为 30m。"""
    repo = Path(__file__).resolve().parents[3] / "CreativeIdeaLab"
    if not repo.exists():
        repo = Path("/Volumes/HZTech/CreativeIdeaLab")
    if not repo.exists():
        return None
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    try:
        from SpringStrategy.pepe_data_loader import load_pepe_bars, resample_ohlcv
    except ImportError:
        return None

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(14, cfg.lookback_bars * cfg.bar_minutes // 1440 + 7))
    df_1m, _ = load_pepe_bars(
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d %H:%M"),
        pepedata_dir=cfg.pepedata_dir,
        warmup_hours=7 * 24,
    )
    df = resample_ohlcv(df_1m, cfg.bar_minutes)
    return df.tail(cfg.lookback_bars).reset_index(drop=True)


def load_ohlcv(cfg: AdvisorConfig) -> pd.DataFrame:
    """
    加载 OHLCV：BTC 优先本地 OKX 1m resample，其次 PEPE 本地，最后 ccxt 实时。
    """
    global _last_ohlcv_source

    if cfg.use_local_pepe or (cfg.symbol.upper().startswith("PEPE") and cfg.pepedata_dir):
        local = _try_load_local_pepe(cfg)
        if local is not None and len(local) >= _MIN_LOCAL_BARS:
            _last_ohlcv_source = "local_pepe_resample"
            return local

    local_btc = _try_load_local_btc(cfg)
    if local_btc is not None:
        _last_ohlcv_source = "local_btc_1m_resample"
        logger.debug(
            "load_ohlcv: 使用本地 OKX 1m resample → %dm (%d bars)",
            cfg.bar_minutes,
            len(local_btc),
        )
        return local_btc

    if cfg.symbol.upper().startswith("BTC") and not cfg.allow_ccxt_ohlcv_fallback:
        raise LocalBtcDataError(
            f"本地 BTC OHLCV 不足（需要 ≥ {_MIN_LOCAL_BARS} 根 {cfg.bar_minutes}m K 线）。"
            "请运行 ./scripts/download_btc.sh 或 ./scripts/start-data-scheduler.sh 下载 OKX 1m 数据。"
        )

    _last_ohlcv_source = "ccxt_live"
    logger.warning(
        "load_ohlcv: 本地数据不足，fallback ccxt %s %dm",
        cfg.exchange,
        cfg.bar_minutes,
    )
    return fetch_ohlcv_ccxt(cfg)


def resample_from_1m(df_1m: pd.DataFrame, bar_minutes: int) -> pd.DataFrame:
    """通用 1m → Nm resample。"""
    d = _normalize_1m_df(df_1m)
    d["datetime"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
    d = d.set_index("datetime")
    rule = f"{bar_minutes}min"
    agg = d.resample(rule, label="right", closed="right").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    agg = agg.dropna(subset=["open"]).reset_index()
    agg["timestamp"] = (agg["datetime"].astype("int64") // 10**6).astype(int)
    return agg


def ohlcv_summary(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    ret_1 = (last["close"] - prev["close"]) / prev["close"] * 100 if prev["close"] else 0
    high_20 = float(df["high"].tail(20).max())
    low_20 = float(df["low"].tail(20).min())
    summary: dict[str, Any] = {
        "bars": len(df),
        "last_close": float(last["close"]),
        "last_change_pct": round(ret_1, 3),
        "range_20bar_high": high_20,
        "range_20bar_low": low_20,
        "avg_volume_20": round(float(df["volume"].tail(20).mean()), 2),
    }
    src = get_last_ohlcv_source()
    if src:
        summary["ohlcv_source"] = src
    return summary
