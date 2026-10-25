"""
硬止开/关反事实脚本 — 单元测试（Mock 验证）

测试逻辑：
1. 两臂 hard_sl 参数不同
2. 其他参数相同
3. 输出文件结构正确
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# 注：本测试在当前仓库使用 mock；迁移到正确仓库后需接入真实引擎
try:
    from scripts.trend_spike_hard_sl_cf import (
        ArmConfig,
        CounterfactualReport,
        SimulationResult,
        _get_hard_sl_for_class,
        _get_universe,
        _mock_simulate_trade,
        run_counterfactual,
    )

    HAS_SCRIPT = True
except ImportError:
    HAS_SCRIPT = False


@pytest.mark.skipif(not HAS_SCRIPT, reason="脚本文件未安装到 Python 路径")
class TestHardSlCounterfactual:
    def test_arm_config_difference(self):
        """验证两臂硬止参数不同"""
        # 臂 A：M30 类 -> M30
        hard_sl_a = _get_hard_sl_for_class("M30", "A")
        assert hard_sl_a == "M30"

        # 臂 A：M50 类 -> M50
        hard_sl_a_m50 = _get_hard_sl_for_class("M50", "A")
        assert hard_sl_a_m50 == "M50"

        # 臂 B：任何类 -> none
        hard_sl_b = _get_hard_sl_for_class("M30", "B")
        assert hard_sl_b == "none"

        hard_sl_b_m50 = _get_hard_sl_for_class("M50", "B")
        assert hard_sl_b_m50 == "none"

    def test_universe_loading(self):
        """验证宇宙品种加载"""
        # PEPE 单品
        pepe_universe = _get_universe("PEPE")
        assert len(pepe_universe) == 1
        assert pepe_universe[0] == ("PEPEUSDT", "M30")

        # 完整宇宙
        full_universe = _get_universe("full")
        assert len(full_universe) > 1
        assert any(sym == "PEPEUSDT" for sym, _ in full_universe)

    def test_simulation_result_structure(self):
        """验证模拟结果结构"""
        result = SimulationResult(
            arm="A-现网硬止",
            symbol="PEPEUSDT",
            symbol_class="M30",
            n_trades=100,
            net_pnl=1500.0,
            exploded_pct=2.0,
            win_rate=55.0,
            profit_factor=1.8,
            max_drawdown=-800.0,
            hard_sl_exit_pct=25.0,
        )
        assert result.arm == "A-现网硬止"
        assert result.n_trades == 100
        assert result.hard_sl_exit_pct == 25.0

    def test_mock_simulate_arm_difference(self):
        """验证 mock 模拟两臂输出不同（硬止出场占比）"""
        params = {"entry_threshold": 0.618}
        market_data = Path("/tmp/mock")

        # 臂 A（M30）
        result_a = _mock_simulate_trade(
            symbol="PEPEUSDT",
            symbol_class="M30",
            params=params,
            hard_sl="M30",
            market_data_path=market_data,
            window_start="2024-01-01",
            window_end="2024-12-31",
        )
        assert result_a.arm == "A-现网硬止"
        assert result_a.hard_sl_exit_pct > 0  # 应有硬止出场

        # 臂 B（none）
        result_b = _mock_simulate_trade(
            symbol="PEPEUSDT",
            symbol_class="M30",
            params=params,
            hard_sl="none",
            market_data_path=market_data,
            window_start="2024-01-01",
            window_end="2024-12-31",
        )
        assert result_b.arm == "B-全关"
        assert result_b.hard_sl_exit_pct == 0  # 无硬止出场

    def test_report_output_format(self):
        """验证报告输出格式"""
        report = CounterfactualReport(
            engine_md5="a3f2c8b1",
            window_label="1y (2024-01-01 ~ 2024-12-31)",
            timestamp="2026-10-25T10:00:00",
            config_notice="现网硬止仍在、未改 Config、未 --apply",
        )
        report.results.append(
            SimulationResult(
                arm="A-现网硬止",
                symbol="PEPEUSDT",
                symbol_class="M30",
                n_trades=100,
                net_pnl=1500.0,
                exploded_pct=2.0,
                win_rate=55.0,
                profit_factor=1.8,
                max_drawdown=-800.0,
                hard_sl_exit_pct=25.0,
            )
        )

        # 转 dict
        summary = report.to_summary_dict()
        assert summary["meta"]["engine_md5"] == "a3f2c8b1"
        assert summary["meta"]["config_notice"] == "现网硬止仍在、未改 Config、未 --apply"
        assert len(summary["results"]) == 1
        assert summary["results"][0]["hard_sl_exit_pct"] == 25.0

        # 转 DataFrame
        df = report.to_dataframe()
        assert len(df) == 1
        assert "硬止出场%" in df.columns
        assert df.iloc[0]["硬止出场%"] == 25.0

    def test_full_run_mock(self):
        """端到端测试（mock 数据）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            market_data = Path(tmpdir) / "market"
            market_data.mkdir()

            report = run_counterfactual(
                universe="PEPE",
                window_label="1y",
                market_data_root=market_data,
                output_dir=output_dir,
            )

            # 验证报告
            assert report.engine_md5
            assert "现网硬止仍在" in report.config_notice
            assert len(report.results) == 2  # 两臂

            # 验证臂 A
            arm_a_results = [r for r in report.results if r.arm == "A-现网硬止"]
            assert len(arm_a_results) == 1
            assert arm_a_results[0].hard_sl_exit_pct > 0

            # 验证臂 B
            arm_b_results = [r for r in report.results if r.arm == "B-全关"]
            assert len(arm_b_results) == 1
            assert arm_b_results[0].hard_sl_exit_pct == 0

    def test_output_files_created(self):
        """验证输出文件创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            market_data = Path(tmpdir) / "market"
            market_data.mkdir()

            # 运行
            from scripts.trend_spike_hard_sl_cf import main

            ret = main(
                [
                    "--universe",
                    "PEPE",
                    "--window",
                    "1y",
                    "--market-data",
                    str(market_data),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            assert ret == 0

            # 检查输出
            result_dirs = list(output_dir.glob("hard_sl_cf_*"))
            assert len(result_dirs) > 0

            result_dir = result_dirs[0]
            json_file = result_dir / "summary.json"
            assert json_file.exists()

            # 验证 JSON 内容
            data = json.loads(json_file.read_text())
            assert "meta" in data
            assert "results" in data
            assert data["meta"]["config_notice"] == "现网硬止仍在、未改 Config、未 --apply；仅研究脚本回放"

            # Excel（可选，需 openpyxl）
            excel_file = result_dir / "summary.xlsx"
            if excel_file.exists():
                import pandas as pd

                df = pd.read_excel(excel_file)
                assert "硬止出场%" in df.columns
