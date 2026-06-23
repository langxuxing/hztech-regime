import '../utils/json_utils.dart';

class FlowPeriod {
  const FlowPeriod({
    required this.period,
    this.inflowUsd,
    this.outflowUsd,
    this.netflowUsd,
    this.changePct,
  });

  factory FlowPeriod.fromJson(Map<String, dynamic> json) => FlowPeriod(
        period: json['period'] as String? ?? '',
        inflowUsd: (json['inflow_usd'] as num?)?.toDouble(),
        outflowUsd: (json['outflow_usd'] as num?)?.toDouble(),
        netflowUsd: (json['netflow_usd'] as num?)?.toDouble(),
        changePct: (json['change_pct'] as num?)?.toDouble(),
      );

  final String period;
  final double? inflowUsd;
  final double? outflowUsd;
  final double? netflowUsd;
  final double? changePct;
}

class MarketFundFlow {
  const MarketFundFlow({
    required this.asset,
    required this.market,
    this.periods = const [],
    this.source = '',
  });

  factory MarketFundFlow.fromJson(Map<String, dynamic> json) => MarketFundFlow(
        asset: json['asset'] as String? ?? '',
        market: json['market'] as String? ?? '',
        periods: asJsonMapList(json['periods']).map(FlowPeriod.fromJson).toList(),
        source: json['source'] as String? ?? '',
      );

  final String asset;
  final String market;
  final List<FlowPeriod> periods;
  final String source;
}

class ExchangeWalletFlow {
  const ExchangeWalletFlow({
    required this.asset,
    this.netToExchange1d,
    this.netToExchange7d,
    this.netToExchange30d,
    this.topExchanges = const [],
    this.source = '',
  });

  factory ExchangeWalletFlow.fromJson(Map<String, dynamic> json) =>
      ExchangeWalletFlow(
        asset: json['asset'] as String? ?? '',
        netToExchange1d: (json['net_to_exchange_1d'] as num?)?.toDouble(),
        netToExchange7d: (json['net_to_exchange_7d'] as num?)?.toDouble(),
        netToExchange30d: (json['net_to_exchange_30d'] as num?)?.toDouble(),
        topExchanges: asJsonMapList(json['top_exchanges']),
        source: json['source'] as String? ?? '',
      );

  final String asset;
  final double? netToExchange1d;
  final double? netToExchange7d;
  final double? netToExchange30d;
  final List<Map<String, dynamic>> topExchanges;
  final String source;
}

class OnChainTransferFlow {
  const OnChainTransferFlow({
    required this.asset,
    this.chainVolume24hUsd,
    this.transactions24h,
    this.volumeChange7dPct,
    this.volumeChange30dPct,
    this.txChange7dPct,
    this.largestTx24hUsd,
    this.interpretation = '',
    this.source = '',
    this.extra = const {},
  });

  factory OnChainTransferFlow.fromJson(Map<String, dynamic> json) =>
      OnChainTransferFlow(
        asset: json['asset'] as String? ?? '',
        chainVolume24hUsd: (json['chain_volume_24h_usd'] as num?)?.toDouble(),
        transactions24h: json['transactions_24h'] as int?,
        volumeChange7dPct: (json['volume_change_7d_pct'] as num?)?.toDouble(),
        volumeChange30dPct: (json['volume_change_30d_pct'] as num?)?.toDouble(),
        txChange7dPct: (json['tx_change_7d_pct'] as num?)?.toDouble(),
        largestTx24hUsd: (json['largest_tx_24h_usd'] as num?)?.toDouble(),
        interpretation: json['interpretation'] as String? ?? '',
        source: json['source'] as String? ?? '',
        extra: asJsonMap(json['extra']),
      );

  final String asset;
  final double? chainVolume24hUsd;
  final int? transactions24h;
  final double? volumeChange7dPct;
  final double? volumeChange30dPct;
  final double? txChange7dPct;
  final double? largestTx24hUsd;
  final String interpretation;
  final String source;
  final Map<String, dynamic> extra;
}

class EtfTickerFlow {
  const EtfTickerFlow({required this.ticker, required this.flowUsd});

  factory EtfTickerFlow.fromJson(Map<String, dynamic> json) => EtfTickerFlow(
        ticker: json['ticker'] as String? ?? '',
        flowUsd: (json['flow_usd'] as num?)?.toDouble() ?? 0,
      );

  final String ticker;
  final double flowUsd;
}

class EtfFlowDay {
  const EtfFlowDay({
    required this.date,
    required this.flowUsd,
    this.priceUsd,
    this.tickers = const [],
  });

  factory EtfFlowDay.fromJson(Map<String, dynamic> json) => EtfFlowDay(
        date: json['date'] as String? ?? '',
        flowUsd: (json['flow_usd'] as num?)?.toDouble() ?? 0,
        priceUsd: (json['price_usd'] as num?)?.toDouble(),
        tickers: asJsonMapList(json['tickers']).map(EtfTickerFlow.fromJson).toList(),
      );

  final String date;
  final double flowUsd;
  final double? priceUsd;
  final List<EtfTickerFlow> tickers;
}

class EtfFlowWeek {
  const EtfFlowWeek({
    required this.weekStart,
    required this.weekEnd,
    required this.flowUsd,
    this.label = '',
    this.daysCount = 0,
  });

  factory EtfFlowWeek.fromJson(Map<String, dynamic> json) => EtfFlowWeek(
        weekStart: json['week_start'] as String? ?? '',
        weekEnd: json['week_end'] as String? ?? '',
        flowUsd: (json['flow_usd'] as num?)?.toDouble() ?? 0,
        label: json['label'] as String? ?? '',
        daysCount: json['days_count'] as int? ?? 0,
      );

  final String weekStart;
  final String weekEnd;
  final double flowUsd;
  final String label;
  final int daysCount;
}

class EtfFlowSnapshot {
  const EtfFlowSnapshot({
    required this.asset,
    this.latest,
    this.history = const [],
    this.weeklyHistory = const [],
    this.total7dUsd,
    this.total30dUsd,
    this.total13wUsd,
    this.interpretation = '',
    this.source = '',
  });

  factory EtfFlowSnapshot.fromJson(Map<String, dynamic> json) => EtfFlowSnapshot(
        asset: json['asset'] as String? ?? '',
        latest: json['latest'] != null
            ? EtfFlowDay.fromJson(asJsonMap(json['latest']))
            : null,
        history: asJsonMapList(json['history']).map(EtfFlowDay.fromJson).toList(),
        weeklyHistory:
            asJsonMapList(json['weekly_history']).map(EtfFlowWeek.fromJson).toList(),
        total7dUsd: (json['total_7d_usd'] as num?)?.toDouble(),
        total30dUsd: (json['total_30d_usd'] as num?)?.toDouble(),
        total13wUsd: (json['total_13w_usd'] as num?)?.toDouble(),
        interpretation: json['interpretation'] as String? ?? '',
        source: json['source'] as String? ?? '',
      );

  final String asset;
  final EtfFlowDay? latest;
  final List<EtfFlowDay> history;
  final List<EtfFlowWeek> weeklyHistory;
  final double? total7dUsd;
  final double? total30dUsd;
  final double? total13wUsd;
  final String interpretation;
  final String source;
}

class CapitalFlowsSnapshot {
  const CapitalFlowsSnapshot({
    this.dataQuality = 'partial',
    this.notes = const [],
    this.btcMarketFlows = const [],
    this.ethMarketFlows = const [],
    this.btcExchangeWallet,
    this.ethExchangeWallet,
    this.btcOnchain,
    this.ethOnchain,
    this.btcEtf,
    this.ethEtf,
  });

  factory CapitalFlowsSnapshot.fromJson(Map<String, dynamic> json) =>
      CapitalFlowsSnapshot(
        dataQuality: json['data_quality'] as String? ?? 'partial',
        notes: (json['notes'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
        btcMarketFlows: asJsonMapList(json['btc_market_flows'])
            .map(MarketFundFlow.fromJson)
            .toList(),
        ethMarketFlows: asJsonMapList(json['eth_market_flows'])
            .map(MarketFundFlow.fromJson)
            .toList(),
        btcExchangeWallet: json['btc_exchange_wallet'] != null
            ? ExchangeWalletFlow.fromJson(asJsonMap(json['btc_exchange_wallet']))
            : null,
        ethExchangeWallet: json['eth_exchange_wallet'] != null
            ? ExchangeWalletFlow.fromJson(asJsonMap(json['eth_exchange_wallet']))
            : null,
        btcOnchain: json['btc_onchain'] != null
            ? OnChainTransferFlow.fromJson(asJsonMap(json['btc_onchain']))
            : null,
        ethOnchain: json['eth_onchain'] != null
            ? OnChainTransferFlow.fromJson(asJsonMap(json['eth_onchain']))
            : null,
        btcEtf: json['btc_etf'] != null
            ? EtfFlowSnapshot.fromJson(asJsonMap(json['btc_etf']))
            : null,
        ethEtf: json['eth_etf'] != null
            ? EtfFlowSnapshot.fromJson(asJsonMap(json['eth_etf']))
            : null,
      );

  final String dataQuality;
  final List<String> notes;
  final List<MarketFundFlow> btcMarketFlows;
  final List<MarketFundFlow> ethMarketFlows;
  final ExchangeWalletFlow? btcExchangeWallet;
  final ExchangeWalletFlow? ethExchangeWallet;
  final OnChainTransferFlow? btcOnchain;
  final OnChainTransferFlow? ethOnchain;
  final EtfFlowSnapshot? btcEtf;
  final EtfFlowSnapshot? ethEtf;

  bool get hasOnchainData => btcOnchain != null || ethOnchain != null;
  bool get hasEtfData => btcEtf != null || ethEtf != null;
}

String formatUsdCompact(double v, {bool showSign = false}) {
  final sign = showSign ? (v >= 0 ? '+' : '-') : (v < 0 ? '-' : '');
  final av = v.abs();
  if (av >= 1e9) return '$sign\$${(av / 1e9).toStringAsFixed(2)}B';
  if (av >= 1e6) return '$sign\$${(av / 1e6).toStringAsFixed(0)}M';
  if (av >= 1e3) return '$sign\$${(av / 1e3).toStringAsFixed(0)}K';
  return '$sign\$${av.toStringAsFixed(0)}';
}
