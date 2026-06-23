# AI 交易建议系统

基于 Gemini 构想文档落地的加密货币日内交易建议管道：**30m 结构化 K 线特征 + SMC/ICT + 流动性清洗地图 + GEX 代理 + 订单簿 → AI 概率输出**。

## 架构

```
交易所 API (OKX/Binance)
    ├── 30m OHLCV ──► SMC (BOS/CHoCH/FVG/OB)
    ├── 订单簿 ──────► 深度/失衡/大单墙
    └── OI/Funding ──► GEX 代理层
              │
              ▼
     结构化文本 Context
              │
              ▼
   LLM (OpenAI 兼容) / 规则引擎 fallback
              │
              ▼
   JSON 交易建议 (bias, confidence, entry, SL, TP)
```

### 四层 Regime 流水线

```
L1 datasource/     多源数据输入 + df_live / df_confirmed
L2 regime/         规则 + 8 模型 ensemble + 硬规则修正
L3 layers/l3/      Regime 驻留防抖 + Advice 冷却（统一入口 run_l3_pipeline）
L4 state_machine/  量化状态机路由 + 黑天鹅熔断
```

### 计算 / API 分离

```
snapshot-worker ──► 定时计算 ──► data/cache/snapshots/*.json
                                      │
Flask API (只读) ◄────────────────────┘
    GET /api/radar          聚合快照（version + snapshot_id）
    GET /api/dashboard      看板（默认读缓存，?live=true 强制重算）
```

## 快速开始

```bash
cd "/Volumes/HZTech/Regime&Trend"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env 填入 AI_API_KEY（可选）

# 规则引擎模式（无需 API Key）
python -m ai_trade_advisor --exchange okx --symbol BTC/USDT:USDT

# 仅查看结构化特征（给 LLM 的输入）
python -m ai_trade_advisor --context-only

# 启用 LLM（配置 .env 中 AI_API_KEY）
python -m ai_trade_advisor -o advice.json
```

## Docker

```bash
cp .env.example .env
docker compose up --build
# API: http://localhost:8765/api/radar
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `AI_API_KEY` | OpenAI 或 Gemini OpenAI 兼容端点 Key |
| `AI_API_BASE` | 默认 `https://api.openai.com/v1` |
| `AI_MODEL` | 如 `gpt-4o-mini` |
| `EXCHANGE` | `okx` / `binance` |
| `SYMBOL` | ccxt 永续符号，如 `BTC/USDT:USDT` |
| `DATA_DIR` | 本地数据根目录（默认 `./data`） |
| `SNAPSHOT_POLL_INTERVAL_SEC` | 快照 worker 轮询间隔（默认 120s） |
| `SNAPSHOT_STALE_SEC` | API 缓存过期阈值（默认 300s） |
| `SCHED_BTC_1M_SEC` | 统一调度器 BTC 1m 间隔（默认 300s） |
| `PEPEDATA_DIR` | 本地 PEPE 1m 数据 |

数据源能力与调度说明见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

```bash
./scripts/start-data-scheduler.sh   # BTC 1m + 事件 + 日同步
./scripts/status.sh                 # 服务与数据层级状态
```

## 模块说明

| 模块 | 职责 |
|------|------|
| `ai_trade_advisor/datasource/` | 拉取 OHLCV、订单簿、资金流、链上、宏观 |
| `ai_trade_advisor/features/` | SMC、流动性地图、GEX、trading_brief |
| `ai_trade_advisor/context/` | 生成 LLM 结构化文本 |
| `ai_trade_advisor/ai/` | LLM 或规则引擎输出建议 |
| `ai_trade_advisor/regime/` | BTC Regime 判定 + 多模型 + 人工反馈闭环 |
| `ai_trade_advisor/bigevent/` | 事件分析引擎（日历/公告/X） |
| `ai_trade_advisor/snapshot/` | 看板快照缓存与 worker |
| `algorithm/` | 纯 Regime 算法库（HMM/聚类/MSAR 等，可独立 pip 安装） |
| `dashboard/` | Flutter 金融雷达看板 |

## BTC/ETH 资金流入流出 & 链上数据

| 数据 | 来源 | 是否需要 Key |
|------|------|-------------|
| 市场 taker 买/卖 netflow（24h/7d/30d） | CoinGlass futures/spot netflow | `COINGLASS_API_KEY`（Startup+） |
| 链上→交易所钱包净流入 | CoinGlass exchange balance | `COINGLASS_API_KEY`（Hobbyist+） |
| BTC 链上成交额/笔数/7d·30d 趋势 | Blockchair + Blockchain.com | 免费 |
| ETH L1/ERC20 链上活跃度 | Blockchair | 免费 |

## BTC Regime 多维度判定

以 **BTC** 为主链，11 类 regime（`macro_frozen_range`、`fake_breakout_wash` 等），详见 `ai_trade_advisor/regime/engine.py`。

**趋势判断业务契约**见 [docs/TREND_JUDGMENT.md](docs/TREND_JUDGMENT.md)。`GET /api/radar` 顶层 `trend_judgment` 为 Dashboard 主信号。

人工标注时，**LLM/规则交易建议**（`trade_advice`）纳入 feedback 打分闭环，与 HMM 等模型一同进入 Leaderboard。

## 量化状态机（The Quant State Machine）

`ai_trade_advisor/state_machine/`：Macro / Flow / Gex 三因子 → 诊断与系统指令。

```bash
curl http://127.0.0.1:8765/api/state-machine
curl http://127.0.0.1:8765/api/radar
```

## 事件分析引擎

`ai_trade_advisor/bigevent/`：CoinGlass 宏观日历 + 交易所公告 + X 突发监控。

```bash
python -m ai_trade_advisor.bigevent.cli
python -m ai_trade_advisor.api_server --poll-events
```

| 端点 | 说明 |
|------|------|
| `GET /api/events` | 返回缓存的事件分析结果 |
| `GET /api/events/scan` | 强制重新扫描 |
| `GET /api/radar` | 聚合快照（dashboard + events + consensus + history） |

## Flutter 金融雷达看板

```bash
# 启动后端 API（默认开启快照轮询）
python -m ai_trade_advisor.api_server

# 独立快照 worker（Docker 或本地）
python -m ai_trade_advisor.snapshot.worker

# Flutter
cd dashboard && flutter pub get && flutter run -d macos
```

看板优先调用 `/api/radar` 单次拉取；失败时回退并行多接口。

### 运维与部署要点

| 场景 | 推荐配置 |
|------|----------|
| 本地一键启动 | `./scripts/start-all.sh`（worker + API 预热 + 看板） |
| 仅 API | `POLL_SNAPSHOTS=0` + 独立 `start-snapshot-worker.sh` |
| 冷启动 | `SNAPSHOT_WARMUP_ON_START=true`（默认）或 `--warmup-snapshot` |
| 生产鉴权 | `.env` 设置 `API_KEY`；Flutter `--dart-define=API_KEY=...` |
| LSTM 模型 | `pip install -e ".[lstm]"`；状态见 `/api/scheduler/status` |
| Git 初始化 | `./scripts/init-repo.sh` |

```bash
# 可选依赖
pip install -e ".[lstm]"   # crypto_lstm
pip install -e ".[ta]"     # heuristic_advanced
```

## 目录结构

```
Regime&Trend/
├── algorithm/           # 纯算法包（pyproject 可编辑安装）
├── ai_trade_advisor/    # 主应用
├── dashboard/           # Flutter 看板
├── data/                # 运行时数据（git 忽略 OHLCV/cache/db）
├── scripts/             # 运维脚本
├── tests/               # pytest
├── vendor/              # 第三方 Regime 参考实现
├── pyproject.toml
└── docker-compose.yml
```

## 免责声明

本系统仅供研究与辅助决策，不构成投资建议。实盘前请充分回测并自行承担风险。
