import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 价格阶梯：流动性 + GEX 同轴展示。
class LiquidityGexLadderPanel extends StatelessWidget {
  const LiquidityGexLadderPanel({
    super.key,
    required this.data,
  });

  final DashboardData data;

  @override
  Widget build(BuildContext context) {
    final price = data.lastPrice;
    final items = <_LadderItem>[];

    for (final lv in data.liquidityLevels) {
      items.add(
        _LadderItem(
          price: lv.price,
          label: lv.swept ? '流动性✓' : '流动性',
          sub: '${lv.side} · ${lv.strength.toStringAsFixed(1)}',
          color: lv.side == 'buy_side' ? AppTheme.long : AppTheme.short,
          opacity: lv.swept ? 0.45 : 1.0,
          barWidth: (lv.strength * 40).clamp(20, 100),
        ),
      );
    }
    for (final g in data.gexLevels) {
      final maxG = data.gexLevels.isEmpty
          ? 1.0
          : data.gexLevels.map((e) => e.gexNotionalProxy).reduce((a, b) => a > b ? a : b);
      items.add(
        _LadderItem(
          price: g.price,
          label: 'GEX ${g.levelType}',
          sub: _compact(g.gexNotionalProxy),
          color: switch (g.levelType) {
            'support' => AppTheme.long,
            'resistance' => AppTheme.short,
            _ => AppTheme.magnet,
          },
          opacity: 1.0,
          barWidth: (g.gexNotionalProxy / maxG * 100).clamp(15, 100),
        ),
      );
    }

    items.sort((a, b) => b.price.compareTo(a.price));

    return SectionCard(
      title: '流动性 × GEX 价格阶梯',
      icon: Icons.layers_outlined,
      child: items.isEmpty
          ? const Text('暂无流动性/GEX 位', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary))
          : Column(
              children: items.map((item) {
                final dist = price > 0 ? (item.price - price) / price * 100 : 0.0;
                final isNear = dist.abs() < 1.5;
                return Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color: isNear
                        ? item.color.withValues(alpha: 0.12)
                        : AppTheme.surfaceHigh,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isNear ? item.color.withValues(alpha: 0.5) : AppTheme.border,
                    ),
                  ),
                  child: Row(
                    children: [
                      SizedBox(
                        width: item.barWidth,
                        child: LinearProgressIndicator(
                          value: 1,
                          minHeight: 4,
                          borderRadius: BorderRadius.circular(2),
                          backgroundColor: AppTheme.border,
                          color: item.color.withValues(alpha: item.opacity),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${item.price.toStringAsFixed(0)} · ${item.label}',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: item.color.withValues(alpha: item.opacity),
                              ),
                            ),
                            Text(
                              item.sub,
                              style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(2)}%',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: isNear ? FontWeight.w700 : FontWeight.normal,
                          color: dist >= 0 ? AppTheme.long : AppTheme.short,
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
    );
  }

  String _compact(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(0)}K';
    return '\$${v.toStringAsFixed(0)}';
  }
}

class _LadderItem {
  const _LadderItem({
    required this.price,
    required this.label,
    required this.sub,
    required this.color,
    required this.opacity,
    required this.barWidth,
  });

  final double price;
  final String label;
  final String sub;
  final Color color;
  final double opacity;
  final double barWidth;
}
