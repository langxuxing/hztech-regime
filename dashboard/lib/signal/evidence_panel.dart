import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// V2 证据层：GEX 墙体 + 清算 pain 价 + 节点明细。
class EvidencePanel extends StatelessWidget {
  const EvidencePanel({super.key, required this.data});

  final DashboardData data;

  @override
  Widget build(BuildContext context) {
    final snap = data.featureSnapshot;
    final gexEngine = snap != null ? snap['gex_engine'] as Map<String, dynamic>? : null;
    final liquidation =
        snap != null ? snap['liquidation'] as Map<String, dynamic>? : null;
    final relative = snap != null ? snap['relative'] as Map<String, dynamic>? : null;
    final levels = data.gexLevels;

    return SectionCard(
      title: 'GEX / 清算地图',
      icon: Icons.blur_on_rounded,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (gexEngine != null) ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (gexEngine['gamma_wall_call'] != null)
                  MetricChip(
                    label: 'Call Wall',
                    value: _priceWithDist(
                      gexEngine['gamma_wall_call'],
                      relative?['call_wall_pct'],
                    ),
                    color: AppTheme.short,
                  ),
                if (gexEngine['gamma_wall_put'] != null)
                  MetricChip(
                    label: 'Put Wall',
                    value: _priceWithDist(
                      gexEngine['gamma_wall_put'],
                      relative?['put_wall_pct'],
                    ),
                    color: AppTheme.long,
                  ),
                MetricChip(
                  label: '来源',
                  value: (gexEngine['source'] as String?) ?? 'proxy',
                ),
              ],
            ),
            if ((gexEngine['alerts'] as List?)?.isNotEmpty == true) ...[
              const SizedBox(height: 8),
              ...(gexEngine['alerts'] as List).map(
                (a) => Text(
                  '• $a',
                  style: const TextStyle(fontSize: 10, color: AppTheme.neutral),
                ),
              ),
            ],
          ],
          if (liquidation != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: MetricChip(
                    label: 'Pain 清算价',
                    value: liquidation['pain_price'] != null
                        ? _price(liquidation['pain_price'])
                        : '—',
                    color: AppTheme.magnet,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: MetricChip(
                    label: '主导侧',
                    value: liquidation['dominant_side']?.toString() ?? '—',
                  ),
                ),
              ],
            ),
          ],
          if (levels.isNotEmpty) ...[
            const SizedBox(height: 14),
            SizedBox(
              height: 140,
              child: _GexChart(levels: levels, lastPrice: data.lastPrice),
            ),
            const SizedBox(height: 12),
            _GexLevelTable(levels: levels, lastPrice: data.lastPrice),
          ] else
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                '暂无 GEX 节点数据',
                style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
            ),
        ],
      ),
    );
  }

  String _price(dynamic v) {
    if (v == null) return '—';
    final p = (v as num).toDouble();
    return p >= 1000 ? p.toStringAsFixed(0) : p.toStringAsFixed(2);
  }

  String _priceWithDist(dynamic price, dynamic distPct) {
    final p = _price(price);
    if (distPct == null) return p;
    final d = (distPct as num).toDouble();
    return '$p (${d >= 0 ? '+' : ''}${d.toStringAsFixed(2)}%)';
  }
}

class _GexLevelTable extends StatelessWidget {
  const _GexLevelTable({required this.levels, required this.lastPrice});

  final List<GexLevel> levels;
  final double lastPrice;

  @override
  Widget build(BuildContext context) {
    final sorted = [...levels]
      ..sort((a, b) => b.gexNotionalProxy.compareTo(a.gexNotionalProxy));

    return Column(
      children: sorted.take(8).map((lv) {
        final dist = lastPrice > 0 ? (lv.price - lastPrice) / lastPrice * 100 : 0.0;
        final typeLabel = switch (lv.levelType) {
          'support' => '支撑',
          'resistance' => '阻力',
          _ => '磁吸',
        };
        final color = switch (lv.levelType) {
          'support' => AppTheme.long,
          'resistance' => AppTheme.short,
          _ => AppTheme.magnet,
        };
        return Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: AppTheme.surfaceHigh,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AppTheme.border),
          ),
          child: Row(
            children: [
              StatusBadge(label: typeLabel, color: color),
              const SizedBox(width: 8),
              Text(
                lv.price.toStringAsFixed(0),
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              Text(
                '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(2)}%',
                style: TextStyle(fontSize: 11, color: color),
              ),
              const SizedBox(width: 10),
              Text(
                _compact(lv.gexNotionalProxy),
                style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  String _compact(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(0)}K';
    return v.toStringAsFixed(0);
  }
}

class _GexChart extends StatelessWidget {
  const _GexChart({required this.levels, required this.lastPrice});

  final List<GexLevel> levels;
  final double lastPrice;

  @override
  Widget build(BuildContext context) {
    final sorted = [...levels]
      ..sort((a, b) => b.gexNotionalProxy.compareTo(a.gexNotionalProxy));
    final maxY = sorted.first.gexNotionalProxy * 1.15;

    return BarChart(
      BarChartData(
        maxY: maxY,
        gridData: FlGridData(
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) =>
              const FlLine(color: AppTheme.border, strokeWidth: 0.5),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(),
          rightTitles: const AxisTitles(),
          leftTitles: const AxisTitles(),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final i = value.toInt();
                if (i < 0 || i >= sorted.length) return const SizedBox.shrink();
                final dist = lastPrice > 0
                    ? (sorted[i].price - lastPrice) / lastPrice * 100
                    : 0.0;
                return Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '${dist >= 0 ? '+' : ''}${dist.toStringAsFixed(1)}%',
                    style: const TextStyle(fontSize: 8, color: AppTheme.textSecondary),
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
                  width: 12,
                  color: switch (sorted[i].levelType) {
                    'support' => AppTheme.long,
                    'resistance' => AppTheme.short,
                    _ => AppTheme.magnet,
                  },
                  borderRadius: BorderRadius.circular(3),
                ),
              ],
            ),
        ],
      ),
    );
  }
}
