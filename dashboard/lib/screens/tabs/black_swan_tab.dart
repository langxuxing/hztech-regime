import 'package:flutter/material.dart';

import '../../bigevent/event_data.dart';
import '../../models/dashboard_data.dart';
import '../../widgets/black_swan_panel.dart';
import '../../widgets/price_header.dart';
import '../../widgets/radar_page_shell.dart';
import '../../layers/l4_execution_tab.dart';

/// 黑天鹅预警专用模块。
class BlackSwanTab extends StatelessWidget {
  const BlackSwanTab({
    super.key,
    required this.data,
    this.events,
    required this.errors,
    required this.onRefresh,
    this.isRefreshing = false,
  });

  final DashboardData data;
  final EventAnalysisData? events;
  final List<String> errors;
  final Future<void> Function() onRefresh;
  final bool isRefreshing;

  @override
  Widget build(BuildContext context) {
    return RadarPageShell(
      onRefresh: onRefresh,
      errors: errors,
      isRefreshing: isRefreshing,
      header: PriceHeader(data: data, compact: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          BlackSwanPanel(data: data, events: events),
          const SizedBox(height: 16),
          L4ExecutionTab(
            data: data,
            errors: const [],
            onRefresh: onRefresh,
            isRefreshing: isRefreshing,
            embedded: true,
          ),
        ],
      ),
    );
  }
}
