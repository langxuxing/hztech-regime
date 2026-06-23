from __future__ import annotations

import csv
import io
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import ensure_macro_layout, get_macro_root

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
INVESTING_ISM_CHART_URL = "https://sbcharts.investing.com/events_charts/us/173.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# FRED 序列：M2 / PPI / CPI / 基准利率 / 非农
FRED_SERIES: dict[str, dict[str, str]] = {
    "m2": {
        "series_id": "M2SL",
        "name": "US M2 Money Stock",
        "unit": "billions_usd",
        "filename": "m2sl.csv",
    },
    "ppi": {
        "series_id": "PPIFIS",
        "name": "PPI Final Demand",
        "unit": "index",
        "filename": "ppifis.csv",
    },
    "cpi": {
        "series_id": "CPIAUCSL",
        "name": "CPI All Urban Consumers",
        "unit": "index",
        "filename": "cpiaucsl.csv",
    },
    "fed_rate": {
        "series_id": "FEDFUNDS",
        "name": "Federal Funds Effective Rate",
        "unit": "percent",
        "filename": "fedfunds.csv",
    },
    "fed_target_upper": {
        "series_id": "DFEDTARU",
        "name": "Fed Funds Target Range Upper",
        "unit": "percent",
        "filename": "fed_target_upper.csv",
        "subdir": "fed_rate",
    },
    "fed_target_lower": {
        "series_id": "DFEDTARL",
        "name": "Fed Funds Target Range Lower",
        "unit": "percent",
        "filename": "fed_target_lower.csv",
        "subdir": "fed_rate",
    },
    "nfp": {
        "series_id": "PAYEMS",
        "name": "Total Nonfarm Payrolls",
        "unit": "thousands",
        "filename": "payems.csv",
    },
}


@dataclass
class MacroFetchResult:
    indicator: str
    path: Path
    rows: int
    latest_date: str
    latest_value: float | None
    source: str


def _macro_root(cfg: AdvisorConfig | None = None) -> Path:
    if cfg and cfg.data_dir is not None:
        return cfg.data_dir / "macro"
    return get_macro_root()


def _download_text(url: str, *, timeout: float = 30.0) -> str:
    """优先 curl 下载（网络环境下比 Python HTTP 客户端更稳定）。"""
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--max-time", str(int(max(5, timeout))), url],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8").strip()


def fetch_fred_series(series_id: str, *, timeout: float = 30.0, retries: int = 3) -> pd.DataFrame:
    """从 FRED 公开 CSV 下载时间序列。"""
    url = f"{FRED_CSV_URL}?id={series_id}"
    last_err: Exception | None = None
    text = ""
    for attempt in range(retries):
        try:
            text = _download_text(url, timeout=timeout)
            if not text.startswith("observation_date"):
                raise ValueError(f"FRED 返回非 CSV 内容 (series={series_id})")
            break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            last_err = e
            if attempt + 1 >= retries:
                raise
    else:
        raise last_err or RuntimeError(f"FRED 下载失败: {series_id}")

    df = pd.read_csv(io.StringIO(text))
    date_col = df.columns[0]
    value_col = df.columns[1]
    df = df.rename(columns={date_col: "date", value_col: "value"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    return df


def _add_change_columns(df: pd.DataFrame) -> pd.DataFrame:
    """为序列补充环比、同比变动率（%）。"""
    out = df.copy()
    out["mom_pct"] = out["value"].pct_change(1) * 100.0
    out["yoy_pct"] = out["value"].pct_change(12) * 100.0
    return out


def _add_nfp_change(df: pd.DataFrame) -> pd.DataFrame:
    """非农：在就业人数水平上计算月度净增（千人）。"""
    out = df.copy()
    out["monthly_change_k"] = out["value"].diff(1)
    return out


def fetch_ism_pmi(*, timeout: float = 30.0) -> pd.DataFrame:
    """
    ISM 制造业 PMI（FRED 已于 2016 停更 NAPM）。
    数据源：Investing.com 经济日历图表 API。
    """
    text = _download_text(INVESTING_ISM_CHART_URL, timeout=timeout)
    payload = json.loads(text)
    rows: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        if not item or len(item) < 2:
            continue
        ts_ms = int(item[0])
        value = float(item[1])
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC).date().isoformat()
        rows.append({"date": dt, "value": value})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return df


def _save_csv(
    df: pd.DataFrame,
    path: Path,
    *,
    extra_columns: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["date", "value"]
    if extra_columns:
        cols.extend(extra_columns)
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out[cols].to_csv(path, index=False, encoding="utf-8")


def _latest_snapshot(results: list[MacroFetchResult]) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "indicators": {},
    }
    for r in results:
        snap["indicators"][r.indicator] = {
            "latest_date": r.latest_date,
            "latest_value": r.latest_value,
            "rows": r.rows,
            "path": str(r.path),
            "source": r.source,
        }
    return snap


def fetch_and_save_all(
    cfg: AdvisorConfig | None = None,
    *,
    timeout: float = 30.0,
) -> list[MacroFetchResult]:
    """爬取全部宏观指标并写入 data/macro/<indicator>/ 子目录。"""
    root = _macro_root(cfg)
    base = cfg.data_dir if cfg and cfg.data_dir else None
    ensure_macro_layout(base)
    results: list[MacroFetchResult] = []

    for key, meta in FRED_SERIES.items():
        series_id = meta["series_id"]
        df = fetch_fred_series(series_id, timeout=timeout)
        extra: list[str] = []
        if key in ("m2", "cpi", "ppi"):
            df = _add_change_columns(df)
            extra = ["mom_pct", "yoy_pct"]
        elif key == "nfp":
            df = _add_nfp_change(df)
            extra = ["monthly_change_k"]

        subdir = meta.get("subdir", key)
        out_path = root / subdir / meta["filename"]
        _save_csv(df, out_path, extra_columns=extra)
        latest = df.iloc[-1]
        results.append(
            MacroFetchResult(
                indicator=key,
                path=out_path,
                rows=len(df),
                latest_date=latest["date"].strftime("%Y-%m-%d"),
                latest_value=float(latest["value"]),
                source=f"fred:{series_id}",
            )
        )

    # ISM PMI 单独目录
    ism_df = fetch_ism_pmi(timeout=timeout)
    ism_path = root / "ism" / "ism_manufacturing_pmi.csv"
    _save_csv(ism_df, ism_path)
    ism_latest = ism_df.iloc[-1]
    results.append(
        MacroFetchResult(
            indicator="ism",
            path=ism_path,
            rows=len(ism_df),
            latest_date=ism_latest["date"].strftime("%Y-%m-%d"),
            latest_value=float(ism_latest["value"]),
            source="investing.com:ism_pmi",
        )
    )

    # 汇总快照
    meta_path = root / "latest.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(_latest_snapshot(results), f, ensure_ascii=False, indent=2)

    # 可读摘要 CSV
    summary_path = root / "summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indicator", "latest_date", "latest_value", "rows", "source", "path"])
        for r in results:
            w.writerow([r.indicator, r.latest_date, r.latest_value, r.rows, r.source, str(r.path)])

    return results
