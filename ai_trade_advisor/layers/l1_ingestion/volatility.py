"""L1 前瞻波动率与历史实现波动率。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult, build_deribit_gex
from ai_trade_advisor.features.gex_proxy import build_gex_proxy
from ai_trade_advisor.models import GexLevel


def _try_vol_ratio(df: pd.DataFrame) -> tuple[float | None, str | None]:
    repo = Path("/Volumes/HZTech/CreativeIdeaLab/Fishinglive")
    if not repo.exists():
        return None, None
    if str(repo.parent) not in sys.path:
        sys.path.insert(0, str(repo.parent))
    try:
        from Fishinglive.Volatilityratio30m import volratio_30m_from_1mbars, volatility_ratio_state
    except ImportError:
        return None, None
    bars = [
        {
            "timestamp": int(r.timestamp),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(getattr(r, "volume", 0) or 0),
        }
        for r in df.itertuples(index=False)
    ]
    vr = volratio_30m_from_1mbars(bars, bar_minutes=30)
    last = float(vr[-1]) if len(vr) else np.nan
    if not np.isfinite(last):
        return None, None
    return last, volatility_ratio_state(last)


def _gk_volatility(df: pd.DataFrame, window: int = 24) -> float | None:
    """Garman-Klass 历史实现波动率代理。"""
    if len(df) < window + 1:
        return None
    sub = df.tail(window)[["open", "high", "low", "close"]].astype(float)
    log_hl = np.log(sub["high"] / sub["low"].clip(lower=1e-12))
    log_co = np.log(sub["close"] / sub["open"].clip(lower=1e-12))
    gk = 0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2
    return round(float(np.sqrt(gk.mean()) * np.sqrt(365 * 24)), 6)


def build_volatility_features(
    cfg: AdvisorConfig,
    df: pd.DataFrame,
    *,
    price: float,
    use_deribit: bool = True,
) -> tuple[dict[str, Any], GexEngineResult | None, list[GexLevel]]:
    """DVOL（Deribit GEX 引擎代理）+ GK 实现波动率。"""
    proxy_gex = build_gex_proxy(cfg, df)
    gex_engine = None
    gex_levels = proxy_gex

    if use_deribit and cfg.use_deribit_gex:
        asset = cfg.symbol.split("/")[0].upper()
        gex_engine = build_deribit_gex(
            currency=asset if asset in ("BTC", "ETH") else "BTC",
            spot_price=price,
            fallback_levels=proxy_gex,
        )
        gex_levels = gex_engine.levels or proxy_gex

    vr, vr_status = _try_vol_ratio(df)
    gk = _gk_volatility(df)

    dvol_lead = None
    if vr is not None and gk is not None:
        dvol_lead = vr > 0.15 and vr > gk * 1.1

    return {
        "vol_ratio": vr,
        "vol_status": vr_status,
        "gk_realized_vol": gk,
        "dvol_proxy": vr,
        "dvol_leads_gk": dvol_lead,
        "gex_levels_count": len(gex_levels),
    }, gex_engine, gex_levels
