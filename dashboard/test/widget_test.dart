import 'package:flutter_test/flutter_test.dart';

import 'package:regime_trend_dashboard/main.dart';

void main() {
  testWidgets('App loads with five-tab navigation', (WidgetTester tester) async {
    await tester.pumpWidget(const RegimeTrendApp());
    expect(find.text('首页'), findsWidgets);
    expect(find.text('Regime'), findsOneWidget);
    expect(find.text('信号'), findsOneWidget);
  });
}
