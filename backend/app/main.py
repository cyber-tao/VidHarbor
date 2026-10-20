"""vidlib 应用入口：uvicorn app.main:app"""
from __future__ import annotations

import asyncio
import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .api import charts, events, stats, tasks, videos
from .config import ensure_dirs, get_settings
from .db import init_db
from .downloader.engine import TaskQueue, evil0ctal_health
from .events import bus
from .logging_setup import setup_logging

setup_logging()
log = logging.getLogger("vidlib.main")
settings = get_settings()


def _startup_checks() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        log.warning("未找到 %s —— 视频探测/转码不可用，请先安装 ffmpeg", ", ".join(missing))
    else:
        log.info("ffmpeg/ffprobe 就绪")
    if settings.cookies_path:
        log.info("已启用 cookies 文件: %s", settings.cookies_path)
    else:
        log.info("未配置 cookies.txt —— YouTube 高清 / B站 1080P+ / TikTok 榜单可能受限（见 README）")
    if settings.evil0ctal.enabled:
        if evil0ctal_health(settings):
            log.info("Evil0ctal 抖音兜底服务在线: %s", settings.evil0ctal.base_url)
        else:
            log.warning(
                "Evil0ctal 兜底服务不可达: %s —— 抖音下载失败时无法自动兜底（部署方法见 README）",
                settings.evil0ctal.base_url,
            )
    if not settings.frontend_dist.exists():
        log.warning("前端尚未构建（%s 不存在）：仅 API 可用，构建方法见 README", settings.frontend_dist)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs(settings)
    init_db()
    bus.bind_loop(asyncio.get_running_loop())
    queue = TaskQueue(settings)
    app.state.queue = queue
    queue.start()
    log.info(
        "vidlib 就绪: 视频库=%s 数据库=%s",
        settings.library_root, settings.db_path,
    )
    yield
    queue.stop()


app = FastAPI(title="vidlib", version="0.1.0", lifespan=lifespan)

for r in (tasks.router, videos.router, charts.router, stats.router, events.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.1.0"}


# 前端静态托管（构建产物存在时）；SPA 路由回退到 index.html
_dist = settings.frontend_dist
if _dist.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path:
            candidate = (_dist / full_path).resolve()
            try:
                candidate.relative_to(_dist.resolve())
            except ValueError:
                return FileResponse(_dist / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
