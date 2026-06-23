import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import '../bigevent/event_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// 顶部指挥官横幅：大字 Regime + 策略路由摘要 + 事件倒计时。
class CommanderBanner extends StatelessWidget {
  const CommanderBanner({
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
    final confirmed = _confirmedRegimeId(data);
    final label = data.regimeConfirmation?['combined']?['regime_label']?.toString() ??
        data.btcRegime?['regime_label']?.toString() ??
        data.board.regime.label;
    final confidence = data.regimeConfirmation?['combined']?['confidence'] as num? ??
        data.board.regime.confidence;
    final cellColor = AppTheme.regimeCellColor(confirmed);
    final liveId = data.regimeConfirmation?['combined']?['live_regime_id']?.toString();
    final locked = liveId != null && liveId != confirmed;
    final l4 = data.pipeline?['layers']?['execution'] as Map<String, dynamic>?;
    final params = l4?['parameter_adjustments'] as Map<String, dynamic>?;
    final nextEvent = _nextEvent(events);

    return Container(
      padding: EdgeInsets.all(compact ? 12 : 16),
      decoration: BoxDecoration(
        color: cellColor.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: locked
              ? AppTheme.accent.withValues(alpha: 0.6)
              : cellColor.withValues(alpha: 0.7),
          width: locked ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (locked)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(
                    Icons.brightness_1,
                    size: 10,
                    color: AppTheme.accent.withValues(alpha: 0.9),
                  ),
                ),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: compact ? 16 : 22,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textPrimary,
                    letterSpacing: 0.3,
                  ),
                ),
              ),
              StatusBadge(
                label: '${(confidence * 100).round()}%',
                color: AppTheme.regimeTypeColor(data.board.regime.regime),
              ),
            ],
          ),
          if (confirmed.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              confirmed,
              style: TextStyle(fontSize: 10, color: cellColor.withValues(alpha: 0.9)),
            ),
          ],
          if (!compact) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _RouteChip(
                  label: 'CTA',
                  active: params?['cta_enabled'] != false,
                  detail: '×${params?['position_scale'] ?? 1}',
                ),
                _RouteChip(
                  label: '网格',
                  active: params?['grid_enabled'] == true,
                ),
                if (data.macroHazardFlag)
                  const StatusBadge(label: '宏观熔断', color: AppTheme.short),
                if (l4?['suspended'] == true)
                  const StatusBadge(label: '已挂起', color: AppTheme.short),
              ],
            ),
          ],
          if (nextEvent != null) ...[
            const SizedBox(height: 10),
            Text(
              nextEvent,
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  static String _confirmedRegimeId(DashboardData data) {
    return data.regimeConfirmation?['combined']?['confirmed_regime_id']?.toString() ??
        data.btcRegime?['regime_id']?.toString() ??
        data.board.regime.regimeId ??
        '';
  }

  String? _nextEvent(EventAnalysisData? ev) {
    if (ev == null || ev.upcomingHighImpact.isEmpty) return null;
    final e = ev.upcomingHighImpact.first;
    final when = e.scheduledAt ?? e.publishedAt;
    return '下一事件: ${e.title}${_relative(when) != null ? ' · ${_relative(when)}' : ''}';
  }

  String? _relative(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = dt.difference(DateTime.now());
      if (diff.isNegative) return '进行中';
      if (diff.inHours >= 1) return 'T-${diff.inHours}h';
      if (diff.inMinutes >= 1) return 'T-${diff.inMinutes}m';
      return '即将';
    } catch (_) {
      return null;
    }
  }
}

class _RouteChip extends StatelessWidget {
  const _RouteChip({
    required this.label,
    required this.active,
    this.detail,
  });

  final String label;
  final bool active;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final color = active ? AppTheme.long : AppTheme.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            active ? Icons.circle : Icons.circle_outlined,
            size: 8,
            color: color,
          ),
          const SizedBox(width: 6),
          Text(
            '$label${detail != null ? ' $detail' : ''}',
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color),
          ),
        ],
      ),
    );
  }
}
