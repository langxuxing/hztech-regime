import 'package:flutter/material.dart';

import '../models/trend_judgment.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 趋势优先主视觉：当前趋势 + 置信度 + Regime + 业务姿态
class TrendJudgmentHero extends StatelessWidget {
  const TrendJudgmentHero({
    super.key,
    required this.judgment,
    this.readinessTier,
    this.offlineDemo = false,
  });

  final TrendJudgment judgment;
  final String? readinessTier;
  final bool offlineDemo;

  @override
  Widget build(BuildContext context) {
    final trendColor = _trendColor(judgment.trend);
    final stabilityColor = _stabilityColor(judgment.stability);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            trendColor.withValues(alpha: 0.14),
            AppTheme.surfaceHigh,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: trendColor.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_trendIcon(judgment.trend), color: trendColor, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '当前趋势 · ${judgment.trendLabel}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: trendColor,
                      ),
                    ),
                    Text(
                      '技术趋势 ${judgment.techTrend == judgment.trend ? '一致' : _techLabel(judgment.techTrend)}',
                      style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${(judgment.confidence * 100).round()}%',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: trendColor,
                    ),
                  ),
                  const Text('置信度', style: TextStyle(fontSize: 9, color: AppTheme.textSecondary)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusBadge(label: judgment.regimeLabel, color: AppTheme.accent),
              StatusBadge(label: _stabilityLabel(judgment.stability), color: stabilityColor),
              if (readinessTier != null)
                StatusBadge(label: '数据: $readinessTier', color: AppTheme.textSecondary),
              if (offlineDemo)
                const StatusBadge(label: '离线演示', color: AppTheme.neutral),
              if (judgment.needsHumanJudgment)
                const StatusBadge(label: '建议人工判断', color: AppTheme.short),
              if (judgment.consensusCapped)
                const StatusBadge(label: '共识分歧', color: AppTheme.neutral),
            ],
          ),
          if (judgment.businessStance.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              judgment.businessStance,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
          if (judgment.drivers.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...judgment.drivers.take(4).map(
                  (d) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
                        Expanded(
                          child: Text(
                            d,
                            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ],
      ),
    );
  }

  String _techLabel(String t) => switch (t) {
        'uptrend' => '上涨',
        'downtrend' => '下跌',
        _ => '震荡',
      };

  String _stabilityLabel(String s) => switch (s) {
        'confirmed' => '已确认',
        'transition' => '转换期',
        _ => '待确认',
      };

  Color _trendColor(String t) => switch (t) {
        'uptrend' => AppTheme.long,
        'downtrend' => AppTheme.short,
        _ => AppTheme.neutral,
      };

  Color _stabilityColor(String s) => switch (s) {
        'confirmed' => AppTheme.long,
        'transition' => AppTheme.short,
        _ => AppTheme.accent,
      };

  IconData _trendIcon(String t) => switch (t) {
        'uptrend' => Icons.trending_up_rounded,
        'downtrend' => Icons.trending_down_rounded,
        _ => Icons.trending_flat_rounded,
      };
}
