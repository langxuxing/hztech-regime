import '../models/board_insights.dart';
import 'event_data.dart';

/// 合并 board 结构事件 + 外部事件引擎的统一条目。
class UnifiedEventItem {
  const UnifiedEventItem({
    required this.id,
    required this.title,
    required this.description,
    required this.category,
    required this.severity,
    required this.impact,
    this.timestamp,
    this.source,
    this.impactScore,
    this.impactConfidence,
    this.actionable = false,
    this.isUpcoming = false,
  });

  final String id;
  final String title;
  final String description;
  final String category;
  final String severity;
  final String impact;
  final String? timestamp;
  final String? source;
  final double? impactScore;
  final double? impactConfidence;
  final bool actionable;
  final bool isUpcoming;

  int get severityRank => switch (severity) {
        'high' || 'critical' => 0,
        'medium' => 1,
        _ => 2,
      };
}

class EventMerger {
  static List<UnifiedEventItem> merge({
    required List<MajorEvent> boardEvents,
    EventAnalysisData? external,
    List<Map<String, dynamic>> serverUnified = const [],
  }) {
    if (serverUnified.isNotEmpty) {
      final seen = <String>{};
      final items = <UnifiedEventItem>[];
      for (final raw in serverUnified) {
        final item = _fromServerMap(raw);
        final key = item.id.isNotEmpty ? item.id : item.title;
        if (seen.contains(key)) continue;
        seen.add(key);
        items.add(item);
      }
      for (final e in boardEvents) {
        if (e.title == '暂无重大事件') continue;
        final key = e.id.isNotEmpty ? e.id : e.title;
        if (seen.contains(key)) continue;
        items.add(
          UnifiedEventItem(
            id: e.id,
            title: e.title,
            description: e.description,
            category: _mapBoardCategory(e.category),
            severity: e.severity,
            impact: e.impact,
            timestamp: e.timestamp,
            source: 'structure',
          ),
        );
      }
      items.sort((a, b) {
        final sr = a.severityRank.compareTo(b.severityRank);
        if (sr != 0) return sr;
        return (b.timestamp ?? '').compareTo(a.timestamp ?? '');
      });
      return items;
    }

    final seen = <String>{};
    final items = <UnifiedEventItem>[];

    void add(UnifiedEventItem item) {
      final key = item.id.isNotEmpty ? item.id : item.title;
      if (seen.contains(key)) return;
      seen.add(key);
      items.add(item);
    }

    for (final e in boardEvents) {
      if (e.title == '暂无重大事件') continue;
      add(
        UnifiedEventItem(
          id: e.id,
          title: e.title,
          description: e.description,
          category: _mapBoardCategory(e.category),
          severity: e.severity,
          impact: e.impact,
          timestamp: e.timestamp,
          source: 'structure',
        ),
      );
    }

    if (external != null) {
      for (final e in external.calendarEvents) {
        if (seen.contains(e.id)) continue;
        add(
          UnifiedEventItem(
            id: e.id,
            title: e.title,
            description: e.summary,
            category: _mapExternalCategory(e.category),
            severity: e.importance >= 4 ? 'high' : 'medium',
            impact: e.impact?.direction ?? 'neutral',
            timestamp: e.scheduledAt ?? e.publishedAt,
            source: e.source,
            impactScore: e.impact?.impactScore,
            impactConfidence: e.impact?.confidence,
            actionable: e.impact?.actionable ?? false,
            isUpcoming: e.isScheduled,
          ),
        );
      }

      for (final e in external.upcomingHighImpact) {
        add(
          UnifiedEventItem(
            id: 'up-${e.id}',
            title: e.title,
            description: e.summary,
            category: 'macro',
            severity: e.importance >= 4 ? 'high' : 'medium',
            impact: 'neutral',
            timestamp: e.scheduledAt ?? e.publishedAt,
            source: e.source,
            isUpcoming: true,
          ),
        );
      }

      for (final e in external.analyzedEvents) {
        final imp = e.impact;
        add(
          UnifiedEventItem(
            id: e.id,
            title: e.title,
            description: imp?.reasoning ?? e.summary,
            category: _mapExternalCategory(e.category),
            severity: imp?.impactLevel ?? 'medium',
            impact: imp?.direction ?? 'neutral',
            timestamp: e.publishedAt,
            source: e.source,
            impactScore: imp?.impactScore,
            impactConfidence: imp?.confidence,
            actionable: imp?.actionable ?? false,
          ),
        );
      }

      for (final e in external.breakingEvents) {
        if (seen.contains(e.id)) continue;
        add(
          UnifiedEventItem(
            id: e.id,
            title: e.title,
            description: e.summary,
            category: 'breaking',
            severity: e.importance >= 4 ? 'high' : 'medium',
            impact: 'neutral',
            timestamp: e.publishedAt,
            source: e.source,
          ),
        );
      }
    }

    items.sort((a, b) {
      final sr = a.severityRank.compareTo(b.severityRank);
      if (sr != 0) return sr;
      return (b.timestamp ?? '').compareTo(a.timestamp ?? '');
    });

    return items;
  }

  static UnifiedEventItem _fromServerMap(Map<String, dynamic> raw) {
    return UnifiedEventItem(
      id: raw['id']?.toString() ?? '',
      title: raw['title']?.toString() ?? '',
      description: raw['description']?.toString() ?? '',
      category: raw['category']?.toString() ?? 'breaking',
      severity: raw['severity']?.toString() ?? 'medium',
      impact: raw['impact']?.toString() ?? 'neutral',
      timestamp: raw['timestamp']?.toString(),
      source: raw['source']?.toString(),
      impactScore: (raw['impact_score'] as num?)?.toDouble(),
      impactConfidence: (raw['impact_confidence'] as num?)?.toDouble(),
      actionable: raw['actionable'] == true,
      isUpcoming: raw['is_upcoming'] == true,
    );
  }

  static String _mapBoardCategory(String c) => switch (c) {
        'structure' => 'structure',
        'liquidity' => 'structure',
        'macro' => 'macro',
        'onchain' => 'onchain',
        'flow' => 'onchain',
        'etf' => 'etf',
        'volatility' => 'breaking',
        'regime' => 'structure',
        _ => 'breaking',
      };

  static String _mapExternalCategory(String c) => switch (c) {
        'macro' => 'macro',
        'exchange' => 'breaking',
        'liquidation' => 'onchain',
        _ => 'breaking',
      };
}

enum EventTab { all, macro, etf, breaking, structure, onchain }

extension EventTabLabel on EventTab {
  String get label => switch (this) {
        EventTab.all => '全部',
        EventTab.macro => '宏观',
        EventTab.etf => 'ETF',
        EventTab.breaking => '突发',
        EventTab.structure => '结构',
        EventTab.onchain => '链上',
      };

  bool matches(UnifiedEventItem item) => switch (this) {
        EventTab.all => true,
        EventTab.macro => item.category == 'macro',
        EventTab.etf => item.category == 'etf',
        EventTab.breaking => item.category == 'breaking',
        EventTab.structure => item.category == 'structure',
        EventTab.onchain => item.category == 'onchain',
      };
}
