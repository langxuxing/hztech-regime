import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import '../widgets/common.dart';
import '../regime/quant_state_panel.dart';
import '../theme/app_theme.dart';

/// L4 业务执行与策略路由层界面。
class L4ExecutionTab extends StatelessWidget {
  const L4ExecutionTab({
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
    final l4 = data.pipeline?['layers']?['execution'] as Map<String, dynamic>?;
    final params = l4?['parameter_adjustments'] as Map<String, dynamic>?;
    final cmds = (l4?['routing_commands'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();
    final paramNotes = (params?['notes'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
          if (l4?['suspended'] == true)
            Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.short.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppTheme.short.withValues(alpha: 0.4)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: AppTheme.short, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l4?['suspend_reason']?.toString() ?? '交易已挂起',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.short),
                    ),
                  ),
                ],
              ),
            ),
          if (data.quantState != null && !embedded) ...[
            QuantStatePanel(quantState: data.quantState!),
            const SizedBox(height: 16),
          ],
          SectionCard(
            title: '策略路由指令',
            icon: Icons.route_outlined,
            child: cmds.isEmpty
                ? const Text('暂无路由指令', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary))
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: cmds
                        .map(
                          (c) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Icon(Icons.chevron_right, size: 16, color: AppTheme.accent),
                                Expanded(child: Text(c, style: const TextStyle(fontSize: 12))),
                              ],
                            ),
                          ),
                        )
                        .toList(),
                  ),
          ),
          if (params != null) ...[
            const SizedBox(height: 16),
            SectionCard(
              title: '参数动态自适应',
              icon: Icons.tune_outlined,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _row('仓位缩放', '×${params['position_scale'] ?? 1}'),
                  _row('止损倍数', '×${params['stop_loss_multiplier'] ?? 1}'),
                  _row('突破阈值', '×${params['breakout_threshold_scale'] ?? 1}'),
                  _row('网格', params['grid_enabled'] == true ? '开启' : '关闭'),
                  _row('CTA', params['cta_enabled'] == true ? '开启' : '关闭'),
                  ...paramNotes.map(
                    (n) => Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text('• $n', style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (l4?['circuit_breaker_active'] == true) ...[
            const SizedBox(height: 16),
            const SectionCard(
              title: '黑天鹅熔断器',
              icon: Icons.electric_bolt_outlined,
              child: Text(
                '宏观事件或极端条件触发，已绕过 AI 模型直接挂起/降级。',
                style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
            ),
          ],
        ],
    );

    if (embedded) return content;
    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: content,
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(label, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
          ),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
