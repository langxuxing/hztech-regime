"""简单实用的黑天鹅预警策略（纯规则，可单测）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.indicators import compute_atr, donchian_14d
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState


@dataclass
class StrategySignal:
    """单条预警策略输出。"""

    id: str
    label: str
    score: float
    level_hint: int
    trigger: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "score": round(self.score, 4),
            "level_hint": self.level_hint,
            "trigger": self.trigger,
            "details": self.details,
        }


def build_practical_signals(
    df: pd.DataFrame,
    *,
    cfg: AdvisorConfig | None = None,
    market: dict[str, Any] | None = None,
    microstructure: dict[str, Any] | None = None,
    volatility: dict[str, Any] | None = None,
    liquidation: LiquidationGridState | None = None,
    regime: dict[str, Any] | None = None,
    price: float | None = None,
) -> dict[str, Any]:
    """
    汇总实用预警策略，供 evaluate_black_swan_alert 消费。

    返回 {scores: dict, strategies: list[dict], max_level_hint: int}
    """
    cfg = cfg or AdvisorConfig.from_env()
    market = market or {}
    micro = microstructure or {}
    vol = volatility or {}
    regime = regime or {}
    spot = price or float(market.get("close") or df.iloc[-1]["close"])

    signals: list[StrategySignal] = [
        _range_squeeze_signal(
            df,
            bar_minutes=cfg.bar_minutes,
            watch_bars=cfg.black_swan_range_watch_bars,
            warn_bars=cfg.black_swan_range_warn_bars,
        ),
        _vol_squeeze_signal(df, gk_vol=vol.get("gk_realized_vol")),
        _funding_extreme_signal(
            micro.get("funding_rate"),
            threshold=cfg.black_swan_funding_extreme_pct,
        ),
        _oi_price_divergence_signal(
            micro.get("oi_change_pct"),
            regime.get("raw_trend"),
            micro.get("oi_price_sync"),
        ),
        _liq_cluster_proximity_signal(liquidation, spot),
        _volume_dryup_signal(df),
        _failed_breakout_signal(regime),
        _cvd_divergence_signal(regime, micro),
    ]

    range_score = next((s.score for s in signals if s.id == "range_squeeze"), 0.0)
    signals.append(_donchian_edge_signal(df, range_squeeze_score=range_score))

    scores = {s.id: s.score for s in signals}
    max_hint = max((s.level_hint for s in signals), default=0)

    return {
        "scores": scores,
        "strategies": [s.to_dict() for s in signals if s.score > 0 or s.trigger],
        "max_level_hint": max_hint,
        "active": [s.id for s in signals if s.level_hint >= 1],
    }


def _range_squeeze_signal(
    df: pd.DataFrame,
    *,
    bar_minutes: int,
    watch_bars: int,
    warn_bars: int,
) -> StrategySignal:
    """
    箱体驻留变盘：窄幅震荡越久，变盘概率越高。

    判定：收盘价在滚动箱体内，且箱体宽度低于阈值；统计连续驻留根数。
    """
    if len(df) < 25:
        return StrategySignal("range_squeeze", "箱体驻留", 0.0, 0)

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    window = 20

    box_high = high.rolling(window).max()
    box_low = low.rolling(window).min()
    width_pct = (box_high - box_low) / close.replace(0, np.nan) * 100

    streak = 0
    for i in range(len(df) - 1, window - 1, -1):
        c = float(close.iloc[i])
        bh = float(box_high.iloc[i])
        bl = float(box_low.iloc[i])
        w = float(width_pct.iloc[i]) if np.isfinite(width_pct.iloc[i]) else 99.0
        in_box = bl <= c <= bh and w <= 4.5
        if in_box:
            streak += 1
        else:
            break

    current_width = float(width_pct.iloc[-1]) if np.isfinite(width_pct.iloc[-1]) else None
    hours = streak * bar_minutes / 60
    score = min(1.0, streak / max(warn_bars, 1))
    if current_width is not None and current_width < 2.5:
        score = min(1.0, score + 0.12)

    level_hint = 0
    trigger = None
    if streak >= warn_bars:
        level_hint = 2
        width_note = f"{current_width:.1f}%" if current_width is not None else "n/a"
        trigger = f"箱体驻留 {streak} 根（≈{hours:.0f}h），通道宽度 {width_note} → 变盘概率高"
    elif streak >= watch_bars:
        level_hint = 1
        trigger = f"箱体驻留 {streak} 根（≈{hours:.0f}h）→ 关注突破方向"

    return StrategySignal(
        "range_squeeze",
        "箱体驻留变盘",
        score,
        level_hint,
        trigger,
        {
            "range_bars": streak,
            "range_hours": round(hours, 1),
            "range_width_pct": round(current_width, 2) if current_width is not None else None,
            "watch_bars": watch_bars,
            "warn_bars": warn_bars,
        },
    )


def _vol_squeeze_signal(df: pd.DataFrame, *, gk_vol: float | None) -> StrategySignal:
    """波动率挤压：ATR 处于近期低位，能量蓄积。"""
    if len(df) < 30:
        return StrategySignal("vol_squeeze", "波动率挤压", 0.0, 0)

    close = df["close"].astype(float)
    atr = compute_atr(df, period=14)
    atr_pct = (atr / close.replace(0, np.nan) * 100).dropna()
    if len(atr_pct) < 10:
        return StrategySignal("vol_squeeze", "波动率挤压", 0.0, 0)

    current = float(atr_pct.iloc[-1])
    p20 = float(atr_pct.tail(48).quantile(0.20))
    p50 = float(atr_pct.tail(48).quantile(0.50))
    score = 0.0
    if current <= p20:
        score = min(1.0, 0.55 + (p20 - current) / max(p20, 1e-6) * 0.35)
    elif current <= p50 * 0.85:
        score = 0.35

    if gk_vol is not None and gk_vol < 0.45:
        score = min(1.0, score + 0.15)

    level_hint = 1 if score >= 0.55 else 0
    trigger = None
    if level_hint:
        trigger = f"ATR%={current:.2f} 处于近 48 根低位（P20={p20:.2f}）→ 波动蓄积"

    return StrategySignal(
        "vol_squeeze",
        "波动率挤压",
        score,
        level_hint,
        trigger,
        {"atr_pct": round(current, 3), "atr_p20": round(p20, 3)},
    )


def _funding_extreme_signal(
    funding_rate: float | None,
    *,
    threshold: float,
) -> StrategySignal:
    """资金费率极端：拥挤交易易触发反向波动。"""
    if funding_rate is None:
        return StrategySignal("funding_extreme", "费率极端", 0.0, 0)

    fr = float(funding_rate)
    abs_fr = abs(fr)
    score = min(1.0, abs_fr / max(threshold, 1e-8))
    level_hint = 0
    trigger = None
    if abs_fr >= threshold * 2:
        level_hint = 2
        side = "多头拥挤" if fr > 0 else "空头拥挤"
        trigger = f"资金费率 {fr * 100:.4f}% → {side}，插针风险"
    elif abs_fr >= threshold:
        level_hint = 1
        trigger = f"资金费率偏高 {fr * 100:.4f}% → 杠杆过热"

    return StrategySignal(
        "funding_extreme",
        "费率极端",
        score,
        level_hint,
        trigger,
        {"funding_rate": fr, "threshold": threshold},
    )


def _oi_price_divergence_signal(
    oi_change_pct: float | None,
    raw_trend: str | None,
    oi_price_sync: str | None,
) -> StrategySignal:
    """OI-价格背离：涨但减仓 / 横盘但增仓。"""
    if oi_change_pct is None:
        return StrategySignal("oi_divergence", "OI背离", 0.0, 0)

    oi = float(oi_change_pct)
    trend = raw_trend or "range"
    sync = oi_price_sync or "neutral"
    score = 0.0
    level_hint = 0
    trigger = None

    if trend == "uptrend" and oi < -1.5:
        score = min(1.0, abs(oi) / 5)
        level_hint = 1
        trigger = f"价格上涨但 OI {oi:+.1f}% → 上涨乏力，假突破风险"
    elif trend == "downtrend" and oi > 1.5:
        score = min(1.0, oi / 5)
        level_hint = 1
        trigger = f"价格下跌但 OI {oi:+.1f}% → 空头堆积，轧空风险"
    elif trend == "range" and oi > 2.5:
        score = min(1.0, oi / 6)
        level_hint = 2
        trigger = f"横盘但 OI 增仓 {oi:+.1f}% → 蓄势待发，变盘临近"
    elif sync == "unwind" and abs(oi) > 2:
        score = 0.45
        level_hint = 1
        trigger = f"OI 减仓 {oi:+.1f}% → 趋势动能衰竭"

    return StrategySignal(
        "oi_divergence",
        "OI背离",
        score,
        level_hint,
        trigger,
        {"oi_change_pct": oi, "raw_trend": trend, "oi_price_sync": sync},
    )


def _liq_cluster_proximity_signal(
    liquidation: LiquidationGridState | None,
    spot: float,
) -> StrategySignal:
    """清算密集区迫近：价格靠近 pain_price 易触发连锁爆仓。"""
    if liquidation is None or liquidation.pain_price is None or spot <= 0:
        return StrategySignal("liq_proximity", "清算迫近", 0.0, 0)

    pain = float(liquidation.pain_price)
    dist_pct = abs(pain - spot) / spot * 100
    score = max(0.0, min(1.0, 1.0 - dist_pct / 5.0))
    level_hint = 0
    trigger = None
    if dist_pct < 1.5:
        level_hint = 2
        trigger = f"距清算痛点 {pain:,.0f} 仅 {dist_pct:.1f}% → 连锁爆仓风险"
    elif dist_pct < 3.0:
        level_hint = 1
        trigger = f"距清算痛点 {dist_pct:.1f}% → 关注磁吸效应"

    return StrategySignal(
        "liq_proximity",
        "清算迫近",
        score,
        level_hint,
        trigger,
        {"pain_price": pain, "dist_pct": round(dist_pct, 2)},
    )


def _volume_dryup_signal(df: pd.DataFrame) -> StrategySignal:
    """成交量干涸：缩量横盘后易放量变盘。"""
    if "volume" not in df.columns or len(df) < 30:
        return StrategySignal("volume_dryup", "成交量干涸", 0.0, 0)

    vol = df["volume"].astype(float)
    recent = float(vol.tail(5).mean())
    baseline = float(vol.tail(48).quantile(0.25))
    if baseline <= 0:
        return StrategySignal("volume_dryup", "成交量干涸", 0.0, 0)

    ratio = recent / baseline
    score = max(0.0, min(1.0, 1.0 - ratio)) if ratio < 1 else 0.0
    level_hint = 1 if ratio < 0.55 else 0
    trigger = None
    if level_hint:
        trigger = f"近 5 根均量仅为 48 根 P25 的 {ratio:.0%} → 缩量蓄势"

    return StrategySignal(
        "volume_dryup",
        "成交量干涸",
        score,
        level_hint,
        trigger,
        {"volume_ratio_to_p25": round(ratio, 3)},
    )


def _failed_breakout_signal(regime: dict[str, Any]) -> StrategySignal:
    """假突破回访：Regime 已识别为洗盘结构。"""
    rid = regime.get("regime_id") or ""
    if rid != "fake_breakout_wash":
        return StrategySignal("failed_breakout", "假突破", 0.0, 0)

    return StrategySignal(
        "failed_breakout",
        "假突破洗盘",
        0.75,
        1,
        "高波突破但现货 CVD 未确认 → 流动性掠夺，勿追趋势",
        {"regime_id": rid},
    )


def _cvd_divergence_signal(
    regime: dict[str, Any],
    micro: dict[str, Any],
) -> StrategySignal:
    """CVD 背离：价格与现货买盘方向不一致。"""
    if not regime.get("cvd_bullish_divergence"):
        return StrategySignal("cvd_divergence", "CVD背离", 0.0, 0)

    return StrategySignal(
        "cvd_divergence",
        "CVD底背离",
        0.65,
        1,
        "价格新低但现货 CVD 抬升 → 下跌动能衰减，警惕反转",
        {"cvd_trend": micro.get("cvd_trend") or regime.get("cvd_trend")},
    )


def _donchian_edge_signal(df: pd.DataFrame, *, range_squeeze_score: float = 0.0) -> StrategySignal:
    """唐奇安贴轨：价格贴近通道边缘；与箱体驻留共振时升至 Warn。"""
    meta = donchian_breakout_imminence(df)
    score = float(meta.get("score") or 0)
    if score <= 0:
        return StrategySignal("donchian_edge", "唐奇安贴轨", 0.0, 0)

    level_hint = 1
    trigger = "价格贴近唐奇安通道边缘 → 突破在即"
    if range_squeeze_score >= 0.55:
        level_hint = 2
        score = min(1.0, score + 0.25)
        trigger = "箱体驻留 + 唐奇安贴轨 → 变盘共振预警"

    return StrategySignal(
        "donchian_edge",
        "唐奇安贴轨",
        score,
        level_hint,
        trigger,
        {
            "dist_upper_pct": meta.get("dist_upper_pct"),
            "dist_lower_pct": meta.get("dist_lower_pct"),
            "range_squeeze_resonance": range_squeeze_score >= 0.55,
        },
    )


def donchian_breakout_imminence(df: pd.DataFrame) -> dict[str, Any]:
    """辅助：价格贴唐奇安轨道运行，突破在即（优先用当前周期滚动通道）。"""
    if len(df) < 20:
        return {"score": 0.0}
    close = float(df.iloc[-1]["close"])
    if close <= 0:
        return {"score": 0.0}

    try:
        d_up, d_lo = donchian_14d(df)
    except (KeyError, ValueError):
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        d_up = float(high.tail(14).max())
        d_lo = float(low.tail(14).min())

    width = (d_up - d_lo) / close * 100 if close > 0 else 0
    dist_upper = (d_up - close) / close * 100
    dist_lower = (close - d_lo) / close * 100
    near_edge = min(dist_upper, dist_lower) < width * 0.08
    return {
        "near_donchian_edge": near_edge,
        "dist_upper_pct": round(dist_upper, 2),
        "dist_lower_pct": round(dist_lower, 2),
        "score": 0.4 if near_edge and width < 6 else 0.0,
    }
