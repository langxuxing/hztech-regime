"""API 鉴权测试。"""

from __future__ import annotations

from flask import Flask

from ai_trade_advisor.api_auth import register_api_auth


def _client(api_key: str = "test-secret-key"):
    app = Flask(__name__)
    register_api_auth(app, api_key)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/dashboard")
    def dashboard():
        return {"ok": True}

    return app.test_client()


def test_health_without_api_key():
    resp = _client().get("/health")
    assert resp.status_code == 200


def test_api_rejects_missing_key():
    resp = _client().get("/api/dashboard")
    assert resp.status_code == 401


def test_api_accepts_x_api_key():
    resp = _client().get("/api/dashboard", headers={"X-API-Key": "test-secret-key"})
    assert resp.status_code == 200


def test_api_accepts_bearer():
    resp = _client().get(
        "/api/dashboard",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    assert resp.status_code == 200


def test_no_auth_when_key_empty():
    resp = _client(api_key="").get("/api/dashboard")
    assert resp.status_code == 200
