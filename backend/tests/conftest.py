"""会话级测试环境隔离。

API/并发测试通过 TestClient 触发真实 lifespan，若无隔离会直接读写部署机的
data/vidharbor.db 与 library/。这里把 config.PROJECT_ROOT 与用户主目录指向
临时目录并重置 DB 引擎与设置缓存，保证 pytest 不触碰真实数据
（test_env_config 的 per-test 隔离 fixture 在此基础上继续生效）。
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_project_root(tmp_path_factory):
    from app import config, db

    saved = (config.PROJECT_ROOT, db._engine, db.SessionLocal, config.Path.home)
    # ~/.vidharbor/config.toml 是文档支持的可选配置位置，必须一并隔离
    fake_home = tmp_path_factory.mktemp("vidharbor-home")
    config.Path.home = classmethod(lambda cls: fake_home)

    root = tmp_path_factory.mktemp("vidharbor-root")
    (root / "data").mkdir()
    config.PROJECT_ROOT = root
    config.invalidate_settings_cache()

    yield root

    config.PROJECT_ROOT, db._engine, db.SessionLocal, config.Path.home = saved
    config.invalidate_settings_cache()
    config._resolve_db_filename.cache_clear()
