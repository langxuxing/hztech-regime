from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.derivatives_trend import analyze_derivatives_trend, resolve_trend_with_derivatives
from ai_trade_advisor.datasource.ohlcv import load_ohlcv
from ai_trade_advisor.datasource.spot_cvd import analyze_spot_cvd
from ai_trade_advisor.features.indicators import donchian_14d, kama_rails
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState, evaluate_macro_hazard
from ai_trade_advisor.regime.labels import REGIME_LABELS
from ai_trade_advisor.regime.triad.fusion import fuse_regime_triad
from ai_trade_advisor.regime.models.ensemble import run_all_regime_models
from ai_trade_advisor.regime.feedback.fusion import fuse_with_leaderboard
from ai_trade_advisor.regime.feedback.market_context import build_market_context
from ai_trade_advisor.regime.feedback.recommender import recommend_model
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.models import CapitalFlowsSnapshot, MarketContext

RawTrend = Literal["uptrend", "downtrend", "range"]
VolBucket = Literal["low_vol", "mid_vol", "high_vol"]
BtcRegimeId = Literal[
    "macro_frozen_range",
    "high_vol_uptrend",
    "fake_breakout_wash",
    "high_vol_downtrend",
    "high_vol_self_heal_range",
    "low_vol_uptrend",
    "mid_vol_uptrend",
    "low_vol_downtrend",
    "low_vol_range",
    "mid_vol_range",
    "high_vol_range",
]

_REGIME_LABELS = REGIME_LABELS

@dataclass
class BtcRegimeAnalysis:
    regime_id: str
    regime_label: str
    raw_trend: RawTrend
    vol_bucket: VolBucket
    close: float
    donchian_upper: float
    donchian_lower: float
    kama: float
    kama_upper: float
    kama_lower: float
    spot_cvd: float | None
    spot_cvd_breakout: bool
    cvd_bullish_divergence: bool
    spot_premium_bps: float | None
    spot_premium_positive: bool
    macro_hazard: bool
    confidence: float
    tech_trend: RawTrend = "range"
    funding_rate: float | None = None
    funding_bias: str = "neutral"
    open_interest: float | None = None
    oi_change_pct: float | None = None
    oi_price_sync: str = "neutral"
    cvd_trend: str = "neutral"
    derivatives_trend: dict[str, Any] | None = None
    drivers: list[str] = field(default_factory=list)
    dashboard_regime: str = "transition"
    triad: dict[str, Any] | None = None
    models: dict[str, Any] | None = None
    model_comparison: dict[str, Any] | None = None
    model_recommendation: dict[str, Any] | None = None
    model_scores_preview: dict[str, Any] | None = None
    hmm_modifier: dict[str, Any] | None = None
    hmm_disagrees: bool = False
    next_regime_label: str | None = None
    changepoint_prob: float | None = None
    in_regime_transition: bool = False

    def to_dict(self) -> dict[str, Any]:
        def _num(v: Any) -> Any:
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                return None
            return v

        return {
            "regime_id": self.regime_id,
            "regime_label": self.regime_label,
            "raw_trend": self.raw_trend,
            "vol_bucket": self.vol_bucket,
            "close": self.close,
            "donchian_upper": self.donchian_upper,
            "donchian_lower": self.donchian_lower,
            "kama": _num(self.kama),
            "kama_upper": _num(self.kama_upper),
            "kama_lower": _num(self.kama_lower),
            "spot_cvd": _num(self.spot_cvd),
            "spot_cvd_breakout": self.spot_cvd_breakout,
            "cvd_bullish_divergence": self.cvd_bullish_divergence,
            "spot_premium_bps": _num(self.spot_premium_bps),
            "spot_premium_positive": self.spot_premium_positive,
            "macro_hazard": self.macro_hazard,
            "confidence": round(self.confidence, 3),
            "tech_trend": self.tech_trend,
            "funding_rate": _num(self.funding_rate),
            "funding_bias": self.funding_bias,
            "open_interest": _num(self.open_interest),
            "oi_change_pct": _num(self.oi_change_pct),
            "oi_price_sync": self.oi_price_sync,
            "cvd_trend": self.cvd_trend,
            "derivatives_trend": self.derivatives_trend,
            "drivers": self.drivers,
            "dashboard_regime": self.dashboard_regime,
            "triad": self.triad,
            "models": self.models,
            "model_comparison": self.model_comparison,
            "model_recommendation": self.model_recommendation,
            "model_scores_preview": self.model_scores_preview,
            "hmm_modifier": self.hmm_modifier,
            "hmm_confidence_modifier": self.hmm_modifier,
            "hmm_disagrees": self.hmm_disagrees,
            "next_regime_label": self.next_regime_label,
            "changepoint_prob": self.changepoint_prob,
            "in_regime_transition": self.in_regime_transition,
        }


def analyze_btc_regime(
    cfg: AdvisorConfig,
    ctx: MarketContext,
    *,
    df: pd.DataFrame | None = None,
    macro: MacroHazardState | None = None,
    cvd: dict[str, Any] | None = None,
    deriv: dict[str, Any] | None = None,
    skip_derivatives: bool = False,
    skip_triad: bool = False,
) -> BtcRegimeAnalysis:
    """PDF 多维度 Regime 状态机（BTC 主链）。"""
    macro = macro or evaluate_macro_hazard(cfg)
    if df is None or len(df) < 50:
        df = load_ohlcv(cfg)

    close = float(df.iloc[-1]["close"])
    d_upper, d_lower = donchian_14d(df)
    kama, k_upper, k_lower = kama_rails(df)
    vol_bucket = _vol_bucket(ctx.vol_status, ctx.vol_ratio)

    if cvd is None:
        cvd = analyze_spot_cvd(cfg, close)

    if skip_derivatives:
        deriv = deriv or _empty_derivatives(cvd)
    elif deriv is None:
        deriv = analyze_derivatives_trend(cfg, df, cvd=cvd)
    tech_trend = _raw_trend(close, d_upper, d_lower, k_upper, k_lower)
    trend_drivers: list[str] = []
    raw_trend = resolve_trend_with_derivatives(tech_trend, deriv, trend_drivers)

    drivers: list[str] = [
        f"KAMA 轨道: {k_lower:.0f} / {kama:.0f} / {k_upper:.0f}",
        f"唐奇安14D: [{d_lower:.0f}, {d_upper:.0f}]",
        f"技术趋势: {tech_trend} → 融合趋势: {raw_trend} | 波动桶: {vol_bucket}",
    ]
    drivers.extend(trend_drivers)
    drivers.extend(deriv.get("drivers") or [])

    if macro.macro_hazard_flag:
        drivers.extend(macro.active_events or ["宏观公布窗口 ±120min"])
        base = _finalize(
            "macro_frozen_range",
            raw_trend,
            vol_bucket,
            close,
            d_upper,
            d_lower,
            kama,
            k_upper,
            k_lower,
            cvd,
            macro.macro_hazard_flag,
            0.88,
            drivers + ["宏观硬熔断，微观技术面降权"],
            dashboard="range",
            tech_trend=tech_trend,
            deriv=deriv,
        )
        if skip_triad:
            return base
        return _attach_triad(df, base, cfg)

    regime_id = _compose_regime(
        raw_trend,
        vol_bucket,
        bool(cvd.get("spot_cvd_breakout")),
        bool(cvd.get("cvd_bullish_divergence")),
        drivers,
        cvd,
    )
    confidence = _confidence(regime_id, raw_trend, cvd, deriv)
    dashboard = _map_dashboard_regime(regime_id)

    base = _finalize(
        regime_id,
        raw_trend,
        vol_bucket,
        close,
        d_upper,
        d_lower,
        kama,
        k_upper,
        k_lower,
        cvd,
        False,
        confidence,
        drivers,
        dashboard=dashboard,
        tech_trend=tech_trend,
        deriv=deriv,
    )
    if skip_triad:
        return base
    return _attach_triad(df, base)


def _attach_triad(df: pd.DataFrame, base: BtcRegimeAnalysis, cfg: AdvisorConfig | None = None) -> BtcRegimeAnalysis:
    """三型融合 + 多模型 Regime 对比 + 推荐模型。"""
    cfg = cfg or AdvisorConfig.from_env()
    try:
        fused = fuse_regime_triad(df, base.to_dict())
    except Exception as exc:
        base.drivers = list(base.drivers) + [f"三型融合跳过: {exc}"]
        fused = None

    if fused is not None:
        base.triad = fused.to_dict()
        base.next_regime_label = fused.transition.next_label
        base.changepoint_prob = round(fused.bocpd.changepoint_prob, 4)
        base.in_regime_transition = fused.in_transition

        if fused.in_transition and base.regime_id != "macro_frozen_range":
            base.dashboard_regime = "transition"
            base.confidence = min(base.confidence, fused.fusion_confidence)

        merged_drivers = list(dict.fromkeys(list(base.drivers) + fused.drivers))
        base.drivers = merged_drivers[:12]

    try:
        mctx = build_market_context(base.to_dict(), df=df)
        segment = mctx.get("segment_primary")
        ensemble = run_all_regime_models(
            df,
            base.to_dict(),
            segment=str(segment) if segment else None,
        )
        base.models = ensemble.get("models")
        comparison = ensemble.get("comparison") or {}

        recommendation = recommend_model(mctx, symbol=cfg.symbol, window_days=cfg.regime_rollup_window_days)
        base.model_recommendation = recommendation

        if cfg.regime_use_recommendation and base.models:
            comparison = fuse_with_leaderboard(
                comparison,
                base.models,
                recommendation,
                use_recommendation=True,
            )
        base.model_comparison = comparison

        if comparison.get("needs_human_judgment"):
            base.drivers = list(base.drivers) + ["多模型分歧较大 → 建议人工判断"]
            base.drivers = base.drivers[:14]
    except Exception as exc:
        base.drivers = list(base.drivers) + [f"多模型对比跳过: {exc}"]

    if base.models:
        try:
            from ai_trade_advisor.regime.hmm_modifier import apply_hmm_confidence_modifier

            base, hmm_meta = apply_hmm_confidence_modifier(base, base.models)
            base.hmm_modifier = hmm_meta
        except Exception as exc:
            base.drivers = list(base.drivers) + [f"HMM 修正跳过: {exc}"]

    try:
        latest = HumanJudgmentStore().latest(cfg.symbol)
        if latest:
            scores = FeedbackStore().scores_for_judgment(latest["id"])
            instant = [s for s in scores if s["score_type"] == "instant"]
            if instant:
                base.model_scores_preview = {
                    "judgment_id": latest["id"],
                    "top_model": max(instant, key=lambda x: float(x["total_score"] or 0))["model_id"],
                    "scores": {s["model_id"]: s["total_score"] for s in instant},
                }
    except Exception as exc:
        base.drivers = list(base.drivers) + [f"人工评分预览跳过: {exc}"]

    return base


def _raw_trend(close: float, d_upper: float, d_lower: float, k_upper: float, k_lower: float) -> RawTrend:
    if close > d_upper and close > k_upper:
        return "uptrend"
    if close < d_lower and close < k_lower:
        return "downtrend"
    return "range"


def _vol_bucket(vol_status: str | None, vol_ratio: float | None) -> VolBucket:
    status = (vol_status or "").lower()
    if status in ("danger", "high", "elevated", "extreme") or (vol_ratio is not None and vol_ratio >= 0.20):
        return "high_vol"
    if status in ("breakout", "mid", "normal") or (vol_ratio is not None and vol_ratio >= 0.06):
        return "mid_vol"
    return "low_vol"


def _compose_regime(
    raw_trend: RawTrend,
    vol_bucket: VolBucket,
    spot_cvd_breakout: bool,
    cvd_bullish_divergence: bool,
    drivers: list[str],
    cvd: dict[str, Any],
) -> str:
    if raw_trend == "uptrend":
        if vol_bucket == "high_vol":
            if spot_cvd_breakout:
                drivers.append("高波上涨 + 现货 CVD 创新高 → 真实买盘")
                return "high_vol_uptrend"
            drivers.append("高波上涨但现货 CVD 未确认 → 假突破/洗盘")
            return "fake_breakout_wash"
        if vol_bucket == "mid_vol":
            drivers.append("中波上行趋势")
            return "mid_vol_uptrend"
        drivers.append("低波上行趋势")
        return "low_vol_uptrend"

    if raw_trend == "downtrend":
        if cvd_bullish_divergence and vol_bucket in ("high_vol", "mid_vol"):
            note = "价格新低但 5m CVD 底背离"
            if cvd.get("spot_premium_positive"):
                note += " + 现货正溢价"
            drivers.append(note + " → 自愈区间")
            return "high_vol_self_heal_range"
        if vol_bucket == "high_vol":
            drivers.append("高波下跌，无 CVD 背离支撑")
            return "high_vol_downtrend"
        return "low_vol_downtrend"

    regime = f"{vol_bucket}_range"
    drivers.append(f"区间结构，维持 {vol_bucket} 震荡")
    return regime


def _map_dashboard_regime(regime_id: str) -> str:
    mapping = {
        "macro_frozen_range": "range",
        "high_vol_uptrend": "trend_up",
        "fake_breakout_wash": "transition",
        "high_vol_downtrend": "trend_down",
        "high_vol_self_heal_range": "range",
        "low_vol_uptrend": "trend_up",
        "mid_vol_uptrend": "trend_up",
        "low_vol_downtrend": "trend_down",
        "low_vol_range": "range",
        "mid_vol_range": "range",
        "high_vol_range": "high_vol",
    }
    return mapping.get(regime_id, "transition")


def _confidence(
    regime_id: str,
    raw_trend: RawTrend,
    cvd: dict[str, Any],
    deriv: dict[str, Any] | None = None,
) -> float:
    base = {
        "macro_frozen_range": 0.90,
        "high_vol_uptrend": 0.82,
        "fake_breakout_wash": 0.72,
        "high_vol_downtrend": 0.78,
        "high_vol_self_heal_range": 0.70,
        "low_vol_uptrend": 0.75,
        "mid_vol_uptrend": 0.73,
        "low_vol_downtrend": 0.75,
        "low_vol_range": 0.68,
        "mid_vol_range": 0.62,
        "high_vol_range": 0.65,
    }.get(regime_id, 0.60)
    if cvd.get("spot_cvd_breakout") and raw_trend == "uptrend":
        base = min(0.92, base + 0.05)
    if deriv:
        bull = int(deriv.get("derivative_votes_bull") or 0)
        bear = int(deriv.get("derivative_votes_bear") or 0)
        if raw_trend == "uptrend" and bull >= 2:
            base = min(0.94, base + 0.04)
        elif raw_trend == "downtrend" and bear >= 2:
            base = min(0.94, base + 0.04)
        elif raw_trend == "range" and bull >= 2 and bear >= 2:
            base = max(0.55, base - 0.05)
    return base


def _finalize(
    regime_id: str,
    raw_trend: RawTrend,
    vol_bucket: VolBucket,
    close: float,
    d_upper: float,
    d_lower: float,
    kama: float,
    k_upper: float,
    k_lower: float,
    cvd: dict[str, Any],
    macro_hazard: bool,
    confidence: float,
    drivers: list[str],
    *,
    dashboard: str,
    tech_trend: RawTrend = "range",
    deriv: dict[str, Any] | None = None,
) -> BtcRegimeAnalysis:
    deriv = deriv or {}
    return BtcRegimeAnalysis(
        regime_id=regime_id,
        regime_label=_REGIME_LABELS.get(regime_id, regime_id),
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        close=close,
        donchian_upper=d_upper,
        donchian_lower=d_lower,
        kama=kama,
        kama_upper=k_upper,
        kama_lower=k_lower,
        spot_cvd=cvd.get("spot_cvd"),
        spot_cvd_breakout=bool(cvd.get("spot_cvd_breakout")),
        cvd_bullish_divergence=bool(cvd.get("cvd_bullish_divergence")),
        spot_premium_bps=cvd.get("spot_premium_bps"),
        spot_premium_positive=bool(cvd.get("spot_premium_positive")),
        macro_hazard=macro_hazard,
        confidence=confidence,
        tech_trend=tech_trend,
        funding_rate=deriv.get("funding_rate"),
        funding_bias=str(deriv.get("funding_bias") or "neutral"),
        open_interest=deriv.get("open_interest"),
        oi_change_pct=deriv.get("oi_change_pct"),
        oi_price_sync=str(deriv.get("oi_price_sync") or "neutral"),
        cvd_trend=str(deriv.get("cvd_trend") or cvd.get("cvd_trend") or "neutral"),
        derivatives_trend=deriv or None,
        drivers=drivers[:10],
        dashboard_regime=dashboard,
    )


def _empty_derivatives(cvd: dict[str, Any] | None = None) -> dict[str, Any]:
    cvd = cvd or {}
    trend = str(cvd.get("cvd_trend") or "neutral")
    bull = 1 if trend == "bullish" else 0
    bear = 1 if trend == "bearish" else 0
    return {
        "funding_rate": None,
        "funding_bias": "neutral",
        "open_interest": None,
        "oi_change_pct": None,
        "oi_price_sync": "neutral",
        "oi_bias": "neutral",
        "cvd_trend": trend,
        "cvd_slope": cvd.get("cvd_slope"),
        "derivative_votes_bull": bull,
        "derivative_votes_bear": bear,
        "drivers": [],
        "source": "skipped",
    }


def flow_regime_from_capital(flows: CapitalFlowsSnapshot | None) -> str | None:
    if flows is None or flows.btc_exchange_wallet is None:
        return None
    net = flows.btc_exchange_wallet.net_to_exchange_1d
    if net is None:
        return "BTC 资金流数据不足"
    if net > 0:
        return "BTC 链上净流入交易所"
    if net < 0:
        return "BTC 链上净流出交易所"
    return "BTC 资金流均衡"
