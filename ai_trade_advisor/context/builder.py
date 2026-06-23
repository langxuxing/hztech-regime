from __future__ import annotations

from ai_trade_advisor.models import (
    CapitalFlowsSnapshot,
    ExchangeWalletFlow,
    GexLevel,
    LiquidityLevel,
    MarketContext,
    MarketFundFlow,
    OnChainTransferFlow,
    OrderBookSnapshot,
    SmcSnapshot,
)


def build_structured_context(ctx: MarketContext) -> str:
    """将多维特征转为 LLM 可读的结构化文本（PDF 推荐方案）。"""
    lines = [
        "# 市场上下文（结构化特征，非图像）",
        f"交易对: {ctx.symbol} @ {ctx.exchange}",
        f"周期: {ctx.timeframe} | 截至: {ctx.as_of}",
        f"最新价: {ctx.last_price}",
        "",
        "## 30m K 线摘要",
        _fmt_dict(ctx.ohlcv_summary),
    ]
    if ctx.vol_ratio is not None:
        lines.extend(
            [
                "",
                "## 波动率状态（30m/7d VR）",
                f"vol_ratio: {ctx.vol_ratio:.4f} | 状态: {ctx.vol_status or 'N/A'}",
            ]
        )
    lines.extend(["", "## SMC / ICT 结构", _fmt_smc(ctx.smc, ctx.last_price)])
    lines.extend(["", "## 流动性清洗地图", _fmt_liquidity(ctx.liquidity_levels, ctx.last_price)])
    lines.extend(["", "## GEX 代理层（OI + 成交量节点）", _fmt_gex(ctx.gex_levels, ctx.last_price)])
    if ctx.orderbook:
        obi_note = ""
        if ctx.obi_smoothed is not None:
            obi_note = f" | OBI EMA={ctx.obi_smoothed:+.4f}"
        lines.extend(["", "## 订单簿", _fmt_orderbook(ctx.orderbook) + obi_note])
    if ctx.capital_flows:
        lines.extend(["", "## BTC/ETH 资金流入流出 & 链上转账", _fmt_capital_flows(ctx.capital_flows)])
    if ctx.btc_regime:
        lines.extend(["", "## BTC Regime 多维度判定（KAMA+唐奇安+CVD）", _fmt_btc_regime(ctx.btc_regime)])
    if ctx.quant_state:
        lines.extend(["", "## 量化状态机（三因子得分 + 系统路由）", _fmt_quant_state(ctx.quant_state)])
    if ctx.feature_snapshot:
        lines.extend(["", "## 特征快照（原子锁定 + 相对距离）", _fmt_feature_snapshot(ctx.feature_snapshot)])
    if ctx.macro_hazard_flag:
        lines.extend(["", "## 宏观熔断", "- macro_hazard_flag=True：强制观望，勿给出激进方向性建议"])
    lines.extend(
        [
            "",
            "## 任务",
            "基于以上结构化数据，给出**短期（1–4 小时）**交易建议。",
            "必须输出 JSON，字段: bias(long|short|neutral), confidence(0-1),",
            "entry_zone [low,high], stop_loss, take_profit [..], time_horizon(如 1h-4h),",
            "reasoning(含 SMC/流动性/GEX/订单簿/CVD/OI/ETF 如何共振), risks [], confluence_score(0-1)。",
            "不要臆造未提供的数据；若信号冲突，降低 confidence 并说明。",
        ]
    )
    return "\n".join(lines)


def _fmt_dict(d: dict) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in d.items())


def _fmt_smc(smc: SmcSnapshot, price: float) -> str:
    lines = [f"- 趋势: {smc.trend}"]
    if smc.mss_or_choch:
        lines.append(f"- MSS/CHoCH: {smc.mss_or_choch} (dir={smc.mss_direction})")
    for note in smc.structure_notes:
        lines.append(f"- {note}")
    if smc.nearest_ob:
        z = smc.nearest_ob
        lines.append(f"- 最近 OB: [{z.low:.6g}, {z.high:.6g}] 距离 {z.width_pct(price):.2f}%")
    if smc.nearest_fvg:
        z = smc.nearest_fvg
        lines.append(f"- 最近 FVG: [{z.low:.6g}, {z.high:.6g}] 距离 {z.width_pct(price):.2f}%")
    if smc.unfilled_fvgs:
        lines.append(f"- 未回补 FVG 数量: {len(smc.unfilled_fvgs)}")
    if smc.active_obs:
        lines.append(f"- 活跃 OB 数量: {len(smc.active_obs)}")
    return "\n".join(lines)


def _fmt_liquidity(levels: list[LiquidityLevel], price: float) -> str:
    if not levels:
        return "- 无显著流动性位"
    lines = []
    for lv in levels:
        dist = (lv.price - price) / price * 100
        status = "已清洗" if lv.swept else "待清洗"
        lines.append(
            f"- {lv.side} @ {lv.price:.6g} ({status}) 距现价 {dist:+.2f}% strength={lv.strength:.2f}"
        )
    return "\n".join(lines)


def _fmt_gex(levels: list[GexLevel], price: float) -> str:
    if not levels:
        return "- GEX 代理数据不可用（可检查 OI API）"
    lines = []
    for lv in levels:
        dist = (lv.price - price) / price * 100
        lines.append(
            f"- {lv.level_type} @ {lv.price:.6g} proxy={lv.gex_notional_proxy:.0f} "
            f"({lv.source}) 距现价 {dist:+.2f}%"
        )
    return "\n".join(lines)


def _fmt_orderbook(ob: OrderBookSnapshot) -> str:
    lines = [
        f"- 最优买/卖: {ob.best_bid} / {ob.best_ask}",
        f"- 价差: {ob.spread_bps} bps",
        f"- 深度(USDT): bid={ob.bid_depth_usdt} ask={ob.ask_depth_usdt}",
        f"- 失衡 imbalance: {ob.imbalance:+.4f} (>0 买盘厚)",
    ]
    for w in ob.walls[:4]:
        lines.append(
            f"- 墙 {w['side']} @ {w['price']} notional={w['notional_usdt']} "
            f"dist={w['distance_bps']}bps"
        )
    return "\n".join(lines)


def _fmt_feature_snapshot(snap: dict) -> str:
    lines = [f"- locked_at: {snap.get('locked_at')}"]
    rel = snap.get("relative") or {}
    for key in (
        "dist_to_call_wall_pct",
        "dist_to_put_wall_pct",
        "dist_to_pain_liq_pct",
        "nearest_ob_dist_pct",
        "nearest_resistance_pct",
        "nearest_support_pct",
    ):
        if rel.get(key) is not None:
            lines.append(f"- {key}: {rel[key]:+.3f}%")
    for alert in snap.get("alerts") or []:
        lines.append(f"- ⚠ {alert}")
    liq = snap.get("liquidation") or {}
    if liq.get("cells"):
        lines.append(f"- 强平池半衰期 {liq.get('half_life_hours')}h，总权重 {liq.get('total_weight')}")
    deb = snap.get("debouncer") or {}
    if deb.get("obi"):
        obi = deb["obi"]
        lines.append(f"- OBI EMA: raw={obi.get('raw')} smoothed={obi.get('smoothed')}")
    return "\n".join(lines) if len(lines) > 1 else "- 快照为空"


def _fmt_capital_flows(cf: CapitalFlowsSnapshot) -> str:
    lines = [f"- 数据质量: {cf.data_quality}"]
    for note in cf.notes:
        lines.append(f"- {note}")

    for asset, market_flows, wallet, onchain in (
        ("BTC", cf.btc_market_flows, cf.btc_exchange_wallet, cf.btc_onchain),
        ("ETH", cf.eth_market_flows, cf.eth_exchange_wallet, cf.eth_onchain),
    ):
        lines.append(f"\n### {asset}")
        if market_flows:
            for mf in market_flows:
                lines.append(_fmt_market_flow(mf))
        else:
            lines.append("- 市场 netflow: 无（需 COINGLASS_API_KEY Startup+）")
        if wallet:
            lines.append(_fmt_exchange_wallet(wallet))
        else:
            lines.append("- 交易所链上净流入: 无（需 COINGLASS_API_KEY Hobbyist+）")
        if onchain:
            lines.append(_fmt_onchain(onchain))
    return "\n".join(lines)


def _fmt_market_flow(mf: MarketFundFlow) -> str:
    parts = [f"- {mf.market} 市场资金 ({mf.source}):"]
    for p in mf.periods:
        net = p.netflow_usd
        net_s = f"{net:+,.0f}" if net is not None else "N/A"
        in_s = f"{p.inflow_usd:,.0f}" if p.inflow_usd is not None else "N/A"
        out_s = f"{p.outflow_usd:,.0f}" if p.outflow_usd is not None else "N/A"
        chg = f" ({p.change_pct:+.1f}%)" if p.change_pct is not None else ""
        parts.append(f"  · {p.period}: 流入 {in_s} / 流出 {out_s} / 净 {net_s} USD{chg}")
    return "\n".join(parts)


def _fmt_exchange_wallet(w: ExchangeWalletFlow) -> str:
    def _fmt(v: float | None, suffix: str) -> str:
        return f"{v:+,.4f}" if v is not None else "N/A"

    lines = [
        f"- 链上→交易所钱包净变化 ({w.source}):",
        f"  · 1d: {_fmt(w.net_to_exchange_1d, w.asset)} {w.asset} (>0 净流入交易所，潜在卖压)",
        f"  · 7d: {_fmt(w.net_to_exchange_7d, w.asset)} {w.asset}",
        f"  · 30d: {_fmt(w.net_to_exchange_30d, w.asset)} {w.asset}",
    ]
    for ex in w.top_exchanges[:3]:
        lines.append(
            f"  · {ex.get('exchange')}: 1d {ex.get('change_1d')} ({ex.get('change_pct_1d')}%)"
        )
    return "\n".join(lines)


def _fmt_onchain(o: OnChainTransferFlow) -> str:
    lines = [f"- 链上转账 ({o.source}):"]
    if o.chain_volume_24h_usd is not None:
        lines.append(f"  · 24h 链上成交额约 ${o.chain_volume_24h_usd:,.0f}")
    if o.transactions_24h is not None:
        lines.append(f"  · 24h 交易笔数: {o.transactions_24h:,}")
    if o.volume_change_7d_pct is not None:
        lines.append(f"  · 链上成交额 7d 变化: {o.volume_change_7d_pct:+.1f}%")
    if o.volume_change_30d_pct is not None:
        lines.append(f"  · 链上成交额 30d 变化: {o.volume_change_30d_pct:+.1f}%")
    if o.tx_change_7d_pct is not None:
        lines.append(f"  · 链上交易笔数 7d 变化: {o.tx_change_7d_pct:+.1f}%")
    if o.largest_tx_24h_usd is not None:
        lines.append(f"  · 24h 最大单笔: ${o.largest_tx_24h_usd:,.0f}")
    if o.extra.get("erc20_transactions_24h"):
        lines.append(f"  · ERC20 24h 交易: {o.extra['erc20_transactions_24h']:,}")
    lines.append(f"  · 解读: {o.interpretation}")
    return "\n".join(lines)


def _fmt_btc_regime(r: dict) -> str:
    lines = [
        f"- Regime: {r.get('regime_id')} ({r.get('regime_label')})",
        f"- 置信度: {r.get('confidence')}",
        f"- 技术趋势: {r.get('tech_trend')} → 融合趋势: {r.get('raw_trend')} | 波动桶: {r.get('vol_bucket')}",
        f"- 收盘 {r.get('close')} vs 唐奇安 [{r.get('donchian_lower')}, {r.get('donchian_upper')}]",
        f"- KAMA {r.get('kama')} 轨道 [{r.get('kama_lower')}, {r.get('kama_upper')}]",
        f"- Funding: {r.get('funding_rate')} ({r.get('funding_bias')}) | OI Δ: {r.get('oi_change_pct')}% ({r.get('oi_price_sync')})",
        f"- CVD 趋势: {r.get('cvd_trend')} | spot={r.get('spot_cvd')} breakout={r.get('spot_cvd_breakout')}",
        f"- CVD 底背离: {r.get('cvd_bullish_divergence')} | 现货溢价 bps: {r.get('spot_premium_bps')}",
    ]
    for d in (r.get("drivers") or [])[:5]:
        lines.append(f"- {d}")
    triad = r.get("triad") or {}
    if triad:
        lines.append(f"- 三型融合: HMM={triad.get('hmm', {}).get('current_label')} "
                     f"变点={r.get('changepoint_prob')} 预测→{r.get('next_regime_label')}")
        if triad.get("summary"):
            lines.append(f"- {triad['summary']}")
    return "\n".join(lines)


def _fmt_quant_state(q: dict) -> str:
    lines = [
        f"- 得分向量: {q.get('score_label')} | 诊断: {q.get('diagnosis')}",
        f"- 事件风险: {q.get('event_risk')} ({q.get('event_risk_score')})",
    ]
    for cmd in q.get("system_commands") or []:
        lines.append(f"- 系统指令: {cmd}")
    bounds = q.get("boundaries") or {}
    if bounds.get("upper_price") or bounds.get("lower_price"):
        lines.append(
            f"- 边界: 上 {bounds.get('upper_price')} / 下 {bounds.get('lower_price')} "
            f"RANGE {bounds.get('range_pct')}%"
        )
    policy = q.get("weekly_policy") or {}
    if policy:
        lines.append(
            f"- SOP1: {policy.get('var_adjustment')} | CTA={policy.get('cta_mode')} "
            f"Grid={policy.get('grid_mode')}"
        )
    for rule in q.get("daily_sop") or []:
        lines.append(f"- SOP2 触发: {rule.get('condition')} → {rule.get('action')}")
    okx = q.get("okx_strategy") or {}
    if okx:
        lines.append(f"- OKX 策略: {okx.get('summary')}")
        grid = okx.get("grid") or {}
        if grid.get("enabled"):
            lines.append(
                f"- 网格 {grid.get('direction_label')}: "
                f"[{grid.get('lower_price')}, {grid.get('upper_price')}] "
                f"{grid.get('grid_count')}格 {grid.get('mode')} {grid.get('leverage')}x"
            )
        mart = okx.get("martingale") or {}
        if mart.get("enabled"):
            lines.append(
                f"- 马丁 {mart.get('direction_label')}: "
                f"首单 ${mart.get('initial_order_usdt')} ×{mart.get('multiplier')} "
                f"最多{mart.get('max_additions')}层"
            )
        for tool in okx.get("other_tools") or []:
            if tool.get("priority") == "primary":
                lines.append(f"- {tool.get('name')}: {tool.get('action')}")
    for d in (q.get("drivers") or [])[:4]:
        lines.append(f"- {d}")
    return "\n".join(lines)
