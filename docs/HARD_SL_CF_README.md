# 硬止开/关反事实脚本 — 说明文档

## ⚠️ 重要声明

**本仓库（`Regime&Trend` / `ai_trade_advisor`）不包含 `hybrid.regime2.trend_spike` 交易引擎。**

经核查：
- 本仓是 **BTC Regime 判定 + 风险看板** 项目
- 缺少附件 `SCRIPT_LIST_PENDING.md` 中提到的：
  - `hybrid.regime2.trend_spike.simulate_trade()` 接口
  - `practical_candidate_v2_live` 参数包
  - `Desktop/t102*/t105*` 等桌面脚本目录
  - 多品种回测框架与 MarketData 管理

**应放置的仓库**：
根据附件线索（Desktop/t102、t105、verify_neighbor、硬止 M30/M50 类参），脚本应放在以下仓库之一：
1. **`MF`**（Market Fundament 量化框架）
2. **`hybrid-backtest`** 或 **`trend_spike`** 独立仓
3. 其他包含 `hybrid/regime2/trend_spike.py` 与多资产回测能力的仓库

---

## 本次交付内容

### 1. 脚本框架（占位版）

**文件**：`scripts/trend_spike_hard_sl_cf.py`

**功能**：
- ✅ 展示硬止开/关反事实对照逻辑（两臂设计）
- ✅ 参数包加载占位、宇宙枚举占位、MarketData 路径占位
- ✅ 输出 `out/hard_sl_cf_<date>/summary.json` + `summary.xlsx`
- ✅ 报告头包含：引擎 MD5、窗口标签、配置声明
- ⚠️ **当前使用 mock 数据**（无真实回测）

**用法**（在正确仓库中）：

```bash
# 1. PEPE 单品烟测（< 5min，推荐先跑）
python scripts/trend_spike_hard_sl_cf.py \
  --universe PEPE \
  --window 1y \
  --market-data /path/to/MarketData \
  --output-dir ./out

# 2. 吃满宇宙（所有品种）
python scripts/trend_spike_hard_sl_cf.py \
  --universe full \
  --window capital-tiers-1y \
  --market-data /path/to/MarketData
```

**两臂设计**：
- **臂 A**：现网硬止（按类 M30/M50，对齐 `v0.2.1-v2-sizing` / `practical_candidate_v2_live`）
- **臂 B**：全关（各类 `hard_sl=none`）
- 其余参数（出场/仓位/vz 门控/杠杆）完全相同
- 同窗同宇宙

**输出列**：
| 列 | 说明 |
|----|------|
| 臂 | A-现网硬止 / B-全关 |
| 品种 | PEPEUSDT 等 |
| 类别 | M30 / M50 等 |
| 笔数 | 交易笔数 |
| 净利 | 累计 PnL |
| 爆仓% | 爆仓占比 |
| 胜率 | 胜率 % |
| PF | Profit Factor |
| 最大回撤 | Max Drawdown |
| 硬止出场% | 硬止触发出场占比 |

---

### 2. 单元测试（Mock 验证）

**文件**：`tests/test_hard_sl_cf.py`

**验证**：
- ✅ 两臂 `hard_sl` 参数不同（A=M30/M50, B=none）
- ✅ 其他参数相同
- ✅ 输出文件结构正确
- ⚠️ 无真实引擎时使用 mock 数据

---

## 在正确仓库中的迁移步骤

### Step 1: 确认仓库包含以下模块

```python
# 必须能成功 import
from hybrid.regime2.trend_spike import simulate_trade

# 或等价路径（根据实际仓库调整）
from mf.engines.trend_spike import simulate_trade
```

### Step 2: 替换占位函数

编辑 `scripts/trend_spike_hard_sl_cf.py`，替换：

```python
def _mock_simulate_trade(...) -> SimulationResult:
    # 当前是 mock
    ...
```

改为：

```python
def _real_simulate_trade(
    symbol: str,
    symbol_class: str,
    params: dict[str, Any],
    hard_sl: str | None,
    market_data_path: Path,
    window_start: str,
    window_end: str,
) -> SimulationResult:
    """调用真实引擎"""
    from hybrid.regime2.trend_spike import simulate_trade  # 实际路径
    
    # 加载 MarketData
    df_ohlcv = pd.read_parquet(market_data_path / "ohlcv.parquet")
    # ... 其他辅助数据
    
    # 调用引擎
    trades = simulate_trade(
        df=df_ohlcv,
        params=params,
        hard_sl=hard_sl,  # 核心参数
        start_date=window_start,
        end_date=window_end,
    )
    
    # 统计指标
    n_trades = len(trades)
    net_pnl = sum(t.pnl for t in trades)
    exploded = sum(1 for t in trades if t.exit_reason == "liquidation")
    hard_sl_exits = sum(1 for t in trades if t.exit_reason == "hard_sl")
    # ... 计算胜率、PF、MDD
    
    arm_name = "A-现网硬止" if hard_sl and hard_sl != "none" else "B-全关"
    return SimulationResult(
        arm=arm_name,
        symbol=symbol,
        symbol_class=symbol_class,
        n_trades=n_trades,
        net_pnl=net_pnl,
        exploded_pct=exploded / n_trades * 100 if n_trades else 0,
        win_rate=...,  # 实际计算
        profit_factor=...,
        max_drawdown=...,
        hard_sl_exit_pct=hard_sl_exits / n_trades * 100 if n_trades else 0,
    )
```

### Step 3: 配置参数包与宇宙

编辑占位函数：

```python
def _load_param_pack(pack_name: str) -> dict[str, Any]:
    """从配置文件加载"""
    import yaml  # 或 json
    
    config_path = Path("config/params") / f"{pack_name}.yaml"
    return yaml.safe_load(config_path.read_text())


def _get_universe(universe_name: str) -> list[tuple[str, str]]:
    """从数据库/配置加载品种宇宙"""
    if universe_name == "PEPE":
        return [("PEPEUSDT", "M30")]
    elif universe_name == "full":
        # 读取完整宇宙配置
        universe_config = Path("config/universe_full.json")
        return json.loads(universe_config.read_text())["symbols"]
    ...
```

### Step 4: 验收标准

在 Mac mini 跑烟测前确认：

- [ ] `python scripts/trend_spike_hard_sl_cf.py --universe PEPE --window 1y` 成功执行
- [ ] 输出文件 `out/hard_sl_cf_<date>/summary.xlsx` 与 `summary.json` 存在
- [ ] 报告头包含：
  - 引擎 MD5（`hybrid/regime2/trend_spike.py` 的 MD5）
  - 窗口标签（`1y (2024-01-01 ~ 2024-12-31)` 等）
  - 配置声明：「现网硬止仍在、未改 Config、未 --apply」
- [ ] 两臂数据：
  - 臂 A 所有品种 `hard_sl` 为 M30/M50（按类）
  - 臂 B 所有品种 `hard_sl` 为 `none`
  - 其余参数完全相同
- [ ] 单元测试通过：`pytest tests/test_hard_sl_cf.py -v`

---

## Mac mini 烟测流程（在正确仓库）

### 环境准备

```bash
# 1. 克隆正确仓库（假设名为 hybrid-backtest）
git clone <repo-url> hybrid-backtest
cd hybrid-backtest

# 2. 安装依赖
pip install -e ".[backtest]"

# 3. 检查 MarketData 是否存在
ls -lh data/market/PEPEUSDT/ohlcv.parquet
```

### 运行烟测

```bash
# 单品 PEPE（< 5min）
python scripts/trend_spike_hard_sl_cf.py \
  --universe PEPE \
  --window 1y \
  --market-data ./data/market \
  --output-dir ./out

# 检查输出
cat out/hard_sl_cf_$(date +%Y%m%d)/summary.json | jq .
open out/hard_sl_cf_$(date +%Y%m%d)/summary.xlsx
```

### 预期输出示例

```
报告头信息:
  引擎 MD5: a3f2c8b1
  窗口: 1y (2024-01-01 ~ 2024-12-31)
  配置声明: 现网硬止仍在、未改 Config、未 --apply；仅研究脚本回放

样本结果:
         臂    品种  类别  笔数     净利  爆仓%  胜率    PF   最大回撤  硬止出场%
A-现网硬止  PEPEUSDT  M30  142   1856.23   3.5  52.1  1.85  -1234.56      28.2
  B-全关  PEPEUSDT  M30  142   2103.45   5.6  48.9  1.62  -1567.89       0.0
```

---

## 约束与禁止项（已遵守）

✅ 只加研究脚本，不碰实盘 `config/` 或进程  
✅ 不修改上线 Config  
✅ 不交审  
✅ 不加 `--apply` 标志  
✅ 报告头明确声明「现网硬止仍在、未改 Config」  
✅ 不降低 z/v 检查标准  

---

## FAQ

**Q: 为何本仓库只有占位版？**  
A: 本仓库是 Regime 判定项目，不含交易引擎。脚本框架展示完整逻辑，需迁移到包含 `hybrid.regime2.trend_spike` 的仓库后替换占位函数。

**Q: Mac mini 无 MarketData 怎么办？**  
A: 脚本会提示缺失并继续用 mock 数据演示流程。正式烟测需从数据源同步 PEPE 1y OHLCV。

**Q: 如何确认在正确仓库？**  
A: 运行 `python -c "from hybrid.regime2.trend_spike import simulate_trade; print('OK')"` 不报错即可。

**Q: 单元测试如何跑？**  
A: `pytest tests/test_hard_sl_cf.py -v`（当前仓库会提示 mock，正确仓库需替换真实引擎后验证）。

---

## 下一步

1. **确认目标仓库**：询问阿郎 `hybrid.regime2.trend_spike` 所在仓库名
2. **迁移脚本**：将 `scripts/trend_spike_hard_sl_cf.py` 与 `tests/test_hard_sl_cf.py` 复制过去
3. **替换占位函数**：按上述 Step 2-3 接入真实引擎与配置
4. **Mac mini 烟测**：跑 PEPE 单品验证逻辑
5. **吃满宇宙**：通过烟测后运行完整回测

---

**联系人**: CloudAgent  
**创建时间**: 2026-10-25  
**状态**: 占位框架完成，待迁移至正确仓库
