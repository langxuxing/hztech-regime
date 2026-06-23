import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// BTC Regime 引擎详情：Triad 融合、Donchian 等。
class BtcRegimeDetailPanel extends StatelessWidget {
  const BtcRegimeDetailPanel({super.key, required this.btcRegime});

  final Map<String, dynamic> btcRegime;

  @override
  Widget build(BuildContext context) {
    final triad = btcRegime['triad'] as Map<String, dynamic>?;

    return SectionCard(
      title: 'Regime 预测引擎',
      icon: Icons.psychology_outlined,
      trailing: btcRegime['regime_label'] != null
          ? StatusBadge(
              label: btcRegime['regime_label'].toString(),
              color: AppTheme.accent,
            )
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (triad?['summary'] != null) ...[
            Text(
              triad!['summary'].toString(),
              style: const TextStyle(fontSize: 12, height: 1.5, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 10),
          ],
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (btcRegime['next_regime_label'] != null)
                MetricChip(
                  label: '3bar 预测',
                  value: btcRegime['next_regime_label'].toString(),
                  color: AppTheme.magnet,
                ),
              if (btcRegime['changepoint_prob'] != null)
                MetricChip(
                  label: '变点概率',
                  value:
                      '${((btcRegime['changepoint_prob'] as num) * 100).round()}%',
                ),
              if (triad?['fusion_confidence'] != null)
                MetricChip(
                  label: 'Triad 置信',
                  value:
                      '${((triad!['fusion_confidence'] as num) * 100).round()}%',
                ),
              if (btcRegime['confidence'] != null)
                MetricChip(
                  label: 'Regime 置信',
                  value:
                      '${((btcRegime['confidence'] as num) * 100).round()}%',
                ),
              if (btcRegime['vol_bucket'] != null)
                MetricChip(
                  label: '波动桶',
                  value: btcRegime['vol_bucket'].toString(),
                ),
            ],
          ),
          if (btcRegime['donchian_upper'] != null || btcRegime['donchian_lower'] != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                if (btcRegime['donchian_lower'] != null)
                  Expanded(
                    child: MetricChip(
                      label: '唐奇安下',
                      value: _price(btcRegime['donchian_lower']),
                      color: AppTheme.long,
                    ),
                  ),
                if (btcRegime['donchian_upper'] != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricChip(
                      label: '唐奇安上',
                      value: _price(btcRegime['donchian_upper']),
                      color: AppTheme.short,
                    ),
                  ),
                ],
              ],
            ),
          ],
          if (btcRegime['kama'] != null) ...[
            const SizedBox(height: 8),
            MetricChip(
              label: 'KAMA',
              value: _price(btcRegime['kama']),
              color: AppTheme.accent,
            ),
          ],
        ],
      ),
    );
  }

  String _price(dynamic v) {
    final p = (v as num).toDouble();
    return p >= 1000 ? p.toStringAsFixed(0) : p.toStringAsFixed(2);
  }
}
