# 生产运维指南（第 3–4 周）

本文档描述从 Demo 升级到可运营生产的步骤。趋势判断契约见 [TREND_JUDGMENT.md](TREND_JUDGMENT.md)。

## 1. 就绪度层级

```bash
python scripts/check_readiness.py
curl http://127.0.0.1:8765/api/scheduler/status
```

| 层级 | 条件 |
|------|------|
| `production` | CoinGlass + 本地 BTC 1m + 资金流完整 |
| `degraded` | 缺 CoinGlass 或资金流 partial |
| `demo` | 无本地数据 / EVENT_DEMO_MODE / 无 X+CoinGlass |

## 2. 数据管道（第 3 周）

```bash
./scripts/download_btc.sh          # 首次
./scripts/start-data-scheduler.sh
./scripts/start-snapshot-worker.sh
./scripts/start-api.sh
./scripts/status.sh
```

推荐 `docker compose up --build -d` 一键启动 API + snapshot-worker。

## 3. 趋势判断监控

### CLI

```bash
python scripts/trend_health_check.py
# exit 0=ok, 2=degraded, 1=critical
```

### API

```bash
curl http://127.0.0.1:8765/api/regime/feedback-stats
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/trend-health
curl http://127.0.0.1:8765/api/radar | jq '.trend_judgment'
```

### 业务评审

```bash
python scripts/run_business_review.py
```

## 4. 人工反馈闭环（第 4 周）

1. Dashboard 或 API 录入人工判断：

```bash
curl -X POST 'http://127.0.0.1:8765/api/regime/human-judgment?symbol=BTC/USDT:USDT' \
  -H 'Content-Type: application/json' \
  -d '{"human_regime":"trend_up","human_trend":"uptrend","human_notes":"目视确认"}'
```

2. 启动反馈 worker（或在 API 加 `--poll-feedback`）

3. 样本 ≥ 30 后评估是否开启 `REGIME_USE_RECOMMENDATION=true`

4. 校准基线：

```bash
python scripts/run_calibrator_baseline.py
```

5. 生产门禁（就绪度 + 趋势健康 + 样本量）：

```bash
python scripts/check_trend_production.py
# exit 0=通过, 2=有警告, 1=阻断
```

## 5. 回测验证

```bash
python scripts/run_trend_backtest.py --bars 720 -o data/exports/reviews/trend_backtest.json
```

关注 `trend_metrics.fake_breakout_reversal_rate` 与 `avg_trend_duration_bars`。

## 6. 生产环境变量

```bash
API_KEY=...                      # 绑定 0.0.0.0 时必设
COINGLASS_API_KEY=...
SNAPSHOT_POLL_INTERVAL_SEC=120
SNAPSHOT_STALE_SEC=300
HMM_DISAGREE_CONFIDENCE_CAP=0.55
CONSENSUS_OPPOSING_CONFIDENCE_CAP=0.55
TREND_HEALTH_REGIME_FLIP_THRESHOLD=6
READINESS_CACHE_TTL_SEC=60
```

## 7. 告警建议

| 信号 | 阈值 | 动作 |
|------|------|------|
| `/api/trend-health` status | `critical` | 重启 snapshot-worker |
| `snapshot_age_sec` | > `SNAPSHOT_STALE_SEC` | 检查调度器 |
| `trend_judgment.stability` | `provisional` 持续 | 勿加仓 |
| `hmm_disagrees` | true | 降置信度参考 |
| `needs_human_judgment` | true | 人工复核 |
