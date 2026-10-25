# 硬止开/关反事实脚本 — 交付验收

## 交付物清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `scripts/trend_spike_hard_sl_cf.py` | 硬止 CF 一键入口（占位框架） | ✅ 完成 |
| `tests/test_hard_sl_cf.py` | 单元测试（7 个测试全通过） | ✅ 完成 |
| `docs/HARD_SL_CF_README.md` | 迁移指南与 Mac mini 烟测说明 | ✅ 完成 |
| PR #1 | GitHub Pull Request | ✅ 已创建 |

---

## 验收要点

### ✅ 1. 脚本可运行（占位版）

```bash
cd /workspace
python3 scripts/trend_spike_hard_sl_cf.py --universe PEPE --window 1y
```

**输出**：
- ⚠️ 提示：未找到 `hybrid.regime2.trend_spike` 模块（预期，本仓库不包含）
- ✅ 使用 mock 数据继续执行
- ✅ 生成 `out/hard_sl_cf_<date>/summary.json` 与 `summary.xlsx`
- ✅ 报告头包含：引擎 MD5、窗口标签、配置声明

### ✅ 2. 两臂逻辑正确

**臂 A（现网硬止）**：
- M30 类品种 → `hard_sl="M30"`
- M50 类品种 → `hard_sl="M50"`
- 硬止出场占比 > 0%

**臂 B（全关）**：
- 所有品种 → `hard_sl="none"`
- 硬止出场占比 = 0%

**验证**：运行单元测试

```bash
python3 -m pytest tests/test_hard_sl_cf.py -v
```

结果：`7 passed`

### ✅ 3. 输出格式符合要求

**summary.json 结构**：

```json
{
  "meta": {
    "engine_md5": "e90615f1",
    "window_label": "1y (2024-01-01 ~ 2024-12-31)",
    "timestamp": "2026-10-25T10:59:10.975693",
    "config_notice": "现网硬止仍在、未改 Config、未 --apply；仅研究脚本回放"
  },
  "results": [
    {
      "arm": "A-现网硬止",
      "symbol": "PEPEUSDT",
      "symbol_class": "M30",
      "n_trades": 189,
      "net_pnl": 131.07,
      "exploded_pct": 11.45,
      "win_rate": 57.61,
      "profit_factor": 1.3,
      "max_drawdown": -1653.26,
      "hard_sl_exit_pct": 21.62
    },
    {
      "arm": "B-全关",
      "symbol": "PEPEUSDT",
      "symbol_class": "M30",
      "n_trades": 190,
      "net_pnl": 649.51,
      "exploded_pct": 0.35,
      "win_rate": 48.07,
      "profit_factor": 1.67,
      "max_drawdown": -1320.65,
      "hard_sl_exit_pct": 0.0
    }
  ]
}
```

**summary.xlsx 列**：臂｜品种｜类别｜笔数｜净利｜爆仓%｜胜率｜PF｜最大回撤｜硬止出场%

### ✅ 4. 约束遵守

- ✅ 仅研究脚本，未修改实盘 `config/` 或 `scripts/` 进程
- ✅ 未改上线 Config
- ✅ 未交审
- ✅ 未添加 `--apply` 标志
- ✅ 报告头声明「现网硬止仍在、未改 Config、未 --apply」
- ✅ 未降低 z/v 检查标准

### ✅ 5. 迁移指南完整

`docs/HARD_SL_CF_README.md` 包含：
- ⚠️ 重要声明：本仓不含 `hybrid.regime2.trend_spike`
- 建议目标仓库（MF / hybrid-backtest 等）
- 迁移步骤（替换占位函数、配置参数包、验收标准）
- Mac mini 烟测流程（在正确仓库）
- FAQ

---

## 核心结论

**本仓库（`hztech-regime`）不是目标仓库**

经核查：
- 本仓是 **BTC Regime 判定 + 风险看板** 项目
- 缺少 `hybrid.regime2.trend_spike.simulate_trade()` 接口
- 缺少 `practical_candidate_v2_live` 参数包
- 缺少 `Desktop/t102*/t105*` 桌面脚本目录

**应放置的仓库**：
根据附件 `SCRIPT_LIST_PENDING.md` 线索（Desktop 脚本、硬止 M30/M50 类参、PEPE 单品宇宙），脚本应放在包含以下模块的仓库：
1. `hybrid.regime2.trend_spike` 交易引擎（或等价路径）
2. 多资产回测框架与 MarketData 管理
3. 参数包配置系统（`practical_candidate_v2_live` 等）

**当前交付**：
- ✅ 完整脚本框架（展示两臂逻辑、输出格式、报告头）
- ✅ 单元测试（验证关键逻辑正确）
- ✅ 迁移指南（3 步接入真实引擎）
- ✅ Mac mini 烟测说明（在正确仓库执行）

---

## PR 信息

- **URL**: https://github.com/langxuxing/hztech-regime/pull/1
- **Branch**: `cursor/hard-sl-cf-placeholder-35d9`
- **Status**: 待审核

---

## 下一步行动

1. **确认目标仓库**：询问阿郎 `hybrid.regime2.trend_spike` 所在仓库名
2. **迁移脚本**：
   ```bash
   # 假设目标仓库为 hybrid-backtest
   cp scripts/trend_spike_hard_sl_cf.py ../hybrid-backtest/scripts/
   cp tests/test_hard_sl_cf.py ../hybrid-backtest/tests/
   cp docs/HARD_SL_CF_README.md ../hybrid-backtest/docs/
   ```
3. **接入真实引擎**：按 `docs/HARD_SL_CF_README.md` 第二节替换占位函数
4. **Mac mini 烟测**：
   ```bash
   cd ../hybrid-backtest
   python scripts/trend_spike_hard_sl_cf.py --universe PEPE --window 1y
   ```
5. **吃满宇宙**：烟测通过后运行完整回测

---

**验收人**：阿郎  
**交付日期**：2026-10-25  
**CloudAgent 任务状态**：✅ 框架完成，待迁移至正确仓库
