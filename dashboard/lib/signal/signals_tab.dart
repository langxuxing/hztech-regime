import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../bigevent/event_merger.dart';
import '../theme/app_theme.dart';
import '../widgets/advice_card.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import 'evidence_panel.dart';
import 'market_panels.dart';
import 'market_signals_panel.dart';
import 'smc_panel.dart';

class SignalsTab extends StatefulWidget {
  const SignalsTab({
    super.key,
    required this.data,
    this.unifiedEvents = const [],
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
  });

  final DashboardData data;
  final List<UnifiedEventItem> unifiedEvents;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;

  @override
  State<SignalsTab> createState() => _SignalsTabState();
}

class _SignalsTabState extends State<SignalsTab> with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final alertCount =
        MarketSignalsPanel.alertCount(widget.data, widget.unifiedEvents);
    final highPriority =
        MarketSignalsPanel.highPriorityCount(widget.data, widget.unifiedEvents);

    return RadarPageShell(
      onRefresh: widget.onRefresh,
      errors: widget.errors,
      isRefreshing: widget.isRefreshing,
      header: PriceHeader(data: widget.data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: AppTheme.surfaceHigh,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppTheme.border),
            ),
            child: TabBar(
              controller: _tabController,
              isScrollable: true,
              tabAlignment: TabAlignment.start,
              labelColor: AppTheme.textPrimary,
              unselectedLabelColor: AppTheme.textSecondary,
              indicatorColor: AppTheme.accent,
              indicatorSize: TabBarIndicatorSize.label,
              dividerColor: Colors.transparent,
              labelStyle: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
              unselectedLabelStyle: const TextStyle(fontSize: 12),
              tabs: [
                _SignalTab(
                  label: '提醒',
                  badge: alertCount > 0 ? alertCount : null,
                  badgeColor: highPriority > 0 ? AppTheme.short : AppTheme.accent,
                ),
                const Tab(text: '结构'),
                const Tab(text: '流动性'),
                const Tab(text: 'GEX'),
                const Tab(text: '概览'),
              ],
            ),
          ),
          const SizedBox(height: 16),
          AnimatedBuilder(
            animation: _tabController,
            builder: (context, _) => _buildTabContent(_tabController.index),
          ),
        ],
      ),
    );
  }

  Widget _buildTabContent(int index) {
    return switch (index) {
      0 => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            MarketSignalsPanel(
              data: widget.data,
              unifiedEvents: widget.unifiedEvents,
            ),
            const SizedBox(height: 16),
            AdviceCard(advice: widget.data.advice),
          ],
        ),
      1 => SmcPanel(smc: widget.data.smc, lastPrice: widget.data.lastPrice),
      2 => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LiquidityPanel(
              levels: widget.data.liquidityLevels,
              lastPrice: widget.data.lastPrice,
            ),
            if (widget.data.orderbook != null) ...[
              const SizedBox(height: 16),
              OrderbookPanel(orderbook: widget.data.orderbook!),
            ],
          ],
        ),
      3 => EvidencePanel(data: widget.data),
      4 => VolatilityPanel(
          volRatio: widget.data.volRatio,
          volStatus: widget.data.volStatus,
          ohlcvSummary: widget.data.ohlcvSummary,
        ),
      _ => const SizedBox.shrink(),
    };
  }
}

class _SignalTab extends StatelessWidget {
  const _SignalTab({
    required this.label,
    this.badge,
    this.badgeColor = AppTheme.accent,
  });

  final String label;
  final int? badge;
  final Color badgeColor;

  @override
  Widget build(BuildContext context) {
    if (badge == null) {
      return Tab(text: label);
    }

    return Tab(
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: badgeColor.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: badgeColor.withValues(alpha: 0.5)),
            ),
            child: Text(
              '$badge',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: badgeColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
