import '../utils/json_utils.dart';

class PredictionSignal {
  const PredictionSignal({
    required this.source,
    required this.category,
    required this.direction,
    required this.score,
    required this.confidence,
    required this.horizon,
    required this.label,
    this.error,
  });

  factory PredictionSignal.fromJson(Map<String, dynamic> json) => PredictionSignal(
        source: json['source'] as String? ?? '',
        category: json['category'] as String? ?? '',
        direction: json['direction'] as String? ?? 'neutral',
        score: (json['score'] as num?)?.toDouble() ?? 0,
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        horizon: json['horizon'] as String? ?? '',
        label: json['label'] as String? ?? '',
        error: json['error'] as String?,
      );

  final String source;
  final String category;
  final String direction;
  final double score;
  final double confidence;
  final String horizon;
  final String label;
  final String? error;
}

class TrendConsensus {
  const TrendConsensus({
    required this.asOf,
    required this.asset,
    required this.direction,
    required this.label,
    required this.score,
    required this.confidence,
    required this.agreement,
    required this.summary,
    this.bullishCount = 0,
    this.bearishCount = 0,
    this.neutralCount = 0,
    this.sourcesOk = 0,
    this.sourcesFailed = 0,
    this.signals = const [],
    this.macroHazardFlag = false,
  });

  factory TrendConsensus.fromJson(Map<String, dynamic> json) => TrendConsensus(
        asOf: json['as_of'] as String? ?? '',
        asset: json['asset'] as String? ?? 'BTC',
        direction: json['direction'] as String? ?? 'neutral',
        label: json['label'] as String? ?? '集成中性',
        score: (json['score'] as num?)?.toDouble() ?? 0,
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        agreement: (json['agreement'] as num?)?.toDouble() ?? 0,
        summary: json['summary'] as String? ?? '',
        bullishCount: json['bullish_count'] as int? ?? 0,
        bearishCount: json['bearish_count'] as int? ?? 0,
        neutralCount: json['neutral_count'] as int? ?? 0,
        sourcesOk: json['sources_ok'] as int? ?? 0,
        sourcesFailed: json['sources_failed'] as int? ?? 0,
        signals: asJsonMapList(json['signals'])
            .map(PredictionSignal.fromJson)
            .toList(),
        macroHazardFlag: json['macro_hazard_flag'] as bool? ?? false,
      );

  final String asOf;
  final String asset;
  final String direction;
  final String label;
  final double score;
  final double confidence;
  final double agreement;
  final String summary;
  final int bullishCount;
  final int bearishCount;
  final int neutralCount;
  final int sourcesOk;
  final int sourcesFailed;
  final List<PredictionSignal> signals;
  final bool macroHazardFlag;
}
