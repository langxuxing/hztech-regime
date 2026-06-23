import '../utils/json_utils.dart';

class EventImpact {
  const EventImpact({
    required this.eventId,
    required this.impactScore,
    required this.impactLevel,
    required this.direction,
    required this.expectedVolatility,
    required this.reasoning,
    this.btcPrice,
    required this.confidence,
    required this.actionable,
    this.timeHorizon = 'intraday',
  });

  factory EventImpact.fromJson(Map<String, dynamic> json) => EventImpact(
        eventId: json['event_id'] as String? ?? '',
        impactScore: (json['impact_score'] as num?)?.toDouble() ?? 0,
        impactLevel: json['impact_level'] as String? ?? 'low',
        direction: json['direction'] as String? ?? 'neutral',
        expectedVolatility: json['expected_volatility'] as String? ?? 'normal',
        reasoning: json['reasoning'] as String? ?? '',
        btcPrice: (json['btc_price'] as num?)?.toDouble(),
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        actionable: json['actionable'] as bool? ?? false,
        timeHorizon: json['time_horizon'] as String? ?? 'intraday',
      );

  final String eventId;
  final double impactScore;
  final String impactLevel;
  final String direction;
  final String expectedVolatility;
  final String reasoning;
  final double? btcPrice;
  final double confidence;
  final bool actionable;
  final String timeHorizon;
}

class MarketEvent {
  const MarketEvent({
    required this.id,
    required this.title,
    required this.summary,
    required this.category,
    required this.source,
    required this.publishedAt,
    required this.importance,
    required this.btcRelevance,
    this.tags = const [],
    this.sourceUrl,
    this.scheduledAt,
    this.isScheduled = false,
    this.impact,
  });

  factory MarketEvent.fromJson(Map<String, dynamic> json) => MarketEvent(
        id: json['id'] as String? ?? '',
        title: json['title'] as String? ?? '',
        summary: json['summary'] as String? ?? '',
        category: json['category'] as String? ?? 'other',
        source: json['source'] as String? ?? '',
        publishedAt: json['published_at'] as String? ?? '',
        importance: json['importance'] as int? ?? 3,
        btcRelevance: (json['btc_relevance'] as num?)?.toDouble() ?? 0.5,
        tags: (json['tags'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
        sourceUrl: json['source_url'] as String?,
        scheduledAt: json['scheduled_at'] as String?,
        isScheduled: json['is_scheduled'] as bool? ?? false,
        impact: json['impact'] != null
            ? EventImpact.fromJson(asJsonMap(json['impact']))
            : null,
      );

  final String id;
  final String title;
  final String summary;
  final String category;
  final String source;
  final String publishedAt;
  final int importance;
  final double btcRelevance;
  final List<String> tags;
  final String? sourceUrl;
  final String? scheduledAt;
  final bool isScheduled;
  final EventImpact? impact;
}

class EventSummary {
  const EventSummary({
    required this.totalCalendar,
    required this.totalBreaking,
    required this.highImpactCount,
    required this.overallRisk,
    this.bullishSignals = 0,
    this.bearishSignals = 0,
    this.upcomingMacro = 0,
  });

  factory EventSummary.fromJson(Map<String, dynamic> json) => EventSummary(
        totalCalendar: json['total_calendar'] as int? ?? 0,
        totalBreaking: json['total_breaking'] as int? ?? 0,
        highImpactCount: json['high_impact_count'] as int? ?? 0,
        overallRisk: json['overall_risk'] as String? ?? 'low',
        bullishSignals: json['bullish_signals'] as int? ?? 0,
        bearishSignals: json['bearish_signals'] as int? ?? 0,
        upcomingMacro: json['upcoming_macro'] as int? ?? 0,
      );

  final int totalCalendar;
  final int totalBreaking;
  final int highImpactCount;
  final String overallRisk;
  final int bullishSignals;
  final int bearishSignals;
  final int upcomingMacro;
}

class EventAnalysisData {
  const EventAnalysisData({
    required this.asOf,
    this.btcPrice,
    required this.dataQuality,
    required this.notes,
    required this.calendarEvents,
    required this.breakingEvents,
    required this.upcomingHighImpact,
    required this.analyzedEvents,
    required this.summary,
    this.scanDurationMs = 0,
  });

  factory EventAnalysisData.fromJson(Map<String, dynamic> json) =>
      EventAnalysisData(
        asOf: json['as_of'] as String? ?? '',
        btcPrice: (json['btc_price'] as num?)?.toDouble(),
        dataQuality: json['data_quality'] as String? ?? 'partial',
        notes: (json['notes'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
        calendarEvents: asJsonMapList(json['calendar_events'])
            .map(MarketEvent.fromJson)
            .toList(),
        breakingEvents: asJsonMapList(json['breaking_events'])
            .map(MarketEvent.fromJson)
            .toList(),
        upcomingHighImpact: asJsonMapList(json['upcoming_high_impact'])
            .map(MarketEvent.fromJson)
            .toList(),
        analyzedEvents: asJsonMapList(json['analyzed_events'])
            .map(MarketEvent.fromJson)
            .toList(),
        summary: EventSummary.fromJson(asJsonMap(json['summary'])),
        scanDurationMs: json['scan_duration_ms'] as int? ?? 0,
      );

  final String asOf;
  final double? btcPrice;
  final String dataQuality;
  final List<String> notes;
  final List<MarketEvent> calendarEvents;
  final List<MarketEvent> breakingEvents;
  final List<MarketEvent> upcomingHighImpact;
  final List<MarketEvent> analyzedEvents;
  final EventSummary summary;
  final int scanDurationMs;
}
