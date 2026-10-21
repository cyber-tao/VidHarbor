from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings

_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(_engine, "connect")
        def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    return _engine


def get_sessionmaker() -> sessionmaker:
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)
    return SessionLocal


def _migrate(engine: Engine) -> None:
    """轻量幂等迁移：补充旧库缺失的列；charts_cache 结构变更则整体重建（纯缓存，可丢弃）。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "charts_cache" in tables:
        cols = {c["name"] for c in insp.get_columns("charts_cache")}
        if "period" not in cols:
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE charts_cache"))

    if "download_tasks" in tables:
        cols = {c["name"] for c in insp.get_columns("download_tasks")}
        with engine.begin() as conn:
            if "options" not in cols:
                conn.execute(text("ALTER TABLE download_tasks ADD COLUMN options TEXT DEFAULT ''"))
            if "schedule_id" not in cols:
                conn.execute(text(
                    "ALTER TABLE download_tasks ADD COLUMN schedule_id INTEGER"
                ))


def init_db() -> None:
    from .models import Base

    engine = get_engine()
    _migrate(engine)
    Base.metadata.create_all(engine)
