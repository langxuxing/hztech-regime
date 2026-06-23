import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'regime_history.dart';
import '../widgets/radar_overview_bar.dart';

class RegimeHistoryPanel extends StatelessWidget {
  const RegimeHistoryPanel({super.key, required this.data});

  final RegimeHistoryData data;

  @override
  Widget build(BuildContext context) {
    if (data.history.isEmpty) {
      return const SectionCard(
        title: 'Regime 历史 · V2',
        icon: Icons.timeline_outlined,
        child: Text(
          '暂无 Regime 切换记录（刷新几次后会自动积累）',
          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
      );
    }

    return SectionCard(
      title: 'Regime 历史 · V2',
      icon: Icons.timeline_outlined,
      trailing: StatusBadge(
        label: '${data.history.length} 次切换',
        color: AppTheme.accent,
      ),
      child: Column(
        children: [
          for (var i = 0; i < data.history.length && i < 8; i++) ...[
            if (i > 0) const Divider(height: 16, color: AppTheme.border),
            _TimelineRow(
              entry: data.history[i],
              isLatest: i == 0,
            ),
          ],
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.entry, required this.isLatest});

  final RegimeHistoryEntry entry;
  final bool isLatest;

  @override
  Widget build(BuildContext context) {
    final color = switch (entry.regime) {
      'trend_up' => AppTheme.long,
      'trend_down' => AppTheme.short,
      'high_vol' => AppTheme.neutral,
      _ => AppTheme.accent,
    };

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: isLatest ? color : AppTheme.border,
                shape: BoxShape.circle,
                border: Border.all(color: color, width: isLatest ? 2 : 1),
              ),
            ),
            if (!isLatest)
              Container(width: 2, height: 28, color: AppTheme.border),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      entry.label,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isLatest ? color : AppTheme.textPrimary,
                      ),
                    ),
                  ),
                  Text(
                    formatRadarTime(entry.recordedAt),
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
              if (entry.confidence != null)
                Text(
                  '置信 ${(entry.confidence! * 100).round()}% · ${entry.volRegime ?? ''}',
                  style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
