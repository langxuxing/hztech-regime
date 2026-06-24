# 第 3–4 周生产验收指南

本文档汇总第 3 周（数据管道 + 趋势监控）与第 4 周（人工反馈闭环 + 上线门禁）的交付物与验收命令。

趋势判断契约见 [TREND_JUDGMENT.md](TREND_JUDGMENT.md)，日常运维见 [PRODUCTION_OPS.md](PRODUCTION_OPS.md)。

## 第 3 周：数据管道与趋势监控

| 交付物 | 说明 |
|--------|------|
| 数据调度器 | `scripts/data_scheduler.py` — BTC 1m / 事件 / 日同步 / 反馈校准 |
| 快照 Worker | `ai_trade_advisor.snapshot.worker` — 定时刷新 `/api/radar` |
| 就绪度 | `check_readiness()` + `GET /api/scheduler/status` |
| 趋势健康 | `run_trend_health_check()` + `GET /api/trend-health` |
| 配置阈值 | `AdvisorConfig` 环境变量（HMM / 共识 / 健康翻转） |
| Readiness 缓存 | `get_cached_readiness_tier()` 60s TTL |

### 验收命令

```bash
./scripts/start-all.sh              # 或 docker compose up --build -d
./scripts/status.sh                 # 含趋势健康 + 反馈样本
python scripts/check_readiness.py
python scripts/trend_health_check.py
curl http://127.0.0.1:8765/api/trend-health
```

### 通过标准

- `readiness_tier` 为 `production` 或 `degraded`（非纯 demo）
- 本地 BTC 1m ≥ 500 bars
- `/api/trend-health` 非 `critical`
- `trend_judgment` 契约字段完整

---

## 第 4 周：人工反馈闭环与上线门禁

| 交付物 | 说明 |
|--------|------|
| 人工判断 API | `POST/GET /api/regime/human-judgment` |
| 反馈统计 | `GET /api/regime/feedback-stats` |
| Dashboard 复核 | `HumanJudgmentQuickPanel`（大屏 / Regime / 模型页） |
| 标注历史 | `JudgmentHistoryPanel` + 样本进度条 |
| 推荐门控 | `should_apply_recommendation_fusion()` — 样本 ≥30 才融合 |
| 生产门禁 | `scripts/check_trend_production.py` |
| 48h soak | `scripts/run_trend_soak_test.py` |
| CI | `.github/workflows/ci.yml` |

### 验收命令

```bash
# 录入人工判断
curl -X POST 'http://127.0.0.1:8765/api/regime/human-judgment?symbol=BTC/USDT:USDT' \
  -H 'Content-Type: application/json' \
  -d '{"human_regime":"trend_up","human_trend":"uptrend"}'

# 反馈 worker（API 默认 --poll-feedback；或手动）
python scripts/regime_feedback_worker.py --once
python scripts/run_calibrator_baseline.py

# 样本 ≥30 后开启推荐融合
# REGIME_USE_RECOMMENDATION=true

python scripts/check_trend_production.py
python scripts/run_trend_soak_test.py --samples 12 --interval-sec 60
```

### 通过标准

- 至少 1 条人工判断记录
- `REGIME_USE_RECOMMENDATION=true` 时 `recommendation_ready=true`
- 生产门禁无 `blockers`
- soak 测试无 `critical` 采样

---

## 一键验收

```bash
python scripts/run_week34_checklist.py
# 仅第 3 周: --week 3
# 仅第 4 周: --week 4
# exit 0 = 该周全部检查通过
```

报告默认写入 `data/exports/reviews/week34_checklist_latest.json`。
