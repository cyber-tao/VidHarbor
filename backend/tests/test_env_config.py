"""配置环境变量覆盖：VIDHARBOR_<section>__<field>，优先级 config.toml < 环境变量 < DB 设置页。"""
import sqlite3

import pytest

from app import config


@pytest.fixture(autouse=True)
def _fresh_settings():
    config.invalidate_settings_cache()
    yield
    config.invalidate_settings_cache()


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    """把 PROJECT_ROOT / home 指向空目录：排除本机 config.toml 与 data/vidharbor.db 干扰。"""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_defaults_without_env(isolated_root):
    s = config.get_settings()
    assert s.evil0ctal.base_url == "http://127.0.0.1:8000"
    assert s.download.max_height == 1080


def test_env_overrides_section_field(isolated_root, monkeypatch):
    monkeypatch.setenv("VIDHARBOR_EVIL0CTAL__BASE_URL", "http://api:8000")
    monkeypatch.setenv("VIDHARBOR_EVIL0CTAL__API_KEY", "dtk_ab_cd")
    s = config.get_settings()
    assert s.evil0ctal.base_url == "http://api:8000"
    assert s.evil0ctal.api_key == "dtk_ab_cd"


def test_env_values_are_coerced(isolated_root, monkeypatch):
    monkeypatch.setenv("VIDHARBOR_EVIL0CTAL__ENABLED", "false")
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__MAX_HEIGHT", "2160")
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__SUB_LANGS", '["ja.*"]')
    monkeypatch.setenv("VIDHARBOR_YOUTUBE__REGION_CODE", "JP")
    s = config.get_settings()
    assert s.evil0ctal.enabled is False
    assert s.download.max_height == 2160
    assert s.download.sub_langs == ["ja.*"]
    assert s.youtube.region_code == "JP"


def test_env_without_double_underscore_is_ignored(isolated_root, monkeypatch):
    monkeypatch.setenv("VIDHARBOR_EVIL0CTAL_BASE_URL", "http://ignored:8000")
    s = config.get_settings()
    assert s.evil0ctal.base_url == "http://127.0.0.1:8000"


def test_db_settings_take_priority_over_env(isolated_root, monkeypatch):
    db = isolated_root / "data" / "vidharbor.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE app_settings (id INTEGER PRIMARY KEY, data TEXT)"
    )
    conn.execute(
        'INSERT INTO app_settings (id, data) VALUES (1, '
        '\'{"evil0ctal": {"base_url": "http://db-wins:8000"}}\')'
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("VIDHARBOR_EVIL0CTAL__BASE_URL", "http://env:8000")
    s = config.get_settings()
    assert s.evil0ctal.base_url == "http://db-wins:8000"


def test_proxy_defaults(isolated_root):
    s = config.get_settings()
    assert s.download.proxy == ""
    assert s.download.proxy_platforms == []
    assert s.proxy_for("youtube") == ""


def test_proxy_for_matches_configured_platforms(isolated_root, monkeypatch):
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS", '["youtube","tiktok"]')
    s = config.get_settings()
    assert s.proxy_for("youtube") == "http://127.0.0.1:7890"
    assert s.proxy_for("tiktok") == "http://127.0.0.1:7890"
    assert s.proxy_for("bilibili") == ""
    assert s.proxy_for("douyin") == ""


def test_empty_env_values_do_not_override(isolated_root, monkeypatch):
    # compose 注入 ${VAR:-} 时为空串：跳过而非把 list 字段覆盖成字符串
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY", "")
    monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS", "")
    s = config.get_settings()
    assert s.download.proxy == ""
    assert s.download.proxy_platforms == []
