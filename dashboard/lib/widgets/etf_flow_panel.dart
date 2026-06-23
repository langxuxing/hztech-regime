import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../models/capital_flows.dart';
import '../theme/app_theme.dart';
import 'common.dart';

class EtfFlowPanel extends StatelessWidget {
  const EtfFlowPanel({super.key, this.flows});

  final CapitalFlowsSnapshot? flows;

  @override
  Widget build(BuildContext context) {
    final btc = flows?.btcEtf;
    final eth = flows?.ethEtf;

    return SectionCard(
      title: 'ETF 资金',
      icon: Icons.account_balance_outlined,
      trailing: flows != null
          ? StatusBadge(
              label: flows!.dataQuality,
              color: flows!.hasEtfData ? AppTheme.long : AppTheme.neutral,
            )
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (btc != null) ...[
            _EtfBlock(snapshot: btc),
            if (eth != null) const SizedBox(height: 14),
          ],
          if (eth != null) _EtfBlock(snapshot: eth),
          if (btc == null && eth == null) _emptyHint(flows),
        ],
      ),
    );
  }

  Widget _emptyHint(CapitalFlowsSnapshot? cf) {
    return Text(
      cf == null
          ? '暂无 ETF 数据。BTC 将自动爬取 Farside；ETH 需 COINGLASS_API_KEY 或本地 CSV。'
          : 'ETF 数据源暂不可用',
      style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
    );
  }
}

class _EtfBlock extends StatelessWidget {
  const _EtfBlock({required this.snapshot});

  final EtfFlowSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final latest = snapshot.latest;
    if (latest == null) {
      return Text(
        '${snapshot.asset} ETF：无数据',
        style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
      );
    }

    final flowColor = latest.flowUsd >= 0 ? AppTheme.long : AppTheme.short;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              '${snapshot.asset} Spot ETF',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const Spacer(),
            Text(
              latest.date,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            MetricChip(
              label: '最新日净流',
              value: formatUsdCompact(latest.flowUsd, showSign: true),
              color: flowColor,
            ),
            if (snapshot.total7dUsd != null)
              MetricChip(
                label: '7 日累计',
                value: formatUsdCompact(snapshot.total7dUsd!, showSign: true),
                color: (snapshot.total7dUsd ?? 0) >= 0 ? AppTheme.long : AppTheme.short,
              ),
            if (snapshot.total30dUsd != null)
              MetricChip(
                label: '30 日累计',
                value: formatUsdCompact(snapshot.total30dUsd!, showSign: true),
              ),
            if (snapshot.total13wUsd != null)
              MetricChip(
                label: '近 13 周',
                value: formatUsdCompact(snapshot.total13wUsd!, showSign: true),
                color: (snapshot.total13wUsd ?? 0) >= 0 ? AppTheme.long : AppTheme.short,
              ),
          ],
        ),
        if (snapshot.history.length > 1) ...[
          const SizedBox(height: 12),
          const Text(
            '近 7 日',
            style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 72,
            child: _EtfHistoryChart(history: snapshot.history),
          ),
        ],
        if (snapshot.weeklyHistory.length > 1) ...[
          const SizedBox(height: 12),
          const Text(
            '近 3 个月（按周）',
            style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 96,
            child: _EtfWeeklyChart(weekly: snapshot.weeklyHistory),
          ),
        ],
        if (latest.tickers.isNotEmpty) ...[
          const SizedBox(height: 10),
          ...latest.tickers.take(5).map((t) {
            final c = t.flowUsd >= 0 ? AppTheme.long : AppTheme.short;
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  SizedBox(
                    width: 48,
                    child: Text(
                      t.ticker,
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                    ),
                  ),
                  Expanded(
                    child: LinearProgressIndicator(
                      value: _tickerBar(snapshot.latest!.tickers, t.flowUsd),
                      backgroundColor: AppTheme.border,
                      color: c.withValues(alpha: 0.7),
                      minHeight: 4,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    formatUsdCompact(t.flowUsd, showSign: true),
                    style: TextStyle(fontSize: 10, color: c),
                  ),
                ],
              ),
            );
          }),
        ],
        if (snapshot.interpretation.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            snapshot.interpretation,
            style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
        ],
      ],
    );
  }

  double _tickerBar(List<EtfTickerFlow> tickers, double flow) {
    final max = tickers.map((t) => t.flowUsd.abs()).fold<double>(0, (a, b) => a > b ? a : b);
    if (max <= 0) return 0;
    return (flow.abs() / max).clamp(0.05, 1.0);
  }
}

class _EtfHistoryChart extends StatelessWidget {
  const _EtfHistoryChart({required this.history});

  final List<EtfFlowDay> history;

  @override
  Widget build(BuildContext context) {
    final maxY = history.map((d) => d.flowUsd.abs()).fold<double>(0, (a, b) => a > b ? a : b) * 1.2;
    if (maxY <= 0) return const SizedBox.shrink();

    return BarChart(
      BarChartData(
        maxY: maxY,
        minY: -maxY,
        gridData: FlGridData(
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) => const FlLine(color: AppTheme.border, strokeWidth: 0.5),
        ),
        borderData: FlBorderData(show: false),
        titlesData: const FlTitlesData(
          topTitles: AxisTitles(),
          rightTitles: AxisTitles(),
          leftTitles: AxisTitles(),
        ),
        barGroups: [
          for (var i = 0; i < history.length; i++)
            BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  fromY: history[i].flowUsd >= 0 ? 0 : history[i].flowUsd,
                  toY: history[i].flowUsd >= 0 ? history[i].flowUsd : 0,
                  width: 10,
                  color: history[i].flowUsd >= 0 ? AppTheme.long : AppTheme.short,
                  borderRadius: BorderRadius.circular(2),
                ),
              ],
            ),
        ],
      ),
    );
  }
}

class _EtfWeeklyChart extends StatelessWidget {
  const _EtfWeeklyChart({required this.weekly});

  final List<EtfFlowWeek> weekly;

  @override
  Widget build(BuildContext context) {
    final maxY = weekly.map((w) => w.flowUsd.abs()).fold<double>(0, (a, b) => a > b ? a : b) * 1.2;
    if (maxY <= 0) return const SizedBox.shrink();

    return BarChart(
      BarChartData(
        maxY: maxY,
        minY: -maxY,
        gridData: FlGridData(
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) => const FlLine(color: AppTheme.border, strokeWidth: 0.5),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(),
          rightTitles: const AxisTitles(),
          leftTitles: const AxisTitles(),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 18,
              interval: 1,
              getTitlesWidget: (value, meta) {
                final i = value.round();
                if (i < 0 || i >= weekly.length) return const SizedBox.shrink();
                final label = weekly[i].label.split('-W').last;
                return Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'W$label',
                    style: const TextStyle(fontSize: 8, color: AppTheme.textSecondary),
                  ),
                );
              },
            ),
          ),
        ),
        barGroups: [
          for (var i = 0; i < weekly.length; i++)
            BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  fromY: weekly[i].flowUsd >= 0 ? 0 : weekly[i].flowUsd,
                  toY: weekly[i].flowUsd >= 0 ? weekly[i].flowUsd : 0,
                  width: 8,
                  color: weekly[i].flowUsd >= 0 ? AppTheme.long : AppTheme.short,
                  borderRadius: BorderRadius.circular(2),
                ),
              ],
            ),
        ],
      ),
    );
  }
}
