import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/chart_data.dart';
import '../theme/app_theme.dart';
import 'common.dart';

/// K 线图 + 流动性/GEX/SMC 水平叠加。
class OhlcvChartPanel extends StatelessWidget {
  const OhlcvChartPanel({
    super.key,
    required this.chart,
    this.height = 300,
  });

  final ChartPayload chart;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (chart.bars.isEmpty) {
      return const SectionCard(
        title: 'K 线图',
        icon: Icons.candlestick_chart_outlined,
        child: Text(
          'K 线数据未加载，请连接 API',
          style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
        ),
      );
    }

    return SectionCard(
      title: 'K 线图 · ${chart.timeframe}',
      icon: Icons.candlestick_chart_outlined,
      trailing: chart.smcTrend != null
          ? StatusBadge(label: chart.smcTrend!, color: _trendColor(chart.smcTrend!))
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: height,
            child: CustomPaint(
              painter: _CandlestickPainter(
                bars: chart.bars,
                overlays: chart.overlays,
              ),
              child: Container(),
            ),
          ),
          const SizedBox(height: 10),
          _OverlayLegend(overlays: chart.overlays),
        ],
      ),
    );
  }

  Color _trendColor(String t) => switch (t) {
        'bullish' => AppTheme.long,
        'bearish' => AppTheme.short,
        _ => AppTheme.neutral,
      };
}

class _OverlayLegend extends StatelessWidget {
  const _OverlayLegend({required this.overlays});

  final List<ChartOverlay> overlays;

  @override
  Widget build(BuildContext context) {
    final items = overlays.where((o) => o.kind != 'kama').take(8);
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: items.map((o) {
        final color = _colorFor(o.color);
        final label = o.label.isNotEmpty
            ? o.label
            : '${o.kind}${o.price != null ? ' @${o.price!.toStringAsFixed(0)}' : ''}';
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            border: Border(left: BorderSide(color: color, width: 3)),
            color: color.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(label, style: TextStyle(fontSize: 9, color: color)),
        );
      }).toList(),
    );
  }
}

Color _colorFor(String name) => switch (name) {
      'long' => AppTheme.long,
      'short' => AppTheme.short,
      'neutral' => AppTheme.neutral,
      'magnet' => AppTheme.magnet,
      _ => AppTheme.accent,
    };

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter({required this.bars, required this.overlays});

  final List<OhlcBar> bars;
  final List<ChartOverlay> overlays;

  @override
  void paint(Canvas canvas, Size size) {
    if (bars.isEmpty) return;

    final padL = 8.0;
    final padR = 8.0;
    final padT = 12.0;
    final padB = 24.0;
    final plotW = size.width - padL - padR;
    final plotH = size.height - padT - padB;

    double yMin = bars.first.low;
    double yMax = bars.first.high;
    for (final b in bars) {
      yMin = math.min(yMin, b.low);
      yMax = math.max(yMax, b.high);
    }
    for (final o in overlays) {
      if (o.price != null) {
        yMin = math.min(yMin, o.price!);
        yMax = math.max(yMax, o.price!);
      }
      if (o.priceLow != null) yMin = math.min(yMin, o.priceLow!);
      if (o.priceHigh != null) yMax = math.max(yMax, o.priceHigh!);
    }
    final span = (yMax - yMin).abs();
    yMin -= span * 0.02;
    yMax += span * 0.02;
    if (yMax <= yMin) {
      yMax = yMin + 1;
    }

    double yOf(double price) => padT + plotH * (1 - (price - yMin) / (yMax - yMin));

    // Grid
    final gridPaint = Paint()
      ..color = AppTheme.border.withValues(alpha: 0.4)
      ..strokeWidth = 0.5;
    for (var i = 0; i <= 4; i++) {
      final y = padT + plotH * i / 4;
      canvas.drawLine(Offset(padL, y), Offset(padL + plotW, y), gridPaint);
    }

    // Overlays (zones first)
    for (final o in overlays) {
      if (o.priceLow != null && o.priceHigh != null) {
        final y1 = yOf(o.priceHigh!);
        final y2 = yOf(o.priceLow!);
        final fill = Paint()..color = _colorFor(o.color).withValues(alpha: 0.12);
        canvas.drawRect(Rect.fromLTRB(padL, y1, padL + plotW, y2), fill);
      }
    }
    for (final o in overlays) {
      if (o.price == null) continue;
      final y = yOf(o.price!);
      final paint = Paint()
        ..color = _colorFor(o.color).withValues(alpha: o.swept ? 0.35 : 0.85)
        ..strokeWidth = o.kind == 'kama' ? 1.5 : 1.0;
      if (o.kind == 'kama') {
        paint.style = PaintingStyle.stroke;
      }
      canvas.drawLine(Offset(padL, y), Offset(padL + plotW, y), paint);
    }

    // KAMA line from bars
    final kamaPoints = <Offset>[];
    final n = bars.length;
    final slot = plotW / n;
    for (var i = 0; i < n; i++) {
      final k = bars[i].kama;
      if (k == null) continue;
      kamaPoints.add(Offset(padL + slot * (i + 0.5), yOf(k)));
    }
    if (kamaPoints.length > 1) {
      final path = Path()..moveTo(kamaPoints.first.dx, kamaPoints.first.dy);
      for (var i = 1; i < kamaPoints.length; i++) {
        path.lineTo(kamaPoints[i].dx, kamaPoints[i].dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = AppTheme.accent.withValues(alpha: 0.9)
          ..strokeWidth = 1.2
          ..style = PaintingStyle.stroke,
      );
    }

    // Candles
    final bodyW = math.max(2.0, slot * 0.55);
    for (var i = 0; i < n; i++) {
      final b = bars[i];
      final cx = padL + slot * (i + 0.5);
      final yHigh = yOf(b.high);
      final yLow = yOf(b.low);
      final yOpen = yOf(b.open);
      final yClose = yOf(b.close);
      final color = b.isBull ? AppTheme.long : AppTheme.short;

      canvas.drawLine(Offset(cx, yHigh), Offset(cx, yLow), Paint()..color = color);

      final top = math.min(yOpen, yClose);
      final bottom = math.max(yOpen, yClose);
      final rect = Rect.fromCenter(
        center: Offset(cx, (top + bottom) / 2),
        width: bodyW,
        height: math.max(1.0, bottom - top),
      );
      canvas.drawRect(rect, Paint()..color = color);
    }

    // Y labels
    final textStyle = TextStyle(color: AppTheme.textSecondary.withValues(alpha: 0.8), fontSize: 9);
    for (var i = 0; i <= 2; i++) {
      final price = yMax - (yMax - yMin) * i / 2;
      final tp = TextPainter(
        text: TextSpan(text: price.toStringAsFixed(0), style: textStyle),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width - tp.width - 2, padT + plotH * i / 2 - 6));
    }
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) =>
      oldDelegate.bars != bars || oldDelegate.overlays != overlays;
}
