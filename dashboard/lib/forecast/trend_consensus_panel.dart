import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'trend_consensus.dart';

class TrendConsensusPanel extends StatelessWidget {
  const TrendConsensusPanel({super.key, required this.consensus});

  final TrendConsensus consensus;

  @override
  Widget build(BuildContext context) {
    final color = switch (consensus.direction) {
      'up' => AppTheme.long,
      'down' => AppTheme.short,
      _ => AppTheme.neutral,
    };

    return SectionCard(
      title: '趋势共识 · V2',
      icon: Icons.hub_rounded,
      trailing: StatusBadge(label: consensus.label, color: color),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: '集成得分',
                  value: consensus.score.toStringAsFixed(3),
                  color: color,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '一致性',
                  value: '${(consensus.agreement * 100).round()}%',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '来源',
                  value: '${consensus.sourcesOk}/${consensus.sourcesOk + consensus.sourcesFailed}',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            consensus.summary,
            style: const TextStyle(fontSize: 11, height: 1.45, color: AppTheme.textSecondary),
          ),
          if (consensus.signals.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('信号源', style: TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
            const SizedBox(height: 6),
            ...consensus.signals.where((s) => s.error == null).take(6).map(
                  (s) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        StatusBadge(
                          label: s.direction == 'up'
                              ? '多'
                              : s.direction == 'down'
                                  ? '空'
                                  : '中',
                          color: switch (s.direction) {
                            'up' => AppTheme.long,
                            'down' => AppTheme.short,
                            _ => AppTheme.textSecondary,
                          },
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '${s.source}: ${s.label}',
                            style: const TextStyle(fontSize: 10),
                          ),
                        ),
                        Text(
                          '${(s.confidence * 100).round()}%',
                          style: const TextStyle(
                            fontSize: 10,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            if (consensus.sourcesFailed > 0) ...[
              const SizedBox(height: 8),
              Text(
                '${consensus.sourcesFailed} 个数据源失败：${consensus.signals.where((s) => s.error != null).map((s) => s.source).take(3).join(', ')}',
                style: const TextStyle(fontSize: 10, color: AppTheme.neutral),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
