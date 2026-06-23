import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// OI / CVD / 费率 / ETF 等衍生品与资金流条带。
class DerivativesFlowStrip extends StatelessWidget {
  const DerivativesFlowStrip({
    super.key,
    required this.data,
    this.brief,
  });

  final DashboardData data;
  final Map<String, dynamic>? brief;

  @override
  Widget build(BuildContext context) {
    final btc = data.btcRegime;
    final micro = data.pipeline?['layers']?['ingestion']?['microstructure'] as Map<String, dynamic>?;
    final macro = data.pipeline?['layers']?['ingestion']?['macro_flow'] as Map<String, dynamic>?;
    final deriv = brief?['derivatives'] as Map<String, dynamic>? ?? {};

    final oi = deriv['oi_change_pct'] ?? micro?['oi_change_pct'] ?? btc?['oi_change_pct'];
    final funding = deriv['funding_rate'] ?? micro?['funding_rate'] ?? btc?['funding_rate'];
    final cvd = deriv['cvd_trend'] ?? micro?['cvd_trend'] ?? btc?['cvd_trend'];
    final etfZ = macro?['etf_flow_zscore'];
    final etf7d = macro?['etf_7d_usd'] ?? data.capitalFlows?.btcEtf?.total7dUsd;
    final cvdBreak = deriv['spot_cvd_breakout'] == true || btc?['spot_cvd_breakout'] == true;

    return SectionCard(
      title: '衍生品 & 资金流',
      icon: Icons.swap_horiz_rounded,
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          if (oi != null)
            MetricChip(
              label: 'OI 变化',
              value: '${(oi as num) >= 0 ? '+' : ''}${(oi as num).toStringAsFixed(1)}%',
              color: (oi as num) >= 0 ? AppTheme.long : AppTheme.short,
            ),
          if (funding != null)
            MetricChip(
              label: '资金费率',
              value: (funding as num).toStringAsFixed(4),
              color: (funding as num) >= 0 ? AppTheme.long : AppTheme.short,
            ),
          if (cvd != null)
            MetricChip(
              label: 'CVD',
              value: cvdBreak ? '真突破' : cvd.toString(),
              color: cvd.toString().contains('bull') || cvdBreak ? AppTheme.long : AppTheme.textSecondary,
            ),
          if (etfZ != null)
            MetricChip(
              label: 'ETF Z',
              value: (etfZ as num).toStringAsFixed(2),
              color: (etfZ as num) >= 0 ? AppTheme.long : AppTheme.short,
            ),
          if (etf7d != null)
            MetricChip(
              label: 'ETF 7D',
              value: _fmtUsd(etf7d as num),
              color: (etf7d as num) >= 0 ? AppTheme.long : AppTheme.short,
            ),
          if (data.volStatus != null)
            MetricChip(label: 'Vol', value: data.volStatus!),
        ],
      ),
    );
  }

  String _fmtUsd(num v) {
    final n = v.toDouble();
    if (n.abs() >= 1e9) return '\$${(n / 1e9).toStringAsFixed(2)}B';
    if (n.abs() >= 1e6) return '\$${(n / 1e6).toStringAsFixed(0)}M';
    return '\$${n.toStringAsFixed(0)}';
  }
}
