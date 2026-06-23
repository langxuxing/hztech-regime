import 'package:flutter/material.dart';

import '../../models/dashboard_data.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../widgets/etf_flow_panel.dart';
import '../../widgets/onchain_panel.dart';
import '../../layers/l1_ingestion_tab.dart';
import '../../signal/smc_panel.dart';
import '../../signal/market_panels.dart';
import '../../signal/evidence_panel.dart';
import '../../widgets/trading_decision_panel.dart';
import '../../widgets/data_sources_panel.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

/// 金融雷达：市场数据多子 Tab。
class MarketRadarTab extends StatefulWidget {
  const MarketRadarTab({
    super.key,
    required this.data,
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.api,
  });

  final DashboardData data;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final ApiService? api;

  @override
  State<MarketRadarTab> createState() => _MarketRadarTabState();
}

class _MarketRadarTabState extends State<MarketRadarTab> with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 8, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;

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
              dividerColor: Colors.transparent,
              labelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
              tabs: const [
                Tab(text: '交易决策'),
                Tab(text: 'L1 输入'),
                Tab(text: '概览'),
                Tab(text: '结构'),
                Tab(text: '流动性'),
                Tab(text: 'GEX'),
                Tab(text: '资金流'),
                Tab(text: '数据源'),
              ],
            ),
          ),
          const SizedBox(height: 16),
          AnimatedBuilder(
            animation: _tabController,
            builder: (_, __) => _buildTab(_tabController.index, wide),
          ),
        ],
      ),
    );
  }

  Widget _buildTab(int index, bool wide) {
    final data = widget.data;
    return switch (index) {
      0 => TradingDecisionPanel(data: data, wide: wide),
      1 => L1IngestionTab(
          data: data,
          errors: widget.errors,
          onRefresh: widget.onRefresh,
          isRefreshing: widget.isRefreshing,
          embedded: true,
        ),
      2 => VolatilityPanel(
          volRatio: data.volRatio,
          volStatus: data.volStatus,
          ohlcvSummary: data.ohlcvSummary,
        ),
      3 => SmcPanel(smc: data.smc, lastPrice: data.lastPrice),
      4 => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LiquidityPanel(levels: data.liquidityLevels, lastPrice: data.lastPrice),
            if (data.orderbook != null) ...[
              const SizedBox(height: 16),
              OrderbookPanel(orderbook: data.orderbook!),
            ],
          ],
        ),
      5 => EvidencePanel(data: data),
      6 => wide
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: EtfFlowPanel(flows: data.capitalFlows)),
                const SizedBox(width: 16),
                Expanded(child: OnChainPanel(flows: data.capitalFlows)),
              ],
            )
          : Column(
              children: [
                EtfFlowPanel(flows: data.capitalFlows),
                const SizedBox(height: 16),
                OnChainPanel(flows: data.capitalFlows),
              ],
            ),
      7 => widget.api != null
          ? DataSourcesPanel(
              api: widget.api!,
              data: data,
              onRefreshParent: widget.onRefresh,
            )
          : Center(
              child: Text(
                'API 未连接',
                style: TextStyle(color: AppTheme.textSecondary),
              ),
            ),
      _ => const SizedBox.shrink(),
    };
  }
}
