import 'package:flutter/material.dart';

import '../../models/dashboard_data.dart';
import '../../regime/regime_history.dart';
import '../../widgets/commander_banner.dart';
import '../../widgets/regime_matrix_panel.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../widgets/advice_card.dart';
import '../../widgets/common.dart';
import '../../regime/regime_panel.dart';
import '../../regime/regime_history_panel.dart';
import '../../regime/quant_state_panel.dart';
import '../../layers/l1_ingestion_tab.dart';
import '../../layers/l2_inference_tab.dart';
import '../../layers/l3_confirmation_tab.dart';
import '../../layers/l4_execution_tab.dart';
import '../../bigevent/event_merger.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

/// Regime 状态：判断 + 确认 + 行动 + 引擎详情折叠。
class RegimeStatusTab extends StatefulWidget {
  const RegimeStatusTab({
    super.key,
    required this.data,
    this.regimeHistory,
    this.unifiedEvents = const [],
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.api,
  });

  final DashboardData data;
  final RegimeHistoryData? regimeHistory;
  final List<UnifiedEventItem> unifiedEvents;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final ApiService? api;

  @override
  State<RegimeStatusTab> createState() => _RegimeStatusTabState();
}

class _RegimeStatusTabState extends State<RegimeStatusTab> {
  bool _engineExpanded = false;

  @override
  Widget build(BuildContext context) {
    final l3 = widget.data.regimeConfirmation ??
        widget.data.pipeline?['layers']?['confirmation'] as Map<String, dynamic>?;
    final combined = l3?['combined'] as Map<String, dynamic>?;
    final liveId = combined?['live_regime_id']?.toString();
    final confirmedId = combined?['confirmed_regime_id']?.toString();
    final locked = liveId != null && confirmedId != null && liveId != confirmedId;

    return RadarPageShell(
      onRefresh: widget.onRefresh,
      errors: widget.errors,
      isRefreshing: widget.isRefreshing,
      header: PriceHeader(data: widget.data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          CommanderBanner(data: widget.data),
          if (locked) ...[
            const SizedBox(height: 8),
            const StatusBadge(label: '防抖锁定: live ≠ confirmed', color: AppTheme.accent),
          ],
          const SizedBox(height: 16),
          RegimeMatrixPanel(data: widget.data),
          const SizedBox(height: 16),
          RegimePanel(regime: widget.data.board.regime),
          const SizedBox(height: 16),
          RegimeHistoryPanel(
            data: widget.regimeHistory ??
                RegimeHistoryData(symbol: widget.data.symbol, history: []),
          ),
          const SizedBox(height: 16),
          _SectionHeader(title: '信号确认', icon: Icons.filter_alt_outlined),
          const SizedBox(height: 8),
          L3ConfirmationTab(
            data: widget.data,
            unifiedEvents: widget.unifiedEvents,
            errors: const [],
            onRefresh: widget.onRefresh,
            isRefreshing: widget.isRefreshing,
            embedded: true,
          ),
          const SizedBox(height: 16),
          _SectionHeader(title: '行动与路由', icon: Icons.route_outlined),
          const SizedBox(height: 8),
          if (widget.data.quantState != null) ...[
            QuantStatePanel(quantState: widget.data.quantState!),
            const SizedBox(height: 16),
          ],
          L4ExecutionTab(
            data: widget.data,
            errors: const [],
            onRefresh: widget.onRefresh,
            isRefreshing: widget.isRefreshing,
            embedded: true,
          ),
          const SizedBox(height: 16),
          AdviceCard(advice: widget.data.advice),
          const SizedBox(height: 16),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text(
              '引擎详情 (L1–L4)',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            initiallyExpanded: _engineExpanded,
            onExpansionChanged: (v) => setState(() => _engineExpanded = v),
            children: [
              L1IngestionTab(
                data: widget.data,
                errors: const [],
                onRefresh: widget.onRefresh,
                embedded: true,
              ),
              const SizedBox(height: 16),
              L2InferenceTab(
                data: widget.data,
                regimeHistory: widget.regimeHistory,
                unifiedEvents: widget.unifiedEvents,
                errors: const [],
                onRefresh: widget.onRefresh,
                api: widget.api,
                embedded: true,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.icon});

  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppTheme.accent),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
        ),
      ],
    );
  }
}
