class RegimeHistoryEntry {
  const RegimeHistoryEntry({
    required this.recordedAt,
    required this.symbol,
    required this.regime,
    required this.label,
    this.regimeId,
    this.confidence,
    this.summary,
    this.volRegime,
    this.structureRegime,
  });

  factory RegimeHistoryEntry.fromJson(Map<String, dynamic> json) =>
      RegimeHistoryEntry(
        recordedAt: json['recorded_at'] as String? ?? '',
        symbol: json['symbol'] as String? ?? '',
        regime: json['regime'] as String? ?? '',
        regimeId: json['regime_id'] as String?,
        label: json['label'] as String? ?? '',
        confidence: (json['confidence'] as num?)?.toDouble(),
        summary: json['summary'] as String?,
        volRegime: json['vol_regime'] as String?,
        structureRegime: json['structure_regime'] as String?,
      );

  final String recordedAt;
  final String symbol;
  final String regime;
  final String? regimeId;
  final String label;
  final double? confidence;
  final String? summary;
  final String? volRegime;
  final String? structureRegime;
}

class RegimeHistoryData {
  const RegimeHistoryData({
    required this.symbol,
    required this.history,
  });

  factory RegimeHistoryData.fromJson(Map<String, dynamic> json) =>
      RegimeHistoryData(
        symbol: json['symbol'] as String? ?? '',
        history: (json['history'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(RegimeHistoryEntry.fromJson)
            .toList(),
      );

  final String symbol;
  final List<RegimeHistoryEntry> history;
}
