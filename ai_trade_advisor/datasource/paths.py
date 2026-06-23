from __future__ import annotations

import os
from pathlib import Path

# 仓库根目录：与 algorithm/、data/ 同级
#   Regime&Trend/
#   ├── algorithm/
#   ├── data/              ← 下载与本地持久化（本模块管理）
#   ├── ai_trade_advisor/
#   └── scripts/
REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT  # 兼容旧名

SUBDIRS = ("db", "cache", "exports", "logs")
MACRO_SUBDIRS = ("m2", "ism", "ppi", "fed_rate", "cpi", "nfp")
OHLCV_ASSET_DIRS = {"BTC": "Btc", "ETH": "Eth"}


def get_data_root() -> Path:
    """本地数据根目录，默认 <仓库根>/data（与 algorithm/ 同级）。"""
    env = os.getenv("DATA_DIR", "").strip()
    return Path(env) if env else REPO_ROOT / "data"


def get_etf_root() -> Path:
    return get_data_root() / "ETF"


def get_ohlcv_root() -> Path:
    return get_data_root() / "OHLCV"


def get_ohlcv_dir(asset: str = "Btc") -> Path:
    """OHLCV 子目录，如 data/OHLCV/Btc。"""
    key = asset.upper()
    sub = OHLCV_ASSET_DIRS.get(key, asset)
    return get_ohlcv_root() / sub


def ensure_data_layout(root: Path | None = None) -> dict[str, Path]:
    """创建 data/ 及 db、cache、exports、logs 子目录。"""
    data_root = root or get_data_root()
    layout: dict[str, Path] = {"root": data_root}
    for name in SUBDIRS:
        path = data_root / name
        path.mkdir(parents=True, exist_ok=True)
        layout[name] = path
    return layout


def default_events_db() -> Path:
    return ensure_data_layout()["db"] / "events.db"


def default_regime_db() -> Path:
    return ensure_data_layout()["db"] / "regime_history.db"


def get_macro_root() -> Path:
    return get_data_root() / "macro"


def ensure_macro_layout(root: Path | None = None) -> dict[str, Path]:
    """创建 data/macro/ 及各指标子目录。"""
    data_root = root or get_data_root()
    macro_root = data_root / "macro"
    layout: dict[str, Path] = {"root": macro_root}
    for name in MACRO_SUBDIRS:
        path = macro_root / name
        path.mkdir(parents=True, exist_ok=True)
        layout[name] = path
    return layout
