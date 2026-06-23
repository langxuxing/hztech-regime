import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 多模型 Regime 对比 + 人工判断表单。
class ModelComparisonPanel extends StatefulWidget {
  const ModelComparisonPanel({
    super.key,
    required this.btcRegime,
    this.api,
    this.symbol = 'BTC/USDT:USDT',
    this.compact = false,
  });

  final Map<String, dynamic> btcRegime;
  final ApiService? api;
  final String symbol;
  final bool compact;

  @override
  State<ModelComparisonPanel> createState() => _ModelComparisonPanelState();
}

class _ModelComparisonPanelState extends State<ModelComparisonPanel> {
  final _notesController = TextEditingController();
  String? _selectedRegime;
  String? _selectedTrend;
  bool _submitting = false;
  String? _submitMessage;
  Map<String, double>? _lastScores;

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

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final models = widget.btcRegime['models'] as Map<String, dynamic>?;
    final comparison = widget.btcRegime['model_comparison'] as Map<String, dynamic>?;
    if (models == null || models.isEmpty) {
      return const SizedBox.shrink();
    }

    final needsHuman = comparison?['needs_human_judgment'] == true;
    final agreement = (comparison?['agreement_ratio'] as num?)?.toDouble();
    final dominantTrend = comparison?['dominant_trend']?.toString();
    final recommendation = widget.btcRegime['model_recommendation'] as Map<String, dynamic>?;
    final scoresPreview = widget.btcRegime['model_scores_preview'] as Map<String, dynamic>?;
    final previewScores = scoresPreview?['scores'] as Map<String, dynamic>?;

    return SectionCard(
      title: '多模型 Regime 对比',
      icon: Icons.compare_arrows,
      trailing: needsHuman
          ? const StatusBadge(label: '需人工判断', color: AppTheme.magnet)
          : (agreement != null
              ? StatusBadge(
                  label: '共识 ${(agreement * 100).round()}%',
                  color: AppTheme.long,
                )
              : null),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (comparison?['summary'] != null) ...[
            Text(
              comparison!['summary'].toString(),
              style: const TextStyle(fontSize: 12, height: 1.5, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
          ],
          if (dominantTrend != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: MetricChip(
                label: '趋势共识',
                value: dominantTrend,
                color: _trendColor(dominantTrend),
              ),
            ),
          if (recommendation?['best_model_id'] != null) ...[
            MetricChip(
              label: '推荐模型',
              value: recommendation!['best_model_name']?.toString() ??
                  recommendation['best_model_id'].toString(),
              color: AppTheme.magnet,
            ),
            const SizedBox(height: 8),
          ],
          ..._modelRows(
            models,
            maxRows: widget.compact ? 4 : null,
            scoreMap: _lastScores ?? _scoresFromPreview(previewScores),
          ),
          if (widget.api != null && !widget.compact) ...[
            const Divider(height: 24),
            const Text(
              '人工判断',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _regimeOptions
                  .map(
                    (o) => ChoiceChip(
                      label: Text(o.$2, style: const TextStyle(fontSize: 11)),
                      selected: _selectedRegime == o.$1,
                      onSelected: (_) => setState(() => _selectedRegime = o.$1),
                      selectedColor: AppTheme.accent.withValues(alpha: 0.25),
                    ),
                  )
                  .toList(),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _trendOptions
                  .map(
                    (o) => ChoiceChip(
                      label: Text(o.$2, style: const TextStyle(fontSize: 11)),
                      selected: _selectedTrend == o.$1,
                      onSelected: (_) => setState(() => _selectedTrend = o.$1),
                      selectedColor: AppTheme.accent.withValues(alpha: 0.25),
                    ),
                  )
                  .toList(),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _notesController,
              maxLines: 2,
              style: const TextStyle(fontSize: 12),
              decoration: const InputDecoration(
                hintText: '备注（可选）',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
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
                  label: const Text('提交人工判断'),
                ),
                if (_submitMessage != null) ...[
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _submitMessage!,
                      style: TextStyle(
                        fontSize: 11,
                        color: _submitMessage!.startsWith('已')
                            ? AppTheme.long
                            : AppTheme.short,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }

  Map<String, double>? _scoresFromPreview(Map<String, dynamic>? preview) {
    if (preview == null) return null;
    return preview.map((k, v) => MapEntry(k, (v as num).toDouble()));
  }

  List<Widget> _modelRows(
    Map<String, dynamic> models, {
    int? maxRows,
    Map<String, double>? scoreMap,
  }) {
    const order = [
      'heuristic',
      'hmm',
      'clustering',
      'msar',
      'heuristic_advanced',
      'hybrid',
    ];
    final rows = <Widget>[];
    var count = 0;
    for (final id in order) {
      if (maxRows != null && count >= maxRows) break;
      final m = models[id] as Map<String, dynamic>?;
      if (m == null) continue;
      rows.add(_modelRow(id, m, scoreMap?[id]));
      rows.add(const SizedBox(height: 6));
      count++;
    }
    for (final entry in models.entries) {
      if (maxRows != null && count >= maxRows) break;
      if (order.contains(entry.key)) continue;
      rows.add(_modelRow(entry.key, entry.value as Map<String, dynamic>, scoreMap?[entry.key]));
      rows.add(const SizedBox(height: 6));
      count++;
    }
    return rows;
  }

  Widget _modelRow(String id, Map<String, dynamic> m, double? humanScore) {
    final error = m['error'] as String?;
    final label = m['regime_label']?.toString() ?? '—';
    final conf = (m['confidence'] as num?)?.toDouble();
    final trend = m['raw_trend']?.toString() ?? '—';
    final name = m['model_name']?.toString() ?? id;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border.withValues(alpha: 0.6)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 2),
                Text(
                  error ?? label,
                  style: TextStyle(
                    fontSize: 11,
                    color: error != null ? AppTheme.short : AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              MetricChip(
                label: '趋势',
                value: trend,
                color: _trendColor(trend),
              ),
              if (humanScore != null) ...[
                const SizedBox(height: 4),
                Text(
                  '一致 ${(humanScore * 100).round()}%',
                  style: TextStyle(
                    fontSize: 10,
                    color: humanScore >= 0.7 ? AppTheme.long : AppTheme.magnet,
                  ),
                ),
              ],
              if (conf != null && error == null) ...[
                const SizedBox(height: 4),
                Text(
                  '${(conf * 100).round()}%',
                  style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _submitMessage = null;
    });
    try {
      final result = await widget.api!.submitHumanJudgment(
        symbol: widget.symbol,
        humanRegime: _selectedRegime!,
        humanTrend: _selectedTrend,
        humanNotes: _notesController.text.trim().isEmpty ? null : _notesController.text.trim(),
      );
      final scoresRaw = result['scores'] as Map<String, dynamic>?;
      if (!mounted) return;
      setState(() {
        _submitMessage = '已记录人工判断';
        _submitting = false;
        if (scoresRaw != null) {
          _lastScores = scoresRaw.map((k, v) => MapEntry(k, (v as num).toDouble()));
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitMessage = '提交失败: $e';
        _submitting = false;
      });
    }
  }

  Color _trendColor(String trend) {
    if (trend == 'uptrend') return AppTheme.long;
    if (trend == 'downtrend') return AppTheme.short;
    return AppTheme.textSecondary;
  }
}
