import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// PDF 量化状态机：三因子得分 + 系统路由 + SOP。
class QuantStatePanel extends StatelessWidget {
  const QuantStatePanel({super.key, required this.quantState});

  final Map<String, dynamic> quantState;

  @override
  Widget build(BuildContext context) {
    final diagnosis = quantState['diagnosis']?.toString() ?? '—';
    final scoreLabel = quantState['score_label']?.toString() ?? '';
    final commands = (quantState['system_commands'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();
    final policy = quantState['weekly_policy'] as Map<String, dynamic>? ?? {};
    final dailySop = quantState['daily_sop'] as List<dynamic>? ?? [];
    final bounds = quantState['boundaries'] as Map<String, dynamic>? ?? {};
    final okx = quantState['okx_strategy'] as Map<String, dynamic>?;

    return SectionCard(
      title: '量化状态机',
      icon: Icons.account_tree_outlined,
      trailing: StatusBadge(label: diagnosis, color: AppTheme.accent),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            scoreLabel,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
              letterSpacing: 0.3,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ScoreChip(label: 'Macro', value: quantState['macro_score']),
              _ScoreChip(label: 'Flow', value: quantState['flow_score']),
              _ScoreChip(label: 'Gex', value: quantState['gex_score']),
              MetricChip(
                label: '事件风险',
                value: quantState['event_risk']?.toString() ?? '—',
                color: _eventColor(quantState['event_risk']?.toString()),
              ),
            ],
          ),
          if (bounds['upper_price'] != null || bounds['lower_price'] != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                if (bounds['upper_price'] != null)
                  Expanded(
                    child: MetricChip(
                      label: 'GEX 阻力',
                      value: _price(bounds['upper_price']),
                      color: AppTheme.short,
                    ),
                  ),
                if (bounds['lower_price'] != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricChip(
                      label: '清算池',
                      value: _price(bounds['lower_price']),
                      color: AppTheme.long,
                    ),
                  ),
                ],
              ],
            ),
            if (bounds['range_pct'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  'RANGE ${bounds['range_pct']}%',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                ),
              ),
          ],
          if (commands.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text(
              '系统指令',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 6),
            ...commands.map(
              (c) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('› ', style: TextStyle(color: AppTheme.accent, fontSize: 12)),
                    Expanded(
                      child: Text(
                        c,
                        style: const TextStyle(fontSize: 12, height: 1.4, color: AppTheme.textSecondary),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (policy.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                MetricChip(
                  label: 'CTA',
                  value: _modeLabel(policy['cta_mode']?.toString()),
                ),
                MetricChip(
                  label: '网格',
                  value: _gridLabel(policy['grid_mode']?.toString()),
                ),
                if (policy['var_limit_pct'] != null)
                  MetricChip(
                    label: 'VaR 上限',
                    value: '${policy['var_limit_pct']}%',
                  ),
              ],
            ),
          ],
          if (okx != null) ...[
            const SizedBox(height: 12),
            _OkxStrategySection(okx: okx, priceFmt: _price),
          ],
          if (dailySop.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.short.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.short.withValues(alpha: 0.25)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'SOP2 盘前快检',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.short),
                  ),
                  const SizedBox(height: 6),
                  ...dailySop.map((r) {
                    final rule = r as Map<String, dynamic>;
                    return Text(
                      '• ${rule['condition']} → ${rule['action']}',
                      style: const TextStyle(fontSize: 11, height: 1.45, color: AppTheme.textSecondary),
                    );
                  }),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _price(dynamic v) {
    final p = (v as num).toDouble();
    return p >= 1000 ? p.toStringAsFixed(0) : p.toStringAsFixed(2);
  }

  Color _eventColor(String? risk) {
    switch (risk) {
      case 'high':
        return AppTheme.short;
      case 'low':
        return AppTheme.magnet;
      default:
        return AppTheme.textSecondary;
    }
  }

  String _modeLabel(String? mode) {
    switch (mode) {
      case 'enhanced':
        return '增强';
      case 'defensive':
        return '防御';
      default:
        return '标准';
    }
  }

  String _gridLabel(String? mode) {
    switch (mode) {
      case 'full_open':
        return '全开';
      case 'widen_or_pause':
        return '拓宽/暂停';
      case 'shift_down':
        return '下移';
      case 'pause':
        return '暂停';
      default:
        return mode ?? '—';
    }
  }
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({required this.label, required this.value});

  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    final n = (value as num?)?.toInt() ?? 0;
    final color = n > 0 ? AppTheme.long : n < 0 ? AppTheme.short : AppTheme.textSecondary;
    final sign = n > 0 ? '+$n' : '$n';
    return MetricChip(label: label, value: sign, color: color);
  }
}

class _OkxStrategySection extends StatelessWidget {
  const _OkxStrategySection({required this.okx, required this.priceFmt});

  final Map<String, dynamic> okx;
  final String Function(dynamic) priceFmt;

  @override
  Widget build(BuildContext context) {
    final grid = okx['grid'] as Map<String, dynamic>? ?? {};
    final mart = okx['martingale'] as Map<String, dynamic>? ?? {};
    final others = okx['other_tools'] as List<dynamic>? ?? [];
    final cautions = (okx['cautions'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.accent.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.accent.withValues(alpha: 0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'OKX 策略建议',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.accent),
          ),
          if (okx['summary'] != null) ...[
            const SizedBox(height: 6),
            Text(
              okx['summary'].toString(),
              style: const TextStyle(fontSize: 11, height: 1.45, color: AppTheme.textSecondary),
            ),
          ],
          if (grid['enabled'] == true) ...[
            const SizedBox(height: 8),
            Text(
              '网格 · ${grid['direction_label'] ?? '—'}',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 4),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                MetricChip(label: '下沿', value: priceFmt(grid['lower_price']), color: AppTheme.long),
                MetricChip(label: '上沿', value: priceFmt(grid['upper_price']), color: AppTheme.short),
                MetricChip(label: '格数', value: '${grid['grid_count'] ?? '—'}'),
                MetricChip(label: '模式', value: grid['mode'] == 'geometric' ? '等比' : '等差'),
                MetricChip(label: '杠杆', value: '${grid['leverage'] ?? '—'}x'),
                if (grid['profit_per_grid_pct'] != null)
                  MetricChip(label: '单格利润', value: '${grid['profit_per_grid_pct']}%'),
              ],
            ),
          ] else if (grid.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              '网格：暂停',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary.withValues(alpha: 0.9)),
            ),
          ],
          if (mart['enabled'] == true) ...[
            const SizedBox(height: 8),
            Text(
              '马丁 · ${mart['direction_label'] ?? '—'}',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 4),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                MetricChip(label: '首单', value: '\$${mart['initial_order_usdt']}'),
                MetricChip(label: '倍数', value: '×${mart['multiplier']}'),
                MetricChip(label: '层数', value: '${mart['max_additions']}'),
                MetricChip(label: '止盈', value: '${mart['take_profit_pct']}%'),
                MetricChip(label: '止损', value: '${mart['stop_loss_pct']}%'),
              ],
            ),
          ],
          if (others.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text(
              '其他工具',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 4),
            ...others.map((t) {
              final tool = t as Map<String, dynamic>;
              final priority = tool['priority']?.toString() ?? '';
              final color = priority == 'avoid'
                  ? AppTheme.short
                  : priority == 'primary'
                      ? AppTheme.accent
                      : AppTheme.textSecondary;
              return Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(
                  '• ${tool['name']}: ${tool['action']}',
                  style: TextStyle(fontSize: 11, height: 1.4, color: color),
                ),
              );
            }),
          ],
          if (cautions.isNotEmpty) ...[
            const SizedBox(height: 6),
            ...cautions.map(
              (c) => Text(
                '⚠ $c',
                style: TextStyle(fontSize: 10, height: 1.4, color: AppTheme.short.withValues(alpha: 0.85)),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
