from __future__ import annotations

import os

import numpy as np
import pandas as pd

os.environ.setdefault("SMC_CREDIT", "0")

try:
    from smartmoneyconcepts import smc
except ImportError as e:
    raise ImportError("请安装: pip install smartmoneyconcepts") from e

from ai_trade_advisor.models import PriceZone, SmcSnapshot


def compute_smc_frame(df: pd.DataFrame, *, swing_length: int = 20) -> pd.DataFrame:
    ohlc = df[["open", "high", "low", "close", "volume"]].astype(float).copy()
    out = df.copy()
    sw = smc.swing_highs_lows(ohlc, swing_length=swing_length)
    bos = smc.bos_choch(ohlc, sw, close_break=True)
    fvg = smc.fvg(ohlc, join_consecutive=True)
    ob = smc.ob(ohlc, sw, close_mitigation=False)
    for frame, prefix in ((sw, "sw"), (bos, "smc"), (fvg, "fvg"), (ob, "ob")):
        for col in frame.columns:
            out[f"{prefix}_{col}"] = frame[col].values
    return out


def _zone_from_row(row: pd.Series, prefix: str, label: str) -> PriceZone | None:
    top = row.get(f"{prefix}_Top")
    bottom = row.get(f"{prefix}_Bottom")
    if pd.isna(top) or pd.isna(bottom):
        return None
    lo, hi = float(min(bottom, top)), float(max(bottom, top))
    if lo <= 0 or hi <= 0:
        return None
    return PriceZone(low=lo, high=hi, label=label, kind=prefix)


def build_smc_snapshot(df: pd.DataFrame, price: float) -> SmcSnapshot:
    enriched = compute_smc_frame(df)
    last = enriched.iloc[-1]
    notes: list[str] = []

    choch = last.get("smc_CHOCH")
    bos = last.get("smc_BOS")
    mss_or_choch: str | None = None
    mss_dir = 0
    if pd.notna(choch) and choch != 0:
        mss_or_choch = "CHoCH"
        mss_dir = int(np.sign(choch))
        notes.append(f"最新 bar 出现 CHoCH，方向={'看涨' if mss_dir > 0 else '看跌'}")
    elif pd.notna(bos) and bos != 0:
        mss_or_choch = "BOS"
        mss_dir = int(np.sign(bos))
        notes.append(f"最新 bar 出现 BOS，方向={'看涨' if mss_dir > 0 else '看跌'}")

    trend = _infer_trend(enriched)
    notes.append(f"结构趋势: {trend}")

    active_obs: list[PriceZone] = []
    unfilled_fvgs: list[PriceZone] = []
    for i in range(len(enriched) - 1, max(len(enriched) - 80, -1), -1):
        row = enriched.iloc[i]
        ob_z = _zone_from_row(row, "ob", f"OB@{i}")
        if ob_z and len(active_obs) < 5:
            active_obs.append(ob_z)
        fvg_z = _zone_from_row(row, "fvg", f"FVG@{i}")
        if fvg_z and len(unfilled_fvgs) < 5:
            mitigated = row.get("fvg_MitigatedIndex")
            if pd.isna(mitigated) or mitigated == 0:
                unfilled_fvgs.append(fvg_z)

    nearest_ob = _nearest_zone(active_obs, price)
    nearest_fvg = _nearest_zone(unfilled_fvgs, price)

    if nearest_ob:
        notes.append(
            f"最近 OB [{nearest_ob.low:.6g}, {nearest_ob.high:.6g}]，距离 {nearest_ob.width_pct(price):.2f}%"
        )
    if nearest_fvg:
        notes.append(
            f"最近未回补 FVG [{nearest_fvg.low:.6g}, {nearest_fvg.high:.6g}]，距离 {nearest_fvg.width_pct(price):.2f}%"
        )

    return SmcSnapshot(
        trend=trend,
        mss_or_choch=mss_or_choch,
        mss_direction=mss_dir,
        nearest_ob=nearest_ob,
        nearest_fvg=nearest_fvg,
        unfilled_fvgs=unfilled_fvgs,
        active_obs=active_obs,
        structure_notes=notes,
    )


def _infer_trend(df: pd.DataFrame) -> str:
    highs = df["high"].tail(30)
    lows = df["low"].tail(30)
    if len(highs) < 10:
        return "unknown"
    hh = highs.iloc[-1] >= highs.iloc[:-1].max()
    hl = lows.iloc[-1] >= lows.iloc[:-1].min()
    lh = highs.iloc[-1] <= highs.iloc[:-1].max()
    ll = lows.iloc[-1] <= lows.iloc[:-1].min()
    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"
    return "ranging"


def _nearest_zone(zones: list[PriceZone], price: float) -> PriceZone | None:
    if not zones:
        return None
    return min(zones, key=lambda z: abs(z.mid() - price))
