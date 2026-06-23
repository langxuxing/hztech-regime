import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../widgets/advice_card.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'trend_consensus.dart';
import 'trend_consensus_panel.dart';
import 'trend_panel.dart';

class TrendTab extends StatelessWidget {
  const TrendTab({
    super.key,
    required this.data,
    this.consensus,
    required this.errors,
    required this.onRefresh,
    this.consensusError,
    this.isRefreshing = false,
  });

  final DashboardData data;
  final TrendConsensus? consensus;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final String? consensusError;
  final bool isRefreshing;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;

    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TrendPanel(trend: data.board.trend),
          const SizedBox(height: 16),
          if (consensus != null)
            TrendConsensusPanel(consensus: consensus!)
          else
            _ConsensusPlaceholder(error: consensusError, onRetry: onRefresh),
          const SizedBox(height: 16),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: AdviceCard(advice: data.advice)),
              ],
            )
          else
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
    return SectionCard(
      title: '多源趋势共识',
      icon: Icons.hub_rounded,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            error ?? '趋势共识数据未加载，下拉刷新或检查 /api/trend-consensus',
            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary, height: 1.45),
          ),
          const SizedBox(height: 10),
          OutlinedButton(
            onPressed: onRetry,
            child: const Text('重试加载', style: TextStyle(fontSize: 11)),
          ),
        ],
      ),
    );
  }
}
