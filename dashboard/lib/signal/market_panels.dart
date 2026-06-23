import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class LiquidityPanel extends StatelessWidget {
  const LiquidityPanel({
    super.key,
    required this.levels,
    required this.lastPrice,
  });

  final List<LiquidityLevel> levels;
  final double lastPrice;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '流动性清洗地图',
      icon: Icons.water_drop_outlined,
      child: levels.isEmpty
          ? const Text(
              '无显著流动性位',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            )
          : Column(
              children: levels.map((lv) {
                final dist = lastPrice > 0
                    ? (lv.price - lastPrice) / lastPrice * 100
                    : 0.0;
                final sideColor =
                    lv.side == 'buy_side' ? AppTheme.long : AppTheme.short;
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
                      StatusBadge(
                        label: lv.swept ? '已清洗' : '待清洗',
                        color: lv.swept ? AppTheme.textSecondary : AppTheme.neutral,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              lv.price.toStringAsFixed(2),
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              '${lv.side} · strength ${lv.strength.toStringAsFixed(2)}',
                              style: const TextStyle(
                                fontSize: 10,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(2)}%',
                        style: TextStyle(fontSize: 12, color: sideColor),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
    );
  }
}

class GexPanel extends StatelessWidget {
  const GexPanel({
    super.key,
    required this.levels,
    required this.lastPrice,
  });

  final List<GexLevel> levels;
  final double lastPrice;

  @override
  Widget build(BuildContext context) {
    final sorted = [...levels]
      ..sort((a, b) => b.gexNotionalProxy.compareTo(a.gexNotionalProxy));
    final maxGex = sorted.isEmpty
        ? 1.0
        : sorted.first.gexNotionalProxy;

    return SectionCard(
      title: 'GEX 代理层',
      icon: Icons.blur_on_rounded,
      child: sorted.isEmpty
          ? const Text(
              '暂无 GEX 节点',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            )
          : SizedBox(
              height: 160,
              child: BarChart(
                BarChartData(
                  alignment: BarChartAlignment.spaceAround,
                  maxY: maxGex * 1.15,
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    getDrawingHorizontalLine: (_) => const FlLine(
                      color: AppTheme.border,
                      strokeWidth: 0.5,
                    ),
                  ),
                  borderData: FlBorderData(show: false),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(),
                    rightTitles: const AxisTitles(),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 42,
                        getTitlesWidget: (value, _) => Text(
                          _compact(value),
                          style: const TextStyle(
                            fontSize: 9,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          final i = meta.appliedInterval == 0
                              ? value.toInt()
                              : value.toInt();
                          if (i < 0 || i >= sorted.length) {
                            return const SizedBox.shrink();
                          }
                          final dist = lastPrice > 0
                              ? (sorted[i].price - lastPrice) /
                                  lastPrice *
                                  100
                              : 0.0;
                          return Padding(
                            padding: const EdgeInsets.only(top: 6),
                            child: Text(
                              '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(1)}%',
                              style: const TextStyle(
                                fontSize: 9,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ),
                  barGroups: [
                    for (var i = 0; i < sorted.length; i++)
                      BarChartGroupData(
                        x: i,
                        barRods: [
                          BarChartRodData(
                            toY: sorted[i].gexNotionalProxy,
                            width: 14,
                            borderRadius: BorderRadius.circular(4),
                            color: _levelColor(sorted[i].levelType),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
    );
  }

  Color _levelColor(String type) => switch (type) {
        'support' => AppTheme.long,
        'resistance' => AppTheme.short,
        _ => AppTheme.magnet,
      };

  String _compact(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(0)}K';
    return v.toStringAsFixed(0);
  }
}

class OrderbookPanel extends StatelessWidget {
  const OrderbookPanel({super.key, required this.orderbook});

  final OrderBookSnapshot orderbook;

  @override
  Widget build(BuildContext context) {
    final total = orderbook.bidDepthUsdt + orderbook.askDepthUsdt;
    final bidPct = total > 0 ? orderbook.bidDepthUsdt / total : 0.5;

    return SectionCard(
      title: '订单簿',
      icon: Icons.swap_vert_rounded,
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: 'Spread',
                  value: '${orderbook.spreadBps.toStringAsFixed(2)} bps',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: 'Imbalance',
                  value: orderbook.imbalance.toStringAsFixed(3),
                  color: orderbook.imbalance >= 0 ? AppTheme.long : AppTheme.short,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: SizedBox(
              height: 10,
              child: Row(
                children: [
                  Expanded(
                    flex: (bidPct * 100).round().clamp(1, 99),
                    child: Container(color: AppTheme.long.withValues(alpha: 0.7)),
                  ),
                  Expanded(
                    flex: ((1 - bidPct) * 100).round().clamp(1, 99),
                    child: Container(color: AppTheme.short.withValues(alpha: 0.7)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Bid ${_compact(orderbook.bidDepthUsdt)}',
                style: const TextStyle(fontSize: 11, color: AppTheme.long),
              ),
              Text(
                'Ask ${_compact(orderbook.askDepthUsdt)}',
                style: const TextStyle(fontSize: 11, color: AppTheme.short),
              ),
            ],
          ),
          if (orderbook.walls.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...orderbook.walls.map((wall) {
              final side = wall['side']?.toString() ?? '';
              final price = (wall['price'] as num?)?.toDouble();
              final size = (wall['size_usdt'] as num?)?.toDouble();
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    StatusBadge(
                      label: side.toUpperCase(),
                      color: side == 'bid' ? AppTheme.long : AppTheme.short,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      price?.toStringAsFixed(2) ?? '—',
                      style: const TextStyle(fontSize: 12),
                    ),
                    const Spacer(),
                    Text(
                      _compact(size ?? 0),
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondary,
                      ),
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

  String _compact(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }
}

class VolatilityPanel extends StatelessWidget {
  const VolatilityPanel({
    super.key,
    required this.volRatio,
    required this.volStatus,
    required this.ohlcvSummary,
  });

  final double? volRatio;
  final String? volStatus;
  final Map<String, dynamic> ohlcvSummary;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '市场概览',
      icon: Icons.insights_outlined,
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: 'Vol Ratio',
                  value: volRatio?.toStringAsFixed(3) ?? 'N/A',
                  color: AppTheme.magnet,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: 'Vol 状态',
                  value: volStatus ?? 'N/A',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: ohlcvSummary.entries.map((e) {
              return MetricChip(
                label: e.key,
                value: e.value.toString(),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
