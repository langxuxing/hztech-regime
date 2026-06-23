import '../utils/json_utils.dart';

class RegimeJudgment {
  const RegimeJudgment({
    required this.regime,
    required this.label,
    required this.confidence,
    required this.summary,
    required this.volRegime,
    required this.structureRegime,
    this.flowRegime,
    this.drivers = const [],
    this.regimeId,
    this.rawTrend,
    this.volBucket,
    this.nextRegimeLabel,
    this.changepointProb,
    this.inRegimeTransition = false,
    this.triadSummary,
    this.techTrend,
    this.derivatives,
  });

  factory RegimeJudgment.fromJson(Map<String, dynamic> json) => RegimeJudgment(
        regime: json['regime'] as String? ?? 'transition',
        label: json['label'] as String? ?? 'Regime 转换中',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        summary: json['summary'] as String? ?? '',
        volRegime: json['vol_regime'] as String? ?? '未知',
        structureRegime: json['structure_regime'] as String? ?? '结构不明',
        flowRegime: json['flow_regime'] as String?,
        drivers: (json['drivers'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
        regimeId: json['regime_id'] as String?,
        rawTrend: json['raw_trend'] as String?,
        volBucket: json['vol_bucket'] as String?,
        nextRegimeLabel: json['next_regime_label'] as String?,
        changepointProb: (json['changepoint_prob'] as num?)?.toDouble(),
        inRegimeTransition: json['in_regime_transition'] as bool? ?? false,
        triadSummary: json['triad_summary'] as String?,
        techTrend: json['tech_trend'] as String?,
        derivatives: json['derivatives'] != null
            ? asJsonMap(json['derivatives'])
            : null,
      );

  final String regime;
  final String label;
  final double confidence;
  final String summary;
  final String volRegime;
  final String structureRegime;
  final String? flowRegime;
  final List<String> drivers;
  final String? regimeId;
  final String? rawTrend;
  final String? volBucket;
  final String? nextRegimeLabel;
  final double? changepointProb;
  final bool inRegimeTransition;
  final String? triadSummary;
  final String? techTrend;
  final Map<String, dynamic>? derivatives;
}

class MajorEvent {
  const MajorEvent({
    required this.id,
    required this.category,
    required this.title,
    required this.description,
    required this.severity,
    required this.impact,
    this.timestamp,
  });

  factory MajorEvent.fromJson(Map<String, dynamic> json) => MajorEvent(
        id: json['id'] as String? ?? '',
        category: json['category'] as String? ?? 'market',
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        severity: json['severity'] as String? ?? 'low',
        impact: json['impact'] as String? ?? 'neutral',
        timestamp: json['timestamp'] as String?,
      );

  final String id;
  final String category;
  final String title;
  final String description;
  final String severity;
  final String impact;
  final String? timestamp;
}

class TrendJudgment {
  const TrendJudgment({
    required this.direction,
    required this.label,
    required this.confidence,
    required this.shortTerm,
    required this.mediumTerm,
    required this.summary,
    this.keyLevels = const {},
    this.signals = const [],
  });

  factory TrendJudgment.fromJson(Map<String, dynamic> json) => TrendJudgment(
        direction: json['direction'] as String? ?? 'sideways',
        label: json['label'] as String? ?? '横盘',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        shortTerm: json['short_term'] as String? ?? '',
        mediumTerm: json['medium_term'] as String? ?? '',
        summary: json['summary'] as String? ?? '',
        keyLevels: asJsonMap(json['key_levels']).map(
          (k, v) => MapEntry(k, v == null ? null : (v as num).toDouble()),
        ),
        signals: (json['signals'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
      );

  final String direction;
  final String label;
  final double confidence;
  final String shortTerm;
  final String mediumTerm;
  final String summary;
  final Map<String, double?> keyLevels;
  final List<String> signals;
}

class BoardInsights {
  const BoardInsights({
    required this.regime,
    required this.majorEvents,
    required this.trend,
  });

  factory BoardInsights.fromJson(Map<String, dynamic> json) => BoardInsights(
        regime: RegimeJudgment.fromJson(asJsonMap(json['regime'])),
        majorEvents: asJsonMapList(json['major_events'])
            .map(MajorEvent.fromJson)
            .toList(),
        trend: TrendJudgment.fromJson(asJsonMap(json['trend'])),
      );

  final RegimeJudgment regime;
  final List<MajorEvent> majorEvents;
  final TrendJudgment trend;
}
