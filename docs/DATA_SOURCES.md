# 数据源能力矩阵

按部署配置，系统分为三档：**free** / **coinglass** / **full**。

查询运行时状态：`GET /api/scheduler/status` 或 `./scripts/status.sh`。

## 部署层级

| 层级 | 条件 | 可用能力 |
|------|------|----------|
| **free** | 无 `COINGLASS_API_KEY` | OKX 本地 K 线、Ticker、Binance 公开 forecast、FRED 宏观、交易所公告、Blockchair 链上活跃度 |
| **coinglass** | 有 `COINGLASS_API_KEY` | + ETF ETH、资金流 netflow、交易所钱包、强平全量、经济日历 API |
| **full** | + `X_BEARER_TOKEN` | + X 实时突发监控 |

## 模块说明

| 模块 | 主数据源 | 刷新建议 | 无 Key 行为 |
|------|----------|----------|-------------|
| OHLCV | OKX 1m 本地 resample | 300s | BTC 报错提示下载；非 BTC 可 ccxt fallback |
| Ticker / 订单簿 | Binance/ccxt | 15–30s | 正常 |
| Spot CVD | Binance taker klines | 180s | 返回 unavailable（不用 proxy） |
| Funding / OI | ccxt（**主 funding 源**） | 180s | 正常 |
| ETF BTC | 本地 CSV → Farside → CoinGlass | 日度 | Farside 爬虫 |
| ETF ETH | CoinGlass API | 日度 | 需 Key 或本地 CSV |
| 交易所钱包 | CoinGlass | 1h | 空 |
| 链上活跃度 | Blockchair | 日度 | **非**交易所净流入 |
| 事件日历 | CoinGlass API | 300s | 不启用 HTML scrape |
| X 突发 | X API v2 | 300s | demo 或跳过 |
| 宏观 FRED | fred.stlouisfed.org | 日度 | 正常 |
| 制造业活动 (ism/) | FRED `IPMAN` | 日度 | 替代 ISM PMI |

## 统一调度器

```bash
./scripts/start-data-scheduler.sh   # BTC 1m + 事件 + 日同步 + 反馈
./scripts/stop-data-scheduler.sh
```

环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `SCHED_BTC_1M_SEC` | 300 | BTC 1m 增量间隔 |
| `SCHED_EVENTS_SEC` | 300 | 事件扫描间隔 |
| `SCHED_SYNC_HOUR` | 8 | 日同步时刻（时） |
| `SCHED_SYNC_MINUTE` | 0 | 日同步时刻（分） |
| `SCHED_SYNC_TIMEZONE` | Asia/Shanghai | 时区 |
| `SCHED_ON_START` | 1 | 启动时立即跑 btc_1m + events |
| `ALLOW_COINGLASS_SCRAPE_FALLBACK` | false | 禁止低质量日历 HTML 兜底 |

旧脚本 `start-sync-scheduler.sh` / `start-btc-1m-scheduler.sh` 仍可用，建议迁移到 `data-scheduler`。

## Funding 主源

衍生品与趋势共识共用 **`funding_snapshot`**（`ai_trade_advisor/datasource/funding_snapshot.py`）：

- 主源：Binance `fapi/v1/premiumIndex` + `fundingRate` 历史
- 补充：CoinGlass 跨所均值（有 `COINGLASS_API_KEY` 时写入 snapshot）
- 消费方：`derivatives_trend`、`forecast/ensemble`（单一 `funding_snapshot` 信号，不再重复拉取）
