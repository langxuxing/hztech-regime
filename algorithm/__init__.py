"""BTC Regime 核心算法库 — 按方法分目录组织。

子包:
  hmm         — hmmlearn GaussianHMM
  clustering  — scikit-learn K-Means / GMM + DTW
  msar        — 马尔可夫转换自回归 (statsmodels / 内置 EM)
  hybrid      — HMM 标注 + 序列预测融合
  heuristic   — 布林带挤压 / ADX / 均线 (pandas-ta)
  common      — 共享特征工程
"""

from algorithm.clustering import ClusteringRegimeResult, fit_clustering_regime
from algorithm.heuristic import HeuristicRegimeResult, fit_heuristic_regime
from algorithm.hmm import HmmRegimeResult, TransitionForecast, fit_hmm_regime, forecast_transition
from algorithm.hybrid import HybridRegimeResult, fit_hybrid_regime
from algorithm.msar import MsarRegimeResult, fit_msar_regime

__all__ = [
    "ClusteringRegimeResult",
    "fit_clustering_regime",
    "HeuristicRegimeResult",
    "fit_heuristic_regime",
    "HmmRegimeResult",
    "TransitionForecast",
    "fit_hmm_regime",
    "forecast_transition",
    "HybridRegimeResult",
    "fit_hybrid_regime",
    "MsarRegimeResult",
    "fit_msar_regime",
]
