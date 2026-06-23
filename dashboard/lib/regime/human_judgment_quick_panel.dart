import 'package:flutter/material.dart';

import '../models/trend_judgment.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 大屏 / Regime 页快速人工判断：预填系统趋势与 Regime。
class HumanJudgmentQuickPanel extends StatefulWidget {
  const HumanJudgmentQuickPanel({
    super.key,
    required this.judgment,
    required this.api,
    this.symbol = 'BTC/USDT:USDT',
    this.compact = false,
    this.showStats = true,
  });

  final TrendJudgment judgment;
  final ApiService api;
  final String symbol;
  final bool compact;
  final bool showStats;

  @override
  State<HumanJudgmentQuickPanel> createState() => _HumanJudgmentQuickPanelState();
}

class _HumanJudgmentQuickPanelState extends State<HumanJudgmentQuickPanel> {
  static const _regimeOptions = [
    ('trend_up', '趋势上行'),
    ('trend_down', '趋势下行'),
    ('range', '震荡区间'),
    ('high_vol', '高波动'),
    ('transition', '转换中'),
  ];

  static const _trendOptions = [
    ('uptrend', '上涨'),
    ('downtrend', '下跌'),
    ('range', '震荡'),
  ];

  String? _selectedRegime;
  String? _selectedTrend;
  bool _submitting = false;
  String? _submitMessage;
  Map<String, dynamic>? _stats;

  @override
  void initState() {
    super.initState();
    _prefillFromJudgment();
    if (widget.showStats) {
      _loadStats();
    }
  }

  @override
  void didUpdateWidget(covariant HumanJudgmentQuickPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.judgment.regimeId != widget.judgment.regimeId ||
        oldWidget.judgment.trend != widget.judgment.trend) {
      _prefillFromJudgment();
    }
  }

  void _prefillFromJudgment() {
    _selectedRegime = widget.judgment.suggestedHumanRegime;
    _selectedTrend = widget.judgment.trend;
  }

  Future<void> _loadStats() async {
    try {
      final stats = await widget.api.fetchFeedbackStats(symbol: widget.symbol);
      if (!mounted) return;
      setState(() => _stats = stats);
    } catch (_) {
      // 离线或 API 未就绪时静默忽略
    }
  }

  Future<void> _submit() async {
    if (_selectedRegime == null) return;
    setState(() {
      _submitting = true;
      _submitMessage = null;
    });
    try {
      await widget.api.submitHumanJudgment(
        symbol: widget.symbol,
        humanRegime: _selectedRegime!,
        humanTrend: _selectedTrend,
      );
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _submitMessage = '已记录人工判断';
      });
      _loadStats();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _submitMessage = '提交失败: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final needsHuman = widget.judgment.needsHumanJudgment;

    return SectionCard(
      title: '人工趋势复核',
      icon: Icons.how_to_reg_outlined,
      trailing: needsHuman
          ? const StatusBadge(label: '建议复核', color: AppTheme.short)
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '系统判断：${widget.judgment.trendLabel} · ${widget.judgment.regimeLabel}',
            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
          ),
          if (_stats != null) ...[
            const SizedBox(height: 6),
            Text(
              '样本 ${_stats!['judgment_count']}/${_stats!['min_judgments_for_recommendation']} · ${_stats!['message']}',
              style: TextStyle(
                fontSize: 10,
                color: (_stats!['recommendation_ready'] as bool? ?? false)
                    ? AppTheme.long
                    : AppTheme.textSecondary,
              ),
            ),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: _regimeOptions
                .map(
                  (o) => ChoiceChip(
                    label: Text(o.$2, style: TextStyle(fontSize: widget.compact ? 10 : 11)),
                    selected: _selectedRegime == o.$1,
                    onSelected: (_) => setState(() => _selectedRegime = o.$1),
                    selectedColor: AppTheme.accent.withValues(alpha: 0.25),
                    visualDensity: VisualDensity.compact,
                  ),
                )
                .toList(),
          ),
          if (!widget.compact) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: _trendOptions
                  .map(
                    (o) => ChoiceChip(
                      label: Text(o.$2, style: const TextStyle(fontSize: 11)),
                      selected: _selectedTrend == o.$1,
                      onSelected: (_) => setState(() => _selectedTrend = o.$1),
                      selectedColor: AppTheme.accent.withValues(alpha: 0.25),
                      visualDensity: VisualDensity.compact,
                    ),
                  )
                  .toList(),
            ),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _submitting || _selectedRegime == null ? null : _submit,
                icon: _submitting
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check, size: 16),
                label: Text(widget.compact ? '确认' : '提交人工判断'),
              ),
              if (_submitMessage != null) ...[
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _submitMessage!,
                    style: TextStyle(
                      fontSize: 10,
                      color: _submitMessage!.startsWith('已') ? AppTheme.long : AppTheme.short,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
