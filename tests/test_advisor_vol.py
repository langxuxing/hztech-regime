from __future__ import annotations

from ai_trade_advisor.ai.advisor import _is_elevated_vol


def test_elevated_vol_recognizes_danger_status():
    assert _is_elevated_vol("danger", None) is True
    assert _is_elevated_vol("breakout", None) is False
    assert _is_elevated_vol(None, 0.25) is True
    assert _is_elevated_vol("normal", 0.03) is False
