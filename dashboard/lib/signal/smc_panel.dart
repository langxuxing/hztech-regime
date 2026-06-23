import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class SmcPanel extends StatelessWidget {
  const SmcPanel({super.key, required this.smc, required this.lastPrice});

  final SmcSnapshot smc;
  final double lastPrice;

  @override
  Widget build(BuildContext context) {
    final trendColor = switch (smc.trend) {
      'bullish' => AppTheme.long,
      'bearish' => AppTheme.short,
      _ => AppTheme.neutral,
    };

    return SectionCard(
      title: 'SMC / ICT 结构',
      icon: Icons.account_tree_outlined,
      trailing: StatusBadge(label: smc.trend, color: trendColor),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (smc.mssOrChoch != null)
            MetricChip(
              label: 'MSS / CHoCH',
              value: '${smc.mssOrChoch} (dir=${smc.mssDirection})',
              color: smc.mssDirection >= 0 ? AppTheme.long : AppTheme.short,
            ),
          const SizedBox(height: 10),
          if (smc.nearestOb != null)
            _ZoneTile(
              label: '最近 OB',
              zone: smc.nearestOb!,
              lastPrice: lastPrice,
              color: AppTheme.accent,
            ),
          if (smc.nearestFvg != null)
            _ZoneTile(
              label: '最近 FVG',
              zone: smc.nearestFvg!,
              lastPrice: lastPrice,
              color: AppTheme.magnet,
            ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: '未回补 FVG',
                  value: '${smc.unfilledFvgs.length}',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '活跃 OB',
                  value: '${smc.activeObs.length}',
                ),
              ),
            ],
          ),
          if (smc.unfilledFvgs.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('未回补 FVG', style: TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
            ...smc.unfilledFvgs.take(3).map(
                  (z) => _ZoneTile(
                    label: z.label.isNotEmpty ? z.label : 'FVG',
                    zone: z,
                    lastPrice: lastPrice,
                    color: AppTheme.magnet,
                  ),
                ),
          ],
          if (smc.activeObs.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('活跃 OB', style: TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
            ...smc.activeObs.take(3).map(
                  (z) => _ZoneTile(
                    label: z.label.isNotEmpty ? z.label : 'OB',
                    zone: z,
                    lastPrice: lastPrice,
                    color: AppTheme.accent,
                  ),
                ),
          ],
          if (smc.structureNotes.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...smc.structureNotes.map(
              (note) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• ', style: TextStyle(color: AppTheme.textSecondary)),
                    Expanded(
                      child: Text(
                        note,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.textSecondary,
                          height: 1.4,
                        ),
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
}

class _ZoneTile extends StatelessWidget {
  const _ZoneTile({
    required this.label,
    required this.zone,
    required this.lastPrice,
    required this.color,
  });

  final String label;
  final PriceZone zone;
  final double lastPrice;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final dist = lastPrice > 0 ? (zone.mid - lastPrice) / lastPrice * 100 : 0.0;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          const Spacer(),
          Text(
            '${zone.low.toStringAsFixed(2)} – ${zone.high.toStringAsFixed(2)}',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
          ),
          const SizedBox(width: 8),
          Text(
            '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(2)}%',
            style: TextStyle(
              fontSize: 11,
              color: dist >= 0 ? AppTheme.long : AppTheme.short,
            ),
          ),
        ],
      ),
    );
  }
}
