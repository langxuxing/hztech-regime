import 'package:flutter_test/flutter_test.dart';

import 'package:regime_trend_dashboard/main.dart';

void main() {
  testWidgets('App loads with six-tab navigation', (WidgetTester tester) async {
    await tester.pumpWidget(const RegimeTrendApp());
    expect(find.text('大屏'), findsWidgets);
    expect(find.text('Regime'), findsOneWidget);
    expect(find.text('模型'), findsOneWidget);
  });
}
