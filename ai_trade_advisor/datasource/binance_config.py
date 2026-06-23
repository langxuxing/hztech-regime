from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIVE_FAPI_BASE_URL = "https://fapi.binance.com"
DEMO_FAPI_BASE_URL = "https://demo-fapi.binance.com"


@dataclass(frozen=True)
class BinanceFuturesConfig:
    name: str
    api_key: str
    api_secret: str
    base_url: str
    sandbox: bool

    @property
    def ticker_source(self) -> str:
        if self.sandbox:
            return "binance:demo-fapi"
        return "binance:fapi"


def normalize_fapi_base_url(base_url: str, sandbox: bool) -> str:
    clean = (base_url or "").strip().rstrip("/")
    if sandbox:
        if not clean or clean in {"https://www.binance.com", "https://binance.com"}:
            return DEMO_FAPI_BASE_URL
        if "demo-fapi" in clean or "testnet" in clean:
            return clean if clean.startswith("http") else DEMO_FAPI_BASE_URL
        return DEMO_FAPI_BASE_URL
    if not clean or clean in {"https://www.binance.com", "https://binance.com"}:
        return LIVE_FAPI_BASE_URL
    return clean


def load_binance_config(path: Path | str | None = None) -> BinanceFuturesConfig | None:
    """读取 Binance JSON 配置（如 biance-ws/alang_demo.json）。"""
    env_key = os.getenv("BINANCE_API_KEY", "").strip()
    env_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    env_base = os.getenv("BINANCE_FAPI_BASE_URL", "").strip()
    env_sandbox = os.getenv("BINANCE_SANDBOX", "").lower() in ("1", "true", "yes")

    if env_key and env_secret:
        return BinanceFuturesConfig(
            name="env",
            api_key=env_key,
            api_secret=env_secret,
            base_url=normalize_fapi_base_url(env_base, env_sandbox),
            sandbox=env_sandbox or "demo-fapi" in env_base,
        )

    config_path = path or os.getenv("BINANCE_CONFIG_PATH", "").strip()
    if not config_path:
        default = Path("/Volumes/HZTech/CreativeIdeaLab/biance-ws/alang_demo.json")
        if default.exists():
            config_path = str(default)
        else:
            return None

    p = Path(config_path).expanduser()
    if not p.exists():
        return None

    try:
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw, dict):
        return None

    data: dict[str, Any] = raw.get("api") if isinstance(raw.get("api"), dict) else raw
    sandbox = bool(data.get("sandbox"))
    key = str(data.get("key") or "").strip()
    secret = str(data.get("secret") or "").strip()
    if not key or not secret:
        return None

    return BinanceFuturesConfig(
        name=str(data.get("name") or p.stem),
        api_key=key,
        api_secret=secret,
        base_url=normalize_fapi_base_url(str(data.get("base_url") or ""), sandbox),
        sandbox=sandbox,
    )
