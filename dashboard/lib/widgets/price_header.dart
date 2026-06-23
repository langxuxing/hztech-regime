import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/dashboard_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

class PriceHeader extends StatelessWidget {
  const PriceHeader({super.key, required this.data, this.compact = false});

  final DashboardData data;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final change = (data.ohlcvSummary['change_pct_24h'] as num?)?.toDouble() ??
        (data.ohlcvSummary['last_change_pct'] as num?)?.toDouble();
    final changeColor = change == null
        ? AppTheme.textSecondary
        : change >= 0
            ? AppTheme.long
            : AppTheme.short;

    return Container(
      padding: EdgeInsets.all(compact ? 14 : 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.surfaceHigh,
            AppTheme.surface.withValues(alpha: 0.6),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                data.symbol,
                style: TextStyle(
                  fontSize: compact ? 16 : 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(width: 10),
              StatusBadge(
                label: '${data.exchange.toUpperCase()} · 实时',
                color: AppTheme.accent,
              ),
              const Spacer(),
              StatusBadge(
                label: data.mode == 'llm' ? 'LLM' : '规则引擎',
                color: AppTheme.magnet,
              ),
            ],
          ),
          SizedBox(height: compact ? 8 : 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                _formatPrice(data.lastPrice),
                style: TextStyle(
                  fontSize: compact ? 24 : 36,
                  fontWeight: FontWeight.w700,
                  height: 1,
                ),
              ),
              const SizedBox(width: 12),
              if (change != null)
                Text(
                  '${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: changeColor,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '更新: ${_formatTime(data.asOf)}',
            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  String _formatPrice(double price) {
    if (price >= 1000) return NumberFormat('#,##0.00').format(price);
    if (price >= 1) return price.toStringAsFixed(4);
    return price.toStringAsFixed(6);
  }

  String _formatTime(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return DateFormat('MM-dd HH:mm:ss').format(dt);
    } catch (_) {
      return iso;
    }
  }
}
