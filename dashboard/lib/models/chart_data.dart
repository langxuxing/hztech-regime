import '../utils/json_utils.dart';

class OhlcBar {
  const OhlcBar({
    required this.time,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    this.volume = 0,
    this.kama,
  });

  factory OhlcBar.fromJson(Map<String, dynamic> json) => OhlcBar(
        time: json['t']?.toString() ?? '',
        open: (json['o'] as num).toDouble(),
        high: (json['h'] as num).toDouble(),
        low: (json['l'] as num).toDouble(),
        close: (json['c'] as num).toDouble(),
        volume: (json['v'] as num?)?.toDouble() ?? 0,
        kama: (json['kama'] as num?)?.toDouble(),
      );

  final String time;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;
  final double? kama;

  bool get isBull => close >= open;
}

class ChartOverlay {
  const ChartOverlay({
    required this.kind,
    this.price,
    this.priceLow,
    this.priceHigh,
    this.label = '',
    this.color = 'accent',
    this.swept = false,
    this.notional,
  });

  factory ChartOverlay.fromJson(Map<String, dynamic> json) => ChartOverlay(
        kind: json['kind']?.toString() ?? '',
        price: (json['price'] as num?)?.toDouble(),
        priceLow: (json['price_low'] as num?)?.toDouble(),
        priceHigh: (json['price_high'] as num?)?.toDouble(),
        label: json['label']?.toString() ?? '',
        color: json['color']?.toString() ?? 'accent',
        swept: json['swept'] == true,
        notional: (json['notional'] as num?)?.toDouble(),
      );

  final String kind;
  final double? price;
  final double? priceLow;
  final double? priceHigh;
  final String label;
  final String color;
  final bool swept;
  final double? notional;
}

class ChartPayload {
  const ChartPayload({
    required this.timeframe,
    required this.bars,
    required this.overlays,
    this.lastPrice,
    this.smcTrend,
    this.changePct24h,
  });

  factory ChartPayload.fromJson(Map<String, dynamic> json) => ChartPayload(
        timeframe: json['timeframe']?.toString() ?? '30m',
        bars: asJsonMapList(json['bars']).map(OhlcBar.fromJson).toList(),
        overlays: asJsonMapList(json['overlays']).map(ChartOverlay.fromJson).toList(),
        lastPrice: (json['last_price'] as num?)?.toDouble(),
        smcTrend: json['smc_trend']?.toString(),
        changePct24h: (json['change_pct_24h'] as num?)?.toDouble(),
      );

  final String timeframe;
  final List<OhlcBar> bars;
  final List<ChartOverlay> overlays;
  final double? lastPrice;
  final String? smcTrend;
  final double? changePct24h;
}
