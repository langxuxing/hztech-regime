import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../widgets/advice_card.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import '../widgets/common.dart';
import '../signal/market_signals_panel.dart';
import '../bigevent/event_merger.dart';
import '../theme/app_theme.dart';

/// L3 信号防抖与合规清洗层界面。
class L3ConfirmationTab extends StatelessWidget {
  const L3ConfirmationTab({
    super.key,
    required this.data,
    this.unifiedEvents = const [],
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.embedded = false,
  });

  final DashboardData data;
  final List<UnifiedEventItem> unifiedEvents;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final bool embedded;

  @override
  Widget build(BuildContext context) {
    final l3 = data.regimeConfirmation ?? data.pipeline?['layers']?['confirmation'] as Map<String, dynamic>?;
    final combined = l3?['combined'] as Map<String, dynamic>?;
    final debouncer = l3?['debouncer'] as Map<String, dynamic>?;
    final notes = (l3?['notes'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
          SectionCard(
            title: 'df_confirmed 状态隔离',
            icon: Icons.lock_clock_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (combined != null) ...[
                  _row('实时 Regime', combined['live_regime_id']?.toString() ?? '—'),
                  _row('已确认 Regime', combined['confirmed_regime_id']?.toString() ?? '—'),
                  _row('输出标签', combined['regime_label']?.toString() ?? '—'),
                  if (combined['live_regime_id'] != combined['confirmed_regime_id'])
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: StatusBadge(label: '防抖锁定中', color: AppTheme.accent),
                    ),
                ] else
                  Text(
                    data.btcRegime?['regime_label']?.toString() ?? data.board.regime.label,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '转置矩阵惩罚 / 驻留',
            icon: Icons.shield_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (l3 != null) ...[
                  _row('转置惩罚', l3['transition_penalty_applied'] == true ? '已施加' : '未施加'),
                  _row('驻留 bars', '${l3['dwell_bars']} / ${l3['min_dwell_bars']}'),
                  _row('状态切换', l3['regime_switched'] == true ? '本次已切换' : '维持'),
                ],
                ...notes.map(
                  (n) => Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('• $n', style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Advice 信号防抖',
            icon: Icons.timer_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (debouncer != null) ...[
                  _row('冷却锁定', debouncer['cooldown_active'] == true ? '是' : '否'),
                  _row('剩余秒', '${debouncer['cooldown_remaining_sec'] ?? 0}'),
                  _row('锁定方向', debouncer['locked_bias']?.toString() ?? '—'),
                ] else
                  const Text('无防抖状态', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
              ],
            ),
          ),
          if (!embedded) ...[
            const SizedBox(height: 16),
            MarketSignalsPanel(data: data, unifiedEvents: unifiedEvents),
            const SizedBox(height: 16),
            AdviceCard(advice: data.advice),
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
            width: 88,
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
