"""VidHarbor 应用入口：uvicorn app.main:app"""
from __future__ import annotations

import asyncio
import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api import access, auth, charts, events, schedules, settings as settings_api, stats, tasks, videos
from .config import PLATFORMS, ensure_dirs, get_settings
from .db import init_db
from .downloader.engine import TaskQueue, evil0ctal_health
from .events import bus
from .logging_setup import setup_logging
from .scheduler import start_scheduler

setup_logging()
log = logging.getLogger("vidharbor.main")
settings = get_settings()


def _startup_checks() -> None:
    """启动自检：缺失依赖与关键配置只在日志里提示，不阻止启动。"""
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        log.warning("未找到 %s —— 视频探测/转码不可用，请先安装 ffmpeg", ", ".join(missing))
    else:
        log.info("ffmpeg/ffprobe 就绪")
    if settings.cookies_path:
        log.info("已启用全局 cookies 文件: %s", settings.cookies_path)
    platform_cookies = [p for p in PLATFORMS if settings.cookie_file_for(p)]
    if platform_cookies:
        log.info("已配置平台 cookies: %s（设置页可管理）", ", ".join(platform_cookies))
    elif not settings.cookies_path:
        log.info("未配置 cookies —— YouTube 高清 / B站 1080P+ / TikTok 榜单可能受限（设置页可扫码/导入）")
    if settings.evil0ctal.enabled:
        if evil0ctal_health(settings):
            log.info("Evil0ctal 兜底服务在线: %s", settings.evil0ctal.base_url)
        else:
            log.warning(
                "Evil0ctal 兜底服务不可达: %s —— 抖音/TikTok 任务失败时无法自动兜底（部署方法见 README）",
                settings.evil0ctal.base_url,
            )
    if not settings.frontend_dist.exists():
        log.warning("前端尚未构建（%s 不存在）：仅 API 可用，构建方法见 README", settings.frontend_dist)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs(settings)
    init_db()
    _startup_checks()
    bus.bind_loop(asyncio.get_running_loop())
    queue = TaskQueue(settings)
    app.state.queue = queue
    queue.start()
    from .downloader.postprocess import set_transcode_limit

    set_transcode_limit(settings.library.transcode_concurrency)
    scheduler = start_scheduler(queue)
    app.state.scheduler = scheduler
    log.info(
        "VidHarbor 就绪: 视频库=%s 数据库=%s",
        settings.library_root, settings.db_path,
    )
    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:  # noqa: BLE001
        pass
    await asyncio.to_thread(queue.stop)


app = FastAPI(title="VidHarbor", version="0.2.0", lifespan=lifespan)

for r in (tasks.router, videos.router, charts.router, stats.router, events.router,
          settings_api.router, auth.router, schedules.router):
    app.include_router(r, dependencies=[Depends(access.require_token)])
# 换取会话的接口本身不能要求已登录
app.include_router(access.router)


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.2.0"}


# 前端静态托管（构建产物存在时）；SPA 路由回退到 index.html
_dist = settings.frontend_dist
if _dist.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            # 未知 API 路径不能回退到 index.html：前端 fetch 会把 HTML 当 JSON 解析报错
            raise HTTPException(status_code=404, detail=f"未知的 API 路径: /{full_path}")
        if full_path:
            candidate = (_dist / full_path).resolve()
            try:
                candidate.relative_to(_dist.resolve())
            except ValueError:
                return FileResponse(_dist / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
