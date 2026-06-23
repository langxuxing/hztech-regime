import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../services/api_service.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import '../widgets/common.dart';
import '../regime/regime_panel.dart';
import '../regime/btc_regime_detail_panel.dart';
import '../regime/model_comparison_panel.dart';
import '../regime/regime_history_panel.dart';
import '../regime/regime_history.dart';
import '../bigevent/unified_events_panel.dart';
import '../bigevent/event_merger.dart';
import '../theme/app_theme.dart';

/// L2 状态识别与推理分类层界面。
class L2InferenceTab extends StatelessWidget {
  const L2InferenceTab({
    super.key,
    required this.data,
    this.regimeHistory,
    this.unifiedEvents = const [],
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.api,
    this.embedded = false,
  });

  final DashboardData data;
  final RegimeHistoryData? regimeHistory;
  final List<UnifiedEventItem> unifiedEvents;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final ApiService? api;
  final bool embedded;

  @override
  Widget build(BuildContext context) {
    final l2 = data.pipeline?['layers']?['inference_live'] as Map<String, dynamic>?;
    final l2Confirmed =
        data.pipeline?['layers']?['inference_confirmed'] as Map<String, dynamic>?;
    final corrections = (l2?['corrections'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!embedded) RegimePanel(regime: data.board.regime),
        if (l2 != null) ...[
          if (!embedded) const SizedBox(height: 16),
          SectionCard(
            title: embedded ? 'L2 推理 (live)' : '推理输出',
            icon: Icons.psychology_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _row('Regime ID', l2['regime_id']?.toString() ?? '—'),
                _row('标签', l2['regime_label']?.toString() ?? '—'),
                _row('置信度', '${((l2['confidence'] as num? ?? 0) * 100).round()}%'),
                if (l2['hard_rule_triggered'] != null)
                  _row('硬规则', l2['hard_rule_triggered'].toString()),
                if (l2['in_transition'] == true)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: StatusBadge(label: '状态转换中', color: AppTheme.accent),
                  ),
              ],
            ),
          ),
        ],
        if (l2Confirmed != null && embedded) ...[
          const SizedBox(height: 16),
          SectionCard(
            title: 'L2 推理 (confirmed)',
            icon: Icons.verified_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _row('Regime ID', l2Confirmed['regime_id']?.toString() ?? '—'),
                _row('标签', l2Confirmed['regime_label']?.toString() ?? '—'),
                _row('置信度', '${((l2Confirmed['confidence'] as num? ?? 0) * 100).round()}%'),
              ],
            ),
          ),
        ],
        if (corrections.isNotEmpty) ...[
          const SizedBox(height: 16),
          SectionCard(
            title: '慢变量纠偏 / CVD 验证',
            icon: Icons.tune_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: corrections
                  .map(
                    (c) => Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Text('• $c', style: const TextStyle(fontSize: 11)),
                    ),
                  )
                  .toList(),
            ),
          ),
        ],
        if (data.btcRegime != null) ...[
          const SizedBox(height: 16),
          BtcRegimeDetailPanel(btcRegime: data.btcRegime!),
          if (!embedded) ...[
            const SizedBox(height: 16),
            ModelComparisonPanel(
              btcRegime: data.btcRegime!,
              api: api,
              symbol: data.symbol,
            ),
          ],
        ],
        if (!embedded && unifiedEvents.isNotEmpty) ...[
          const SizedBox(height: 16),
          UnifiedEventsPanel(events: unifiedEvents),
        ],
        if (!embedded) ...[
          const SizedBox(height: 16),
          RegimeHistoryPanel(
            data: regimeHistory ?? RegimeHistoryData(symbol: data.symbol, history: []),
          ),
        ],
      ],
    );

    if (embedded) return content;
    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: content,
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(label, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
