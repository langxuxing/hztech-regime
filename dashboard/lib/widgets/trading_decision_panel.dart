import 'package:flutter/material.dart';

import '../models/chart_data.dart';
import '../models/dashboard_data.dart';
import 'ohlcv_chart_panel.dart';
import 'liquidity_gex_ladder_panel.dart';
import 'derivatives_flow_strip.dart';
import 'ai_trading_brief_panel.dart';
import '../signal/smc_panel.dart';
import '../signal/market_panels.dart';

/// 交易决策综合面板：K线 + 流动性GEX + 订单簿 + SMC + 衍生品 + AI。
class TradingDecisionPanel extends StatelessWidget {
  const TradingDecisionPanel({
    super.key,
    required this.data,
    this.wide = false,
  });

  final DashboardData data;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final chartJson = data.chart;
    final chart = chartJson != null ? ChartPayload.fromJson(chartJson) : null;
    final brief = data.tradingBrief;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (chart != null) OhlcvChartPanel(chart: chart),
        if (chart != null) const SizedBox(height: 16),
        if (wide)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: LiquidityGexLadderPanel(data: data)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  children: [
                    if (data.orderbook != null) OrderbookPanel(orderbook: data.orderbook!),
                    const SizedBox(height: 16),
                    SmcPanel(smc: data.smc, lastPrice: data.lastPrice),
                  ],
                ),
              ),
            ],
          )
        else ...[
          LiquidityGexLadderPanel(data: data),
          const SizedBox(height: 16),
          if (data.orderbook != null) ...[
            OrderbookPanel(orderbook: data.orderbook!),
            const SizedBox(height: 16),
          ],
          SmcPanel(smc: data.smc, lastPrice: data.lastPrice),
        ],
        const SizedBox(height: 16),
        DerivativesFlowStrip(data: data, brief: brief),
        const SizedBox(height: 16),
        AiTradingBriefPanel(data: data, brief: brief),
      ],
    );
  }
}
