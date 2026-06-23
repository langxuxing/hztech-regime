from __future__ import annotations

from typing import Any

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.exchange import make_exchange


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp" not in out.columns and "datetime" in out.columns:
        out["timestamp"] = out["datetime"]
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        out = out.set_index("timestamp")
    elif not isinstance(out.index, pd.DatetimeIndex):
        raise ValueError("OHLCV frame needs timestamp or datetime column")

    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")

    for col in ("open", "high", "low", "close", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_index()


def _to_pandas_freq(tf: str) -> str:
    unit = tf[-1]
    val = tf[:-1]
    mapping = {"m": "min", "h": "h", "d": "D"}
    if unit in mapping:
        return f"{val}{mapping[unit]}"
    return tf


def _tf_seconds(tf: str) -> int:
    unit = tf[-1]
    val = int(tf[:-1])
    if unit == "m":
        return val * 60
    if unit == "h":
        return val * 3600
    if unit == "d":
        return val * 86400
    return val * 60


def fetch_btc_timeframe(
    cfg: AdvisorConfig | None,
    *,
    timeframe: str = "5m",
    limit: int = 500,
) -> pd.DataFrame:
    """拉取 BTC 指定周期 OHLCV（默认 Binance 永续）。"""
    cfg = cfg or AdvisorConfig()
    exchange = make_exchange(
        cfg.exchange,
        market_type="swap",
        binance=cfg.binance_futures(),
    )
    exchange.load_markets()
    raw = exchange.fetch_ohlcv(cfg.symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return _standardize_ohlcv(df)


def merge_timeframes(
    main_tf: str,
    context_tfs: list[str],
    klines_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """合并多周期 OHLCV（akash 项目 data_cleaner 逻辑精简版）。"""
    main = _standardize_ohlcv(klines_map[main_tf])
    main_freq = _to_pandas_freq(main_tf)
    main_secs = _tf_seconds(main_tf)

    merged = main.rename(
        columns={
            "open": f"open_{main_tf}",
            "high": f"high_{main_tf}",
            "low": f"low_{main_tf}",
            "close": f"close_{main_tf}",
            "volume": f"volume_{main_tf}",
        }
    )

    for tf in context_tfs:
        if tf == main_tf or tf not in klines_map:
            continue
        ctx = _standardize_ohlcv(klines_map[tf])
        ctx_freq = _to_pandas_freq(tf)
        ctx_secs = _tf_seconds(tf)
        ctx = ctx.rename(
            columns={
                "open": f"open_{tf}",
                "high": f"high_{tf}",
                "low": f"low_{tf}",
                "close": f"close_{tf}",
                "volume": f"volume_{tf}",
            }
        )

        if ctx_secs < main_secs:
            agg = {
                f"open_{tf}": "first",
                f"high_{tf}": "max",
                f"low_{tf}": "min",
                f"close_{tf}": "last",
                f"volume_{tf}": "sum",
            }
            ctx_agg = ctx.resample(main_freq, label="left", closed="left").agg(agg)
            merged = merged.join(ctx_agg, how="left")
        elif ctx_secs > main_secs:
            left = merged.index.to_frame(index=False).rename(columns={"index": "timestamp"})
            right = ctx.reset_index().rename(columns={ctx.index.name or "index": "timestamp"})
            asof = pd.merge_asof(
                left.sort_values("timestamp"),
                right.sort_values("timestamp"),
                on="timestamp",
                direction="backward",
            ).set_index("timestamp")
            ctx_cols = [c for c in asof.columns if c != "timestamp"]
            merged = merged.join(asof[ctx_cols], how="left")
        else:
            merged = merged.join(ctx, how="left")

    merged = merged.sort_index().ffill().reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in merged.columns:
        merged = merged.rename(columns={merged.columns[0]: "timestamp"})
    return merged


def prepare_btc_multiframe(
    df: pd.DataFrame | None = None,
    *,
    cfg: AdvisorConfig | None = None,
    main_tf: str = "5m",
    context_tfs: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """为 akash LSTM 引擎准备 5m/15m 合并数据。"""
    context_tfs = context_tfs or ["15m"]
    cfg = cfg or AdvisorConfig()
    klines: dict[str, pd.DataFrame] = {}

    def _resample_indexed(std: pd.DataFrame, tf: str) -> pd.DataFrame:
        freq = _to_pandas_freq(tf)
        resampled = std.resample(freq, label="right", closed="right").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        return resampled.dropna(subset=["open"]).reset_index()

    if df is not None and len(df) >= 100 and (
        "timestamp" in df.columns or "datetime" in df.columns or isinstance(df.index, pd.DatetimeIndex)
    ):
        std = _standardize_ohlcv(df)
        if len(std) >= 2:
            bar_minutes = max(1, int((std.index[-1] - std.index[-2]).total_seconds() / 60))
            if bar_minutes <= int(main_tf[:-1]):
                klines[main_tf] = std.reset_index()
                for tf in context_tfs:
                    if tf != main_tf:
                        klines[tf] = _resample_indexed(std, tf)

    # 粗粒度输入（如 30m）或数据不足：优先本地 OKX 1m resample
    need_fetch = any(
        tf not in klines or klines[tf] is None or len(klines[tf]) < 80
        for tf in [main_tf, *context_tfs]
    )
    if need_fetch:
        try:
            from ai_trade_advisor.datasource.ohlcv import load_local_btc_1m_csvs

            df_1m = load_local_btc_1m_csvs(lookback_days=30)
            if df_1m is not None and len(df_1m) >= 500:
                std_1m = _standardize_ohlcv(df_1m)
                klines[main_tf] = _resample_indexed(std_1m, main_tf)
                for tf in context_tfs:
                    if tf != main_tf:
                        klines[tf] = _resample_indexed(std_1m, tf)
        except Exception:
            pass

    for tf in [main_tf, *context_tfs]:
        if tf not in klines or klines[tf] is None or len(klines[tf]) < 80:
            klines[tf] = fetch_btc_timeframe(cfg, timeframe=tf, limit=limit).reset_index()

    merged = merge_timeframes(main_tf, context_tfs, klines)
    return {"klines": klines, "merged": merged, "main_tf": main_tf, "context_tfs": context_tfs}
