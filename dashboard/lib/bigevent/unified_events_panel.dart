import 'package:flutter/material.dart';

import 'event_merger.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import '../widgets/radar_overview_bar.dart';

class UnifiedEventsPanel extends StatefulWidget {
  const UnifiedEventsPanel({
    super.key,
    required this.events,
    this.summaryHighImpact = 0,
  });

  final List<UnifiedEventItem> events;
  final int summaryHighImpact;

  @override
  State<UnifiedEventsPanel> createState() => _UnifiedEventsPanelState();
}

class _UnifiedEventsPanelState extends State<UnifiedEventsPanel> {
  EventTab _tab = EventTab.all;

  @override
  Widget build(BuildContext context) {
    final filtered =
        widget.events.where((e) => _tab.matches(e)).toList();

    return SectionCard(
      title: '重大事件',
      icon: Icons.notifications_active_outlined,
      trailing: StatusBadge(
        label: '${widget.events.length} 项',
        color: widget.summaryHighImpact > 0 ? AppTheme.short : AppTheme.accent,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: EventTab.values.map((tab) {
                final selected = _tab == tab;
                final count = widget.events.where((e) => tab.matches(e)).length;
                return Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: FilterChip(
                    label: Text('${tab.label} ($count)'),
                    selected: selected,
                    onSelected: (_) => setState(() => _tab = tab),
                    visualDensity: VisualDensity.compact,
                    selectedColor: AppTheme.accent.withValues(alpha: 0.2),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),
          if (filtered.isEmpty)
            const Text(
              '该分类暂无事件',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            )
          else
            ...filtered.take(12).map(_EventRow.new),
        ],
      ),
    );
  }
}

class _EventRow extends StatelessWidget {
  const _EventRow(this.event);

  final UnifiedEventItem event;

  @override
  Widget build(BuildContext context) {
    final severityColor = switch (event.severity) {
      'high' || 'critical' => AppTheme.short,
      'medium' => AppTheme.neutral,
      _ => AppTheme.textSecondary,
    };
    final impactColor = switch (event.impact) {
      'bullish' => AppTheme.long,
      'bearish' => AppTheme.short,
      _ => AppTheme.textSecondary,
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
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
            children: [
              Container(
                width: 4,
                height: 36,
                decoration: BoxDecoration(
                  color: severityColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      event.title,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (event.isUpcoming)
                      const Text(
                        '即将发生',
                        style: TextStyle(fontSize: 9, color: AppTheme.neutral),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.only(left: 14),
            child: Text(
              event.description,
              style: const TextStyle(
                fontSize: 11,
                height: 1.4,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.only(left: 14),
            child: Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                StatusBadge(label: _catLabel(event.category), color: AppTheme.accent),
                StatusBadge(label: _impactLabel(event.impact), color: impactColor),
                if (event.impactScore != null)
                  StatusBadge(
                    label: '影响 ${event.impactScore!.toStringAsFixed(2)}',
                    color: event.impactScore! >= 0 ? AppTheme.long : AppTheme.short,
                  ),
                if (event.actionable)
                  const StatusBadge(label: '可交易', color: AppTheme.magnet),
                if (event.timestamp != null)
                  Text(
                    formatRadarTime(event.timestamp!),
                    style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _catLabel(String c) => switch (c) {
        'macro' => '宏观',
        'etf' => 'ETF',
        'breaking' => '突发',
        'structure' => '结构',
        'onchain' => '链上',
        _ => '市场',
      };

  String _impactLabel(String i) => switch (i) {
        'bullish' => '偏多',
        'bearish' => '偏空',
        _ => '中性',
      };
}
