import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:regime_trend_dashboard/models/trend_judgment.dart';
import 'package:regime_trend_dashboard/widgets/trend_judgment_hero.dart';

void main() {
  const judgment = TrendJudgment(
    trend: 'uptrend',
    trendLabel: '上涨',
    techTrend: 'uptrend',
    confidence: 0.72,
    regimeId: 'mid_vol_uptrend',
    regimeLabel: '中波上行',
    stability: 'transition',
    businessStance: '顺势做多',
    inRegimeTransition: true,
    needsHumanJudgment: true,
  );

  testWidgets('TrendJudgmentHero shows trend and transition banner', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: TrendJudgmentHero(
            judgment: judgment,
            readinessTier: 'demo',
          ),
        ),
      ),
    );

    expect(find.textContaining('当前趋势'), findsOneWidget);
    expect(find.textContaining('上涨'), findsWidgets);
    expect(find.textContaining('变点转换期'), findsOneWidget);
    expect(find.text('建议人工判断'), findsOneWidget);
    expect(find.text('72%'), findsOneWidget);
  });

  testWidgets('TrendJudgmentHero hides transition banner when confirmed', (tester) async {
    const confirmed = TrendJudgment(
      trend: 'range',
      trendLabel: '震荡',
      techTrend: 'range',
      confidence: 0.5,
      regimeId: 'mid_vol_range',
      regimeLabel: '中波震荡',
      stability: 'confirmed',
      businessStance: '震荡策略',
    );

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: TrendJudgmentHero(judgment: confirmed),
        ),
      ),
    );

    expect(find.textContaining('变点转换期'), findsNothing);
    expect(find.text('已确认'), findsOneWidget);
  });
}
