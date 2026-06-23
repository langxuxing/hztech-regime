import 'package:flutter/material.dart';

import '../models/board_insights.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class RegimePanel extends StatelessWidget {
  const RegimePanel({super.key, required this.regime});

  final RegimeJudgment regime;

  @override
  Widget build(BuildContext context) {
    final color = _regimeColor(regime.regime);

    return SectionCard(
      title: 'Regime 判断',
      icon: Icons.hub_outlined,
      trailing: StatusBadge(label: regime.label, color: color),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _ConfidenceRing(
                value: regime.confidence,
                color: color,
                label: '置信度',
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SubRegimeRow(label: '波动', value: regime.volRegime),
                    _SubRegimeRow(label: '结构', value: regime.structureRegime),
                    if (regime.rawTrend != null)
                      _SubRegimeRow(label: '融合趋势', value: _trendLabel(regime.rawTrend!)),
                    if (regime.techTrend != null && regime.techTrend != regime.rawTrend)
                      _SubRegimeRow(label: '技术趋势', value: _trendLabel(regime.techTrend!)),
                    if (regime.regimeId != null)
                      _SubRegimeRow(label: 'Regime ID', value: regime.regimeId!),
                    if (regime.nextRegimeLabel != null)
                      _SubRegimeRow(
                        label: '3bar预测',
                        value: regime.nextRegimeLabel!,
                      ),
                    if (regime.changepointProb != null)
                      _SubRegimeRow(
                        label: '变点概率',
                        value: '${(regime.changepointProb! * 100).round()}%',
                      ),
                    if (regime.inRegimeTransition)
                      _SubRegimeRow(label: '切换窗口', value: '是'),
                    if (regime.flowRegime != null)
                      _SubRegimeRow(label: '资金流', value: regime.flowRegime!),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            regime.summary,
            style: const TextStyle(
              fontSize: 12,
              height: 1.55,
              color: AppTheme.textSecondary,
            ),
          ),
          if (regime.triadSummary != null && regime.triadSummary!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.magnet.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.magnet.withValues(alpha: 0.25)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.psychology_outlined, size: 14, color: AppTheme.magnet),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      regime.triadSummary!,
                      style: const TextStyle(fontSize: 11, height: 1.45),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (regime.drivers.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text(
              '驱动因素',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 6),
            ...regime.drivers.map(
              (d) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.chevron_right, size: 14, color: color),
                    Expanded(
                      child: Text(
                        d,
                        style: const TextStyle(fontSize: 11, height: 1.4),
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

  Color _regimeColor(String regime) => switch (regime) {
        'trend_up' => AppTheme.long,
        'trend_down' => AppTheme.short,
        'high_vol' => AppTheme.neutral,
        'range' => AppTheme.accent,
        'macro_frozen_range' => AppTheme.magnet,
        'fake_breakout_wash' => AppTheme.short,
        'high_vol_self_heal' => AppTheme.long,
        _ => AppTheme.magnet,
      };

  String _trendLabel(String t) => switch (t) {
        'uptrend' => '上行',
        'downtrend' => '下行',
        'range' => '震荡',
        _ => t,
      };
}

class _SubRegimeRow extends StatelessWidget {
  const _SubRegimeRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 48,
            child: Text(
              label,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfidenceRing extends StatelessWidget {
  const _ConfidenceRing({
    required this.value,
    required this.color,
    required this.label,
  });

  final double value;
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 72,
      height: 72,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CircularProgressIndicator(
            value: value.clamp(0, 1),
            strokeWidth: 6,
            backgroundColor: AppTheme.surfaceHigh,
            color: color,
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${(value * 100).round()}%',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
              Text(
                label,
                style: const TextStyle(fontSize: 8, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
