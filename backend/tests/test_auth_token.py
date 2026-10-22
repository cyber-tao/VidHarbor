"""可选访问令牌：设置 VIDHARBOR_TOKEN 后 /api 需鉴权（请求头或会话 Cookie；/api/health 除外）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def token(client, monkeypatch):
    """启用令牌 s3cret；每个用例从无 Cookie 状态开始。"""
    from app.api import access

    monkeypatch.setattr(access, "_AUTH_TOKEN", "s3cret")
    client.cookies.clear()
    yield "s3cret"
    client.cookies.clear()


def test_open_when_no_token(client, monkeypatch):
    from app.api import access

    monkeypatch.setattr(access, "_AUTH_TOKEN", "")
    assert client.get("/api/stats").status_code == 200
    assert client.get("/api/auth/session").json() == {"required": False, "authenticated": True}


def test_rejects_missing_or_wrong_token(client, token):
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats", headers={"X-Vidharbor-Token": "wrong"}).status_code == 401


def test_header_accepted(client, token):
    assert client.get("/api/stats", headers={"X-Vidharbor-Token": token}).status_code == 200


def test_query_token_no_longer_accepted(client, token):
    # 查询参数里的令牌会进访问日志：API 只认请求头或会话 Cookie
    assert client.get(f"/api/stats?token={token}").status_code == 401


def test_session_cookie_flow(client, token):
    assert client.get("/api/auth/session").json() == {"required": True, "authenticated": False}
    assert client.post("/api/auth/session", json={"token": "wrong"}).status_code == 401
    assert "vidharbor_session" not in client.cookies

    r = client.post("/api/auth/session", json={"token": token})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=strict" in set_cookie
    assert token not in r.headers["set-cookie"]  # Cookie 存派生值，不存令牌原文
    # 之后的同源请求（fetch / SSE / 媒体）只靠 Cookie 即可通过
    assert client.get("/api/stats").status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is True


def test_session_invalid_after_token_rotation(client, token, monkeypatch):
    from app.api import access

    assert client.post("/api/auth/session", json={"token": token}).status_code == 200
    monkeypatch.setattr(access, "_AUTH_TOKEN", "rotated")
    assert client.get("/api/stats").status_code == 401


def test_non_ascii_tokens(client, monkeypatch):
    from app.api import access

    client.cookies.clear()
    monkeypatch.setattr(access, "_AUTH_TOKEN", "s3cret")
    assert client.post("/api/auth/session", json={"token": "令牌"}).status_code == 401
    monkeypatch.setattr(access, "_AUTH_TOKEN", "中文令牌")
    assert client.post("/api/auth/session", json={"token": "中文令牌"}).status_code == 200
    assert client.get("/api/stats").status_code == 200
    client.cookies.clear()


def test_health_always_open(client, token):
    assert client.get("/api/health").status_code == 200
