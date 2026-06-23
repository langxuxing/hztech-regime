import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 分市场模型 Leaderboard + 当前推荐。
class ModelLeaderboardPanel extends StatefulWidget {
  const ModelLeaderboardPanel({
    super.key,
    required this.api,
    this.symbol = 'BTC/USDT:USDT',
    this.recommendation,
  });

  final ApiService api;
  final String symbol;
  final Map<String, dynamic>? recommendation;

  @override
  State<ModelLeaderboardPanel> createState() => _ModelLeaderboardPanelState();
}

class _ModelLeaderboardPanelState extends State<ModelLeaderboardPanel> {
  List<Map<String, dynamic>> _board = [];
  Map<String, dynamic>? _rec;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _rec = widget.recommendation;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final board = await widget.api.fetchModelLeaderboard(symbol: widget.symbol);
      Map<String, dynamic>? rec = _rec;
      if (rec == null || rec['best_model_id'] == null) {
        try {
          rec = await widget.api.fetchRecommendedModel(symbol: widget.symbol);
        } catch (_) {}
      }
      if (!mounted) return;
      setState(() {
        _board = board;
        _rec = rec;
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
      title: '模型 Leaderboard',
      icon: Icons.leaderboard_outlined,
      trailing: IconButton(
        icon: const Icon(Icons.refresh, size: 18),
        onPressed: _loading ? null : _load,
      ),
      child: _loading
          ? const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2)))
          : _error != null
              ? Text(_error!, style: const TextStyle(fontSize: 11, color: AppTheme.short))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_rec != null && _rec!['best_model_id'] != null) ...[
                      MetricChip(
                        label: '推荐',
                        value: _rec!['best_model_name']?.toString() ?? _rec!['best_model_id'].toString(),
                        color: AppTheme.magnet,
                      ),
                      if (_rec!['reason'] != null) ...[
                        const SizedBox(height: 6),
                        Text(
                          _rec!['reason'].toString(),
                          style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                        ),
                      ],
                      const SizedBox(height: 12),
                    ] else
                      const Text(
                        '样本不足，继续人工标注后将生成推荐',
                        style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                      ),
                    if (_board.isEmpty)
                      const Text('暂无打分汇总', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary))
                    else
                      ..._board.take(8).map(_row),
                  ],
                ),
    );
  }

  Widget _row(Map<String, dynamic> r) {
    final low = r['low_confidence'] == true;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${r['model_id']} · ${r['segment_primary']}',
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
                Text(
                  'n=${r['sample_count']} instant=${_pct(r['instant_avg'])} forward=${_pct(r['forward_avg'])}',
                  style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
          Text(
            low ? '低置信' : _pct(r['combined_score']),
            style: TextStyle(
              fontSize: 11,
              color: low ? AppTheme.textSecondary : AppTheme.long,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _pct(dynamic v) {
    if (v == null) return '—';
    return '${((v as num) * 100).round()}%';
  }
}
