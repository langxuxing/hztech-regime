import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 五段业务流拓扑可视化（首页）。
class PipelineFlowPanel extends StatelessWidget {
  const PipelineFlowPanel({
    super.key,
    required this.pipeline,
    this.confirmedRegime,
  });

  final Map<String, dynamic>? pipeline;
  final String? confirmedRegime;

  @override
  Widget build(BuildContext context) {
    final flow = pipeline?['flow'] as List<dynamic>? ?? _defaultFlow;
    final layers = pipeline?['layers'] as Map<String, dynamic>?;

    return SectionCard(
      title: '业务流拓扑',
      icon: Icons.account_tree_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (confirmedRegime != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  const Text(
                    '当前确认状态',
                    style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      confirmedRegime!,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.accent,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ...List.generate(flow.length, (i) {
            final step = flow[i].toString();
            final isLayer = step.startsWith('L');
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 22,
                    height: 22,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: isLayer
                          ? AppTheme.accent.withValues(alpha: 0.15)
                          : AppTheme.surfaceHigh,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: isLayer ? AppTheme.accent : AppTheme.border,
                      ),
                    ),
                    child: Text(
                      '${i + 1}',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: isLayer ? AppTheme.accent : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      step,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isLayer ? FontWeight.w600 : FontWeight.w400,
                        color: isLayer ? AppTheme.textPrimary : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
          if (layers != null) ...[
            const SizedBox(height: 12),
            const Divider(color: AppTheme.border, height: 1),
            const SizedBox(height: 12),
            _LayerSummaryRow(
              label: 'L1 输入',
              detail: _l1Summary(layers['ingestion']),
            ),
            _LayerSummaryRow(
              label: 'L2 推理',
              detail: _l2Summary(layers['inference_live']),
            ),
            _LayerSummaryRow(
              label: 'L3 确认',
              detail: _l3Summary(layers['confirmation']),
            ),
            _LayerSummaryRow(
              label: 'L4 执行',
              detail: _l4Summary(layers['execution']),
            ),
          ],
        ],
      ),
    );
  }

  static const _defaultFlow = [
    'L1 多源数据输入',
    'L1 特征变频清洗',
    'L2 推理与硬规则',
    'L2 慢变量纠偏 + CVD 验证',
    'L3 转置惩罚 + df_confirmed',
    'L4 策略路由 + 参数微调 + 熔断',
  ];

  String _l1Summary(dynamic raw) {
    if (raw is! Map) return '—';
    final t = raw['transform'];
    if (t is Map) {
      return '${t['confirmed_bars']} bars confirmed';
    }
    return '—';
  }

  String _l2Summary(dynamic raw) {
    if (raw is! Map) return '—';
    return raw['regime_label']?.toString() ?? '—';
  }

  String _l3Summary(dynamic raw) {
    if (raw is! Map) return '—';
    final c = raw['combined'];
    if (c is Map) {
      final live = c['live_regime_id'];
      final confirmed = c['confirmed_regime_id'];
      if (live != confirmed) return '$confirmed ← 防抖中';
      return confirmed?.toString() ?? '—';
    }
    return '—';
  }

  String _l4Summary(dynamic raw) {
    if (raw is! Map) return '—';
    if (raw['suspended'] == true) return '已挂起';
    final cmds = raw['routing_commands'];
    if (cmds is List && cmds.isNotEmpty) return cmds.first.toString();
    return '—';
  }
}

class _LayerSummaryRow extends StatelessWidget {
  const _LayerSummaryRow({required this.label, required this.detail});

  final String label;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 56,
            child: Text(
              label,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ),
          Expanded(
            child: Text(
              detail,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
