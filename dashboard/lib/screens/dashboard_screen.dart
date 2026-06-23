import 'package:flutter/material.dart';

import '../bigevent/event_data.dart';
import '../models/dashboard_data.dart';
import '../models/radar_tab.dart';
import '../regime/regime_history.dart';
import '../forecast/trend_consensus.dart';
import '../models/trend_judgment.dart';
import '../services/api_service.dart';
import '../bigevent/event_merger.dart';
import '../signal/market_signals_panel.dart';
import '../theme/app_theme.dart';
import 'tabs/wallboard_tab.dart';
import 'tabs/market_radar_tab.dart';
import 'tabs/regime_status_tab.dart';
import 'tabs/events_signals_tab.dart';
import 'tabs/models_tab.dart';
import 'tabs/black_swan_tab.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _api = ApiService();
  DashboardData? _data;
  EventAnalysisData? _events;
  TrendConsensus? _consensus;
  RegimeHistoryData? _regimeHistory;
  TrendJudgment? _trendJudgment;
  String? _readinessTier;
  List<UnifiedEventItem> _unifiedEvents = [];
  bool _loading = true;
  bool _refreshing = false;
  bool _apiHealthy = false;
  List<String> _errors = [];
  RadarTab _tab = RadarTab.wallboard;
  final Set<RadarTab> _visitedTabs = {RadarTab.wallboard};

  int get _eventsBadgeCount {
    if (_data == null) return 0;
    return MarketSignalsPanel.alertCount(_data!, _unifiedEvents);
  }

  int get _blackSwanBadgeCount {
    final level = (_data?.blackSwanAlert?['level'] as num?)?.toInt() ?? 0;
    if (level >= 2) return 1;
    if (_data?.blackSwanAlert?['suspended'] == true) return 1;
    if (_data?.pipeline?['layers']?['execution']?['suspended'] == true) return 1;
    return 0;
  }

  int get _regimeBadgeCount {
    final combined = _data?.regimeConfirmation?['combined'] as Map<String, dynamic>?;
    if (combined == null) return 0;
    final live = combined['live_regime_id']?.toString();
    final confirmed = combined['confirmed_regime_id']?.toString();
    return live != null && confirmed != null && live != confirmed ? 1 : 0;
  }

  String? get _consensusError {
    for (final e in _errors) {
      if (e.startsWith('趋势共识:')) return e;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh({bool deepScanEvents = false}) async {
    final hasData = _data != null;
    setState(() {
      if (hasData) {
        _refreshing = true;
      } else {
        _loading = true;
      }
      if (!deepScanEvents) _errors = [];
    });

    final healthy = await _api.checkHealth();

    try {
      final result = await _api.loadRadar(
        deepScanEvents: deepScanEvents,
      );
      if (!mounted) return;

      final unified = EventMerger.merge(
        boardEvents: result.dashboard.board.majorEvents,
        external: result.events,
        serverUnified: result.dashboard.unifiedEvents,
      );

      setState(() {
        _data = result.dashboard;
        _events = result.events;
        _consensus = result.consensus;
        _regimeHistory = result.regimeHistory;
        _trendJudgment = result.trendJudgment;
        _readinessTier = result.readinessTier;
        _unifiedEvents = unified;
        _errors = result.errors;
        _apiHealthy = healthy;
        _loading = false;
        _refreshing = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        if (!hasData) _data = null;
        _errors = ['数据加载失败: $e', '请确认 API 已启动且本地 BTC 数据已下载'];
        _apiHealthy = false;
        _loading = false;
        _refreshing = false;
      });
    }
  }

  void _goToTab(RadarTab tab) {
    setState(() {
      _tab = tab;
      _visitedTabs.add(tab);
    });
  }

  @override
  Widget build(BuildContext context) {
    final current = _tab;
    final narrow = MediaQuery.sizeOf(context).width < 480;

    return Scaffold(
      appBar: AppBar(
        title: Text(current.title),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert_rounded),
            onSelected: (v) {
              if (v == 'deep_scan') {
                _refresh(deepScanEvents: true);
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'deep_scan',
                child: Text('深度扫描事件'),
              ),
            ],
          ),
          IconButton(
            tooltip: '刷新',
            onPressed: _loading || _refreshing ? null : () => _refresh(),
            icon: _loading || _refreshing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Stack(
        children: [
          _buildBody(),
          if (_refreshing)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: LinearProgressIndicator(
                minHeight: 2,
                backgroundColor: Colors.transparent,
                color: AppTheme.accent.withValues(alpha: 0.8),
              ),
            ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: current.index,
        onDestinationSelected: (i) => _goToTab(RadarTab.values[i]),
        height: 64,
        labelBehavior: narrow
            ? NavigationDestinationLabelBehavior.onlyShowSelected
            : NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          for (final tab in RadarTab.values)
            NavigationDestination(
              icon: _badgedIcon(tab, tab.icon),
              selectedIcon: _badgedIcon(tab, tab.selectedIcon),
              label: tab.navLabel,
            ),
        ],
      ),
    );
  }

  Widget _badgedIcon(RadarTab tab, IconData icon) {
    final count = switch (tab) {
      RadarTab.eventsSignals => _eventsBadgeCount,
      RadarTab.blackSwan => _blackSwanBadgeCount,
      RadarTab.regimeStatus => _regimeBadgeCount,
      _ => 0,
    };
    if (count <= 0) return Icon(icon);
    return Badge(
      label: Text('$count'),
      child: Icon(icon),
    );
  }

  Widget _buildBody() {
    if (_loading && _data == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final data = _data;
    if (data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_rounded, size: 48, color: AppTheme.neutral),
              const SizedBox(height: 16),
              const Text('无法加载数据', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              if (_errors.isNotEmpty) ...[
                const SizedBox(height: 12),
                for (final err in _errors)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(err, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: AppTheme.neutral)),
                  ),
              ],
              const SizedBox(height: 20),
              FilledButton(onPressed: _refresh, child: const Text('重试')),
            ],
          ),
        ),
      );
    }

    Widget? tabContent(RadarTab tab, Widget child) {
      if (!_visitedTabs.contains(tab)) return null;
      return child;
    }

    return IndexedStack(
      index: _tab.index,
      children: [
        tabContent(
              RadarTab.wallboard,
              WallboardTab(
                data: data,
                events: _events,
                consensus: _consensus,
                regimeHistory: _regimeHistory,
                unifiedEvents: _unifiedEvents,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
                onNavigate: _goToTab,
                apiHealthy: _apiHealthy,
                api: _api,
                trendJudgment: _trendJudgment,
                readinessTier: _readinessTier,
              ),
            ) ??
            const SizedBox.shrink(),
        tabContent(
              RadarTab.marketRadar,
              MarketRadarTab(
                data: data,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
                api: _api,
              ),
            ) ??
            const SizedBox.shrink(),
        tabContent(
              RadarTab.regimeStatus,
              RegimeStatusTab(
                data: data,
                regimeHistory: _regimeHistory,
                unifiedEvents: _unifiedEvents,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
                api: _api,
                trendJudgment: _trendJudgment,
                readinessTier: _readinessTier,
              ),
            ) ??
            const SizedBox.shrink(),
        tabContent(
              RadarTab.eventsSignals,
              EventsSignalsTab(
                data: data,
                unifiedEvents: _unifiedEvents,
                events: _events,
                consensus: _consensus,
                consensusError: _consensusError,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
                onDeepScan: () => _refresh(deepScanEvents: true),
              ),
            ) ??
            const SizedBox.shrink(),
        tabContent(
              RadarTab.models,
              ModelsTab(
                data: data,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
                api: _api,
              ),
            ) ??
            const SizedBox.shrink(),
        tabContent(
              RadarTab.blackSwan,
              BlackSwanTab(
                data: data,
                events: _events,
                errors: _errors,
                isRefreshing: _refreshing,
                onRefresh: () => _refresh(),
              ),
            ) ??
            const SizedBox.shrink(),
      ],
    );
  }
}
