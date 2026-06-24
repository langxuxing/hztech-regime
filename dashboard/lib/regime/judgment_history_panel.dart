import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 人工 Regime 标注历史。
class JudgmentHistoryPanel extends StatefulWidget {
  const JudgmentHistoryPanel({
    super.key,
    required this.api,
    this.symbol = 'BTC/USDT:USDT',
  });

  final ApiService api;
  final String symbol;

  @override
  State<JudgmentHistoryPanel> createState() => _JudgmentHistoryPanelState();
}

class _JudgmentHistoryPanelState extends State<JudgmentHistoryPanel> {
  List<Map<String, dynamic>> _history = [];
  Map<String, dynamic>? _stats;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        widget.api.fetchHumanJudgmentHistory(symbol: widget.symbol),
        widget.api.fetchFeedbackStats(symbol: widget.symbol),
      ]);
      if (!mounted) return;
      setState(() {
        _history = results[0] as List<Map<String, dynamic>>;
        _stats = results[1] as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '人工标注历史',
      icon: Icons.history_edu_outlined,
      trailing: IconButton(
        icon: const Icon(Icons.refresh, size: 18),
        onPressed: _loading ? null : _load,
        tooltip: '刷新',
      ),
      child: _loading
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          : _error != null
              ? Text(_error!, style: const TextStyle(fontSize: 11, color: AppTheme.short))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_stats != null) ...[
                      _FeedbackStatsStrip(stats: _stats!),
                      const SizedBox(height: 12),
                    ],
                    if (_history.isEmpty)
                      const Text(
                        '暂无人工标注记录',
                        style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                      )
                    else
                      Column(
                        children: _history
                            .take(10)
                            .map(
                              (row) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            row['human_regime']?.toString() ?? '—',
                                            style: const TextStyle(
                                              fontSize: 12,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          if (row['human_trend'] != null)
                                            Text(
                                              '趋势: ${row['human_trend']}',
                                              style: const TextStyle(
                                                fontSize: 10,
                                                color: AppTheme.textSecondary,
                                              ),
                                            ),
                                          if (row['forward_scored_at'] != null)
                                            Text(
                                              'forward ✓ ${(row['realized_regime'] as Map?)?['realized_trend'] ?? ''}',
                                              style: const TextStyle(fontSize: 9, color: AppTheme.long),
                                            ),
                                          if (row['scores'] != null)
                                            Text(
                                              _fmtScores(row['scores'] as List<dynamic>),
                                              style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
                                            ),
                                          if (row['human_notes'] != null)
                                            Text(
                                              row['human_notes'].toString(),
                                              style: const TextStyle(
                                                fontSize: 10,
                                                color: AppTheme.textSecondary,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ),
                                    Text(
                                      _fmtTime(row['recorded_at']?.toString()),
                                      style: const TextStyle(
                                        fontSize: 9,
                                        color: AppTheme.textSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            )
                            .toList(),
                      ),
                  ],
                ),
    );
  }

  String _fmtTime(String? iso) {
    if (iso == null || iso.length < 16) return iso ?? '—';
    return iso.substring(0, 16).replaceFirst('T', ' ');
  }

  String _fmtScores(List<dynamic> scores) {
    final instant = scores.where((s) => s is Map && s['score_type'] == 'instant').toList();
    if (instant.isEmpty) return '';
    instant.sort((a, b) => ((b['total_score'] as num?) ?? 0).compareTo((a['total_score'] as num?) ?? 0));
    final top = instant.first as Map<String, dynamic>;
    return 'instant top: ${top['model_id']} ${(((top['total_score'] as num?) ?? 0) * 100).round()}%';
  }
}

class _FeedbackStatsStrip extends StatelessWidget {
  const _FeedbackStatsStrip({required this.stats});

  final Map<String, dynamic> stats;

  @override
  Widget build(BuildContext context) {
    final count = stats['judgment_count'] as int? ?? 0;
    final min = stats['min_judgments_for_recommendation'] as int? ?? 30;
    final ready = stats['recommendation_ready'] as bool? ?? false;
    final forward = stats['forward_scored_count'] as int? ?? 0;
    final color = ready ? AppTheme.long : AppTheme.accent;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '反馈闭环 · $count/$min 样本 · forward $forward',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color),
          ),
          const SizedBox(height: 4),
          Text(
            stats['message']?.toString() ?? '',
            style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }
}
