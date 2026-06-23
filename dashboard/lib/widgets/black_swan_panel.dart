import 'package:flutter/material.dart';

import '../bigevent/event_data.dart';
import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 黑天鹅分级预警面板：等级仪表 + 触发因子 + 建议动作。
class BlackSwanPanel extends StatelessWidget {
  const BlackSwanPanel({
    super.key,
    required this.data,
    this.events,
    this.compact = false,
  });

  final DashboardData data;
  final EventAnalysisData? events;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final alert = data.blackSwanAlert ??
        data.pipeline?['layers']?['black_swan'] as Map<String, dynamic>? ??
        data.quantState?['black_swan'] as Map<String, dynamic>?;
    if (alert == null) {
      return const SectionCard(
        title: '黑天鹅预警',
        icon: Icons.electric_bolt_outlined,
        child: Text(
          '暂无黑天鹅预警数据（仅 BTC 完整支持）',
          style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
        ),
      );
    }

    final level = (alert['level'] as num?)?.toInt() ?? 0;
    final levelColor = AppTheme.blackSwanLevelColor(level);
    final levelLabel = AppTheme.blackSwanLevelLabel(level);
    final triggers = (alert['triggers'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    final scores = alert['scores'] as Map<String, dynamic>? ?? {};
    final actions = alert['actions'] as Map<String, dynamic>? ?? {};
    final suspended = alert['suspended'] == true;
    final reason = alert['suspend_reason']?.toString();
    final micro = data.pipeline?['layers']?['ingestion']?['microstructure']
        as Map<String, dynamic>?;
    final pulse = micro?['liquidation_pulse'] as Map<String, dynamic>?;

    return SectionCard(
      title: '黑天鹅预警',
      icon: Icons.electric_bolt_outlined,
      trailing: StatusBadge(label: levelLabel, color: levelColor),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (suspended)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.short.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.short.withValues(alpha: 0.5)),
              ),
              child: Text(
                reason ?? '系统已挂起，绕过 AI 推理输出熔断 JSON',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.short,
                ),
              ),
            ),
          _LevelGauge(level: level, color: levelColor),
          if (!compact) ...[
            const SizedBox(height: 14),
            const Text(
              '触发因子',
              style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 6),
            if (triggers.isEmpty)
              const Text('无活跃触发', style: TextStyle(fontSize: 11))
            else
              ...triggers.map(
                (t) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.warning_amber_rounded, size: 14, color: levelColor),
                      const SizedBox(width: 6),
                      Expanded(child: Text(t, style: const TextStyle(fontSize: 11))),
                    ],
                  ),
                ),
              ),
            if (scores.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                '分项得分',
                style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: scores.entries.map((e) {
                  final v = (e.value as num?)?.toDouble() ?? 0;
                  return MetricChip(
                    label: e.key,
                    value: v.toStringAsFixed(2),
                    color: v >= 0.7 ? AppTheme.short : null,
                  );
                }).toList(),
              ),
            ],
            if (pulse != null) ...[
              const SizedBox(height: 12),
              _PulseRow(pulse: pulse),
            ],
            if (actions.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                '建议动作',
                style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 6),
              _ActionRow(label: '仓位缩放', value: '×${actions['position_scale'] ?? 1}'),
              _ActionRow(
                label: '新开仓',
                value: actions['allow_new_orders'] == false ? '禁止' : '允许',
              ),
              _ActionRow(
                label: '止损倍数',
                value: '×${actions['widen_stop_multiplier'] ?? 1}',
              ),
            ],
            if (events != null && events!.upcomingHighImpact.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                '宏观事件倒计时',
                style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 6),
              ...events!.upcomingHighImpact.take(3).map(
                    (e) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text(
                        '• ${e.title}',
                        style: const TextStyle(fontSize: 11),
                      ),
                    ),
                  ),
            ],
          ],
        ],
      ),
    );
  }
}

class _LevelGauge extends StatelessWidget {
  const _LevelGauge({required this.level, required this.color});

  final int level;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(4, (i) {
        final active = i <= level;
        return Expanded(
          child: Container(
            height: 8,
            margin: EdgeInsets.only(right: i < 3 ? 4 : 0),
            decoration: BoxDecoration(
              color: active ? color.withValues(alpha: 0.5 + i * 0.12) : AppTheme.border,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        );
      }),
    );
  }
}

class _PulseRow extends StatelessWidget {
  const _PulseRow({required this.pulse});

  final Map<String, dynamic> pulse;

  @override
  Widget build(BuildContext context) {
    final near = pulse['near_notional_usd'];
    final total = pulse['total_weight'];
    final extreme = pulse['extreme_pulse'] == true;
    return Row(
      children: [
        Icon(
          extreme ? Icons.bolt : Icons.water_drop_outlined,
          size: 16,
          color: extreme ? AppTheme.short : AppTheme.textSecondary,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            '清算脉冲: 近端 \$$near / 权重 \$$total${extreme ? ' · 异常' : ''}',
            style: TextStyle(
              fontSize: 11,
              color: extreme ? AppTheme.short : AppTheme.textSecondary,
              fontWeight: extreme ? FontWeight.w600 : FontWeight.normal,
            ),
          ),
        ),
      ],
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
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
