"""Regime 标签目录（公共常量，供契约层与引擎共用）。"""

REGIME_LABELS: dict[str, str] = {
    "macro_frozen_range": "宏观熔断 · 强制观望",
    "high_vol_uptrend": "高波上涨 · 现货 CVD 确认",
    "fake_breakout_wash": "假突破洗盘 · 缺现货买盘",
    "high_vol_downtrend": "高波下跌 · 趋势延续",
    "high_vol_self_heal_range": "高波自愈区间 · CVD 底背离",
    "low_vol_uptrend": "低波上行 · 趋势延续",
    "mid_vol_uptrend": "中波上行 · 趋势延续",
    "low_vol_downtrend": "低波下行 · 趋势延续",
    "low_vol_range": "低波死寂 · 震荡",
    "mid_vol_range": "中波震荡 · 等待突破",
    "high_vol_range": "高波震荡 · 事件驱动",
}
