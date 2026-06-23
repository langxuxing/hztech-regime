import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../bigevent/event_merger.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 市场信号提醒：聚合 GEX / 流动性 / 结构 / 可交易事件。
class MarketSignalsPanel extends StatelessWidget {
  const MarketSignalsPanel({
    super.key,
    required this.data,
    this.unifiedEvents = const [],
  });

  final DashboardData data;
  final List<UnifiedEventItem> unifiedEvents;

  static int alertCount(DashboardData data, List<UnifiedEventItem> unifiedEvents) {
    return _buildAlerts(data, unifiedEvents).length;
  }

  static int highPriorityCount(DashboardData data, List<UnifiedEventItem> unifiedEvents) {
    return _buildAlerts(data, unifiedEvents)
        .where((a) => a.level == _AlertLevel.high)
        .length;
  }

  @override
  Widget build(BuildContext context) {
    final alerts = _buildAlerts(data, unifiedEvents);

    return SectionCard(
      title: '实时信号提醒',
      icon: Icons.campaign_outlined,
      trailing: StatusBadge(
        label: '${alerts.length} 条',
        color: alerts.any((a) => a.level == _AlertLevel.high)
            ? AppTheme.short
            : AppTheme.accent,
      ),
      child: alerts.isEmpty
          ? const Text(
              '当前无高优先级市场信号',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            )
          : Column(
              children: alerts.map(_AlertTile.new).toList(),
            ),
    );
  }

  static List<_AlertItem> _buildAlerts(
    DashboardData data,
    List<UnifiedEventItem> unifiedEvents,
  ) {
    final items = <_AlertItem>[];
    final snap = data.featureSnapshot;

    if (data.macroHazardFlag) {
      items.add(const _AlertItem(
        level: _AlertLevel.high,
        category: '宏观',
        title: '宏观熔断窗口',
        detail: 'CPI/FOMC/NFP ±120min，系统强制观望',
      ));
    }

    final gex = snap?['gex_engine'] as Map<String, dynamic>?;
    for (final a in (gex?['alerts'] as List?) ?? []) {
      items.add(_AlertItem(
        level: _AlertLevel.medium,
        category: 'GEX',
        title: a.toString(),
        detail: '来源 ${gex?['source'] ?? 'proxy'}',
      ));
    }

    for (final lv in data.liquidityLevels.where((l) => !l.swept)) {
      final side = lv.side == 'sell_side' ? '上方' : '下方';
      items.add(_AlertItem(
        level: _AlertLevel.medium,
        category: '流动性',
        title: '$side待清洗 ${lv.price.toStringAsFixed(0)}',
        detail: 'strength ${lv.strength.toStringAsFixed(2)}',
      ));
    }

    if (data.smc.mssOrChoch != null) {
      final dir = data.smc.mssDirection > 0 ? '看涨' : '看跌';
      items.add(_AlertItem(
        level: _AlertLevel.high,
        category: '结构',
        title: '${data.smc.mssOrChoch} · $dir',
        detail: data.smc.structureNotes.isNotEmpty
            ? data.smc.structureNotes.first
            : '市场结构变化',
      ));
    }

    for (final e in unifiedEvents.where((x) => x.actionable || x.severity == 'high')) {
      items.add(_AlertItem(
        level: e.severity == 'high' ? _AlertLevel.high : _AlertLevel.medium,
        category: _catStatic(e.category),
        title: e.title,
        detail: e.description,
      ));
    }

    if (data.volStatus == 'elevated' || data.volStatus == 'high') {
      items.add(_AlertItem(
        level: _AlertLevel.medium,
        category: '波动',
        title: '波动率升高',
        detail: 'vol_ratio ${data.volRatio?.toStringAsFixed(3) ?? '—'}',
      ));
    }

    items.sort((a, b) => a.level.index.compareTo(b.level.index));
    return items.take(12).toList();
  }

  static String _catStatic(String c) => switch (c) {
        'macro' => '宏观',
        'etf' => 'ETF',
        'onchain' => '链上',
        'structure' => '结构',
        'breaking' => '突发',
        _ => '市场',
      };
}

enum _AlertLevel { high, medium, low }

class _AlertItem {
  const _AlertItem({
    required this.level,
    required this.category,
    required this.title,
    required this.detail,
  });

  final _AlertLevel level;
  final String category;
  final String title;
  final String detail;
}

class _AlertTile extends StatelessWidget {
  const _AlertTile(this.item);

  final _AlertItem item;

  @override
  Widget build(BuildContext context) {
    final color = switch (item.level) {
      _AlertLevel.high => AppTheme.short,
      _AlertLevel.medium => AppTheme.neutral,
      _AlertLevel.low => AppTheme.textSecondary,
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.circle, size: 8, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    StatusBadge(label: item.category, color: color),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        item.title,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  item.detail,
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppTheme.textSecondary,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
