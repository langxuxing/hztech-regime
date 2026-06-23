"""可选 API Key 鉴权（未配置 API_KEY 时不启用）。"""

from __future__ import annotations

from flask import Flask, jsonify, request


def register_api_auth(app: Flask, api_key: str) -> None:
    """保护 /api/* 路由；/health 与 OPTIONS 放行。"""
    key = (api_key or "").strip()
    if not key:
        return

    @app.before_request
    def _require_api_key():
        if request.method == "OPTIONS":
            return None
        if request.path == "/health":
            return None
        if not request.path.startswith("/api"):
            return None

        provided = (request.headers.get("X-API-Key") or "").strip()
        if not provided:
            auth = (request.headers.get("Authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip()

        if provided != key:
            return jsonify({"error": "unauthorized"}), 401
        return None
