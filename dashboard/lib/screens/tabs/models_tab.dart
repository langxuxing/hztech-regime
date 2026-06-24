import 'package:flutter/material.dart';

import '../../models/trend_judgment.dart';
import '../../models/dashboard_data.dart';
import '../../regime/btc_regime_detail_panel.dart';
import '../../regime/human_judgment_quick_panel.dart';
import '../../regime/model_comparison_panel.dart';
import '../../regime/judgment_history_panel.dart';
import '../../regime/model_leaderboard_panel.dart';
import '../../services/api_service.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../widgets/regime_matrix_panel.dart';

/// 算法与模型：对比 + Triad + 人工标注 + 历史。
class ModelsTab extends StatelessWidget {
  const ModelsTab({
    super.key,
    required this.data,
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.api,
    this.trendJudgment,
  });

  final DashboardData data;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final ApiService? api;
  final TrendJudgment? trendJudgment;

  @override
  Widget build(BuildContext context) {
    final btc = data.btcRegime;
    final heroJudgment =
        trendJudgment ?? TrendJudgment.fromBtcRegime(btc);

    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (api != null) ...[
            HumanJudgmentQuickPanel(
              judgment: heroJudgment,
              api: api!,
              symbol: data.symbol,
            ),
            const SizedBox(height: 16),
          ],
          if (btc != null) ...[
            RegimeMatrixPanel(data: data),
            const SizedBox(height: 16),
            BtcRegimeDetailPanel(btcRegime: btc),
            const SizedBox(height: 16),
            ModelComparisonPanel(
              btcRegime: btc,
              api: api,
              symbol: data.symbol,
            ),
            if (api != null) ...[
              const SizedBox(height: 16),
              ModelLeaderboardPanel(
                api: api!,
                symbol: data.symbol,
                recommendation: btc['model_recommendation'] as Map<String, dynamic>?,
              ),
            ],
          ] else
            const Text(
              '模型数据仅 BTC 完整支持；请连接 API 服务。',
              style: TextStyle(fontSize: 12),
            ),
          if (api != null) ...[
            const SizedBox(height: 16),
            JudgmentHistoryPanel(api: api!, symbol: data.symbol),
          ],
        ],
      ),
    );
  }
}
