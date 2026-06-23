import 'package:flutter/material.dart';

import '../models/board_insights.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class TrendPanel extends StatelessWidget {
  const TrendPanel({super.key, required this.trend});

  final TrendJudgment trend;

  @override
  Widget build(BuildContext context) {
    final color = _directionColor(trend.direction);

    return SectionCard(
      title: '走势判断',
      icon: Icons.trending_up_rounded,
      trailing: StatusBadge(label: trend.label, color: color),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: '短周期',
                  value: trend.shortTerm,
                  color: color,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '中周期',
                  value: trend.mediumTerm,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '置信度',
                  value: '${(trend.confidence * 100).round()}%',
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _DirectionBar(direction: trend.direction, color: color),
          const SizedBox(height: 14),
          Text(
            trend.summary,
            style: const TextStyle(
              fontSize: 12,
              height: 1.55,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: trend.keyLevels.entries
                .where((e) => e.value != null)
                .map(
                  (e) => MetricChip(
                    label: _levelLabel(e.key),
                    value: _formatPrice(e.value!),
                    color: _levelColor(e.key),
                  ),
                )
                .toList(),
          ),
          if (trend.signals.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text(
              '信号清单',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: trend.signals
                  .map((s) => StatusBadge(label: s, color: color))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  Color _directionColor(String d) => switch (d) {
        'up' => AppTheme.long,
        'down' => AppTheme.short,
        'correction' => AppTheme.neutral,
        _ => AppTheme.accent,
      };

  String _levelLabel(String key) => switch (key) {
        'support' => '支撑',
        'resistance' => '阻力',
        'invalidation' => '失效位',
        _ => key,
      };

  Color _levelColor(String key) => switch (key) {
        'support' => AppTheme.long,
        'resistance' => AppTheme.short,
        'invalidation' => AppTheme.neutral,
        _ => AppTheme.textPrimary,
      };

  String _formatPrice(double price) {
    if (price >= 1000) return price.toStringAsFixed(2);
    if (price >= 1) return price.toStringAsFixed(4);
    return price.toStringAsFixed(6);
  }
}

class _DirectionBar extends StatelessWidget {
  const _DirectionBar({required this.direction, required this.color});

  final String direction;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final labels = ['偏空', '横盘', '偏多'];
    final active = switch (direction) {
      'down' => 0,
      'correction' => 1,
      'sideways' => 1,
      'up' => 2,
      _ => 1,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '方向刻度',
          style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 8),
        Row(
          children: List.generate(3, (i) {
            final isActive = i == active;
            return Expanded(
              child: Container(
                margin: EdgeInsets.only(right: i < 2 ? 6 : 0),
                height: 8,
                decoration: BoxDecoration(
                  color: isActive
                      ? color
                      : AppTheme.surfaceHigh,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: isActive ? color : AppTheme.border,
                  ),
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: labels
              .map(
                (l) => Text(
                  l,
                  style: TextStyle(
                    fontSize: 9,
                    color: labels.indexOf(l) == active
                        ? color
                        : AppTheme.textSecondary,
                    fontWeight:
                        labels.indexOf(l) == active ? FontWeight.w600 : null,
                  ),
                ),
              )
              .toList(),
        ),
      ],
    );
  }
}
