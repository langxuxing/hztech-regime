import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../services/api_service.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import 'model_comparison_panel.dart';
import 'regime_history.dart';
import 'regime_history_panel.dart';
import 'regime_panel.dart';
import 'btc_regime_detail_panel.dart';
import 'derivatives_trend_panel.dart';
import 'quant_state_panel.dart';

class RegimeTab extends StatelessWidget {
  const RegimeTab({
    super.key,
    required this.data,
    this.regimeHistory,
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.api,
  });

  final DashboardData data;
  final RegimeHistoryData? regimeHistory;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final ApiService? api;

  @override
  Widget build(BuildContext context) {
    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          RegimePanel(regime: data.board.regime),
          if (data.quantState != null) ...[
            const SizedBox(height: 16),
            QuantStatePanel(quantState: data.quantState!),
          ],
          if (data.btcRegime != null) ...[
            const SizedBox(height: 16),
            DerivativesTrendPanel(
              btcRegime: data.btcRegime!,
              derivatives: data.board.regime.derivatives,
            ),
            const SizedBox(height: 16),
            BtcRegimeDetailPanel(btcRegime: data.btcRegime!),
            const SizedBox(height: 16),
            ModelComparisonPanel(
              btcRegime: data.btcRegime!,
              api: api,
              symbol: data.symbol,
            ),
          ],
          const SizedBox(height: 16),
          RegimeHistoryPanel(data: regimeHistory ?? RegimeHistoryData(symbol: data.symbol, history: [])),
        ],
      ),
    );
  }
}
