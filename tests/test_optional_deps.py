from ai_trade_advisor.regime.optional_deps import optional_dependency_status, tensorflow_available


def test_optional_dependency_status_shape():
    status = optional_dependency_status()
    assert "tensorflow" in status
    assert "install" in status["tensorflow"]
    assert isinstance(tensorflow_available(), bool)
