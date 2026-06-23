# algorithm — BTC Regime 纯算法库

与 `ai_trade_advisor` 解耦，仅含特征工程与模型拟合，无 I/O 依赖。

## 子包

| 目录 | 方法 |
|------|------|
| `hmm/` | Gaussian HMM (hmmlearn) |
| `clustering/` | K-Means / GMM + DTW |
| `msar/` | 马尔可夫转换自回归 |
| `hybrid/` | HMM 标注 + 序列预测 |
| `heuristic/` | 布林带挤压 / ADX / 均线 |
| `common/` | 共享特征工程 |

## 安装

```bash
pip install -e .   # 从仓库根目录安装 regime-trend（含 algorithm）
```

业务适配层见 `ai_trade_advisor/regime/models/`。
