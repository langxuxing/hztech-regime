"""向后兼容：re-export algorithm.common.features。"""

from algorithm.common.features import (
    build_cluster_features,
    normalize_features,
    recent_return_window,
)

__all__ = ["build_cluster_features", "normalize_features", "recent_return_window"]
