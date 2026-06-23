import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'event_data.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class EventsPanel extends StatelessWidget {
  const EventsPanel({super.key, required this.data});

  final EventAnalysisData data;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '事件分析引擎',
      icon: Icons.event_note_rounded,
      trailing: StatusBadge(
        label: _riskLabel(data.summary.overallRisk),
        color: _riskColor(data.summary.overallRisk),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              MetricChip(
                label: '日历事件',
                value: '${data.summary.totalCalendar}',
              ),
              MetricChip(
                label: '突发',
                value: '${data.summary.totalBreaking}',
                color: data.summary.totalBreaking > 0
                    ? AppTheme.accent
                    : null,
              ),
              MetricChip(
                label: '高风险',
                value: '${data.summary.highImpactCount}',
                color: data.summary.highImpactCount > 0
                    ? AppTheme.short
                    : null,
              ),
              MetricChip(
                label: '质量',
                value: data.dataQuality,
              ),
            ],
          ),
          if (data.upcomingHighImpact.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              '即将发生 · 高影响',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            ...data.upcomingHighImpact.take(3).map(_EventTile.new),
          ],
          if (data.breakingEvents.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              '突发监控 (X / 新闻)',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            ...data.breakingEvents.take(5).map((e) {
              final impact = data.analyzedEvents
                  .where((a) => a.id == e.id)
                  .map((a) => a.impact)
                  .whereType<EventImpact>()
                  .firstOrNull;
              return _EventTile(e, impact: impact);
            }),
          ],
          if (data.calendarEvents.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              '宏观 / 交易所日历',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            ...data.calendarEvents.take(5).map((e) {
              final impact = data.analyzedEvents
                  .where((a) => a.id == e.id)
                  .map((a) => a.impact)
                  .whereType<EventImpact>()
                  .firstOrNull;
              return _EventTile(e, impact: impact);
            }),
          ],
          if (data.notes.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              data.notes.join(' · '),
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  String _riskLabel(String risk) {
    switch (risk) {
      case 'elevated':
        return '风险升高';
      case 'bearish':
        return '偏空';
      case 'bullish':
        return '偏多';
      case 'mixed':
        return '多空交织';
      default:
        return '风险低';
    }
  }

  Color _riskColor(String risk) {
    switch (risk) {
      case 'elevated':
        return AppTheme.short;
      case 'bearish':
        return AppTheme.short;
      case 'bullish':
        return AppTheme.long;
      case 'mixed':
        return AppTheme.neutral;
      default:
        return AppTheme.long;
    }
  }
}

class _EventTile extends StatelessWidget {
  const _EventTile(this.event, {this.impact});

  final MarketEvent event;
  final EventImpact? impact;

  @override
  Widget build(BuildContext context) {
    final level = impact?.impactLevel ?? 'low';
    final direction = impact?.direction ?? 'neutral';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHigh,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  event.title,
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                ),
              ),
              const SizedBox(width: 8),
              StatusBadge(
                label: level.toUpperCase(),
                color: _levelColor(level),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              _chip(event.category),
              const SizedBox(width: 6),
              _chip(event.source),
              if (impact != null) ...[
                const SizedBox(width: 6),
                _chip(direction, color: _directionColor(direction)),
              ],
              const Spacer(),
              Text(
                _formatTime(event.publishedAt),
                style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
            ],
          ),
          if (impact != null && impact!.reasoning.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              impact!.reasoning,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  Widget _chip(String label, {Color? color}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: (color ?? AppTheme.accent).withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 9, color: color ?? AppTheme.accent),
      ),
    );
  }

  Color _levelColor(String level) {
    switch (level) {
      case 'critical':
      case 'high':
        return AppTheme.short;
      case 'medium':
        return AppTheme.neutral;
      default:
        return AppTheme.textSecondary;
    }
  }

  Color _directionColor(String direction) {
    switch (direction) {
      case 'bullish':
        return AppTheme.long;
      case 'bearish':
        return AppTheme.short;
      default:
        return AppTheme.neutral;
    }
  }

  String _formatTime(String iso) {
    if (iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return DateFormat('MM-dd HH:mm').format(dt);
    } catch (_) {
      return iso.length > 16 ? iso.substring(0, 16) : iso;
    }
  }
}

extension _FirstOrNull<E> on Iterable<E> {
  E? get firstOrNull {
    final it = iterator;
    return it.moveNext() ? it.current : null;
  }
}
