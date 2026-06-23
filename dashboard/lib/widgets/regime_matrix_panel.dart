import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 2×3 Regime 象限矩阵 + HMM 概率条。
class RegimeMatrixPanel extends StatelessWidget {
  const RegimeMatrixPanel({
    super.key,
    required this.data,
  });

  final DashboardData data;

  static const _cells = [
    ('low_vol_uptrend', '低波↑', 0, 0),
    ('high_vol_uptrend', '高波↑', 0, 1),
    ('low_vol_range', '低波↔', 1, 0),
    ('high_vol_range', '高波↔', 1, 1),
    ('low_vol_downtrend', '低波↓', 2, 0),
    ('high_vol_downtrend', '高波↓', 2, 1),
  ];

  @override
  Widget build(BuildContext context) {
    final btc = data.btcRegime;
    final matrix = btc?['matrix'] as Map<String, dynamic>?;
    final hmmProbs = btc?['hmm_probs'] as Map<String, dynamic>? ?? {};
    final current = matrix?['current_cell']?.toString() ??
        matrix?['confirmed_cell']?.toString() ??
        btc?['regime_id']?.toString() ??
        '';
    final confirmed = matrix?['confirmed_cell']?.toString() ?? current;
    final live = matrix?['current_cell']?.toString() ?? current;
    final history = (matrix?['history_points'] as List<dynamic>? ?? []);

    return SectionCard(
      title: '2×3 象限矩阵',
      icon: Icons.grid_on_outlined,
      trailing: live != confirmed
          ? const StatusBadge(label: 'live≠confirmed', color: AppTheme.accent)
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(
                width: 28,
                child: Column(
                  children: [
                    SizedBox(height: 18),
                    _AxisLabel('涨'),
                    SizedBox(height: 28),
                    _AxisLabel('横'),
                    SizedBox(height: 28),
                    _AxisLabel('跌'),
                  ],
                ),
              ),
              Expanded(
                child: Column(
                  children: [
                    const Row(
                      children: [
                        Expanded(child: _ColLabel('低波')),
                        Expanded(child: _ColLabel('高波')),
                      ],
                    ),
                    for (var row = 0; row < 3; row++)
                      Row(
                        children: [
                          for (var col = 0; col < 2; col++)
                            Expanded(
                              child: _MatrixCell(
                                cellId: _cellAt(row, col),
                                isConfirmed: _cellAt(row, col) == confirmed,
                                isLive: _cellAt(row, col) == live && live != confirmed,
                                historyCount: _historyCount(history, _cellAt(row, col)),
                              ),
                            ),
                        ],
                      ),
                  ],
                ),
              ),
            ],
          ),
          if (hmmProbs.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text(
              'HMM 状态概率',
              style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            ...hmmProbs.entries.map((e) {
              final p = (e.value as num?)?.toDouble() ?? 0;
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 110,
                      child: Text(
                        e.key,
                        style: const TextStyle(fontSize: 9),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Expanded(
                      child: LinearProgressIndicator(
                        value: p.clamp(0, 1),
                        minHeight: 6,
                        borderRadius: BorderRadius.circular(3),
                        backgroundColor: AppTheme.border,
                        color: AppTheme.regimeCellColor(e.key),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${(p * 100).round()}%',
                      style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              );
            }),
          ],
        ],
      ),
    );
  }

  static String _cellAt(int row, int col) {
    for (final c in _cells) {
      if (c.$3 == row && c.$4 == col) return c.$1;
    }
    return '';
  }

  static int _historyCount(List<dynamic> history, String cellId) {
    return history.where((p) => (p as Map)['cell'] == cellId).length;
  }
}

class _MatrixCell extends StatelessWidget {
  const _MatrixCell({
    required this.cellId,
    required this.isConfirmed,
    required this.isLive,
    required this.historyCount,
  });

  final String cellId;
  final bool isConfirmed;
  final bool isLive;
  final int historyCount;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.regimeCellColor(cellId);
    final label = RegimeMatrixPanel._cells
        .where((c) => c.$1 == cellId)
        .map((c) => c.$2)
        .firstOrNull ?? cellId;

    return Container(
      height: 52,
      margin: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isConfirmed ? 0.55 : 0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isLive
              ? AppTheme.accent
              : isConfirmed
                  ? color
                  : AppTheme.border,
          width: isConfirmed || isLive ? 2 : 1,
        ),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isConfirmed ? FontWeight.w700 : FontWeight.w500,
                  color: AppTheme.textPrimary,
                ),
              ),
              if (historyCount > 0)
                Text(
                  '$historyCount pts',
                  style: const TextStyle(fontSize: 8, color: AppTheme.textSecondary),
                ),
            ],
          ),
          if (isLive)
            Positioned(
              top: 4,
              right: 4,
              child: Icon(
                Icons.add,
                size: 12,
                color: AppTheme.accent.withValues(alpha: 0.9),
              ),
            ),
        ],
      ),
    );
  }
}

class _AxisLabel extends StatelessWidget {
  const _AxisLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
    );
  }
}

class _ColLabel extends StatelessWidget {
  const _ColLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
      ),
    );
  }
}

extension _FirstOrNull<E> on Iterable<E> {
  E? get firstOrNull {
    final it = iterator;
    if (it.moveNext()) return it.current;
    return null;
  }
}
