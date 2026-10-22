"""VidHarbor 应用入口：uvicorn app.main:app"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from .api import auth, charts, events, schedules, settings as settings_api, stats, tasks, videos
from .config import ensure_dirs, get_settings
from .db import init_db
from .downloader.engine import TaskQueue, evil0ctal_health
from .events import bus
from .logging_setup import setup_logging
from .scheduler import start_scheduler

setup_logging()
log = logging.getLogger("vidharbor.main")
settings = get_settings()


def _startup_checks() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        log.warning("未找到 %s —— 视频探测/转码不可用，请先安装 ffmpeg", ", ".join(missing))
    else:
        log.info("ffmpeg/ffprobe 就绪")
    if settings.cookies_path:
        log.info("已启用全局 cookies 文件: %s", settings.cookies_path)
    platform_cookies = [p for p in ("bilibili", "youtube", "tiktok", "douyin")
                        if settings.cookie_file_for(p)]
    if platform_cookies:
        log.info("已配置平台 cookies: %s（设置页可管理）", ", ".join(platform_cookies))
    elif not settings.cookies_path:
        log.info("未配置 cookies —— YouTube 高清 / B站 1080P+ / TikTok 榜单可能受限（设置页可扫码/导入）")
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
    queue.stop()


app = FastAPI(title="VidHarbor", version="0.2.0", lifespan=lifespan)

# 可选访问令牌：设置 VIDHARBOR_TOKEN 环境变量后，除 /api/health 外的所有
# API 需携带令牌（X-Vidharbor-Token 头或 ?token= 查询参数，后者供 SSE/媒体标签用）。
# 不配置时行为不变（本机部署默认）。不进 Settings/DB，避免被设置页回显或覆盖。
_AUTH_TOKEN = os.environ.get("VIDHARBOR_TOKEN", "").strip()


async def _require_token(request: Request) -> None:
    if not _AUTH_TOKEN:
        return
    supplied = request.headers.get("X-Vidharbor-Token") or request.query_params.get("token", "")
    # 按字节比较：compare_digest 对含非 ASCII 字符的 str 会抛 TypeError（变成 500）
    if not secrets.compare_digest(_AUTH_TOKEN.encode(), supplied.encode()):
        raise HTTPException(status_code=401, detail="缺少或无效的访问令牌")


for r in (tasks.router, videos.router, charts.router, stats.router, events.router,
          settings_api.router, auth.router, schedules.router):
    app.include_router(r, dependencies=[Depends(_require_token)])


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
