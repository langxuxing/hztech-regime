import '../utils/json_utils.dart';

/// 对外趋势判断契约（/api/radar → trend_judgment）
class TrendJudgment {
  const TrendJudgment({
    required this.trend,
    required this.trendLabel,
    required this.techTrend,
    required this.confidence,
    required this.regimeId,
    required this.regimeLabel,
    required this.stability,
    required this.businessStance,
    this.drivers = const [],
    this.dataTier = 'unknown',
    this.needsHumanJudgment = false,
    this.inRegimeTransition = false,
    this.hmmDisagrees = false,
    this.consensusCapped = false,
    this.consensusMisaligned = false,
    this.modelAgreement,
  });

  factory TrendJudgment.fromJson(Map<String, dynamic> json) => TrendJudgment(
        trend: json['trend'] as String? ?? 'range',
        trendLabel: json['trend_label'] as String? ?? '震荡',
        techTrend: json['tech_trend'] as String? ?? 'range',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        regimeId: json['regime_id'] as String? ?? '',
        regimeLabel: json['regime_label'] as String? ?? '',
        stability: json['stability'] as String? ?? 'provisional',
        businessStance: json['business_stance'] as String? ?? '',
        drivers: (json['drivers'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
        dataTier: json['data_tier'] as String? ?? 'unknown',
        needsHumanJudgment: json['needs_human_judgment'] as bool? ?? false,
        inRegimeTransition: json['in_regime_transition'] as bool? ?? false,
        hmmDisagrees: json['hmm_disagrees'] as bool? ?? false,
        consensusCapped: json['consensus_capped'] as bool? ?? false,
        consensusMisaligned: json['consensus_misaligned'] as bool? ?? false,
        modelAgreement: (json['model_agreement'] as num?)?.toDouble(),
      );

  /// 从 btc_regime 降级推导（API 未升级时）
  factory TrendJudgment.fromBtcRegime(Map<String, dynamic>? btc) {
    if (btc == null || btc.isEmpty) {
      return const TrendJudgment(
        trend: 'range',
        trendLabel: '震荡',
        techTrend: 'range',
        confidence: 0,
        regimeId: '',
        regimeLabel: '—',
        stability: 'provisional',
        businessStance: '数据不可用',
      );
    }
    final trend = btc['raw_trend'] as String? ?? 'range';
    return TrendJudgment(
      trend: trend,
      trendLabel: _trendLabel(trend),
      techTrend: btc['tech_trend'] as String? ?? trend,
      confidence: (btc['confidence'] as num?)?.toDouble() ?? 0.5,
      regimeId: btc['regime_id'] as String? ?? '',
      regimeLabel: btc['regime_label'] as String? ?? '',
      stability: btc['in_regime_transition'] == true ? 'transition' : 'provisional',
      businessStance: '',
      drivers: (btc['drivers'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
    );
  }

  static String _trendLabel(String trend) => switch (trend) {
        'uptrend' => '上涨',
        'downtrend' => '下跌',
        _ => '震荡',
      };

  final String trend;
  final String trendLabel;
  final String techTrend;
  final double confidence;
  final String regimeId;
  final String regimeLabel;
  final String stability;
  final String businessStance;
  final List<String> drivers;
  final String dataTier;
  final bool needsHumanJudgment;
  final bool inRegimeTransition;
  final bool hmmDisagrees;
  final bool consensusCapped;
  final bool consensusMisaligned;
  final double? modelAgreement;

  bool get isConfirmed => stability == 'confirmed';
}

TrendJudgment? parseTrendJudgment(Map<String, dynamic>? json, {Map<String, dynamic>? btcFallback}) {
  if (json != null && json.isNotEmpty) {
    return TrendJudgment.fromJson(json);
  }
  if (btcFallback != null) {
    return TrendJudgment.fromBtcRegime(btcFallback);
  }
  return null;
}
