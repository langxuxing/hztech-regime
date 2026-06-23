import 'package:flutter/material.dart';

import 'event_data.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 重大事件影响分析 Tab 顶部汇总。
class EventImpactSummary extends StatelessWidget {
  const EventImpactSummary({super.key, this.events});

  final EventAnalysisData? events;

  @override
  Widget build(BuildContext context) {
    if (events == null) {
      return const SectionCard(
        title: '影响分析汇总',
        icon: Icons.analytics_outlined,
        child: Text(
          '事件引擎数据未加载',
          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
      );
    }

    final s = events!.summary;
    final riskColor = switch (s.overallRisk) {
      'elevated' || 'bearish' => AppTheme.short,
      'bullish' => AppTheme.long,
      'mixed' => AppTheme.neutral,
      _ => AppTheme.accent,
    };

    return SectionCard(
      title: '影响分析汇总',
      icon: Icons.analytics_outlined,
      trailing: StatusBadge(
        label: _riskLabel(s.overallRisk),
        color: riskColor,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              MetricChip(
                label: '高影响事件',
                value: '${s.highImpactCount}',
                color: s.highImpactCount > 0 ? AppTheme.short : AppTheme.accent,
              ),
              MetricChip(
                label: '偏多信号',
                value: '${s.bullishSignals}',
                color: AppTheme.long,
              ),
              MetricChip(
                label: '偏空信号',
                value: '${s.bearishSignals}',
                color: AppTheme.short,
              ),
              MetricChip(
                label: '宏观待公布',
                value: '${s.upcomingMacro}',
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '日历 ${s.totalCalendar} · 突发 ${s.totalBreaking} · 扫描 ${events!.scanDurationMs}ms',
            style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
          if (events!.notes.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              events!.notes.first,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  String _riskLabel(String r) => switch (r) {
        'elevated' => '风险偏高',
        'bearish' => '偏空环境',
        'bullish' => '偏多环境',
        'mixed' => '混合环境',
        _ => '正常',
      };
}
