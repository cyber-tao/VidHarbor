"""可选访问令牌：设置 VIDHARBOR_TOKEN 后 /api 需鉴权（/api/health 除外）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_open_when_no_token(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "")
    assert client.get("/api/stats").status_code == 200


def test_rejects_missing_or_wrong_token(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "s3cret")
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats", headers={"X-Vidharbor-Token": "wrong"}).status_code == 401
    assert client.get("/api/stats?token=wrong").status_code == 401


def test_accepts_header_and_query(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "s3cret")
    assert client.get("/api/stats", headers={"X-Vidharbor-Token": "s3cret"}).status_code == 200
    assert client.get("/api/stats?token=s3cret").status_code == 200


def test_non_ascii_supplied_token_is_401_not_500(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "s3cret")
    assert client.get("/api/stats", params={"token": "令牌"}).status_code == 401


def test_non_ascii_configured_token(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "中文令牌")
    assert client.get("/api/stats", params={"token": "中文令牌"}).status_code == 200
    assert client.get("/api/stats", params={"token": "wrong"}).status_code == 401


def test_health_always_open(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_AUTH_TOKEN", "s3cret")
    assert client.get("/api/health").status_code == 200
