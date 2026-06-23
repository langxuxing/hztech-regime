#!/usr/bin/env python3
"""按业务流执行自动化评审：数据质量、配置冲突、模型可用性、测试套件。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root, get_ohlcv_dir, get_macro_root
from ai_trade_advisor.datasource.ohlcv import load_ohlcv, resample_from_1m
from ai_trade_advisor.layers.l3_confirmation.regime_stabilizer import (
    DEFAULT_MIN_DWELL_BARS,
    TRANSITION_PENALTY_CONFIDENCE,
)
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

REPORT_DIR = get_data_root() / "exports" / "reviews"
BAR_MS = 60_000


@dataclass
class Finding:
    severity: str  # critical | high | medium | low | info
    category: str
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewReport:
    generated_at: str
    findings: list[Finding] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "summary": {
                "total": len(self.findings),
                "critical": sum(1 for f in self.findings if f.severity == "critical"),
                "high": sum(1 for f in self.findings if f.severity == "high"),
                "medium": sum(1 for f in self.findings if f.severity == "medium"),
                "low": sum(1 for f in self.findings if f.severity == "low"),
            },
            "sections": self.sections,
            "findings": [asdict(f) for f in self.findings],
        }


def _load_local_1m_csvs(btc_dir: Path) -> pd.DataFrame | None:
    files = sorted(btc_dir.glob("btc_usdt_swap_mark_1m_*.csv"))
    if not files:
        return None
    frames: list[pd.DataFrame] = []
    for fp in files:
        df = pd.read_csv(fp)
        if "ts" in df.columns and "timestamp" not in df.columns:
            df = df.rename(columns={"ts": "timestamp"})
        frames.append(df)
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return merged.reset_index(drop=True)


def audit_ohlcv_local(report: ReviewReport) -> None:
    btc_dir = get_ohlcv_dir("Btc")
    df = _load_local_1m_csvs(btc_dir)
    section: dict[str, Any] = {"btc_dir": str(btc_dir), "files": 0}

    if df is None or df.empty:
        report.add(
            Finding(
                severity="high",
                category="data",
                title="本地 BTC 1m OHLCV 无数据",
                detail=f"目录 {btc_dir} 下未找到 btc_usdt_swap_mark_1m_*.csv",
            )
        )
        report.sections["ohlcv_local"] = section
        return

    section["files"] = len(list(btc_dir.glob("btc_usdt_swap_mark_1m_*.csv")))
    section["bars"] = len(df)
    section["start"] = str(pd.to_datetime(df["timestamp"].iloc[0], unit="ms", utc=True))
    section["end"] = str(pd.to_datetime(df["timestamp"].iloc[-1], unit="ms", utc=True))

    ts = df["timestamp"].astype(int)
    gaps = []
    for i in range(1, len(ts)):
        delta = int(ts.iloc[i] - ts.iloc[i - 1])
        if delta > BAR_MS:
            gaps.append(
                {
                    "after": str(pd.to_datetime(ts.iloc[i - 1], unit="ms", utc=True)),
                    "missing_bars": delta // BAR_MS - 1,
                }
            )

    ohlc_bad = df[(df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])]
    zero_vol = int((df.get("volume", pd.Series([0] * len(df))) == 0).sum()) if "volume" in df.columns else None

    section["gap_count"] = len(gaps)
    section["gap_samples"] = gaps[:5]
    section["ohlc_violations"] = len(ohlc_bad)
    section["zero_volume_bars"] = zero_vol

    if gaps:
        report.add(
            Finding(
                severity="high" if len(gaps) > 10 else "medium",
                category="data_cleaning",
                title=f"本地 1m K 线存在 {len(gaps)} 处时间缺口",
                detail="缺口可能导致 resample 后 30m bar 不完整，影响 Donchian/KAMA/HMM",
                evidence={"samples": gaps[:3]},
            )
        )

    if len(ohlc_bad) > 0:
        report.add(
            Finding(
                severity="high",
                category="data_cleaning",
                title="OHLC 逻辑异常行",
                detail=f"发现 {len(ohlc_bad)} 行 high/low/open/close 不一致",
                evidence={"count": len(ohlc_bad)},
            )
        )

    # resample 30m 并检查
    df_std = df.rename(columns={"timestamp": "timestamp"})
    if "volume" not in df_std.columns:
        df_std["volume"] = 0.0
    df_30m = resample_from_1m(df_std, 30)
    section["bars_30m_resampled"] = len(df_30m)

    report.sections["ohlcv_local"] = section


def audit_pipeline_data_path(report: ReviewReport) -> None:
    """主链路 load_ohlcv 是否使用本地数据。"""
    import inspect

    from ai_trade_advisor import datasource

    source = inspect.getsource(datasource.ohlcv.load_ohlcv)
    uses_local_btc = "get_ohlcv_dir" in source or "btc_usdt_swap" in source

    section = {
        "load_ohlcv_uses_local_btc": uses_local_btc,
        "local_1m_scheduler": (ROOT / "scripts" / "btc_1m_scheduler.py").exists(),
        "default_exchange": AdvisorConfig.from_env().exchange,
    }
    report.sections["pipeline_data_path"] = section

    if not uses_local_btc and section["local_1m_scheduler"]:
        report.add(
            Finding(
                severity="critical",
                category="data",
                title="训练-服务数据割裂",
                detail=(
                    "scripts 持续下载 OKX mark 1m 到 data/OHLCV/Btc，"
                    "但 load_ohlcv() 实盘默认 fetch_ohlcv_ccxt(Binance 30m)，"
                    "回测/历史与线上数据源不一致"
                ),
                evidence=section,
            )
        )


def audit_env_readiness(report: ReviewReport) -> None:
    cfg = AdvisorConfig.from_env()

    def _set(name: str) -> bool:
        return bool(os.getenv(name, "").strip())

    keys = {
        "COINGLASS_API_KEY": _set("COINGLASS_API_KEY"),
        "X_BEARER_TOKEN": _set("X_BEARER_TOKEN"),
        "AI_API_KEY": _set("AI_API_KEY") or _set("OPENAI_API_KEY"),
        "BINANCE_CONFIG_PATH": bool(cfg.binance_config_path) or _set("BINANCE_API_KEY"),
    }

    etf_dir = cfg.etfdata_dir or (get_data_root() / "ETF")
    macro_dir = get_macro_root()
    btc_dir = get_ohlcv_dir("Btc")

    data_layout = {
        "data_root": str(get_data_root()),
        "etf_csv_count": len(list(etf_dir.rglob("*.csv"))) if etf_dir.exists() else 0,
        "macro_subdirs": [p.name for p in macro_dir.iterdir() if p.is_dir()] if macro_dir.exists() else [],
        "btc_1m_files": len(list(btc_dir.glob("btc_usdt_swap_mark_1m_*.csv"))),
    }

    # capital flows quality simulation
    from ai_trade_advisor.datasource.capital_flows import build_capital_flows

    try:
        flows = build_capital_flows(cfg)
        cf_quality = flows.data_quality
    except Exception as exc:
        cf_quality = f"error: {exc}"

    event_demo = cfg.event_demo_mode
    readiness = "production"
    if not keys["COINGLASS_API_KEY"]:
        readiness = "degraded"
    if event_demo or (not keys["X_BEARER_TOKEN"] and cfg.event_demo_mode):
        readiness = "demo"

    section = {
        "api_keys_configured": keys,
        "capital_flows_quality": cf_quality,
        "readiness_tier": readiness,
        "data_layout": data_layout,
        "use_deribit_gex": cfg.use_deribit_gex,
        "use_taker_cvd": cfg.use_taker_cvd,
    }
    report.sections["env_readiness"] = section

    if not keys["COINGLASS_API_KEY"]:
        report.add(
            Finding(
                severity="medium",
                category="data",
                title="CoinGlass API Key 未配置",
                detail="资金流/日历质量降级为 partial，ETF 纠偏与 netflow 能力受限",
            )
        )
    if cf_quality in ("partial", "free_only"):
        report.add(
            Finding(
                severity="medium",
                category="data",
                title=f"资金流数据质量: {cf_quality}",
                detail="L2 ETF 慢变量纠偏可能跳过或不可靠",
            )
        )


def audit_config_conflicts(report: ReviewReport) -> None:
    cfg = AdvisorConfig.from_env()
    section = {
        "regime_min_dwell_bars_config": cfg.regime_min_dwell_bars,
        "stabilizer_default_min_dwell": DEFAULT_MIN_DWELL_BARS,
        "regime_transition_penalty_config": cfg.regime_transition_penalty,
        "stabilizer_transition_penalty_confidence": TRANSITION_PENALTY_CONFIDENCE,
        "production_path": "orchestrator → run_l3_pipeline → confirm_regime_state",
        "backtest_path": "run_confirmation → stabilize_regime (time-based dwell)",
    }
    report.sections["config_l3"] = section

    if cfg.regime_min_dwell_bars != DEFAULT_MIN_DWELL_BARS:
        report.add(
            Finding(
                severity="medium",
                category="signal",
                title="L3 驻留周期默认值不一致",
                detail=(
                    f"生产路径 confirm_regime_state 使用 config={cfg.regime_min_dwell_bars}；"
                    f"stabilize_regime 默认常量={DEFAULT_MIN_DWELL_BARS}（仅 run_confirmation 回测路径）"
                ),
                evidence=section,
            )
        )

    report.add(
        Finding(
            severity="medium",
            category="signal",
            title="L3 双实现路径",
            detail=(
                "生产 orchestrator 使用 confirm_regime_state（bar 计数 dwell）；"
                "run_confirmation 使用 stabilize_regime（wall-clock 计时 + 邻接矩阵惩罚 0.78）"
            ),
            evidence=section,
        )
    )


def audit_duplicate_ticker(report: ReviewReport) -> None:
    import inspect

    from ai_trade_advisor.layers.l1_ingestion import bundle, market

    bundle_src = inspect.getsource(bundle.run_ingestion)
    market_src = inspect.getsource(market.build_market_features)
    double = "fetch_live_ticker" in bundle_src and "fetch_live_ticker" in market_src

    report.sections["duplicate_api"] = {"double_ticker_fetch": double}
    if double:
        report.add(
            Finding(
                severity="low",
                category="data_cleaning",
                title="Ticker 重复拉取",
                detail="run_ingestion 与 build_market_features 各调用 fetch_live_ticker，可能导致价格时间戳不一致",
            )
        )


def audit_models_on_local_data(report: ReviewReport) -> None:
    btc_dir = get_ohlcv_dir("Btc")
    df_1m = _load_local_1m_csvs(btc_dir)
    if df_1m is None or len(df_1m) < 200:
        report.sections["models"] = {"skipped": "insufficient local 1m data"}
        return

    if "volume" not in df_1m.columns:
        df_1m["volume"] = 0.0
    df = resample_from_1m(df_1m, 30).tail(720)
    if len(df) < 100:
        report.sections["models"] = {"skipped": "insufficient 30m bars after resample"}
        return

    from ai_trade_advisor.regime.models.ensemble import run_all_regime_models

    rule = {
        "regime_id": "mid_vol_range",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.6,
        "dashboard_regime": "range",
    }
    try:
        ensemble = run_all_regime_models(df, rule)
    except Exception as exc:
        report.add(
            Finding(
                severity="high",
                category="models",
                title="模型 ensemble 运行失败",
                detail=str(exc),
            )
        )
        return

    models = ensemble.get("models") or {}
    errors = [m for m in models.values() if isinstance(m, dict) and m.get("error")]
    ok = [m for m in models.values() if isinstance(m, dict) and not m.get("error")]

    trends: dict[str, int] = {}
    for m in ok:
        t = m.get("raw_trend", "unknown")
        trends[t] = trends.get(t, 0) + 1

    section = {
        "bars_used": len(df),
        "models_total": len(models),
        "models_ok": len(ok),
        "models_error": len(errors),
        "error_models": [
            {"id": m.get("model_id"), "error": m.get("error")} for m in errors[:5]
        ],
        "trend_distribution": trends,
        "changepoint_prob": ensemble.get("changepoint_prob"),
        "dominant_trend": ensemble.get("dominant_trend"),
    }
    report.sections["models"] = section

    if errors:
        report.add(
            Finding(
                severity="high" if len(errors) > 3 else "medium",
                category="models",
                title=f"{len(errors)}/{len(models)} 个 Regime 模型运行失败",
                detail="; ".join(f"{e.get('model_id')}: {e.get('error')}" for e in errors[:3]),
                evidence={"errors": section["error_models"]},
            )
        )

    if len(ok) >= 2 and len(set(m.get("raw_trend") for m in ok)) >= 3:
        report.add(
            Finding(
                severity="info",
                category="models",
                title="模型趋势分歧较大",
                detail=f"可用模型 raw_trend 分布: {trends}",
                evidence=section,
            )
        )


def run_pytest(report: ReviewReport) -> None:
    tests = [
        "tests/test_data_paths.py",
        "tests/test_layers.py",
        "tests/test_regime_confirmation.py",
        "tests/test_regime_models.py",
        "tests/test_regime_core.py",
        "tests/test_derivatives_trend.py",
        "tests/test_taker_cvd.py",
        "tests/test_black_swan.py",
    ]
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", *tests]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    section = {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-5:] if proc.stdout else [],
        "stderr_tail": proc.stderr.strip().splitlines()[-5:] if proc.stderr else [],
    }
    report.sections["pytest"] = section
    if proc.returncode != 0:
        report.add(
            Finding(
                severity="high",
                category="engineering",
                title="核心测试套件未全部通过",
                detail=proc.stdout.strip() or proc.stderr.strip(),
                evidence=section,
            )
        )


def write_report(report: ReviewReport) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"business_review_{ts}.json"
    md_path = REPORT_DIR / f"business_review_{ts}.md"

    data = report.to_dict()
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Regime&Trend 业务流评审报告",
        f"",
        f"生成时间 (UTC): {report.generated_at}",
        f"",
        f"## 摘要",
        f"- 发现项: {data['summary']['total']} "
        f"(critical={data['summary']['critical']}, high={data['summary']['high']}, "
        f"medium={data['summary']['medium']})",
        f"",
    ]
    for name, sec in report.sections.items():
        lines.append(f"## {name}")
        lines.append("```json")
        lines.append(json.dumps(sec, ensure_ascii=False, indent=2)[:4000])
        lines.append("```")
        lines.append("")

    lines.append("## 发现项清单")
    for f in report.findings:
        lines.append(f"### [{f.severity.upper()}] {f.title}")
        lines.append(f"- **类别**: {f.category}")
        lines.append(f"- **详情**: {f.detail}")
        if f.evidence:
            lines.append(f"- **证据**: `{json.dumps(f.evidence, ensure_ascii=False)[:500]}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> int:
    report = ReviewReport(generated_at=datetime.now(timezone.utc).isoformat())

    print("P1 本地 OHLCV 扫描...")
    audit_ohlcv_local(report)
    audit_pipeline_data_path(report)
    audit_env_readiness(report)

    print("P2 清洗与配置审计...")
    audit_config_conflicts(report)
    audit_duplicate_ticker(report)

    print("P3 模型 ensemble（本地 30m）...")
    audit_models_on_local_data(report)

    print("P6 测试套件...")
    run_pytest(report)

    md_path = write_report(report)
    summary = report.to_dict()["summary"]
    print(f"\n评审完成: {summary['total']} 项发现 "
          f"(critical={summary['critical']}, high={summary['high']})")
    print(f"报告: {md_path}")
    return 1 if summary["critical"] > 0 or summary["high"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
