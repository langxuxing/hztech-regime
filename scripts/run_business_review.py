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
from ai_trade_advisor.datasource.ohlcv import get_last_ohlcv_source, load_ohlcv, resample_from_1m
from ai_trade_advisor.layers.l1_ingestion import bundle, market
from ai_trade_advisor.layers.l3_confirmation.regime_stabilizer import DEFAULT_MIN_DWELL_BARS
from ai_trade_advisor.readiness import check_readiness
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
    """主链路 load_ohlcv 运行时数据来源。"""
    cfg = AdvisorConfig.from_env()
    try:
        df = load_ohlcv(cfg)
        source = get_last_ohlcv_source()
        ok = source == "local_btc_1m_resample" and len(df) >= 50
    except Exception as exc:
        source = None
        ok = False
        err = str(exc)
    else:
        err = None

    section = {
        "ohlcv_source": source,
        "bars": len(df) if source else 0,
        "local_1m_scheduler": (ROOT / "scripts" / "btc_1m_scheduler.py").exists(),
        "default_exchange": cfg.exchange,
        "allow_ccxt_fallback": cfg.allow_ccxt_ohlcv_fallback,
    }
    if err:
        section["error"] = err
    report.sections["pipeline_data_path"] = section

    if not ok:
        report.add(
            Finding(
                severity="critical" if not cfg.allow_ccxt_ohlcv_fallback else "high",
                category="data",
                title="本地 BTC OHLCV 未作为主数据源",
                detail=err or f"load_ohlcv source={source}，期望 local_btc_1m_resample",
                evidence=section,
            )
        )


def audit_env_readiness(report: ReviewReport) -> None:
    cfg = AdvisorConfig.from_env()
    readiness = check_readiness(cfg)

    etf_dir = cfg.etfdata_dir or (get_data_root() / "ETF")
    macro_dir = get_macro_root()
    btc_dir = get_ohlcv_dir("Btc")

    section = {
        "readiness": readiness.to_dict(),
        "data_layout": {
            "data_root": str(get_data_root()),
            "etf_csv_count": len(list(etf_dir.rglob("*.csv"))) if etf_dir.exists() else 0,
            "macro_subdirs": [p.name for p in macro_dir.iterdir() if p.is_dir()]
            if macro_dir.exists()
            else [],
            "btc_1m_files": len(list(btc_dir.glob("btc_usdt_swap_mark_1m_*.csv"))),
        },
        "use_deribit_gex": cfg.use_deribit_gex,
        "use_taker_cvd": cfg.use_taker_cvd,
    }
    report.sections["env_readiness"] = section

    if readiness.tier == "demo":
        report.add(
            Finding(
                severity="medium",
                category="data",
                title=f"环境就绪度: {readiness.tier}",
                detail="; ".join(readiness.notes[:4]) or "缺少生产 API Key 或本地数据",
            )
        )
    elif readiness.tier == "degraded":
        report.add(
            Finding(
                severity="low",
                category="data",
                title=f"环境就绪度: {readiness.tier}",
                detail="; ".join(readiness.notes[:3]) or "部分数据源降级",
            )
        )


def audit_config_conflicts(report: ReviewReport) -> None:
    cfg = AdvisorConfig.from_env()
    section = {
        "regime_min_dwell_bars_config": cfg.regime_min_dwell_bars,
        "stabilizer_default_min_dwell": DEFAULT_MIN_DWELL_BARS,
        "dwell_aligned": cfg.regime_min_dwell_bars == DEFAULT_MIN_DWELL_BARS,
        "regime_transition_penalty_config": cfg.regime_transition_penalty,
        "production_path": "orchestrator → run_l3_pipeline → confirm_regime_state",
        "backtest_path": "run_confirmation → confirm_regime_state (fallback: stabilize_regime)",
    }
    report.sections["config_l3"] = section

    if not section["dwell_aligned"]:
        report.add(
            Finding(
                severity="medium",
                category="signal",
                title="L3 驻留周期默认值不一致",
                detail=(
                    f"config={cfg.regime_min_dwell_bars} vs "
                    f"stabilize_regime 默认={DEFAULT_MIN_DWELL_BARS}"
                ),
                evidence=section,
            )
        )


def audit_duplicate_ticker(report: ReviewReport) -> None:
    import inspect

    bundle_src = inspect.getsource(bundle.run_ingestion)
    market_src = inspect.getsource(market.build_market_features)
    accepts_ticker_param = "ticker:" in market_src or "ticker:" in market_src.replace(" ", "")
    bundle_passes_ticker = "ticker=ticker" in bundle_src

    section = {
        "market_accepts_ticker_param": accepts_ticker_param,
        "bundle_passes_ticker": bundle_passes_ticker,
    }
    report.sections["duplicate_api"] = section

    if not bundle_passes_ticker:
        report.add(
            Finding(
                severity="low",
                category="data_cleaning",
                title="Ticker 未从 bundle 注入 market 层",
                detail="run_ingestion 与 build_market_features 可能重复拉取 ticker",
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


def audit_feedback_loop(report: ReviewReport) -> None:
    """人工反馈闭环样本与推荐就绪度。"""
    from ai_trade_advisor.regime.feedback.stats import build_feedback_stats

    cfg = AdvisorConfig.from_env()
    try:
        stats = build_feedback_stats(symbol=cfg.symbol, cfg=cfg)
    except Exception as exc:
        report.add(
            Finding(
                severity="medium",
                category="feedback",
                title="反馈统计查询失败",
                detail=str(exc),
            )
        )
        return

    report.sections["feedback"] = stats

    if stats["judgment_count"] < stats["min_judgments_for_recommendation"]:
        report.add(
            Finding(
                severity="info",
                category="feedback",
                title="人工判断样本不足",
                detail=stats.get("message", ""),
                evidence={
                    "judgment_count": stats["judgment_count"],
                    "min": stats["min_judgments_for_recommendation"],
                },
            )
        )

    if cfg.regime_use_recommendation and not stats["recommendation_ready"]:
        report.add(
            Finding(
                severity="medium",
                category="feedback",
                title="REGIME_USE_RECOMMENDATION 已开但样本未就绪",
                detail=stats.get("message", ""),
                evidence=stats,
            )
        )


def audit_trend_health(report: ReviewReport) -> None:
    """趋势判断健康检查（快照 / trend_judgment 契约）。"""
    from ai_trade_advisor.regime.trend_health import run_trend_health_check

    try:
        health = run_trend_health_check()
    except Exception as exc:
        report.add(
            Finding(
                severity="high",
                category="trend_health",
                title="趋势健康检查失败",
                detail=str(exc),
            )
        )
        return

    report.sections["trend_health"] = {
        "status": health.get("status"),
        "readiness_tier": health.get("readiness_tier"),
        "snapshot_present": health.get("snapshot_present"),
        "findings_count": len(health.get("findings") or []),
    }

    for finding in health.get("findings") or []:
        sev = finding.get("severity", "info")
        if sev in ("critical", "high", "medium"):
            report.add(
                Finding(
                    severity=sev,
                    category="trend_health",
                    title=finding.get("title", "趋势健康"),
                    detail=finding.get("detail", ""),
                )
            )


def run_pytest(report: ReviewReport) -> None:
    tests = [
        "tests/test_data_paths.py",
        "tests/test_ohlcv_local.py",
        "tests/test_readiness.py",
        "tests/test_readiness_cache.py",
        "tests/test_layers.py",
        "tests/test_regime_confirmation.py",
        "tests/test_regime_models.py",
        "tests/test_regime_core.py",
        "tests/test_derivatives_trend.py",
        "tests/test_taker_cvd.py",
        "tests/test_black_swan.py",
        "tests/test_trend_judgment.py",
        "tests/test_trend_health_check.py",
        "tests/test_api_radar_contract.py",
        "tests/test_feedback_stats.py",
        "tests/test_trend_soak.py",
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

    print("P4 趋势健康...")
    audit_trend_health(report)

    print("P5 反馈闭环...")
    audit_feedback_loop(report)

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
