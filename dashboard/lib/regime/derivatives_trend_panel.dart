import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// Funding / OI / CVD 衍生品趋势三指标面板。
class DerivativesTrendPanel extends StatelessWidget {
  const DerivativesTrendPanel({
    super.key,
    required this.btcRegime,
    this.derivatives,
  });

  final Map<String, dynamic> btcRegime;
  final Map<String, dynamic>? derivatives;

  @override
  Widget build(BuildContext context) {
    final d = _merged();

    return SectionCard(
      title: '衍生品趋势指标',
      icon: Icons.candlestick_chart_outlined,
      trailing: _voteBadge(d),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_hasTrendFusion()) ...[
            _TrendFusionRow(
              techTrend: btcRegime['tech_trend']?.toString(),
              fusedTrend: btcRegime['raw_trend']?.toString(),
            ),
            const SizedBox(height: 14),
          ],
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 520;
              final cards = [
                _IndicatorCard(
                  title: 'Funding',
                  subtitle: '资金费率',
                  icon: Icons.payments_outlined,
                  value: _fmtFunding(d['funding_rate']),
                  bias: d['funding_bias']?.toString(),
                  note: _findDriver(d, '资金费率'),
                ),
                _IndicatorCard(
                  title: 'Open Interest',
                  subtitle: '持仓量',
                  icon: Icons.stacked_line_chart,
                  value: _fmtOi(d),
                  bias: d['oi_bias']?.toString() ?? _syncToBias(d['oi_price_sync']?.toString()),
                  note: _findDriver(d, 'OI'),
                ),
                _IndicatorCard(
                  title: 'CVD',
                  subtitle: '累计成交量差',
                  icon: Icons.waterfall_chart_outlined,
                  value: _fmtCvd(d),
                  bias: d['cvd_trend']?.toString(),
                  note: _cvdNote(d),
                ),
              ];
              if (wide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (var i = 0; i < cards.length; i++) ...[
                      if (i > 0) const SizedBox(width: 10),
                      Expanded(child: cards[i]),
                    ],
                  ],
                );
              }
              return Column(
                children: [
                  for (var i = 0; i < cards.length; i++) ...[
                    if (i > 0) const SizedBox(height: 10),
                    cards[i],
                  ],
                ],
              );
            },
          ),
          if (_extraSignals(d).isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _extraSignals(d),
            ),
          ],
        ],
      ),
    );
  }

  Map<String, dynamic> _merged() {
    final base = Map<String, dynamic>.from(derivatives ?? {});
    void put(String key) {
      if (base[key] == null && btcRegime[key] != null) {
        base[key] = btcRegime[key];
      }
    }

    for (final key in [
      'funding_rate',
      'funding_bias',
      'open_interest',
      'oi_change_pct',
      'oi_price_sync',
      'oi_bias',
      'cvd_trend',
      'cvd_slope',
      'spot_cvd',
      'spot_cvd_breakout',
      'cvd_bullish_divergence',
      'derivative_votes_bull',
      'derivative_votes_bear',
      'drivers',
    ]) {
      put(key);
    }

    final nested = btcRegime['derivatives_trend'];
    if (nested is Map<String, dynamic>) {
      for (final e in nested.entries) {
        base.putIfAbsent(e.key, () => e.value);
      }
    }
    return base;
  }

  bool _hasTrendFusion() =>
      btcRegime['tech_trend'] != null && btcRegime['raw_trend'] != null;

  Widget? _voteBadge(Map<String, dynamic> d) {
    final bull = d['derivative_votes_bull'];
    final bear = d['derivative_votes_bear'];
    if (bull == null && bear == null) return null;
    return StatusBadge(
      label: '多${bull ?? 0} / 空${bear ?? 0}',
      color: AppTheme.magnet,
    );
  }

  String _fmtFunding(dynamic rate) {
    if (rate == null) return '—';
    final pct = (rate as num).toDouble() * 100;
    return '${pct.toStringAsFixed(4)}%';
  }

  String _fmtOi(Map<String, dynamic> d) {
    final oi = d['open_interest'];
    final chg = d['oi_change_pct'];
    if (oi == null && chg == null) return '—';
    final oiStr = oi != null ? _compactNum(oi as num) : '';
    final chgStr = chg != null ? 'Δ${(chg as num).toStringAsFixed(1)}%' : '';
    return [oiStr, chgStr].where((s) => s.isNotEmpty).join(' · ');
  }

  String _fmtCvd(Map<String, dynamic> d) {
    final trend = d['cvd_trend']?.toString();
    final spot = d['spot_cvd'];
    if (trend == null && spot == null) return '—';
    final parts = <String>[];
    if (trend != null && trend != 'neutral') {
      parts.add(_biasLabel(trend));
    } else if (trend != null) {
      parts.add('中性');
    }
    if (spot != null) {
      parts.add('值 ${_compactNum(spot as num)}');
    }
    return parts.isEmpty ? '—' : parts.join(' · ');
  }

  String? _findDriver(Map<String, dynamic> d, String keyword) {
    final drivers = (d['drivers'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .where((s) => s.contains(keyword))
        .toList();
    return drivers.isNotEmpty ? drivers.first : null;
  }

  String? _cvdNote(Map<String, dynamic> d) {
    if (d['spot_cvd_breakout'] == true) return '现货 CVD 突破确认';
    if (d['cvd_bullish_divergence'] == true) return '5m CVD 底背离';
    return _findDriver(d, 'CVD');
  }

  String? _syncToBias(String? sync) => switch (sync) {
        'long_build' => 'bullish',
        'short_build' => 'bearish',
        'unwind' => 'neutral',
        _ => null,
      };

  List<Widget> _extraSignals(Map<String, dynamic> d) {
    final chips = <Widget>[];
    final sync = d['oi_price_sync']?.toString();
    if (sync != null && sync != 'neutral') {
      chips.add(MetricChip(
        label: 'OI 联动',
        value: _syncLabel(sync),
        color: _syncColor(sync),
      ));
    }
    if (d['spot_cvd_breakout'] == true) {
      chips.add(const MetricChip(label: 'CVD', value: '突破确认', color: AppTheme.long));
    }
    if (d['cvd_bullish_divergence'] == true) {
      chips.add(const MetricChip(label: 'CVD', value: '底背离', color: AppTheme.long));
    }
    return chips;
  }

  String _compactNum(num v) {
    final a = v.abs().toDouble();
    if (a >= 1e9) return '${(v / 1e9).toStringAsFixed(2)}B';
    if (a >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M';
    if (a >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }

  String _biasLabel(String bias) => switch (bias) {
        'bullish' => '看多',
        'bearish' => '看空',
        'uptrend' => '上行',
        'downtrend' => '下行',
        'range' => '震荡',
        _ => bias,
      };

  String _syncLabel(String sync) => switch (sync) {
        'long_build' => '多头增仓',
        'short_build' => '空头增仓',
        'unwind' => '减仓离场',
        _ => sync,
      };

  Color _syncColor(String sync) => switch (sync) {
        'long_build' => AppTheme.long,
        'short_build' => AppTheme.short,
        _ => AppTheme.magnet,
      };
}

class _TrendFusionRow extends StatelessWidget {
  const _TrendFusionRow({this.techTrend, this.fusedTrend});

  final String? techTrend;
  final String? fusedTrend;

  @override
  Widget build(BuildContext context) {
    final changed = techTrend != fusedTrend;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          const Icon(Icons.merge_type, size: 14, color: AppTheme.textSecondary),
          const SizedBox(width: 8),
          Text(
            '技术 ${_trendLabel(techTrend)}',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Icon(Icons.arrow_forward, size: 14, color: AppTheme.accent),
          ),
          Text(
            '融合 ${_trendLabel(fusedTrend)}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: changed ? AppTheme.accent : AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  String _trendLabel(String? t) => switch (t) {
        'uptrend' => '上行',
        'downtrend' => '下行',
        'range' => '震荡',
        _ => t ?? '—',
      };
}

class _IndicatorCard extends StatelessWidget {
  const _IndicatorCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.value,
    this.bias,
    this.note,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final String value;
  final String? bias;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final color = _biasColor(bias);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              if (bias != null && bias != 'neutral')
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    _biasLabel(bias!),
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            value,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: value == '—' ? AppTheme.textSecondary : color,
            ),
          ),
          if (note != null && note!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              note!,
              style: const TextStyle(fontSize: 10, height: 1.4, color: AppTheme.textSecondary),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }

  String _biasLabel(String bias) => switch (bias) {
        'bullish' => '看多',
        'bearish' => '看空',
        _ => '中性',
      };

  Color _biasColor(String? bias) => switch (bias) {
        'bullish' => AppTheme.long,
        'bearish' => AppTheme.short,
        _ => AppTheme.textSecondary,
      };
}
