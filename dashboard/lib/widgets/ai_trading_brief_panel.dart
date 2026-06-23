import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 短期预测 + AI 辅助决策面板。
class AiTradingBriefPanel extends StatelessWidget {
  const AiTradingBriefPanel({
    super.key,
    required this.data,
    this.brief,
  });

  final DashboardData data;
  final Map<String, dynamic>? brief;

  @override
  Widget build(BuildContext context) {
    if (brief == null || brief!.isEmpty) {
      return SectionCard(
        title: '短期预测与操作建议',
        icon: Icons.auto_awesome_outlined,
        child: Text(
          data.advice.reasoning,
          style: const TextStyle(fontSize: 12, height: 1.5, color: AppTheme.textSecondary),
        ),
      );
    }

    final bias = brief!['bias']?.toString() ?? data.advice.bias;
    final color = AppTheme.biasColor(bias);
    final aiMode = brief!['ai_mode']?.toString() ?? (data.advice.ruleBased ? 'rule_based' : 'llm');
    final aiEnhanced = brief!['ai_enhanced'] == true;
    final plan = (brief!['operation_plan'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    final catalysts = (brief!['catalysts'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    final levels = brief!['key_levels'] as Map<String, dynamic>? ?? {};

    return SectionCard(
      title: '短期预测与操作建议',
      icon: Icons.auto_awesome_outlined,
      trailing: StatusBadge(
        label: aiEnhanced ? 'AI 大模型' : (aiMode == 'llm' ? 'LLM' : '规则引擎'),
        color: aiEnhanced ? AppTheme.magnet : AppTheme.accent,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: MetricChip(
                  label: '方向',
                  value: AppTheme.biasLabel(bias),
                  color: color,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '周期',
                  value: brief!['horizon']?.toString() ?? data.advice.timeHorizon,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: MetricChip(
                  label: '置信',
                  value: '${(((brief!['confidence'] as num?) ?? data.advice.confidence) * 100).round()}%',
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _ScenarioBlock(
            title: '多头情景',
            text: brief!['scenario_bull']?.toString() ?? '—',
            color: AppTheme.long,
          ),
          _ScenarioBlock(
            title: '空头情景',
            text: brief!['scenario_bear']?.toString() ?? '—',
            color: AppTheme.short,
          ),
          _ScenarioBlock(
            title: '基准情景',
            text: brief!['scenario_base']?.toString() ?? '—',
            color: AppTheme.neutral,
          ),
          const SizedBox(height: 10),
          ..._signalNotes(brief!).map(
            (n) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 72,
                    child: Text(
                      n.$1,
                      style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                    ),
                  ),
                  Expanded(
                    child: Text(n.$2, style: const TextStyle(fontSize: 11, height: 1.35)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          if (plan.isNotEmpty) ...[
            const Text('操作计划', style: TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
            const SizedBox(height: 6),
            ...plan.map(
              (p) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.check_circle_outline, size: 14, color: color),
                    const SizedBox(width: 6),
                    Expanded(child: Text(p, style: const TextStyle(fontSize: 11))),
                  ],
                ),
              ),
            ),
          ],
          if (levels.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: levels.entries.map((e) {
                final v = e.value;
                if (v == null) return const SizedBox.shrink();
                return MetricChip(
                  label: e.key,
                  value: (v as num).toStringAsFixed(0),
                );
              }).toList(),
            ),
          ],
          const SizedBox(height: 12),
          Text(
            brief!['ai_summary']?.toString() ?? data.advice.reasoning,
            style: const TextStyle(fontSize: 12, height: 1.5, color: AppTheme.textSecondary),
          ),
          if (catalysts.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: catalysts.map((c) => StatusBadge(label: c, color: AppTheme.accent)).toList(),
            ),
          ],
        ],
      ),
    );
  }

  static List<(String, String)> _signalNotes(Map<String, dynamic> brief) {
    final items = <(String, String)>[];
    void add(String label, String key) {
      final v = brief[key]?.toString();
      if (v != null && v.isNotEmpty) items.add((label, v));
    }

    add('SMC/ICT', 'smc_action');
    add('流动性', 'liquidity_note');
    add('GEX', 'gex_note');
    add('衍生品', 'derivatives_note');
    add('资金流', 'flow_note');
    return items;
  }
}

class _ScenarioBlock extends StatelessWidget {
  const _ScenarioBlock({
    required this.title,
    required this.text,
    required this.color,
  });

  final String title;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 4,
            height: 36,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
                Text(
                  text,
                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary, height: 1.35),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
