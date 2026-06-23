import 'package:flutter/material.dart';

import '../models/dashboard_data.dart';
import 'event_data.dart';
import 'event_impact_summary.dart';
import 'event_merger.dart';
import 'events_panel.dart';
import '../widgets/etf_flow_panel.dart';
import '../widgets/onchain_panel.dart';
import '../widgets/price_header.dart';
import '../widgets/radar_page_shell.dart';
import 'unified_events_panel.dart';

class EventsTab extends StatelessWidget {
  const EventsTab({
    super.key,
    required this.data,
    required this.unifiedEvents,
    this.events,
    required this.errors,
    required this.onRefresh,
    this.onDeepScan,
    this.isRefreshing = false,
  });

  final DashboardData data;
  final List<UnifiedEventItem> unifiedEvents;
  final EventAnalysisData? events;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final VoidCallback? onDeepScan;
  final bool isRefreshing;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;

    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          EventImpactSummary(events: events),
          if (onDeepScan != null) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton.icon(
                onPressed: isRefreshing ? null : onDeepScan,
                icon: const Icon(Icons.radar_rounded, size: 16),
                label: const Text('深度扫描事件', style: TextStyle(fontSize: 11)),
              ),
            ),
          ],
          const SizedBox(height: 16),
          if (events != null) ...[
            EventsPanel(data: events!),
            const SizedBox(height: 16),
          ],
          UnifiedEventsPanel(
            events: unifiedEvents,
            summaryHighImpact: events?.summary.highImpactCount ?? 0,
          ),
          const SizedBox(height: 16),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: EtfFlowPanel(flows: data.capitalFlows)),
                const SizedBox(width: 16),
                Expanded(child: OnChainPanel(flows: data.capitalFlows)),
              ],
            )
          else ...[
            EtfFlowPanel(flows: data.capitalFlows),
            const SizedBox(height: 16),
            OnChainPanel(flows: data.capitalFlows),
          ],
        ],
      ),
    );
  }
}
