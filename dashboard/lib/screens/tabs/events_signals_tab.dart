import 'package:flutter/material.dart';

import '../../models/dashboard_data.dart';
import '../../bigevent/event_data.dart';
import '../../bigevent/event_merger.dart';
import '../../bigevent/event_impact_summary.dart';
import '../../bigevent/events_panel.dart';
import '../../bigevent/unified_events_panel.dart';
import '../../forecast/trend_consensus.dart';
import '../../forecast/trend_consensus_panel.dart';
import '../../forecast/trend_panel.dart';
import '../../signal/market_signals_panel.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../widgets/advice_card.dart';

/// 事件与信号：日历 + 影响 + 统一事件流 + 警报 + 趋势共识。
class EventsSignalsTab extends StatelessWidget {
  const EventsSignalsTab({
    super.key,
    required this.data,
    required this.unifiedEvents,
    this.events,
    this.consensus,
    this.consensusError,
    required this.errors,
    required this.onRefresh,
    this.onDeepScan,
    this.isRefreshing = false,
  });

  final DashboardData data;
  final List<UnifiedEventItem> unifiedEvents;
  final EventAnalysisData? events;
  final TrendConsensus? consensus;
  final String? consensusError;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final VoidCallback? onDeepScan;
  final bool isRefreshing;

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
          EventImpactSummary(events: events),
          if (onDeepScan != null) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton.icon(
                onPressed: isRefreshing ? null : onDeepScan,
                icon: const Icon(Icons.radar_rounded, size: 16),
                label: const Text('深度扫描事件', style: TextStyle(fontSize: 11)),
              ),
            ),
          ],
          const SizedBox(height: 16),
          if (events != null) ...[
            EventsPanel(data: events!),
            const SizedBox(height: 16),
          ],
          UnifiedEventsPanel(
            events: unifiedEvents,
            summaryHighImpact: events?.summary.highImpactCount ?? 0,
          ),
          const SizedBox(height: 16),
          MarketSignalsPanel(data: data, unifiedEvents: unifiedEvents),
          const SizedBox(height: 16),
          TrendPanel(trend: data.board.trend),
          const SizedBox(height: 16),
          if (consensus != null)
            TrendConsensusPanel(consensus: consensus!)
          else
            _ConsensusPlaceholder(error: consensusError, onRetry: onRefresh),
          const SizedBox(height: 16),
          AdviceCard(advice: data.advice),
        ],
      ),
    );
  }
}

class _ConsensusPlaceholder extends StatelessWidget {
  const _ConsensusPlaceholder({this.error, required this.onRetry});

  final String? error;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return TrendConsensusPanel(
      consensus: TrendConsensus.fromJson({
        'as_of': DateTime.now().toUtc().toIso8601String(),
        'asset': 'BTC',
        'direction': 'sideways',
        'label': error ?? '趋势共识未加载',
        'score': 0,
        'confidence': 0,
        'agreement': 0,
        'bullish_count': 0,
        'bearish_count': 0,
        'neutral_count': 0,
        'sources_ok': 0,
        'sources_failed': 1,
        'summary': error ?? '下拉刷新重试 /api/trend-consensus',
        'signals': [],
      }),
    );
  }
}
