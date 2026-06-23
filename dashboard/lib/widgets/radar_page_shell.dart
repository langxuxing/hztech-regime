import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// 各 Tab 页共享：下拉刷新 + 最大宽度 + 错误条。
class RadarPageShell extends StatelessWidget {
  const RadarPageShell({
    super.key,
    required this.onRefresh,
    required this.child,
    this.errors = const [],
    this.header,
    this.isRefreshing = false,
  });

  final Future<void> Function() onRefresh;
  final Widget child;
  final List<String> errors;
  final Widget? header;
  final bool isRefreshing;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1100),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (errors.isNotEmpty) _ErrorBanner(errors: errors),
                      if (header != null) ...[
                        header!,
                        const SizedBox(height: 12),
                      ],
                      child,
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.errors});

  final List<String> errors;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.neutral.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.neutral.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '部分模块加载失败（其余数据仍可用）',
            style: TextStyle(fontSize: 11, color: AppTheme.neutral),
          ),
          ...errors.take(3).map(
                (e) => Text(
                  '• $e',
                  style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                ),
              ),
        ],
      ),
    );
  }
}
