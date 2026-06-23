import 'package:flutter/material.dart';

import '../models/capital_flows.dart';
import '../theme/app_theme.dart';
import 'common.dart';

class OnChainPanel extends StatelessWidget {
  const OnChainPanel({super.key, this.flows});

  final CapitalFlowsSnapshot? flows;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '链上资产 & 资金流',
      icon: Icons.hub_outlined,
      trailing: flows != null
          ? StatusBadge(
              label: flows!.dataQuality,
              color: flows!.hasOnchainData ? AppTheme.accent : AppTheme.neutral,
            )
          : null,
      child: flows == null
          ? const Text(
              '资金流数据未加载。请确认 API 未使用 --skip-capital-flows。',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (flows!.btcOnchain != null) ...[
                  _OnChainBlock(onchain: flows!.btcOnchain!),
                  const SizedBox(height: 12),
                ],
                if (flows!.ethOnchain != null) ...[
                  _OnChainBlock(onchain: flows!.ethOnchain!),
                  const SizedBox(height: 12),
                ],
                if (flows!.btcExchangeWallet != null) ...[
                  _WalletBlock(wallet: flows!.btcExchangeWallet!),
                  const SizedBox(height: 12),
                ],
                if (flows!.ethExchangeWallet != null) ...[
                  _WalletBlock(wallet: flows!.ethExchangeWallet!),
                  const SizedBox(height: 12),
                ],
                if (flows!.btcMarketFlows.isNotEmpty) ...[
                  _MarketFlowBlock(flows: flows!.btcMarketFlows, title: 'BTC 市场 Netflow'),
                  const SizedBox(height: 12),
                ],
                if (flows!.ethMarketFlows.isNotEmpty)
                  _MarketFlowBlock(flows: flows!.ethMarketFlows, title: 'ETH 市场 Netflow'),
                if (!flows!.hasOnchainData &&
                    flows!.btcExchangeWallet == null &&
                    flows!.btcMarketFlows.isEmpty)
                  const Text(
                    '链上统计可用；交易所/市场 netflow 需 COINGLASS_API_KEY。',
                    style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                  ),
              ],
            ),
    );
  }
}

class _OnChainBlock extends StatelessWidget {
  const _OnChainBlock({required this.onchain});

  final OnChainTransferFlow onchain;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${onchain.asset} 链上活跃度',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (onchain.chainVolume24hUsd != null)
              MetricChip(
                label: '24h 成交额',
                value: formatUsdCompact(onchain.chainVolume24hUsd!),
              ),
            if (onchain.transactions24h != null)
              MetricChip(
                label: '24h 交易笔数',
                value: _fmtInt(onchain.transactions24h!),
              ),
            if (onchain.volumeChange7dPct != null)
              MetricChip(
                label: '成交额 7d',
                value: '${onchain.volumeChange7dPct! >= 0 ? '+' : ''}${onchain.volumeChange7dPct!.toStringAsFixed(1)}%',
                color: (onchain.volumeChange7dPct ?? 0) >= 0 ? AppTheme.long : AppTheme.short,
              ),
            if (onchain.largestTx24hUsd != null)
              MetricChip(
                label: '最大单笔',
                value: formatUsdCompact(onchain.largestTx24hUsd!),
                color: AppTheme.magnet,
              ),
          ],
        ),
        if (onchain.interpretation.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            onchain.interpretation,
            style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
        ],
      ],
    );
  }

  String _fmtInt(int v) {
    if (v >= 1000000) return '${(v / 1000000).toStringAsFixed(1)}M';
    if (v >= 1000) return '${(v / 1000).toStringAsFixed(1)}K';
    return v.toString();
  }
}

class _WalletBlock extends StatelessWidget {
  const _WalletBlock({required this.wallet});

  final ExchangeWalletFlow wallet;

  @override
  Widget build(BuildContext context) {
    final net1d = wallet.netToExchange1d;
    final color = (net1d ?? 0) >= 0 ? AppTheme.short : AppTheme.long;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${wallet.asset} 交易所钱包',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            MetricChip(
              label: '1d 净流',
              value: net1d != null
                  ? '${net1d >= 0 ? '+' : ''}${net1d.toStringAsFixed(0)} ${wallet.asset}'
                  : '—',
              color: color,
            ),
            if (wallet.netToExchange7d != null)
              MetricChip(
                label: '7d 净流',
                value: '${wallet.netToExchange7d! >= 0 ? '+' : ''}${wallet.netToExchange7d!.toStringAsFixed(0)}',
              ),
          ],
        ),
        if (wallet.topExchanges.isNotEmpty) ...[
          const SizedBox(height: 8),
          ...wallet.topExchanges.take(3).map((ex) {
            final name = ex['exchange']?.toString() ?? '—';
            final chg = (ex['change_1d'] as num?)?.toDouble();
            return Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                '$name 1d ${chg != null ? '${chg >= 0 ? '+' : ''}${chg.toStringAsFixed(0)}' : '—'}',
                style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
              ),
            );
          }),
        ],
      ],
    );
  }
}

class _MarketFlowBlock extends StatelessWidget {
  const _MarketFlowBlock({required this.flows, required this.title});

  final List<MarketFundFlow> flows;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...flows.map((mf) {
          final p24 = mf.periods.where((p) => p.period == '24h').firstOrNull;
          final net = p24?.netflowUsd;
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                Text(
                  mf.market.toUpperCase(),
                  style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                ),
                const Spacer(),
                Text(
                  net != null ? formatUsdCompact(net, showSign: true) : '—',
                  style: TextStyle(
                    fontSize: 11,
                    color: (net ?? 0) >= 0 ? AppTheme.long : AppTheme.short,
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
}

extension _FirstOrNull<E> on Iterable<E> {
  E? get firstOrNull {
    final it = iterator;
    if (it.moveNext()) return it.current;
    return null;
  }
}
