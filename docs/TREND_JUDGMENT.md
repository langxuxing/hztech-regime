# 趋势判断规范

本文档定义系统对外**趋势判断（Trend Judgment）**的业务契约，是 Dashboard 与 API 的主信号。

## 核心定义

| 概念 | 字段 | 说明 |
|------|------|------|
| **业务趋势** | `trend` | 衍生品融合后的 `raw_trend`（非单独 `tech_trend`） |
| **技术趋势** | `tech_trend` | Donchian 14D + KAMA 轨道判定 |
| **Regime** | `regime_id` | 趋势 + 波动桶 + CVD 语义的 11 类状态 |
| **稳定性** | `stability` | `confirmed` / `provisional` / `transition` |
| **置信度** | `confidence` | 0–1；共识分歧或 HMM 分歧时会被上限裁剪 |

## 计算路径

```
BTC 30m OHLCV
  → tech_trend（Donchian + KAMA）
  → Funding + OI + CVD 投票
  → resolve_trend_with_derivatives → trend（主信号）
  → _compose_regime → regime_id
  → L3 驻留确认 → stability
  → HMM 第二意见 → 置信度修正（不覆盖 trend）
  → 外部共识交叉验证 → 置信度上限 0.55
```

## API 契约

`GET /api/radar` 顶层字段：

```json
{
  "trend_judgment": {
    "trend": "uptrend",
    "trend_label": "上涨",
    "tech_trend": "uptrend",
    "confidence": 0.72,
    "regime_id": "mid_vol_uptrend",
    "regime_label": "中波上行 · 趋势延续",
    "stability": "confirmed",
    "business_stance": "顺势做多 · 中波趋势延续",
    "drivers": ["..."],
    "data_tier": "demo",
    "needs_human_judgment": false
  },
  "readiness_tier": "degraded"
}
```

## 稳定性规则

| 条件 | stability |
|------|-----------|
| `in_regime_transition` 或 BOCPD 变点期 | `transition` |
| live_regime ≠ confirmed_regime | `provisional` |
| dwell_bars ≥ min_dwell_bars | `confirmed` |
| 其他 | `provisional` |

## 业务决策矩阵

| 趋势 | Regime | 建议姿态 |
|------|--------|----------|
| uptrend | low/mid_vol_uptrend | 顺势做多 |
| uptrend | high_vol_uptrend | 顺势做多（CVD 确认） |
| uptrend | fake_breakout_wash | 减仓观望 |
| downtrend | high/low_vol_downtrend | 顺势做空或空仓 |
| downtrend | high_vol_self_heal_range | 谨慎抄底 |
| range | mid/low_vol_range | 震荡策略 |
| range | high_vol_range | 事件驱动 |
| 任意 | macro_frozen_range | 强制观望 |

## HMM 第二意见

- HMM `raw_trend` 与规则 `raw_trend` 不一致 → `confidence ≤ 0.55`，`hmm_disagrees = true`
- HMM 置信度 < 50% → `confidence ≤ 0.60`
- **不修改** `trend`、`regime_id` 或 `in_regime_transition`（BOCPD/triad 专用）

## 外部共识

- `direction=up/down` 与内部趋势明确相反 → 可能裁剪置信度至 0.55（`consensus_capped=true`）
- `direction=neutral` 不触发压制（`consensus_misaligned=false`）
- `consensus_misaligned` 表示存在方向性分歧；`consensus_capped` 仅在实际降低了置信度时为 true

## 运维脚本

```bash
python scripts/trend_health_check.py      # 快照与趋势健康
python scripts/run_trend_backtest.py      # 历史 walk-forward
python scripts/run_calibrator_baseline.py # 校准器基线
```
