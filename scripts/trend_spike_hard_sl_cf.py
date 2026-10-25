#!/usr/bin/env python3
"""
硬止损开/关反事实脚本（占位 / 框架示例）

⚠️ 本仓库不含 hybrid.regime2.trend_spike 引擎
本脚本展示 API 调用逻辑；实际执行需迁移至包含以下模块的仓库：
- hybrid.regime2.trend_spike.simulate_trade()
- practical_candidate_v2_live 参数包
- Desktop/t102/t105 等桌面脚本目录

用法（假设在正确仓库）：
    python scripts/trend_spike_hard_sl_cf.py --universe PEPE --window 1y
    python scripts/trend_spike_hard_sl_cf.py --universe full --window capital-tiers-1y
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

try:
    import pandas as pd
except ImportError:
    print("错误: 需要 pandas。运行: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(1)


@dataclass
class ArmConfig:
    """对照臂配置"""

    name: str
    hard_sl_by_class: dict[str, str | None]  # {"M30": "M30", "M50": "M50", ...} or {"all": "none"}


@dataclass
class SimulationResult:
    """单臂回测结果"""

    arm: str
    symbol: str
    symbol_class: str
    n_trades: int
    net_pnl: float
    exploded_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    hard_sl_exit_pct: float


@dataclass
class CounterfactualReport:
    """反事实报告"""

    engine_md5: str
    window_label: str
    timestamp: str
    config_notice: str
    results: list[SimulationResult] = field(default_factory=list)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "engine_md5": self.engine_md5,
                "window_label": self.window_label,
                "timestamp": self.timestamp,
                "config_notice": self.config_notice,
            },
            "results": [
                {
                    "arm": r.arm,
                    "symbol": r.symbol,
                    "symbol_class": r.symbol_class,
                    "n_trades": r.n_trades,
                    "net_pnl": round(r.net_pnl, 2),
                    "exploded_pct": round(r.exploded_pct, 2),
                    "win_rate": round(r.win_rate, 2),
                    "profit_factor": round(r.profit_factor, 2),
                    "max_drawdown": round(r.max_drawdown, 2),
                    "hard_sl_exit_pct": round(r.hard_sl_exit_pct, 2),
                }
                for r in self.results
            ],
        }

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for r in self.results:
            rows.append(
                {
                    "臂": r.arm,
                    "品种": r.symbol,
                    "类别": r.symbol_class,
                    "笔数": r.n_trades,
                    "净利": round(r.net_pnl, 2),
                    "爆仓%": round(r.exploded_pct, 2),
                    "胜率": round(r.win_rate, 2),
                    "PF": round(r.profit_factor, 2),
                    "最大回撤": round(r.max_drawdown, 2),
                    "硬止出场%": round(r.hard_sl_exit_pct, 2),
                }
            )
        return pd.DataFrame(rows)


def _mock_simulate_trade(
    symbol: str,
    symbol_class: str,
    params: dict[str, Any],
    hard_sl: str | None,
    market_data_path: Path,
    window_start: str,
    window_end: str,
) -> SimulationResult:
    """
    占位函数：模拟 hybrid.regime2.trend_spike.simulate_trade() 调用

    实际实现需：
    1. 加载 MarketData（OHLCV + 订单簿/资金费等辅助）
    2. 遍历时间窗，按 params 执行进场/出场/硬止逻辑
    3. 统计 trades、PnL、爆仓、胜率、PF、MDD、硬止出场占比
    """
    # Mock 返回（实际需调用真实引擎）
    import random

    random.seed(hash((symbol, hard_sl)))
    arm_name = "A-现网硬止" if hard_sl and hard_sl != "none" else "B-全关"

    return SimulationResult(
        arm=arm_name,
        symbol=symbol,
        symbol_class=symbol_class,
        n_trades=random.randint(50, 200),
        net_pnl=random.uniform(-1000, 3000),
        exploded_pct=random.uniform(0, 15),
        win_rate=random.uniform(40, 60),
        profit_factor=random.uniform(0.8, 2.5),
        max_drawdown=random.uniform(-2000, -500),
        hard_sl_exit_pct=0 if hard_sl == "none" else random.uniform(10, 40),
    )


def _get_engine_md5() -> str:
    """
    计算引擎文件 MD5（占位）

    实际应指向 hybrid/regime2/trend_spike.py 或等价 .so
    """
    # 占位：当前脚本自身
    script_path = Path(__file__)
    if script_path.exists():
        return hashlib.md5(script_path.read_bytes()).hexdigest()[:8]
    return "00000000"


def _load_param_pack(pack_name: str) -> dict[str, Any]:
    """
    加载参数包（占位）

    实际应从 config/ 或 params/ 目录加载 practical_candidate_v2_live
    """
    return {
        "entry_threshold": 0.618,
        "exit_mode": "dynamic",
        "leverage": 3,
        "position_size": 0.05,
        "vz_gate": 0.15,
        # 硬止由 simulate_trade(..., hard_sl=) 参数单独控制
    }


def _get_universe(universe_name: str) -> list[tuple[str, str]]:
    """
    获取品种宇宙（占位）

    返回: [(symbol, symbol_class), ...]
    实际应从配置/数据库加载
    """
    if universe_name == "PEPE":
        return [("PEPEUSDT", "M30")]
    elif universe_name == "full":
        # 占位：多品种
        return [
            ("PEPEUSDT", "M30"),
            ("DOGEUSDT", "M50"),
            ("SHIBUSDT", "M30"),
            ("BTCUSDT", "M50"),
        ]
    else:
        raise ValueError(f"未知宇宙: {universe_name}")


def _get_window_dates(window_label: str) -> tuple[str, str]:
    """
    获取时间窗起止（占位）

    实际应从 capital-tiers 配置或标准一年窗标签映射
    """
    if window_label == "1y":
        return "2024-01-01", "2024-12-31"
    elif window_label.startswith("capital-tiers-"):
        # 占位
        return "2024-01-01", "2024-12-31"
    else:
        raise ValueError(f"未知窗口: {window_label}")


def _get_hard_sl_for_class(symbol_class: str, arm: Literal["A", "B"]) -> str | None:
    """
    按品种类别与臂返回硬止参数

    臂 A：现网硬止（按类 M30/M50，对齐 v0.2.1-v2-sizing）
    臂 B：全关（hard_sl=none）
    """
    if arm == "B":
        return "none"
    # 臂 A
    if symbol_class == "M30":
        return "M30"
    elif symbol_class == "M50":
        return "M50"
    else:
        # 默认（实际应查表）
        return "M30"


def run_counterfactual(
    universe: str,
    window_label: str,
    market_data_root: Path,
    output_dir: Path,
) -> CounterfactualReport:
    """
    执行硬止开/关反事实对照

    流程：
    1. 加载参数包 practical_candidate_v2_live
    2. 遍历宇宙品种
    3. 每品种跑两臂：A=现网硬止，B=全关
    4. 汇总结果
    """
    engine_md5 = _get_engine_md5()
    params = _load_param_pack("practical_candidate_v2_live")
    universe_list = _get_universe(universe)
    start_date, end_date = _get_window_dates(window_label)

    report = CounterfactualReport(
        engine_md5=engine_md5,
        window_label=f"{window_label} ({start_date} ~ {end_date})",
        timestamp=datetime.now().isoformat(),
        config_notice="现网硬止仍在、未改 Config、未 --apply；仅研究脚本回放",
    )

    for symbol, symbol_class in universe_list:
        for arm in ["A", "B"]:
            hard_sl = _get_hard_sl_for_class(symbol_class, arm)
            print(f"模拟 {arm} 臂 {symbol} ({symbol_class}) hard_sl={hard_sl} ...")

            result = _mock_simulate_trade(
                symbol=symbol,
                symbol_class=symbol_class,
                params=params,
                hard_sl=hard_sl,
                market_data_path=market_data_root / symbol,
                window_start=start_date,
                window_end=end_date,
            )
            report.results.append(result)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="硬止开/关反事实脚本（占位/框架示例）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--universe",
        default="PEPE",
        help="品种宇宙：PEPE | full（默认 PEPE 单品烟测）",
    )
    parser.add_argument(
        "--window",
        default="1y",
        help="时间窗：1y | capital-tiers-1y（默认 1y）",
    )
    parser.add_argument(
        "--market-data",
        type=Path,
        default=Path("./data/market"),
        help="MarketData 根目录（默认 ./data/market）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./out"),
        help="输出目录（默认 ./out）",
    )

    args = parser.parse_args(argv)

    # 检查是否在正确仓库
    try:
        # 占位：尝试 import hybrid.regime2（实际需改为正确包路径）
        # from hybrid.regime2.trend_spike import simulate_trade
        raise ImportError("hybrid.regime2 not found")
    except ImportError:
        print(
            "⚠️  警告: 未找到 hybrid.regime2.trend_spike 模块",
            file=sys.stderr,
        )
        print("本仓库不包含所需交易引擎；脚本将使用 mock 数据演示逻辑", file=sys.stderr)
        print("", file=sys.stderr)

    if not args.market_data.exists():
        print(f"警告: MarketData 目录不存在: {args.market_data}", file=sys.stderr)
        print("将继续使用 mock 数据（无实际回测）", file=sys.stderr)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    date_suffix = datetime.now().strftime("%Y%m%d")
    output_subdir = args.output_dir / f"hard_sl_cf_{date_suffix}"
    output_subdir.mkdir(parents=True, exist_ok=True)

    print(f"开始反事实模拟：宇宙={args.universe}，窗口={args.window}")
    report = run_counterfactual(
        universe=args.universe,
        window_label=args.window,
        market_data_root=args.market_data,
        output_dir=output_subdir,
    )

    # 写 JSON
    json_path = output_subdir / "summary.json"
    json_path.write_text(
        json.dumps(report.to_summary_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入: {json_path}")

    # 写 Excel
    try:
        df = report.to_dataframe()
        excel_path = output_subdir / "summary.xlsx"
        df.to_excel(excel_path, index=False, sheet_name="硬止反事实")
        print(f"已写入: {excel_path}")
    except Exception as e:
        print(f"写 Excel 失败: {e}", file=sys.stderr)

    print("")
    print("报告头信息:")
    print(f"  引擎 MD5: {report.engine_md5}")
    print(f"  窗口: {report.window_label}")
    print(f"  配置声明: {report.config_notice}")
    print("")
    print("样本结果（前 5 行）:")
    print(report.to_dataframe().head().to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
