import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../models/data_sources_status.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 数据源与调度任务查看面板。
class DataSourcesPanel extends StatefulWidget {
  const DataSourcesPanel({
    super.key,
    required this.api,
    required this.data,
    this.useMock = false,
    this.onRefreshParent,
  });

  final ApiService api;
  final DashboardData data;
  final bool useMock;
  final Future<void> Function()? onRefreshParent;

  @override
  State<DataSourcesPanel> createState() => _DataSourcesPanelState();
}

class _DataSourcesPanelState extends State<DataSourcesPanel> {
  DataSourcesStatus? _status;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final status = widget.useMock
          ? DataSourcesStatus.demo()
          : await widget.api.fetchSchedulerStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _refreshAll() async {
    await _load();
    await widget.onRefreshParent?.call();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _status == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(),
        ),
      );
    }

    final status = _status;
    if (status == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error ?? '无法加载数据源状态', style: const TextStyle(color: AppTheme.short)),
            const SizedBox(height: 12),
            FilledButton(onPressed: _load, child: const Text('重试')),
          ],
        ),
      );
    }

    final ohlcv = widget.data.ohlcvSummary;
    final ohlcvSource = ohlcv['ohlcv_source']?.toString();

    return RefreshIndicator(
      onRefresh: _refreshAll,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!, style: const TextStyle(fontSize: 11, color: AppTheme.short)),
            ),
          SectionCard(
            title: '部署层级',
            icon: Icons.layers_outlined,
            trailing: IconButton(
              tooltip: '刷新',
              onPressed: _loading ? null : _load,
              icon: _loading
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.refresh_rounded, size: 18),
            ),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _TierChip(label: _tierLabel(status.tier), tier: status.tier),
                if (status.coinglassApiKey) const _KeyChip(label: 'CoinGlass', on: true),
                if (status.xBearerToken) const _KeyChip(label: 'X API', on: true),
                if (status.eventDemoMode) const _KeyChip(label: '事件演示', on: false),
                if (status.snapshotAgeSec != null)
                  MetricChip(
                    label: '快照年龄',
                    value: _fmtAge(status.snapshotAgeSec!),
                  ),
                if (ohlcvSource != null)
                  MetricChip(label: '当前 K 线源', value: ohlcvSource),
                MetricChip(
                  label: 'Funding 主源',
                  value: status.fundingPrimarySource,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '调度任务',
            icon: Icons.schedule_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${status.tasksOk}/${status.taskCount} 任务最近成功'
                  '${status.schedulerUpdatedAt != null ? ' · 更新 ${status.schedulerUpdatedAt}' : ''}',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 12),
                if (status.schedulerTasks.isEmpty)
                  const Text(
                    '暂无调度记录。启动: ./scripts/start-data-scheduler.sh',
                    style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                  )
                else
                  ...status.schedulerTasks.values.map(_TaskRow.new),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '数据模块',
            icon: Icons.storage_outlined,
            child: Column(
              children: [
                for (final mod in status.modules.values) _ModuleRow(module: mod),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '本地路径',
            icon: Icons.folder_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _PathLine(label: 'OHLCV', path: status.ohlcvDir),
                const SizedBox(height: 8),
                _PathLine(label: 'K 线 bars', path: '${ohlcv['bars'] ?? '—'} 根'),
                if (ohlcv['last_close'] != null) ...[
                  const SizedBox(height: 8),
                  _PathLine(
                    label: '末根收盘',
                    path: '${ohlcv['last_close']} (${ohlcv['last_change_pct'] ?? 0}%)',
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  static String _tierLabel(String tier) => switch (tier) {
        'full' => '全量',
        'coinglass' => 'CoinGlass',
        'free' => '免费栈',
        'demo' => '演示',
        _ => tier,
      };

  static String _fmtAge(double sec) {
    if (sec < 60) return '${sec.round()}s';
    if (sec < 3600) return '${(sec / 60).round()}m';
    return '${(sec / 3600).toStringAsFixed(1)}h';
  }
}

class _TierChip extends StatelessWidget {
  const _TierChip({required this.label, required this.tier});

  final String label;
  final String tier;

  @override
  Widget build(BuildContext context) {
    final color = switch (tier) {
      'full' => AppTheme.long,
      'coinglass' => AppTheme.accent,
      'free' => AppTheme.neutral,
      'demo' => AppTheme.magnet,
      _ => AppTheme.textSecondary,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

class _KeyChip extends StatelessWidget {
  const _KeyChip({required this.label, required this.on});

  final String label;
  final bool on;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(on ? Icons.check_circle : Icons.cancel_outlined, size: 12, color: on ? AppTheme.long : AppTheme.short),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(fontSize: 10)),
        ],
      ),
    );
  }
}

class _TaskRow extends StatelessWidget {
  const _TaskRow(this.task);

  final SchedulerTaskStatus task;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            task.lastOk ? Icons.check_circle_outline : Icons.error_outline,
            size: 16,
            color: task.lastOk ? AppTheme.long : AppTheme.short,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(task.label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                if (task.lastRunAt != null)
                  Text(
                    '最近运行 ${task.lastRunAt}',
                    style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                  ),
                if (task.detail != null && task.detail!.isNotEmpty)
                  Text(task.detail!, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                if (task.lastError != null)
                  Text(task.lastError!, style: const TextStyle(fontSize: 10, color: AppTheme.short)),
              ],
            ),
          ),
          if (task.durationMs != null)
            Text('${task.durationMs}ms', style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }
}

class _ModuleRow extends StatelessWidget {
  const _ModuleRow({required this.module});

  final DataModuleStatus module;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _StatusDot(status: module.status),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(module.label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                Text(module.note, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                if (module.local1mBars != null)
                  Text(
                    '本地 1m: ${module.local1mBars} bars',
                    style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                  ),
              ],
            ),
          ),
          Text(module.status, style: TextStyle(fontSize: 10, color: _statusColor(module.status))),
        ],
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      margin: const EdgeInsets.only(top: 4),
      decoration: BoxDecoration(
        color: _statusColor(status),
        shape: BoxShape.circle,
      ),
    );
  }
}

class _PathLine extends StatelessWidget {
  const _PathLine({required this.label, required this.path});

  final String label;
  final String path;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 72,
          child: Text(label, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
        ),
        Expanded(
          child: Text(path, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500)),
        ),
      ],
    );
  }
}

Color _statusColor(String status) => switch (status) {
      'ok' => AppTheme.long,
      'degraded' || 'partial' || 'fragile' => AppTheme.neutral,
      'missing_key' || 'disabled' => AppTheme.textSecondary,
      'demo' => AppTheme.magnet,
      _ => AppTheme.short,
    };
