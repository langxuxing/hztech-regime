import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:http/http.dart' as http;

import '../models/dashboard_data.dart';
import '../bigevent/event_data.dart';
import '../regime/regime_history.dart';
import '../forecast/trend_consensus.dart';
import '../models/data_sources_status.dart';
import '../utils/json_utils.dart';

class RadarLoadResult {
  const RadarLoadResult({
    required this.dashboard,
    this.events,
    this.consensus,
    this.regimeHistory,
    this.errors = const [],
    this.usedMock = false,
  });

  final DashboardData dashboard;
  final EventAnalysisData? events;
  final TrendConsensus? consensus;
  final RegimeHistoryData? regimeHistory;
  final List<String> errors;
  final bool usedMock;
}

class ApiService {
  ApiService({String? baseUrl, String? apiKey})
      : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'API_BASE_URL',
              defaultValue: 'http://127.0.0.1:8765',
            ),
        _apiKey = apiKey ??
            const String.fromEnvironment('API_KEY', defaultValue: '');

  final String baseUrl;
  final String _apiKey;

  Map<String, String> get _headers {
    if (_apiKey.isEmpty) return const {};
    return {'X-API-Key': _apiKey};
  }

  Future<http.Response> _get(Uri uri, {Duration? timeout}) {
    return http.get(uri, headers: _headers).timeout(
          timeout ?? const Duration(seconds: 45),
        );
  }

  Future<http.Response> _post(Uri uri, {required String body, Duration? timeout}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      ..._headers,
    };
    return http.post(uri, headers: headers, body: body).timeout(
          timeout ?? const Duration(seconds: 45),
        );
  }

  Future<DashboardData> fetchDashboard({
    String exchange = 'binance',
    String symbol = 'BTC/USDT:USDT',
  }) async {
    final uri = Uri.parse('$baseUrl/api/dashboard').replace(
      queryParameters: {'exchange': exchange, 'symbol': symbol},
    );
    final response = await _get(uri);
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '看板'));
    }
    return DashboardData.fromJson(asJsonMap(jsonDecode(response.body)));
  }

  Future<EventAnalysisData> fetchEvents({bool refresh = false}) async {
    final path = refresh ? '/api/events/scan' : '/api/events';
    final uri = Uri.parse('$baseUrl$path');
    final response = await _get(uri, timeout: Duration(seconds: refresh ? 90 : 30));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '事件'));
    }
    return EventAnalysisData.fromJson(asJsonMap(jsonDecode(response.body)));
  }

  Future<TrendConsensus> fetchTrendConsensus() async {
    final uri = Uri.parse('$baseUrl/api/trend-consensus');
    final response = await _get(uri, timeout: const Duration(seconds: 30));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '趋势共识'));
    }
    return TrendConsensus.fromJson(asJsonMap(jsonDecode(response.body)));
  }

  Future<RegimeHistoryData> fetchRegimeHistory({
    String symbol = 'BTC/USDT:USDT',
  }) async {
    final uri = Uri.parse('$baseUrl/api/regime/history').replace(
      queryParameters: {'symbol': symbol, 'limit': '30'},
    );
    final response = await _get(uri, timeout: const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, 'Regime历史'));
    }
    return RegimeHistoryData.fromJson(asJsonMap(jsonDecode(response.body)));
  }

  Future<Map<String, dynamic>> submitHumanJudgment({
    String symbol = 'BTC/USDT:USDT',
    required String humanRegime,
    String? humanTrend,
    String? humanNotes,
  }) async {
    final uri = Uri.parse('$baseUrl/api/regime/human-judgment').replace(
      queryParameters: {'symbol': symbol},
    );
    final body = <String, dynamic>{
      'human_regime': humanRegime,
      if (humanTrend != null) 'human_trend': humanTrend,
      if (humanNotes != null) 'human_notes': humanNotes,
    };
    final response = await _post(uri, body: jsonEncode(body));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '人工判断'));
    }
    return asJsonMap(jsonDecode(response.body));
  }

  Future<List<Map<String, dynamic>>> fetchModelLeaderboard({
    String symbol = 'BTC/USDT:USDT',
    String segment = '',
    int windowDays = 30,
  }) async {
    final uri = Uri.parse('$baseUrl/api/regime/model-leaderboard').replace(
      queryParameters: {
        'symbol': symbol,
        if (segment.isNotEmpty) 'segment': segment,
        'window_days': '$windowDays',
      },
    );
    final response = await _get(uri, timeout: const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, 'Leaderboard'));
    }
    final body = asJsonMap(jsonDecode(response.body));
    return asJsonMapList(body['leaderboard']);
  }

  Future<Map<String, dynamic>> fetchRecommendedModel({
    String symbol = 'BTC/USDT:USDT',
  }) async {
    final uri = Uri.parse('$baseUrl/api/regime/recommended-model').replace(
      queryParameters: {'symbol': symbol},
    );
    final response = await _get(uri);
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '推荐模型'));
    }
    final body = asJsonMap(jsonDecode(response.body));
    return asJsonMap(body['recommendation']);
  }

  Future<List<Map<String, dynamic>>> fetchHumanJudgmentHistory({
    String symbol = 'BTC/USDT:USDT',
    int limit = 20,
  }) async {
    final uri = Uri.parse('$baseUrl/api/regime/human-judgment').replace(
      queryParameters: {'symbol': symbol, 'limit': '$limit'},
    );
    final response = await _get(uri, timeout: const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '标注历史'));
    }
    final body = asJsonMap(jsonDecode(response.body));
    return asJsonMapList(body['history']);
  }

  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/health');
      final response = await http.get(uri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<DataSourcesStatus> fetchSchedulerStatus() async {
    final uri = Uri.parse('$baseUrl/api/scheduler/status');
    final response = await _get(uri, timeout: const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '数据源状态'));
    }
    return DataSourcesStatus.fromJson(asJsonMap(jsonDecode(response.body)));
  }

  /// 单次拉取聚合雷达快照（含 version / snapshot_id）。
  Future<Map<String, dynamic>> fetchRadar({
    String exchange = 'binance',
    String symbol = 'BTC/USDT:USDT',
    bool live = false,
  }) async {
    final uri = Uri.parse('$baseUrl/api/radar').replace(
      queryParameters: {
        'exchange': exchange,
        'symbol': symbol,
        if (live) 'live': 'true',
      },
    );
    final response = await _get(uri, timeout: const Duration(seconds: 90));
    if (response.statusCode != 200) {
      throw Exception(_errorFromResponse(response, '雷达'));
    }
    return asJsonMap(jsonDecode(response.body));
  }

  /// 优先 /api/radar 单次拉取；失败时回退并行多接口。
  Future<RadarLoadResult> loadRadar({
    bool deepScanEvents = false,
  }) async {
    final errors = <String>[];

    try {
      final bundle = await fetchRadar(live: deepScanEvents);
      final dashJson = asJsonMap(bundle['dashboard']);
      final dashboard = DashboardData.fromJson(dashJson);

      EventAnalysisData? events;
      if (bundle['events'] != null) {
        events = EventAnalysisData.fromJson(asJsonMap(bundle['events']));
      }

      TrendConsensus? consensus;
      if (bundle['consensus'] != null) {
        consensus = TrendConsensus.fromJson(asJsonMap(bundle['consensus']));
      }

      RegimeHistoryData? history;
      if (bundle['regime_history'] != null) {
        history = RegimeHistoryData.fromJson(asJsonMap(bundle['regime_history']));
      }

      for (final err in asJsonStringList(bundle['errors'])) {
        errors.add(err);
      }

      return RadarLoadResult(
        dashboard: dashboard,
        events: events,
        consensus: consensus,
        regimeHistory: history,
        errors: errors,
      );
    } catch (e) {
      errors.add('雷达聚合: $e');
      try {
        return await _loadRadarLegacy(errors: errors, deepScanEvents: deepScanEvents);
      } catch (legacyError) {
        errors.add('看板: $legacyError');
        rethrow;
      }
    }
  }

  Future<RadarLoadResult> _loadRadarLegacy({
    required List<String> errors,
    bool deepScanEvents = false,
  }) async {
    DashboardData dashboard;

    try {
      dashboard = await fetchDashboard();
    } catch (e) {
      errors.add('看板: $e');
      rethrow;
    }

    final symbol = dashboard.symbol;
    EventAnalysisData? events;
    TrendConsensus? consensus;
    RegimeHistoryData? history;

    await Future.wait([
      () async {
        try {
          events = await fetchEvents(refresh: deepScanEvents);
        } catch (e) {
          errors.add('事件: $e');
        }
      }(),
      () async {
        try {
          consensus = await fetchTrendConsensus();
        } catch (e) {
          errors.add('趋势共识: $e');
        }
      }(),
      () async {
        try {
          history = await fetchRegimeHistory(symbol: symbol);
        } catch (e) {
          errors.add('Regime历史: $e');
        }
      }(),
    ]);

    return RadarLoadResult(
      dashboard: dashboard,
      events: events,
      consensus: consensus,
      regimeHistory: history,
      errors: errors,
    );
  }

  String _errorFromResponse(http.Response response, String label) {
    try {
      final body = asJsonMap(jsonDecode(response.body));
      return body['error']?.toString() ?? '$label 失败 (${response.statusCode})';
    } catch (_) {
      final snippet = response.body.length > 80
          ? '${response.body.substring(0, 80)}…'
          : response.body;
      return '$label 失败 (${response.statusCode}): $snippet';
    }
  }

  TrendConsensus mockConsensus() => TrendConsensus.fromJson({
        'as_of': DateTime.now().toUtc().toIso8601String(),
        'asset': 'BTC',
        'direction': 'up',
        'label': '集成偏多',
        'score': 0.24,
        'confidence': 0.62,
        'agreement': 0.71,
        'bullish_count': 4,
        'bearish_count': 2,
        'neutral_count': 1,
        'sources_ok': 5,
        'sources_failed': 2,
        'summary': '多源信号偏多，Funding 与 Taker 方向一致。',
        'signals': [
          {
            'source': 'binance_taker',
            'category': 'flow',
            'direction': 'up',
            'score': 0.3,
            'confidence': 0.7,
            'horizon': '15m',
            'label': 'Taker 买入占优',
          },
        ],
      });

  RegimeHistoryData mockRegimeHistory() {
    final now = DateTime.now().toUtc();
    return RegimeHistoryData.fromJson({
      'symbol': 'BTC/USDT:USDT',
      'history': [
        {
          'recorded_at': now.toIso8601String(),
          'symbol': 'BTC/USDT:USDT',
          'regime': 'trend_up',
          'regime_id': 'high_vol_uptrend',
          'label': '高波上涨 · 现货 CVD 确认',
          'confidence': 0.82,
          'vol_regime': '高波动',
          'structure_regime': 'KAMA+唐奇安多头',
        },
        {
          'recorded_at': now.subtract(const Duration(hours: 6)).toIso8601String(),
          'symbol': 'BTC/USDT:USDT',
          'regime': 'range',
          'regime_id': 'mid_vol_range',
          'label': '中波震荡 · 等待突破',
          'confidence': 0.62,
          'vol_regime': '中波动',
          'structure_regime': 'KAMA+唐奇安区间',
        },
      ],
    });
  }

  EventAnalysisData mockEvents() {
    final now = DateTime.now().toUtc().toIso8601String();
    return EventAnalysisData.fromJson({
      'as_of': now,
      'btc_price': 97234.5,
      'data_quality': 'demo',
      'notes': ['演示数据'],
      'scan_duration_ms': 120,
      'summary': {
        'total_calendar': 2,
        'total_breaking': 2,
        'high_impact_count': 2,
        'overall_risk': 'mixed',
        'bullish_signals': 1,
        'bearish_signals': 1,
        'upcoming_macro': 1,
      },
      'calendar_events': [
        {
          'id': 'demo-cal-1',
          'title': '美国 CPI 月率',
          'summary': 'US | Major Impact | 预期 0.3%',
          'category': 'macro',
          'source': 'coinglass',
          'published_at': now,
          'importance': 5,
          'btc_relevance': 0.85,
          'tags': ['macro', 'cpi'],
          'is_scheduled': true,
          'scheduled_at': now,
        },
      ],
      'breaking_events': [
        {
          'id': 'demo-br-1',
          'title': 'Whale Alert: 5,000 BTC transferred to Coinbase',
          'summary': 'Large exchange inflow detected',
          'category': 'liquidation',
          'source': 'x:demo',
          'published_at': now,
          'importance': 4,
          'btc_relevance': 0.9,
          'tags': ['x', 'whale'],
        },
      ],
      'upcoming_high_impact': [
        {
          'id': 'demo-cal-1',
          'title': '美国 CPI 月率',
          'summary': 'US | Major Impact',
          'category': 'macro',
          'source': 'coinglass',
          'published_at': now,
          'importance': 5,
          'btc_relevance': 0.85,
          'tags': ['macro'],
          'is_scheduled': true,
        },
      ],
      'analyzed_events': [
        {
          'id': 'demo-br-1',
          'title': 'Whale Alert: 5,000 BTC transferred to Coinbase',
          'summary': 'Large exchange inflow',
          'category': 'liquidation',
          'source': 'x:demo',
          'published_at': now,
          'importance': 4,
          'btc_relevance': 0.9,
          'tags': ['x'],
          'impact': {
            'event_id': 'demo-br-1',
            'impact_score': -0.35,
            'impact_level': 'high',
            'direction': 'bearish',
            'expected_volatility': 'high',
            'reasoning': '大额流入交易所，潜在卖压',
            'confidence': 0.72,
            'actionable': true,
          },
        },
      ],
    });
  }

  DashboardData mockData() => DashboardData.fromJson({
        'symbol': 'BTC/USDT:USDT',
        'exchange': 'binance',
        'timeframe': '30m',
        'as_of': DateTime.now().toUtc().toIso8601String(),
        'last_price': 97234.5,
        'macro_hazard_flag': false,
        'ohlcv_summary': {
          'bars': 120,
          'last_change_pct': 1.82,
          'change_pct_24h': 1.82,
        },
        'smc': {
          'trend': 'bullish',
          'mss_or_choch': 'CHoCH',
          'mss_direction': 1,
          'structure_notes': ['Higher low on 30m'],
        },
        'liquidity_levels': [
          {'price': 96500, 'side': 'sell_side', 'swept': true, 'strength': 0.85},
          {'price': 95800, 'side': 'buy_side', 'swept': false, 'strength': 1.2},
          {'price': 98800, 'side': 'sell_side', 'swept': false, 'strength': 0.95},
        ],
        'gex_levels': [
          {'price': 97000, 'gex_notional_proxy': 4200000, 'level_type': 'magnet', 'source': 'deribit'},
          {'price': 98500, 'gex_notional_proxy': 3100000, 'level_type': 'resistance', 'source': 'deribit'},
          {'price': 95500, 'gex_notional_proxy': 2800000, 'level_type': 'support', 'source': 'deribit'},
        ],
        'capital_flows': {
          'data_quality': 'demo',
          'notes': ['演示数据'],
          'btc_onchain': {
            'asset': 'BTC',
            'chain_volume_24h_usd': 12500000000,
            'transactions_24h': 412000,
            'volume_change_7d_pct': 8.2,
            'largest_tx_24h_usd': 85000000,
            'interpretation': '链上成交额 7d +8.2%；链上活动升温',
            'source': 'blockchair',
          },
          'btc_exchange_wallet': {
            'asset': 'BTC',
            'net_to_exchange_1d': -1250,
            'net_to_exchange_7d': -4200,
            'top_exchanges': [
              {'exchange': 'Binance', 'change_1d': -800},
              {'exchange': 'Coinbase', 'change_1d': -320},
            ],
            'source': 'coinglass:exchange_balance',
          },
          'btc_market_flows': [
            {
              'asset': 'BTC',
              'market': 'futures',
              'periods': [
                {'period': '24h', 'netflow_usd': 125000000, 'change_pct': 12.5},
              ],
              'source': 'coinglass:futures',
            },
          ],
          'btc_etf': {
            'asset': 'BTC',
            'latest': {
              'date': '2026-06-20',
              'flow_usd': 285000000,
              'price_usd': 97234,
              'tickers': [
                {'ticker': 'IBIT', 'flow_usd': 180000000},
                {'ticker': 'FBTC', 'flow_usd': 95000000},
                {'ticker': 'GBTC', 'flow_usd': -45000000},
              ],
            },
            'history': [
              {'date': '2026-06-14', 'flow_usd': 120000000},
              {'date': '2026-06-15', 'flow_usd': -45000000},
              {'date': '2026-06-16', 'flow_usd': 210000000},
              {'date': '2026-06-17', 'flow_usd': 95000000},
              {'date': '2026-06-18', 'flow_usd': 180000000},
              {'date': '2026-06-19', 'flow_usd': 65000000},
              {'date': '2026-06-20', 'flow_usd': 285000000},
            ],
            'total_7d_usd': 920000000,
            'total_30d_usd': 2100000000,
            'interpretation': r'最新日净流入 +$285M；7 日累计大幅净流入',
            'source': 'coinglass:etf_flow',
          },
        },
        'vol_ratio': 0.22,
        'vol_status': 'elevated',
        'advice': {
          'bias': 'long',
          'confidence': 0.68,
          'entry_zone': [96800, 97200],
          'stop_loss': 96200,
          'take_profit': [98200, 99100],
          'time_horizon': 'intraday',
          'reasoning': 'Bullish CHoCH with liquidity sweep below.',
          'risks': ['Macro event risk'],
          'confluence_score': 0.71,
          'rule_based': true,
        },
        'mode': 'rule_based',
        'feature_snapshot': {
          'gex_engine': {
            'gamma_wall_call': 98500,
            'gamma_wall_put': 95500,
            'source': 'deribit',
            'alerts': ['Call wall 距现价 +1.3%'],
          },
          'relative': {
            'call_wall_pct': 1.31,
            'put_wall_pct': -1.78,
          },
          'liquidation': {
            'pain_price': 96800,
            'dominant_side': 'long',
          },
        },
        'board': {
          'regime': {
            'regime': 'trend_up',
            'regime_id': 'high_vol_uptrend',
            'label': '高波上涨 · 现货 CVD 确认',
            'confidence': 0.82,
            'summary': '高波上涨且现货 CVD 确认，BTC 97234 上方趋势有效。',
            'vol_regime': '高波动',
            'structure_regime': 'KAMA+唐奇安多头',
            'triad_summary': 'Triad 融合：结构偏多 + 波动中高 + 资金流净流出所',
            'drivers': ['KAMA 轨道偏多', '现货 CVD 创新高'],
          },
          'major_events': [
            {
              'id': 'evt-0',
              'category': 'structure',
              'title': 'CHoCH 结构突破',
              'description': '最新 bar 出现 CHoCH，方向=看涨',
              'severity': 'high',
              'impact': 'bullish',
            },
            {
              'id': 'evt-etf',
              'category': 'etf',
              'title': 'BTC Spot ETF 净流入',
              'description': r'2026-06-20 净流 +$285M；7d 累计 +$920M',
              'severity': 'high',
              'impact': 'bullish',
            },
          ],
          'trend': {
            'direction': 'up',
            'label': '偏多',
            'confidence': 0.75,
            'short_term': '延续上攻',
            'medium_term': '中期偏多',
            'summary': '短周期延续上攻，Regime 为高波上涨。',
            'key_levels': {
              'support': 96800,
              'resistance': 98500,
              'invalidation': 96200,
              'kama': 97100,
            },
            'signals': ['Regime: 高波上涨 + CVD 确认', 'CHoCH 看涨'],
          },
        },
        'orderbook': {
          'best_bid': 97200,
          'best_ask': 97235,
          'spread_bps': 3.6,
          'bid_depth_usdt': 1250000,
          'ask_depth_usdt': 980000,
          'imbalance': 0.12,
          'walls': [],
        },
        'btc_regime': _mockBtcRegime(),
        'quant_state': _mockQuantState(),
        'regime_confirmation': _mockRegimeConfirmation(),
        'black_swan_alert': _mockBlackSwanAlert(),
        'pipeline': _mockPipeline(),
        'unified_events': [
          {
            'id': 'evt-0',
            'title': 'CHoCH 结构突破',
            'description': '最新 bar 出现 CHoCH，方向=看涨',
            'category': 'structure',
            'severity': 'high',
            'impact': 'bullish',
            'source': 'structure',
          },
        ],
        'chart': _mockChart(),
        'trading_brief': _mockTradingBrief(),
      });

  Map<String, dynamic> _mockBtcRegime() => {
        'regime_id': 'high_vol_uptrend',
        'regime_label': '高波上涨 · 现货 CVD 确认',
        'raw_trend': 'uptrend',
        'vol_bucket': 'high_vol',
        'confidence': 0.82,
        'dashboard_regime': 'trend_up',
        'changepoint_prob': 0.15,
        'in_regime_transition': false,
        'matrix': {
          'current_cell': 'high_vol_uptrend',
          'confirmed_cell': 'high_vol_uptrend',
          'history_points': [
            {'cell': 'mid_vol_range', 'trend': 0, 'vol': 0.5},
            {'cell': 'high_vol_uptrend', 'trend': 0.8, 'vol': 0.85},
          ],
        },
        'hmm_probs': {
          'low_vol_uptrend': 0.05,
          'high_vol_uptrend': 0.72,
          'high_vol_range': 0.18,
          'low_vol_range': 0.05,
        },
        'triad': {
          'summary': 'Triad 融合偏多',
          'fusion_confidence': 0.78,
          'hmm': {'state_probs': [0.1, 0.15, 0.65, 0.1], 'current_label': 'bull'},
        },
        'models': {
          'heuristic': {
            'model_name': 'Heuristic',
            'regime_label': '高波上涨',
            'raw_trend': 'uptrend',
            'confidence': 0.8,
          },
          'hmm': {
            'model_name': 'HMM',
            'regime_label': '高波上涨',
            'raw_trend': 'uptrend',
            'confidence': 0.75,
          },
        },
        'model_comparison': {
          'agreement_ratio': 0.85,
          'dominant_trend': 'uptrend',
          'needs_human_judgment': false,
          'summary': '多模型共识偏多',
        },
      };

  Map<String, dynamic> _mockQuantState() => {
        'macro_score': 1,
        'flow_score': 2,
        'gex_score': 1,
        'score_label': 'M1 F2 G1',
        'event_risk': 'elevated',
        'event_risk_score': 2,
        'diagnosis': '趋势跟随',
        'diagnosis_id': 'trend_follow',
        'system_commands': ['CTA: ENABLE', 'GRID: SUSPEND'],
        'match_type': 'exact',
        'matrix_quadrant': 'high_vol_uptrend',
        'boundaries': {'upper_price': 98500, 'lower_price': 96200},
        'weekly_policy': {'label': '偏多', 'bias': 'long'},
        'daily_sop': [],
        'black_swan': _mockBlackSwanAlert(),
      };

  Map<String, dynamic> _mockRegimeConfirmation() => {
        'combined': {
          'live_regime_id': 'high_vol_uptrend',
          'confirmed_regime_id': 'high_vol_uptrend',
          'regime_label': '高波上涨 · 现货 CVD 确认',
          'confidence': 0.82,
        },
        'transition_penalty_applied': false,
        'dwell_bars': 3,
        'min_dwell_bars': 2,
        'regime_switched': false,
        'debouncer': {'cooldown_active': false, 'cooldown_remaining_sec': 0},
        'notes': [],
      };

  Map<String, dynamic> _mockBlackSwanAlert() => {
        'level': 1,
        'level_label': 'watch',
        'suspended': false,
        'circuit_breaker_active': false,
        'triggers': ['前瞻波动率领先实现波动率 → 高波预警'],
        'scores': {
          'macro_hazard': 0,
          'liq_pulse': 0.2,
          'changepoint': 0.15,
          'dvol_lead': 0.8,
        },
        'actions': {
          'position_scale': 0.85,
          'allow_new_orders': true,
          'widen_stop_multiplier': 1.1,
        },
      };

  Map<String, dynamic> _mockPipeline() => {
        'flow': ['L1', 'L2', 'L3', 'L4'],
        'layers': {
          'ingestion': {
            'transform': {'confirmed_bars': 119, 'dropped_unclosed': true},
            'market': {
              'close': 97234.5,
              'kama': 97100,
              'donchian_upper': 98500,
              'donchian_lower': 95800,
              'smc_trend': 'bullish',
            },
            'volatility': {
              'vol_ratio': 0.22,
              'gk_realized_vol': 0.45,
              'dvol_leads_gk': true,
            },
            'microstructure': {
              'funding_rate': 0.0001,
              'oi_change_pct': 1.2,
              'cvd_trend': 'bullish',
              'liquidation_pulse': {
                'near_notional_usd': 1200000,
                'total_weight': 3500000,
                'extreme_pulse': false,
              },
            },
            'macro_flow': {
              'etf_flow_zscore': 1.2,
              'etf_7d_usd': 920000000,
              'macro_hazard': false,
            },
          },
          'inference_live': {
            'regime_id': 'high_vol_uptrend',
            'regime_label': '高波上涨',
            'confidence': 0.82,
            'corrections': ['CVD 真突破确认'],
          },
          'inference_confirmed': {
            'regime_id': 'high_vol_uptrend',
            'regime_label': '高波上涨',
            'confidence': 0.82,
          },
          'confirmation': _mockRegimeConfirmation(),
          'black_swan': _mockBlackSwanAlert(),
          'execution': {
            'suspended': false,
            'circuit_breaker_active': false,
            'routing_commands': ['CTA: ENABLE weight=1.0', 'GRID: SUSPEND'],
            'parameter_adjustments': {
              'position_scale': 0.85,
              'stop_loss_multiplier': 1.1,
              'breakout_threshold_scale': 1.0,
              'grid_enabled': false,
              'cta_enabled': true,
            },
          },
        },
      };

  Map<String, dynamic> _mockChart() {
    final bars = <Map<String, dynamic>>[];
  var price = 96800.0;
  for (var i = 0; i < 60; i++) {
    final o = price;
    final c = price + (i % 5 - 2) * 80;
    final h = math.max(o, c) + 120;
    final l = math.min(o, c) - 120;
    bars.add({
      't': '2026-06-${(20 + i ~/ 24).toString().padLeft(2, '0')}T${(i % 24).toString().padLeft(2, '0')}:00:00Z',
      'o': o,
      'h': h,
      'l': l,
      'c': c,
      'v': 1200 + i * 10,
      'kama': (o + c) / 2 - 50,
    });
    price = c;
  }
    return {
      'timeframe': '30m',
      'bars': bars,
      'last_price': 97234.5,
      'smc_trend': 'bullish',
      'overlays': [
        {'kind': 'kama', 'price': 97100, 'label': 'KAMA', 'color': 'accent'},
        {'kind': 'donchian_upper', 'price': 98500, 'label': '唐奇安上', 'color': 'neutral'},
        {'kind': 'donchian_lower', 'price': 95800, 'label': '唐奇安下', 'color': 'neutral'},
        {'kind': 'liquidity', 'price': 96500, 'label': '流动性 sell_side', 'color': 'short', 'swept': true},
        {'kind': 'gex', 'price': 97000, 'label': 'GEX magnet', 'color': 'magnet', 'notional': 4200000},
      ],
    };
  }

  Map<String, dynamic> _mockTradingBrief() => {
        'horizon': '1h-4h',
        'bias': 'long',
        'confidence': 0.68,
        'confluence_score': 0.71,
        'scenario_bull': '突破 98500 且 CVD 确认 → 延续上攻',
        'scenario_bear': '跌破 96200 → 下探买盘 OB',
        'scenario_base': '区间 95800–98500 震荡，偏多',
        'smc_action': '趋势=bullish · CHoCH(多) · 关注 OB 96800-97200',
        'liquidity_note': '最近待清洗位 下方 95800',
        'gex_note': '磁吸/墙位: magnet@97000, resistance@98500',
        'derivatives_note': 'OI +1.2% · 费率 0.0001 · CVD bullish',
        'flow_note': 'ETF 日流 +\$285M',
        'catalysts': ['CHoCH 结构信号', 'ETF 净流入'],
        'ai_enhanced': false,
        'ai_mode': 'rule_based',
        'ai_summary': 'Bullish CHoCH with liquidity sweep below. CVD 确认真突破。',
        'operation_plan': [
          '方向: 做多 (置信 68%)',
          '入场区 96800–97200',
          '止损 96200',
          '止盈 98200 / 99100',
        ],
        'key_levels': {
          'current': 97234.5,
          'support': 96800,
          'resistance': 98500,
          'stop_loss': 96200,
        },
        'derivatives': {
          'oi_change_pct': 1.2,
          'funding_rate': 0.0001,
          'cvd_trend': 'bullish',
          'spot_cvd_breakout': true,
        },
        'flows': {'summary': 'ETF 日流 +\$285M', 'etf_signal': 'ETF 净流入'},
      };
}
