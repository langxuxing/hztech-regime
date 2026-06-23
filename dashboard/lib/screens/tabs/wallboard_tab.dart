import 'dart:async';

import 'package:flutter/material.dart';

import '../../bigevent/event_data.dart';
import '../../bigevent/event_merger.dart';
import '../../forecast/trend_consensus.dart';
import '../../models/dashboard_data.dart';
import '../../models/trend_judgment.dart';
import '../../models/radar_tab.dart';
import '../../regime/regime_history.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/trend_judgment_hero.dart';
import '../../widgets/commander_banner.dart';
import '../../widgets/black_swan_panel.dart';
import '../../widgets/regime_matrix_panel.dart';
import '../../widgets/radar_overview_bar.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../layers/pipeline_flow_panel.dart';
import '../../regime/model_comparison_panel.dart';

/// 大屏总览：六区聚合只读视图。
class WallboardTab extends StatefulWidget {
  const WallboardTab({
    super.key,
    required this.data,
    this.events,
    this.consensus,
    this.regimeHistory,
    required this.unifiedEvents,
    required this.errors,
    required this.onRefresh,
    required this.onNavigate,
    this.isRefreshing = false,
    this.apiHealthy = false,
    this.api,
    this.trendJudgment,
    this.readinessTier,
  });

  final DashboardData data;
  final EventAnalysisData? events;
  final TrendConsensus? consensus;
  final RegimeHistoryData? regimeHistory;
  final List<UnifiedEventItem> unifiedEvents;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final void Function(RadarTab tab) onNavigate;
  final bool isRefreshing;
  final bool apiHealthy;
  final ApiService? api;
  final TrendJudgment? trendJudgment;
  final String? readinessTier;

  @override
  State<WallboardTab> createState() => _WallboardTabState();
}

class _WallboardTabState extends State<WallboardTab> {
  Timer? _autoRefresh;

  @override
  void initState() {
    super.initState();
    _autoRefresh = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!widget.isRefreshing) widget.onRefresh();
    });
  }

  @override
  void dispose() {
    _autoRefresh?.cancel();
    super.dispose();
  }

  TrendJudgment? get _heroJudgment =>
      widget.trendJudgment ?? TrendJudgment.fromBtcRegime(widget.data.btcRegime);

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 1000;

    return RadarPageShell(
      onRefresh: widget.onRefresh,
      errors: widget.errors,
      isRefreshing: widget.isRefreshing,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              PriceHeader(data: widget.data, compact: true),
              const Spacer(),
              _HealthDot(healthy: widget.apiHealthy),
              const SizedBox(width: 8),
              Text(
                '30s 自动刷新',
                style: TextStyle(
                  fontSize: 9,
                  color: AppTheme.textSecondary.withValues(alpha: 0.8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_heroJudgment != null)
            TrendJudgmentHero(
              judgment: _heroJudgment!,
              readinessTier: widget.readinessTier,
            ),
          if (_heroJudgment != null) const SizedBox(height: 12),
          CommanderBanner(data: widget.data, events: widget.events),
          if (widget.data.tradingBrief != null) ...[
            const SizedBox(height: 12),
            _TradingBriefStrip(brief: widget.data.tradingBrief!),
          ],
          const SizedBox(height: 12),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: RegimeMatrixPanel(data: widget.data)),
                const SizedBox(width: 12),
                Expanded(
                  child: BlackSwanPanel(
                    data: widget.data,
                    events: widget.events,
                    compact: true,
                  ),
                ),
              ],
            )
          else ...[
            RegimeMatrixPanel(data: widget.data),
            const SizedBox(height: 12),
            BlackSwanPanel(
              data: widget.data,
              events: widget.events,
              compact: true,
            ),
          ],
          const SizedBox(height: 12),
          RadarOverviewBar(data: widget.data, events: widget.events),
          const SizedBox(height: 12),
          PipelineFlowPanel(
            pipeline: widget.data.pipeline,
            confirmedRegime: widget.data.regimeConfirmation?['combined']?['confirmed_regime_id']
                    ?.toString() ??
                widget.data.btcRegime?['regime_id']?.toString(),
          ),
          if (widget.consensus != null) ...[
            const SizedBox(height: 12),
            _ConsensusStrip(consensus: widget.consensus!),
          ],
          if (widget.data.btcRegime?['models'] != null) ...[
            const SizedBox(height: 12),
            ModelComparisonPanel(
              btcRegime: widget.data.btcRegime!,
              api: widget.api,
              symbol: widget.data.symbol,
              compact: true,
            ),
          ],
          const SizedBox(height: 16),
          _ModuleShortcuts(onNavigate: widget.onNavigate),
        ],
      ),
    );
  }
}

class _TradingBriefStrip extends StatelessWidget {
  const _TradingBriefStrip({required this.brief});
  final Map<String, dynamic> brief;

  @override
  Widget build(BuildContext context) {
    final bias = brief['bias']?.toString() ?? 'neutral';
    final color = switch (bias) {
      'long' => AppTheme.long,
      'short' => AppTheme.short,
      _ => AppTheme.neutral,
    };
    final conf = ((brief['confidence'] as num?) ?? 0) * 100;
    final aiMode = brief['ai_mode']?.toString() ?? 'rule_based';
    final summary = brief['ai_summary']?.toString() ?? brief['scenario_base']?.toString() ?? '';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.auto_awesome_outlined, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '短期决策 · ${bias.toUpperCase()} · ${conf.round()}% · ${aiMode == 'llm' ? 'AI' : '规则'}',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color),
                ),
                if (summary.isNotEmpty)
                  Text(
                    summary,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HealthDot extends StatelessWidget {
  const _HealthDot({required this.healthy});
  final bool healthy;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          Icons.circle,
          size: 8,
          color: healthy ? AppTheme.long : AppTheme.short,
        ),
        const SizedBox(width: 4),
        Text(
          healthy ? 'API 在线' : 'API 离线',
          style: TextStyle(
            fontSize: 9,
            color: healthy ? AppTheme.long : AppTheme.short,
          ),
        ),
      ],
    );
  }
}

class _ConsensusStrip extends StatelessWidget {
  const _ConsensusStrip({required this.consensus});
  final TrendConsensus consensus;

  @override
  Widget build(BuildContext context) {
    final color = switch (consensus.direction) {
      'up' => AppTheme.long,
      'down' => AppTheme.short,
      _ => AppTheme.neutral,
    };
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          const Icon(Icons.hub_rounded, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '趋势共识: ${consensus.label} · ${(consensus.confidence * 100).round()}%',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color),
            ),
          ),
        ],
      ),
    );
  }
}

class _ModuleShortcuts extends StatelessWidget {
  const _ModuleShortcuts({required this.onNavigate});
  final void Function(RadarTab tab) onNavigate;

  @override
  Widget build(BuildContext context) {
    final modules = RadarTab.values.where((t) => t != RadarTab.wallboard).toList();
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: modules.map((tab) {
        return ActionChip(
          avatar: Icon(tab.icon, size: 16),
          label: Text(tab.navLabel, style: const TextStyle(fontSize: 11)),
          onPressed: () => onNavigate(tab),
        );
      }).toList(),
    );
  }
}
