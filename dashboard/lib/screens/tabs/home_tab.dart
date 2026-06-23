import 'package:flutter/material.dart';

import '../../models/dashboard_data.dart';
import '../../models/trend_judgment.dart';
import '../../bigevent/event_data.dart';
import '../../models/radar_tab.dart';
import '../../theme/app_theme.dart';
import '../../widgets/etf_flow_panel.dart';
import '../../widgets/onchain_panel.dart';
import '../../widgets/trend_judgment_hero.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_overview_bar.dart';
import '../../widgets/radar_page_shell.dart';
import '../../widgets/common.dart';
import '../../layers/pipeline_flow_panel.dart';

class HomeTab extends StatelessWidget {
  const HomeTab({
    super.key,
    required this.data,
    this.events,
    required this.errors,
    required this.onRefresh,
    required this.onNavigate,
    this.isRefreshing = false,
    this.trendJudgment,
    this.readinessTier,
  });

  final DashboardData data;
  final EventAnalysisData? events;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final void Function(RadarTab tab) onNavigate;
  final bool isRefreshing;
  final TrendJudgment? trendJudgment;
  final String? readinessTier;

  @override
  Widget build(BuildContext context) {
    final board = data.board;
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final confirmed = data.regimeConfirmation?['combined']?['confirmed_regime_id']?.toString() ??
        data.pipeline?['layers']?['confirmation']?['combined']?['confirmed_regime_id']?.toString() ??
        data.btcRegime?['regime_label']?.toString() ??
        board.regime.label;

    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PriceHeader(data: data),
          const SizedBox(height: 12),
          TrendJudgmentHero(
            judgment: trendJudgment ?? TrendJudgment.fromBtcRegime(data.btcRegime),
            readinessTier: readinessTier,
          ),
          const SizedBox(height: 12),
          RadarOverviewBar(data: data, events: events),
          const SizedBox(height: 16),
          PipelineFlowPanel(
            pipeline: data.pipeline,
            confirmedRegime: confirmed,
          ),
          const SizedBox(height: 16),
          _LayerNavGrid(onNavigate: onNavigate),
          const SizedBox(height: 16),
          SectionCard(
            title: '引擎状态摘要',
            icon: Icons.summarize_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SummaryRow(
                  label: 'L2 推理',
                  value: board.regime.label,
                  color: _regimeColor(board.regime.regime),
                ),
                _SummaryRow(
                  label: 'L3 确认',
                  value: confirmed,
                  color: AppTheme.accent,
                ),
                _SummaryRow(
                  label: 'L4 执行',
                  value: data.pipeline?['layers']?['execution']?['suspended'] == true
                      ? '已挂起'
                      : (data.quantState?['diagnosis']?.toString() ?? '—'),
                  color: data.pipeline?['layers']?['execution']?['suspended'] == true
                      ? AppTheme.short
                      : AppTheme.textSecondary,
                ),
                if (events != null)
                  _SummaryRow(
                    label: '高影响事件',
                    value: '${events!.summary.highImpactCount} 条待关注',
                    color: events!.summary.highImpactCount > 0
                        ? AppTheme.short
                        : AppTheme.textSecondary,
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: EtfFlowPanel(flows: data.capitalFlows)),
                const SizedBox(width: 16),
                Expanded(child: OnChainPanel(flows: data.capitalFlows)),
              ],
            )
          else ...[
            EtfFlowPanel(flows: data.capitalFlows),
            const SizedBox(height: 16),
            OnChainPanel(flows: data.capitalFlows),
          ],
        ],
      ),
    );
  }

  Color _regimeColor(String r) => switch (r) {
        'trend_up' => AppTheme.long,
        'trend_down' => AppTheme.short,
        _ => AppTheme.accent,
      };
}

class _LayerNavGrid extends StatelessWidget {
  const _LayerNavGrid({required this.onNavigate});

  final void Function(RadarTab tab) onNavigate;

  @override
  Widget build(BuildContext context) {
    final modules = RadarTab.values.where((t) => t != RadarTab.wallboard).toList();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: modules.map((tab) {
        return InkWell(
          onTap: () => onNavigate(tab),
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: (MediaQuery.sizeOf(context).width - 48) / 2 > 160
                ? 160
                : (MediaQuery.sizeOf(context).width - 48) / 2,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surfaceHigh,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              children: [
                Icon(tab.icon, size: 18, color: AppTheme.accent),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    tab.navLabel,
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                  ),
                ),
                const Icon(Icons.chevron_right, size: 16, color: AppTheme.textSecondary),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
            ),
          ),
        ],
      ),
    );
  }
}
