from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.spot_cvd import analyze_spot_cvd_from_frames, load_taker_history_for_backtest
from ai_trade_advisor.features.indicators import compute_atr
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.regime.engine import analyze_btc_regime
from ai_trade_advisor.models import MarketContext, SmcSnapshot


@dataclass
class RegimeBacktestResult:
    bars_evaluated: int
    warmup_bars: int
    cvd_source: str
    regime_counts: dict[str, int]
    forward_returns: dict[str, dict[str, float]]
    samples_by_regime: dict[str, int] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bars_evaluated": self.bars_evaluated,
            "warmup_bars": self.warmup_bars,
            "cvd_source": self.cvd_source,
            "regime_counts": self.regime_counts,
            "forward_returns": self.forward_returns,
            "samples_by_regime": self.samples_by_regime,
            "timeline_tail": self.timeline[-20:],
        }


def _vol_proxy_at(df: pd.DataFrame, idx: int) -> tuple[float | None, str | None]:
    sub = df.iloc[: idx + 1]
    if len(sub) < 30:
        return None, None
    atr = compute_atr(sub, period=14)
    last = float(atr.iloc[-1])
    window = min(len(atr), 672)
    baseline = float(atr.iloc[-window:].mean())
    if not np.isfinite(last) or not np.isfinite(baseline) or baseline <= 0:
        return None, None
    excess = last / baseline - 1.0
    if excess >= 0.50:
        return 0.25, "elevated"
    if excess >= 0.15:
        return 0.10, "normal"
    return 0.03, "low"


def _minimal_ctx(cfg: AdvisorConfig, df: pd.DataFrame, idx: int) -> MarketContext:
    row = df.iloc[idx]
    vr, vs = _vol_proxy_at(df, idx)
    return MarketContext(
        symbol=cfg.symbol,
        exchange=cfg.exchange,
        timeframe=f"{cfg.bar_minutes}m",
        as_of=str(row.get("datetime", row["timestamp"])),
        last_price=float(row["close"]),
        ohlcv_summary={},
        smc=SmcSnapshot(trend="sideways", mss_or_choch=None, mss_direction=0, nearest_ob=None, nearest_fvg=None),
        liquidity_levels=[],
        gex_levels=[],
        orderbook=None,
        vol_ratio=vr,
        vol_status=vs,
    )


def _cvd_at_bar(df_30m: pd.DataFrame, df_5m: pd.DataFrame, idx: int) -> dict[str, Any]:
    slice_30 = df_30m.iloc[: idx + 1]
    ts = int(slice_30.iloc[-1]["timestamp"])
    slice_5 = df_5m[df_5m["timestamp"] <= ts]
    price = float(slice_30.iloc[-1]["close"])
    return analyze_spot_cvd_from_frames(
        df_30m=slice_30,
        df_5m=slice_5,
        perp_price=price,
        source="binance_spot_taker:backtest",
    )


def _forward_return(closes: pd.Series, idx: int, horizon: int) -> float | None:
    if idx + horizon >= len(closes):
        return None
    c0 = float(closes.iloc[idx])
    c1 = float(closes.iloc[idx + horizon])
    if c0 <= 0:
        return None
    return (c1 - c0) / c0


def run_regime_backtest(
    cfg: AdvisorConfig,
    *,
    bars: int = 720,
    warmup: int = 200,
    horizons: tuple[int, ...] = (1, 4, 8, 24),
    df_30m: pd.DataFrame | None = None,
    df_5m: pd.DataFrame | None = None,
    skip_macro: bool = True,
    store_timeline: bool = False,
) -> RegimeBacktestResult:
    """
    Walk-forward Regime 验证：每根 30m bar 用真实 spot taker CVD + 历史切片重算状态，
    并统计各 regime 的未来收益。
    """
    if df_30m is None or df_5m is None:
        df_30m, df_5m = load_taker_history_for_backtest(
            cfg,
            bars_30m=bars,
            bars_5m=min(bars * 6, 5000),
        )

    if len(df_30m) < warmup + 20:
        raise ValueError(f"30m 数据不足: {len(df_30m)} < warmup+20")

    macro_off = MacroHazardState(macro_hazard_flag=False, active_events=[])
    closes = df_30m["close"].astype(float)
    regime_counts: dict[str, int] = {}
    ret_buckets: dict[str, dict[int, list[float]]] = {}
    timeline: list[dict[str, Any]] = []
    cvd_source = "binance_spot_taker"

    for idx in range(warmup, len(df_30m) - max(horizons)):
        ctx = _minimal_ctx(cfg, df_30m, idx)
        cvd = _cvd_at_bar(df_30m, df_5m, idx)
        cvd_source = str(cvd.get("source", cvd_source))
        slice_df = df_30m.iloc[: idx + 1].reset_index(drop=True)

        macro = macro_off if skip_macro else None
        analysis = analyze_btc_regime(
            cfg,
            ctx,
            df=slice_df,
            macro=macro,
            cvd=cvd,
            skip_derivatives=True,
            skip_triad=True,
        )
        rid = analysis.regime_id
        regime_counts[rid] = regime_counts.get(rid, 0) + 1

        bucket = ret_buckets.setdefault(rid, {h: [] for h in horizons})
        for h in horizons:
            r = _forward_return(closes, idx, h)
            if r is not None:
                bucket[h].append(r)

        if store_timeline:
            timeline.append(
                {
                    "timestamp": int(df_30m.iloc[idx]["timestamp"]),
                    "regime_id": rid,
                    "close": float(closes.iloc[idx]),
                    "spot_cvd_breakout": analysis.spot_cvd_breakout,
                }
            )

    forward_returns: dict[str, dict[str, float]] = {}
    samples: dict[str, int] = {}
    for rid, by_h in ret_buckets.items():
        forward_returns[rid] = {}
        samples[rid] = max((len(v) for v in by_h.values()), default=0)
        for h, vals in by_h.items():
            if vals:
                forward_returns[rid][f"h{h}"] = round(float(np.mean(vals)) * 100, 4)

    return RegimeBacktestResult(
        bars_evaluated=len(df_30m) - warmup - max(horizons),
        warmup_bars=warmup,
        cvd_source=cvd_source,
        regime_counts=regime_counts,
        forward_returns=forward_returns,
        samples_by_regime=samples,
        timeline=timeline,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="BTC Regime 历史 walk-forward 验证（真实 spot taker CVD）")
    parser.add_argument("--bars", type=int, default=720, help="30m K 线根数")
    parser.add_argument("--warmup", type=int, default=200, help="预热 bar 数")
    parser.add_argument("--symbol", default="", help="永续符号，如 BTC/USDT:USDT")
    parser.add_argument("--output", "-o", default="", help="JSON 报告路径")
    parser.add_argument("--timeline", action="store_true", help="保存完整 timeline（较大）")
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    if args.symbol:
        cfg.symbol = args.symbol
    cfg.use_taker_cvd = True

    try:
        result = run_regime_backtest(
            cfg,
            bars=args.bars,
            warmup=args.warmup,
            store_timeline=args.timeline,
        )
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    payload = result.to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已写入 {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
