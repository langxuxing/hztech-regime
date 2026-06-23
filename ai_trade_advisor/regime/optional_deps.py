"""可选依赖探测（LSTM 等）。"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def tensorflow_available() -> bool:
    try:
        import tensorflow  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def pandas_ta_available() -> bool:
    try:
        import pandas_ta  # noqa: F401

        return True
    except ImportError:
        return False


def optional_dependency_status() -> dict[str, dict[str, str]]:
    """返回可选依赖安装状态与安装提示。"""
    return {
        "tensorflow": {
            "available": tensorflow_available(),
            "install": 'pip install -e ".[lstm]"',
            "used_by": "crypto_lstm (akash LSTM)",
        },
        "pandas_ta": {
            "available": pandas_ta_available(),
            "install": 'pip install -e ".[ta]"',
            "used_by": "heuristic_advanced (ADX/BB/KC)",
        },
    }
