import 'package:flutter_test/flutter_test.dart';

import 'package:regime_trend_dashboard/models/trend_judgment.dart';

void main() {
  group('TrendJudgment.fromJson', () {
    test('parses full contract', () {
      final tj = TrendJudgment.fromJson({
        'trend': 'uptrend',
        'trend_label': '上涨',
        'tech_trend': 'uptrend',
        'confidence': 0.72,
        'regime_id': 'mid_vol_uptrend',
        'regime_label': '中波上行',
        'stability': 'confirmed',
        'business_stance': '顺势做多',
        'drivers': ['A', 'B'],
        'data_tier': 'demo',
        'needs_human_judgment': false,
        'in_regime_transition': false,
        'hmm_disagrees': true,
        'consensus_misaligned': false,
        'consensus_capped': false,
        'model_agreement': 0.8,
        'dashboard_regime': 'trend_up',
      });
      expect(tj.trend, 'uptrend');
      expect(tj.dashboardRegime, 'trend_up');
      expect(tj.suggestedHumanRegime, 'trend_up');
      expect(tj.hmmDisagrees, isTrue);
      expect(tj.isConfirmed, isTrue);
      expect(tj.confidence, 0.72);
    });

    test('suggestedHumanRegime from regime_id', () {
      final tj = TrendJudgment.fromJson({
        'trend': 'downtrend',
        'trend_label': '下跌',
        'tech_trend': 'downtrend',
        'confidence': 0.6,
        'regime_id': 'low_vol_downtrend',
        'regime_label': '低波下行',
        'stability': 'provisional',
        'business_stance': '',
        'drivers': [],
        'data_tier': 'demo',
        'needs_human_judgment': false,
        'in_regime_transition': false,
        'hmm_disagrees': false,
        'consensus_misaligned': false,
        'consensus_capped': false,
      });
      expect(tj.suggestedHumanRegime, 'trend_down');
    });

    test('fromBtcRegime fallback', () {
      final tj = TrendJudgment.fromBtcRegime({
        'raw_trend': 'downtrend',
        'confidence': 0.6,
        'regime_id': 'low_vol_downtrend',
        'regime_label': '低波下行',
      });
      expect(tj.trend, 'downtrend');
      expect(tj.trendLabel, '下跌');
      expect(tj.stability, 'provisional');
    });

    test('parseTrendJudgment prefers explicit block', () {
      final parsed = parseTrendJudgment(
        {'trend': 'range', 'trend_label': '震荡', 'tech_trend': 'range', 'confidence': 0.5, 'regime_id': 'x', 'regime_label': 'y', 'stability': 'provisional', 'business_stance': '', 'drivers': [], 'data_tier': 'demo', 'needs_human_judgment': false, 'in_regime_transition': false, 'hmm_disagrees': false, 'consensus_misaligned': false, 'consensus_capped': false},
        btcFallback: {'raw_trend': 'uptrend'},
      );
      expect(parsed?.trend, 'range');
    });
  });
}
