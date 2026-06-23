import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/capital_flows.dart';
import '../models/dashboard_data.dart';
import '../bigevent/event_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

class RadarOverviewBar extends StatelessWidget {
  const RadarOverviewBar({
    super.key,
    required this.data,
    this.events,
  });

  final DashboardData data;
  final EventAnalysisData? events;

  @override
  Widget build(BuildContext context) {
    final board = data.board;
    final regimeColor = _regimeColor(board.regime.regime);
    final trendColor = _trendColor(board.trend.direction);
    final risk = events?.summary.overallRisk ?? _riskFromRegime(data);
    final riskColor = _riskColor(risk);
    final nextEvent = _nextEventLabel(events);
    final etfChip = _etfChip(data.capitalFlows);
    final onchainChip = _onchainChip(data.capitalFlows);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.surfaceHigh,
            regimeColor.withValues(alpha: 0.08),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.radar_rounded, color: regimeColor, size: 20),
              const SizedBox(width: 8),
              Text(
                '金融雷达',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: regimeColor,
                  letterSpacing: 0.5,
                ),
              ),
              const Spacer(),
              if (data.macroHazardFlag)
                const StatusBadge(
                  label: '宏观熔断',
                  color: AppTheme.short,
                ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _Chip(
                label: 'Regime',
                value: board.regime.label,
                sub: '${(board.regime.confidence * 100).round()}%',
                color: regimeColor,
              ),
              _Chip(
                label: '风险',
                value: _riskLabel(risk),
                color: riskColor,
              ),
              _Chip(
                label: '走势',
                value: board.trend.label,
                sub: board.trend.shortTerm,
                color: trendColor,
              ),
              if (etfChip != null) etfChip,
              if (onchainChip != null) onchainChip,
              if (data.quantState != null)
                _Chip(
                  label: '状态机',
                  value: data.quantState!['diagnosis']?.toString() ?? '—',
                  sub: data.quantState!['score_label']?.toString(),
                  color: AppTheme.accent,
                ),
            ],
          ),
          if (nextEvent != null) ...[
            const SizedBox(height: 10),
            Text(
              nextEvent,
              style: const TextStyle(
                fontSize: 11,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }

  _Chip? _etfChip(CapitalFlowsSnapshot? cf) {
    final etf = cf?.btcEtf ?? cf?.ethEtf;
    final latest = etf?.latest;
    if (latest == null) return null;
    final bullish = latest.flowUsd >= 0;
    return _Chip(
      label: 'ETF',
      value: formatUsdCompact(latest.flowUsd, showSign: true),
      sub: etf!.asset,
      color: bullish ? AppTheme.long : AppTheme.short,
    );
  }

  _Chip? _onchainChip(CapitalFlowsSnapshot? cf) {
    final w = cf?.btcExchangeWallet;
    if (w?.netToExchange1d == null) {
      final oc = cf?.btcOnchain;
      if (oc?.volumeChange7dPct == null) return null;
      final rising = (oc!.volumeChange7dPct ?? 0) >= 0;
      return _Chip(
        label: '链上',
        value:
            '${oc.volumeChange7dPct! >= 0 ? '+' : ''}${oc.volumeChange7dPct!.toStringAsFixed(1)}% 7d',
        sub: '成交额',
        color: rising ? AppTheme.long : AppTheme.short,
      );
    }
    final net = w!.netToExchange1d!;
    final inbound = net >= 0;
    return _Chip(
      label: '链上',
      value: inbound ? '流入所' : '流出所',
      sub: '${net >= 0 ? '+' : ''}${net.toStringAsFixed(0)} BTC',
      color: inbound ? AppTheme.short : AppTheme.long,
    );
  }

  String? _nextEventLabel(EventAnalysisData? ev) {
    if (ev == null || ev.upcomingHighImpact.isEmpty) return null;
    final e = ev.upcomingHighImpact.first;
    final when = e.scheduledAt ?? e.publishedAt;
    final rel = _relativeTime(when);
    return '下一事件: ${e.title}${rel != null ? ' · $rel' : ''}';
  }

  String? _relativeTime(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = dt.difference(DateTime.now());
      if (diff.isNegative) return '进行中';
      if (diff.inHours >= 1) return 'T-${diff.inHours}h';
      if (diff.inMinutes >= 1) return 'T-${diff.inMinutes}m';
      return '即将';
    } catch (_) {
      return null;
    }
  }

  String _riskFromRegime(DashboardData data) {
    if (data.macroHazardFlag) return 'elevated';
    if (data.volStatus == 'elevated' || data.volStatus == 'high') {
      return 'elevated';
    }
    return 'low';
  }

  String _riskLabel(String r) => switch (r) {
        'elevated' => '偏高',
        'bearish' => '偏空',
        'bullish' => '偏多',
        'mixed' => '混合',
        _ => '正常',
      };

  Color _riskColor(String r) => switch (r) {
        'elevated' => AppTheme.short,
        'bearish' => AppTheme.short,
        'bullish' => AppTheme.long,
        'mixed' => AppTheme.neutral,
        _ => AppTheme.accent,
      };

  Color _regimeColor(String r) => switch (r) {
        'trend_up' => AppTheme.long,
        'trend_down' => AppTheme.short,
        'high_vol' => AppTheme.neutral,
        'macro_frozen_range' => AppTheme.magnet,
        'fake_breakout_wash' => AppTheme.short,
        'high_vol_self_heal' => AppTheme.long,
        _ => AppTheme.accent,
      };

  Color _trendColor(String d) => switch (d) {
        'up' => AppTheme.long,
        'down' => AppTheme.short,
        _ => AppTheme.neutral,
      };
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.value,
    this.sub,
    required this.color,
  });

  final String label;
  final String value;
  final String? sub;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary)),
          Text(
            value,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color),
          ),
          if (sub != null)
            Text(sub!, style: TextStyle(fontSize: 9, color: color.withValues(alpha: 0.8))),
        ],
      ),
    );
  }
}

String formatRadarTime(String iso) {
  try {
    return DateFormat('MM-dd HH:mm').format(DateTime.parse(iso).toLocal());
  } catch (_) {
    return iso.length > 16 ? iso.substring(0, 16) : iso;
  }
}
