import 'board_insights.dart';
import 'capital_flows.dart';
import '../utils/json_utils.dart';

class PriceZone {
  const PriceZone({
    required this.low,
    required this.high,
    this.label = '',
    this.kind = '',
  });

  factory PriceZone.fromJson(Map<String, dynamic> json) => PriceZone(
        low: (json['low'] as num).toDouble(),
        high: (json['high'] as num).toDouble(),
        label: json['label'] as String? ?? '',
        kind: json['kind'] as String? ?? '',
      );

  final double low;
  final double high;
  final String label;
  final String kind;

  double get mid => (low + high) / 2;
}

class SmcSnapshot {
  const SmcSnapshot({
    required this.trend,
    this.mssOrChoch,
    required this.mssDirection,
    this.nearestOb,
    this.nearestFvg,
    this.unfilledFvgs = const [],
    this.activeObs = const [],
    this.structureNotes = const [],
  });

  factory SmcSnapshot.fromJson(Map<String, dynamic> json) => SmcSnapshot(
        trend: json['trend'] as String? ?? 'neutral',
        mssOrChoch: json['mss_or_choch'] as String?,
        mssDirection: json['mss_direction'] as int? ?? 0,
        nearestOb: json['nearest_ob'] != null
            ? PriceZone.fromJson(asJsonMap(json['nearest_ob']))
            : null,
        nearestFvg: json['nearest_fvg'] != null
            ? PriceZone.fromJson(asJsonMap(json['nearest_fvg']))
            : null,
        unfilledFvgs: asJsonMapList(json['unfilled_fvgs'])
            .map(PriceZone.fromJson)
            .toList(),
        activeObs: asJsonMapList(json['active_obs'])
            .map(PriceZone.fromJson)
            .toList(),
        structureNotes: (json['structure_notes'] as List<dynamic>? ?? [])
            .map((e) => e.toString())
            .toList(),
      );

  final String trend;
  final String? mssOrChoch;
  final int mssDirection;
  final PriceZone? nearestOb;
  final PriceZone? nearestFvg;
  final List<PriceZone> unfilledFvgs;
  final List<PriceZone> activeObs;
  final List<String> structureNotes;
}

class LiquidityLevel {
  const LiquidityLevel({
    required this.price,
    required this.side,
    required this.swept,
    this.sweepTime,
    required this.strength,
  });

  factory LiquidityLevel.fromJson(Map<String, dynamic> json) => LiquidityLevel(
        price: (json['price'] as num).toDouble(),
        side: json['side'] as String? ?? 'buy_side',
        swept: json['swept'] as bool? ?? false,
        sweepTime: json['sweep_time'] as String?,
        strength: (json['strength'] as num?)?.toDouble() ?? 1,
      );

  final double price;
  final String side;
  final bool swept;
  final String? sweepTime;
  final double strength;
}

class GexLevel {
  const GexLevel({
    required this.price,
    required this.gexNotionalProxy,
    required this.levelType,
    this.source = 'oi_cluster',
  });

  factory GexLevel.fromJson(Map<String, dynamic> json) => GexLevel(
        price: (json['price'] as num).toDouble(),
        gexNotionalProxy: (json['gex_notional_proxy'] as num).toDouble(),
        levelType: json['level_type'] as String? ?? 'magnet',
        source: json['source'] as String? ?? 'oi_cluster',
      );

  final double price;
  final double gexNotionalProxy;
  final String levelType;
  final String source;
}

class OrderBookSnapshot {
  const OrderBookSnapshot({
    required this.bestBid,
    required this.bestAsk,
    required this.spreadBps,
    required this.bidDepthUsdt,
    required this.askDepthUsdt,
    required this.imbalance,
    this.walls = const [],
  });

  factory OrderBookSnapshot.fromJson(Map<String, dynamic> json) =>
      OrderBookSnapshot(
        bestBid: (json['best_bid'] as num).toDouble(),
        bestAsk: (json['best_ask'] as num).toDouble(),
        spreadBps: (json['spread_bps'] as num).toDouble(),
        bidDepthUsdt: (json['bid_depth_usdt'] as num).toDouble(),
        askDepthUsdt: (json['ask_depth_usdt'] as num).toDouble(),
        imbalance: (json['imbalance'] as num).toDouble(),
        walls: asJsonMapList(json['walls']),
      );

  final double bestBid;
  final double bestAsk;
  final double spreadBps;
  final double bidDepthUsdt;
  final double askDepthUsdt;
  final double imbalance;
  final List<Map<String, dynamic>> walls;
}

class TradeAdvice {
  const TradeAdvice({
    required this.bias,
    required this.confidence,
    this.entryZone,
    this.stopLoss,
    this.takeProfit = const [],
    required this.timeHorizon,
    required this.reasoning,
    this.risks = const [],
    required this.confluenceScore,
    this.ruleBased = false,
  });

  factory TradeAdvice.fromJson(Map<String, dynamic> json) {
    final entry = json['entry_zone'];
    List<double>? entryZone;
    if (entry is List && entry.length == 2) {
      entryZone = entry.map((e) => (e as num).toDouble()).toList();
    }

    return TradeAdvice(
      bias: json['bias'] as String? ?? 'neutral',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      entryZone: entryZone,
      stopLoss: (json['stop_loss'] as num?)?.toDouble(),
      takeProfit: (json['take_profit'] as List<dynamic>? ?? [])
          .map((e) => (e as num).toDouble())
          .toList(),
      timeHorizon: json['time_horizon'] as String? ?? 'intraday',
      reasoning: json['reasoning'] as String? ?? '',
      risks: (json['risks'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      confluenceScore: (json['confluence_score'] as num?)?.toDouble() ?? 0,
      ruleBased: json['rule_based'] as bool? ?? false,
    );
  }

  final String bias;
  final double confidence;
  final List<double>? entryZone;
  final double? stopLoss;
  final List<double> takeProfit;
  final String timeHorizon;
  final String reasoning;
  final List<String> risks;
  final double confluenceScore;
  final bool ruleBased;
}

class DashboardData {
  const DashboardData({
    required this.symbol,
    required this.exchange,
    required this.timeframe,
    required this.asOf,
    required this.lastPrice,
    required this.ohlcvSummary,
    required this.smc,
    required this.liquidityLevels,
    required this.gexLevels,
    this.orderbook,
    this.volRatio,
    this.volStatus,
    required this.advice,
    required this.mode,
    required this.board,
    this.featureSnapshot,
    this.macroHazardFlag = false,
    this.btcRegime,
    this.capitalFlows,
    this.quantState,
    this.pipeline,
    this.regimeConfirmation,
    this.blackSwanAlert,
    this.unifiedEvents = const [],
    this.chart,
    this.tradingBrief,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) => DashboardData(
        symbol: json['symbol'] as String? ?? '',
        exchange: json['exchange'] as String? ?? '',
        timeframe: json['timeframe'] as String? ?? '30m',
        asOf: json['as_of'] as String? ?? '',
        lastPrice: (json['last_price'] as num?)?.toDouble() ?? 0,
        ohlcvSummary: asJsonMap(json['ohlcv_summary']),
        smc: SmcSnapshot.fromJson(asJsonMap(json['smc'])),
        liquidityLevels: asJsonMapList(json['liquidity_levels'])
            .map(LiquidityLevel.fromJson)
            .toList(),
        gexLevels: asJsonMapList(json['gex_levels'])
            .map(GexLevel.fromJson)
            .toList(),
        orderbook: json['orderbook'] != null
            ? OrderBookSnapshot.fromJson(asJsonMap(json['orderbook']))
            : null,
        volRatio: (json['vol_ratio'] as num?)?.toDouble(),
        volStatus: json['vol_status'] as String?,
        advice: TradeAdvice.fromJson(asJsonMap(json['advice'])),
        mode: json['mode'] as String? ?? 'rule_based',
        board: BoardInsights.fromJson(
          json['board'] != null
              ? asJsonMap(json['board'])
              : _fallbackBoard(json),
        ),
        featureSnapshot: json['feature_snapshot'] != null
            ? asJsonMap(json['feature_snapshot'])
            : null,
        macroHazardFlag: json['macro_hazard_flag'] as bool? ?? false,
        btcRegime: json['btc_regime'] != null
            ? asJsonMap(json['btc_regime'])
            : null,
        capitalFlows: json['capital_flows'] != null
            ? CapitalFlowsSnapshot.fromJson(asJsonMap(json['capital_flows']))
            : null,
        quantState: json['quant_state'] != null
            ? asJsonMap(json['quant_state'])
            : null,
        pipeline: json['pipeline'] != null ? asJsonMap(json['pipeline']) : null,
        regimeConfirmation: json['regime_confirmation'] != null
            ? asJsonMap(json['regime_confirmation'])
            : null,
        blackSwanAlert: json['black_swan_alert'] != null
            ? asJsonMap(json['black_swan_alert'])
            : null,
        unifiedEvents: asJsonMapList(json['unified_events']),
        chart: json['chart'] != null ? asJsonMap(json['chart']) : null,
        tradingBrief: json['trading_brief'] != null ? asJsonMap(json['trading_brief']) : null,
      );

  static Map<String, dynamic> _fallbackBoard(Map<String, dynamic> json) {
    final advice = asJsonMap(json['advice']);
    final smc = asJsonMap(json['smc']);
    final bias = advice['bias'] as String? ?? 'neutral';
    return {
      'regime': {
        'regime': smc['trend'] == 'bullish'
            ? 'trend_up'
            : smc['trend'] == 'bearish'
                ? 'trend_down'
                : 'range',
        'label': 'Regime 未加载',
        'confidence': 0.5,
        'summary': '后端未返回 board 字段',
        'vol_regime': json['vol_status'] ?? '未知',
        'structure_regime': smc['trend'] ?? 'unknown',
        'drivers': [],
      },
      'major_events': [],
      'trend': {
        'direction': bias == 'long'
            ? 'up'
            : bias == 'short'
                ? 'down'
                : 'sideways',
        'label': bias == 'long' ? '偏多' : bias == 'short' ? '偏空' : '横盘',
        'confidence': advice['confidence'] ?? 0.5,
        'short_term': '—',
        'medium_term': '—',
        'summary': advice['reasoning'] ?? '',
        'key_levels': {},
        'signals': [],
      },
    };
  }

  final String symbol;
  final String exchange;
  final String timeframe;
  final String asOf;
  final double lastPrice;
  final Map<String, dynamic> ohlcvSummary;
  final SmcSnapshot smc;
  final List<LiquidityLevel> liquidityLevels;
  final List<GexLevel> gexLevels;
  final OrderBookSnapshot? orderbook;
  final double? volRatio;
  final String? volStatus;
  final TradeAdvice advice;
  final String mode;
  final BoardInsights board;
  final Map<String, dynamic>? featureSnapshot;
  final bool macroHazardFlag;
  final Map<String, dynamic>? btcRegime;
  final CapitalFlowsSnapshot? capitalFlows;
  final Map<String, dynamic>? quantState;
  final Map<String, dynamic>? pipeline;
  final Map<String, dynamic>? regimeConfirmation;
  final Map<String, dynamic>? blackSwanAlert;
  final List<Map<String, dynamic>> unifiedEvents;
  final Map<String, dynamic>? chart;
  final Map<String, dynamic>? tradingBrief;
}
