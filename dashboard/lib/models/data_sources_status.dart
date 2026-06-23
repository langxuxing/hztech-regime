import '../utils/json_utils.dart';

/// `/api/scheduler/status` 响应模型。
class DataSourcesStatus {
  const DataSourcesStatus({
    required this.tier,
    required this.coinglassApiKey,
    required this.xBearerToken,
    required this.eventDemoMode,
    required this.fundingPrimarySource,
    required this.ohlcvDir,
    required this.modules,
    required this.schedulerTasks,
    this.schedulerUpdatedAt,
    this.tasksOk = 0,
    this.taskCount = 0,
    this.snapshotAgeSec,
  });

  final String tier;
  final bool coinglassApiKey;
  final bool xBearerToken;
  final bool eventDemoMode;
  final String fundingPrimarySource;
  final String ohlcvDir;
  final Map<String, DataModuleStatus> modules;
  final Map<String, SchedulerTaskStatus> schedulerTasks;
  final String? schedulerUpdatedAt;
  final int tasksOk;
  final int taskCount;
  final double? snapshotAgeSec;

  factory DataSourcesStatus.fromJson(Map<String, dynamic> json) {
    final caps = asJsonMap(json['capabilities']);
    final sched = asJsonMap(json['scheduler']);
    final modulesRaw = asJsonMap(caps['modules']);
    final tasksRaw = asJsonMap(sched['tasks']);

    final modules = <String, DataModuleStatus>{};
    for (final entry in modulesRaw.entries) {
      modules[entry.key] = DataModuleStatus.fromJson(
        entry.key,
        asJsonMap(entry.value),
      );
    }

    final tasks = <String, SchedulerTaskStatus>{};
    for (final entry in tasksRaw.entries) {
      tasks[entry.key] = SchedulerTaskStatus.fromJson(
        entry.key,
        asJsonMap(entry.value),
      );
    }

    final snapAge = json['snapshot_age_sec'];
    return DataSourcesStatus(
      tier: caps['tier']?.toString() ?? 'unknown',
      coinglassApiKey: caps['coinglass_api_key'] == true,
      xBearerToken: caps['x_bearer_token'] == true,
      eventDemoMode: caps['event_demo_mode'] == true,
      fundingPrimarySource: caps['funding_primary_source']?.toString() ?? '—',
      ohlcvDir: caps['ohlcv_dir']?.toString() ?? '—',
      modules: modules,
      schedulerTasks: tasks,
      schedulerUpdatedAt: sched['updated_at']?.toString(),
      tasksOk: (sched['tasks_ok'] as num?)?.toInt() ?? 0,
      taskCount: (sched['task_count'] as num?)?.toInt() ?? 0,
      snapshotAgeSec: snapAge is num ? snapAge.toDouble() : null,
    );
  }

  static DataSourcesStatus demo() {
    return DataSourcesStatus(
      tier: 'demo',
      coinglassApiKey: false,
      xBearerToken: false,
      eventDemoMode: true,
      fundingPrimarySource: 'binance_fapi',
      ohlcvDir: 'data/OHLCV/Btc',
      modules: {
        'ohlcv': const DataModuleStatus(
          id: 'ohlcv',
          status: 'ok',
          note: '演示：本地 1m resample',
          local1mBars: 4320,
        ),
        'spot_cvd': const DataModuleStatus(
          id: 'spot_cvd',
          status: 'ok',
          note: 'Binance taker',
        ),
        'etf_btc': const DataModuleStatus(
          id: 'etf_btc',
          status: 'partial',
          note: 'Farside / 本地 CSV',
        ),
      },
      schedulerTasks: {
        'btc_1m': SchedulerTaskStatus(
          id: 'btc_1m',
          lastOk: true,
          lastRunAt: DateTime.now().toIso8601String(),
          detail: 'exit 0',
        ),
        'events': SchedulerTaskStatus(
          id: 'events',
          lastOk: true,
          lastRunAt: DateTime.now().toIso8601String(),
          detail: 'breaking=2 calendar=12',
        ),
      },
      tasksOk: 2,
      taskCount: 2,
      snapshotAgeSec: 45,
    );
  }
}

class DataModuleStatus {
  const DataModuleStatus({
    required this.id,
    required this.status,
    required this.note,
    this.local1mBars,
    this.source,
  });

  final String id;
  final String status;
  final String note;
  final int? local1mBars;
  final String? source;

  factory DataModuleStatus.fromJson(String id, Map<String, dynamic> json) {
    return DataModuleStatus(
      id: id,
      status: json['status']?.toString() ?? 'unknown',
      note: json['note']?.toString() ?? '',
      local1mBars: (json['local_1m_bars'] as num?)?.toInt(),
      source: json['source']?.toString(),
    );
  }

  String get label => switch (id) {
        'ohlcv' => 'K 线 OHLCV',
        'ticker_orderbook' => 'Ticker / 订单簿',
        'spot_cvd' => 'Spot CVD',
        'derivatives' => '衍生品 OI / Funding',
        'etf_btc' => 'BTC ETF',
        'etf_eth' => 'ETH ETF',
        'fund_flow' => '资金流 / 钱包',
        'chain_activity' => '链上活跃度',
        'events_calendar' => '事件日历',
        'events_x' => 'X 监控',
        'macro_fred' => '宏观 FRED',
        'macro_ism' => '制造业活动 (FRED IPMAN)',
        'forecast_consensus' => '趋势共识源',
        'funding_snapshot' => 'Funding 统一快照',
        _ => id,
      };
}

class SchedulerTaskStatus {
  const SchedulerTaskStatus({
    required this.id,
    required this.lastOk,
    this.lastRunAt,
    this.lastOkAt,
    this.durationMs,
    this.detail,
    this.lastError,
  });

  final String id;
  final bool lastOk;
  final String? lastRunAt;
  final String? lastOkAt;
  final int? durationMs;
  final String? detail;
  final String? lastError;

  factory SchedulerTaskStatus.fromJson(String id, Map<String, dynamic> json) {
    return SchedulerTaskStatus(
      id: id,
      lastOk: json['last_ok'] == true,
      lastRunAt: json['last_run_at']?.toString(),
      lastOkAt: json['last_ok_at']?.toString(),
      durationMs: (json['duration_ms'] as num?)?.toInt(),
      detail: json['detail']?.toString(),
      lastError: json['last_error']?.toString(),
    );
  }

  String get label => switch (id) {
        'btc_1m' => 'BTC 1m 增量',
        'daily_sync' => '日同步 macro/ETF',
        'events' => '事件扫描',
        'regime_feedback' => 'Regime 反馈校准',
        _ => id,
      };
}
