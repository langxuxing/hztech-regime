import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../widgets/etf_flow_panel.dart';
import '../widgets/onchain_panel.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import '../widgets/common.dart';
import '../regime/derivatives_trend_panel.dart';
import '../signal/market_panels.dart';
import '../theme/app_theme.dart';

/// L1 多源数据输入层界面。
class L1IngestionTab extends StatelessWidget {
  const L1IngestionTab({
    super.key,
    required this.data,
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
    this.embedded = false,
  });

  final DashboardData data;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;
  final bool embedded;

  @override
  Widget build(BuildContext context) {
    final content = _buildContent();
    if (embedded) return content;
    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: content,
    );
  }

  Widget _buildContent() {
    final l1 = data.pipeline?['layers']?['ingestion'] as Map<String, dynamic>?;
    final market = l1?['market'] as Map<String, dynamic>?;
    final vol = l1?['volatility'] as Map<String, dynamic>?;
    final micro = l1?['microstructure'] as Map<String, dynamic>?;
    final macro = l1?['macro_flow'] as Map<String, dynamic>?;
    final transform = l1?['transform'] as Map<String, dynamic>?;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
          SectionCard(
            title: '特征变频清洗',
            icon: Icons.cleaning_services_outlined,
            child: _kvGrid([
              if (transform != null) ...[
                _KV('confirmed bars', '${transform['confirmed_bars']}'),
                _KV('剔除未收盘', transform['dropped_unclosed'] == true ? '是' : '否'),
              ],
            ]),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '市场价格与技术',
            icon: Icons.candlestick_chart_outlined,
            child: _kvGrid([
              if (market != null) ...[
                _KV('收盘', '${market['close']}'),
                _KV('KAMA', '${market['kama']?.toStringAsFixed(0) ?? '—'}'),
                _KV('唐奇安上', '${market['donchian_upper']?.toStringAsFixed(0) ?? '—'}'),
                _KV('唐奇安下', '${market['donchian_lower']?.toStringAsFixed(0) ?? '—'}'),
                _KV('SMC', '${market['smc_trend'] ?? '—'}'),
              ],
            ]),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '波动率特征',
            icon: Icons.show_chart_outlined,
            child: _kvGrid([
              if (vol != null) ...[
                _KV('VR 波动比', vol['vol_ratio']?.toString() ?? '—'),
                _KV('GK 实现波', vol['gk_realized_vol']?.toString() ?? '—'),
                _KV('DVOL 领先', vol['dvol_leads_gk'] == true ? '是' : '否'),
              ] else ...[
                _KV('VR', data.volRatio?.toString() ?? '—'),
                _KV('状态', data.volStatus ?? '—'),
              ],
            ]),
          ),
          const SizedBox(height: 16),
          if (data.btcRegime != null) ...[
            DerivativesTrendPanel(
              btcRegime: data.btcRegime!,
              derivatives: data.board.regime.derivatives,
            ),
            const SizedBox(height: 16),
          ],
          SectionCard(
            title: '微观结构与杠杆',
            icon: Icons.bolt_outlined,
            child: _kvGrid([
              if (micro != null) ...[
                _KV('资金费率', micro['funding_rate']?.toString() ?? '—'),
                _KV('OI 变化', '${micro['oi_change_pct'] ?? '—'}%'),
                _KV('CVD 趋势', micro['cvd_trend']?.toString() ?? '—'),
                _KV('强平脉冲', micro['liquidation_pulse']?['extreme_pulse'] == true ? '极端' : '正常'),
              ],
            ]),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: '跨市场慢变量',
            icon: Icons.public_outlined,
            child: _kvGrid([
              if (macro != null) ...[
                _KV('ETF z-score', macro['etf_flow_zscore']?.toString() ?? '—'),
                _KV('ETF 7D', _fmtUsd(macro['etf_7d_usd'])),
                _KV('宏观熔断', macro['macro_hazard'] == true ? '是' : '否'),
              ],
            ]),
          ),
          const SizedBox(height: 16),
          EtfFlowPanel(flows: data.capitalFlows),
          const SizedBox(height: 16),
          OnChainPanel(flows: data.capitalFlows),
          const SizedBox(height: 16),
          VolatilityPanel(
            volRatio: data.volRatio,
            volStatus: data.volStatus,
            ohlcvSummary: data.ohlcvSummary,
          ),
        ],
    );
  }

  static String _fmtUsd(dynamic v) {
    if (v == null) return '—';
    final n = (v as num).toDouble();
    if (n.abs() >= 1e9) return '\$${(n / 1e9).toStringAsFixed(2)}B';
    if (n.abs() >= 1e6) return '\$${(n / 1e6).toStringAsFixed(1)}M';
    return '\$${n.toStringAsFixed(0)}';
  }
}

class _KV {
  const _KV(this.k, this.v);
  final String k;
  final String v;
}

Widget _kvGrid(List<_KV> items) {
  return Wrap(
    spacing: 16,
    runSpacing: 8,
    children: items
        .map(
          (e) => SizedBox(
            width: 140,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(e.k, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                Text(e.v, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        )
        .toList(),
  );
}
