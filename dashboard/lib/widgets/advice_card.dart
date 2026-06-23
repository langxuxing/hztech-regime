import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

class AdviceCard extends StatelessWidget {
  const AdviceCard({super.key, required this.advice});

  final TradeAdvice advice;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.biasColor(advice.bias);

    return SectionCard(
      title: 'AI 交易建议',
      icon: Icons.auto_graph_rounded,
      trailing: StatusBadge(
        label: AppTheme.biasLabel(advice.bias),
        color: color,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: '置信度',
                  value: '${(advice.confidence * 100).toStringAsFixed(0)}%',
                  color: color,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '共振分',
                  value: advice.confluenceScore.toStringAsFixed(2),
                  color: AppTheme.accent,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '周期',
                  value: advice.timeHorizon,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _LevelRow(
            label: '入场区',
            value: _zone(advice.entryZone),
            color: color,
          ),
          _LevelRow(
            label: '止损',
            value: advice.stopLoss != null
                ? _formatPrice(advice.stopLoss!)
                : '—',
            color: AppTheme.short,
          ),
          _LevelRow(
            label: '止盈',
            value: advice.takeProfit.isEmpty
                ? '—'
                : advice.takeProfit.map(_formatPrice).join(' / '),
            color: AppTheme.long,
          ),
          const SizedBox(height: 12),
          Text(
            advice.reasoning,
            style: const TextStyle(
              fontSize: 12,
              height: 1.5,
              color: AppTheme.textSecondary,
            ),
          ),
          if (advice.risks.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: advice.risks
                  .map(
                    (r) => StatusBadge(
                      label: r,
                      color: AppTheme.neutral,
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  String _zone(List<double>? zone) {
    if (zone == null || zone.length < 2) return '—';
    return '${_formatPrice(zone[0])} – ${_formatPrice(zone[1])}';
  }

  String _formatPrice(double price) {
    if (price >= 1000) return price.toStringAsFixed(2);
    if (price >= 1) return price.toStringAsFixed(4);
    return price.toStringAsFixed(6);
  }
}

class _LevelRow extends StatelessWidget {
  const _LevelRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 56,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 11,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
