from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from ai_trade_advisor.datasource.http_client import get_json
from ai_trade_advisor.models import GexLevel

DERIBIT_API = "https://www.deribit.com/api/v2/public"

# 深虚值过滤：距现价 ±30% 且日内成交量为 0
OTM_DISTANCE_PCT = 30.0
# Volume/OI 短时暴增阈值（相对上一快照）
VOL_OI_SPIKE_RATIO = 2.5
VOL_OI_MIN_OI = 50.0

# instrument_name 形如 BTC-31JUL26-69000-C
_INSTRUMENT_STRIKE = re.compile(r"-(\d+(?:\.\d+)?)-[CP]$")


def _parse_strike(instrument_name: str) -> float:
    m = _INSTRUMENT_STRIKE.search(instrument_name.strip().upper())
    if not m:
        return 0.0
    return float(m.group(1))


@dataclass
class GexEngineResult:
    levels: list[GexLevel]
    spot_price: float
    filtered_contracts: int
    alerts: list[str] = field(default_factory=list)
    gamma_wall_call: float | None = None
    gamma_wall_put: float | None = None
    source: str = "deribit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "spot_price": self.spot_price,
            "filtered_contracts": self.filtered_contracts,
            "alerts": self.alerts,
            "gamma_wall_call": self.gamma_wall_call,
            "gamma_wall_put": self.gamma_wall_put,
            "source": self.source,
            "levels": [
                {
                    "price": lv.price,
                    "gex_notional_proxy": lv.gex_notional_proxy,
                    "level_type": lv.level_type,
                    "source": lv.source,
                }
                for lv in self.levels
            ],
        }


_prev_vol_oi: dict[tuple[float, str], float] = {}


def build_deribit_gex(
    currency: str = "BTC",
    *,
    spot_price: float | None = None,
    fallback_levels: list[GexLevel] | None = None,
) -> GexEngineResult:
    """
    Deribit 期权 GEX 清洗引擎：
    1. 过滤 ±30% 外且 volume=0 的深虚值合约，避免 IV 断更导致 Gamma 假跳
    2. 监控 Volume/OI，检测做市商头寸翻转（墙体由阻力变突破口）
    """
    try:
        spot = spot_price or _fetch_spot(currency)
        summaries = _fetch_option_summaries(currency)
    except Exception:
        levels = fallback_levels or []
        return GexEngineResult(
            levels=levels,
            spot_price=spot_price or 0.0,
            filtered_contracts=0,
            alerts=["Deribit GEX 不可用，已回退至 OI 代理层"],
            source="fallback",
        )

    filtered = 0
    strike_gex: dict[float, float] = {}
    alerts: list[str] = []
    global _prev_vol_oi

    for row in summaries:
        instrument = str(row.get("instrument_name") or "")
        strike = float(row.get("strike") or 0) or _parse_strike(instrument)
        oi = float(row.get("open_interest") or 0)
        vol = float(row.get("volume") or 0)
        underlying = float(row.get("underlying_price") or spot)

        if strike <= 0 or oi <= 0:
            continue

        dist_pct = abs(strike - underlying) / underlying * 100
        if dist_pct > OTM_DISTANCE_PCT and vol <= 0:
            filtered += 1
            continue

        is_call = instrument.endswith("-C") or "-C" in instrument.split("-")[-1]
        # Gamma 代理：OI × 距现价衰减 × 方向（Call 上方为正 Gamma 暴露）
        decay = max(0.15, 1.0 - dist_pct / 100)
        sign = 1.0 if is_call else -1.0
        gex_proxy = oi * decay * sign * underlying * 0.01
        strike_gex[strike] = strike_gex.get(strike, 0.0) + gex_proxy

        if oi >= VOL_OI_MIN_OI:
            vol_oi = vol / oi if oi else 0.0
            opt = "C" if is_call else "P"
            key = (strike, opt)
            prev = _prev_vol_oi.get(key, 0.0)
            if prev > 0 and vol_oi >= prev * VOL_OI_SPIKE_RATIO and vol_oi >= 0.15:
                side = "Call" if is_call else "Put"
                alerts.append(
                    f"行权价 {strike:.0f} {side} Volume/OI 暴增至 {vol_oi:.2f}（前 {prev:.2f}）；"
                    "做市商可能由卖方转为买方，墙体可能由阻力变为突破口"
                )
            _prev_vol_oi[key] = vol_oi

    levels = _strikes_to_levels(strike_gex, spot)
    call_wall = _top_strike(strike_gex, spot, above=True)
    put_wall = _top_strike(strike_gex, spot, above=False)

    if not levels and fallback_levels:
        return GexEngineResult(
            levels=fallback_levels,
            spot_price=spot,
            filtered_contracts=filtered,
            alerts=alerts or ["Deribit 有效 GEX 为空，已回退至 OI 代理层"],
            gamma_wall_call=call_wall,
            gamma_wall_put=put_wall,
            source="fallback",
        )

    return GexEngineResult(
        levels=levels[:10],
        spot_price=spot,
        filtered_contracts=filtered,
        alerts=alerts[:5],
        gamma_wall_call=call_wall,
        gamma_wall_put=put_wall,
    )


def _fetch_spot(currency: str) -> float:
    data = get_json(
        f"{DERIBIT_API}/get_index_price",
        params={"index_name": f"{currency.lower()}_usd"},
    )
    return float(data["result"]["index_price"])


def _fetch_option_summaries(currency: str) -> list[dict[str, Any]]:
    data = get_json(
        f"{DERIBIT_API}/get_book_summary_by_currency",
        params={"currency": currency, "kind": "option"},
    )
    rows = data.get("result") or []
    return [r for r in rows if isinstance(r, dict)]


def _strikes_to_levels(strike_gex: dict[float, float], spot: float) -> list[GexLevel]:
    out: list[GexLevel] = []
    for strike, gex in sorted(strike_gex.items(), key=lambda x: abs(x[1]), reverse=True)[:10]:
        if abs(gex) < 1e-6:
            continue
        if strike > spot * 1.002:
            level_type = "resistance" if gex > 0 else "magnet"
        elif strike < spot * 0.998:
            level_type = "support" if gex < 0 else "magnet"
        else:
            level_type = "magnet"
        out.append(
            GexLevel(
                price=strike,
                gex_notional_proxy=abs(gex),
                level_type=level_type,  # type: ignore[arg-type]
                source="deribit_gex",
            )
        )
    out.sort(key=lambda x: x.gex_notional_proxy, reverse=True)
    return out


def _top_strike(strike_gex: dict[float, float], spot: float, *, above: bool) -> float | None:
    candidates = {
        k: abs(v)
        for k, v in strike_gex.items()
        if (k >= spot if above else k <= spot)
    }
    if not candidates:
        return None
    return max(candidates, key=candidates.get)
