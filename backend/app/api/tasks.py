"""任务 API：创建（含批量+下载选项）、列表、取消/删除、重试。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import get_sessionmaker
from ..downloader.engine import detect_platform, task_snapshot
from ..downloader.urlnorm import normalize_inputs
from ..events import bus
from ..models import DownloadTask

log = logging.getLogger("vidharbor.api.tasks")
router = APIRouter()


class TaskOptionsIn(BaseModel):
    max_height: int | None = Field(default=None, ge=0, le=4320)
    audio_langs: list[str] | None = None
    sub_langs: list[str] | None = None
    codec: str | None = None


class CreateTasksReq(BaseModel):
    urls: list[str] = Field(default_factory=list)
    options: TaskOptionsIn | None = None


@router.post("/api/tasks")
def create_tasks(req: CreateTasksReq, request: Request):
    # 分享文案提取 URL + 短链展开（v.douyin.com / vm.tiktok.com 等）
    urls: list[str] = normalize_inputs(req.urls)
    if not urls:
        raise HTTPException(status_code=400, detail="没有可下载的 URL")
    if len(urls) > 200:
        raise HTTPException(status_code=400, detail="单次最多 200 条 URL")

    options_json = ""
    if req.options is not None:
        data = req.options.model_dump(exclude_none=True)
        if data:
            import json
            options_json = json.dumps(data, ensure_ascii=False)

    sm = get_sessionmaker()
    queue = request.app.state.queue
    with sm() as session:
        tasks = []
        for u in urls:
            t = DownloadTask(url=u[:1024], platform=detect_platform(u), options=options_json)
            session.add(t)
            tasks.append(t)
        session.commit()
        for t in tasks:
            queue.submit(t.id, t.platform)
        snapshots = [task_snapshot(t) for t in tasks]
    log.info("创建 %d 个下载任务", len(snapshots))
    return {"tasks": snapshots}


@router.get("/api/tasks")
def list_tasks(limit: int = 200, schedule_id: int = 0):
    if limit < 1 or limit > 1000:
        limit = 200
    sm = get_sessionmaker()
    with sm() as session:
        query = session.query(DownloadTask)
        if schedule_id:
            query = query.filter(DownloadTask.schedule_id == schedule_id)
        rows = (
            query.order_by(DownloadTask.id.desc())
            .limit(limit)
            .all()
        )
        return {"tasks": [task_snapshot(t) for t in rows]}


@router.delete("/api/tasks/{task_id}")
def cancel_task(task_id: int, request: Request):
    queue = request.app.state.queue
    sm = get_sessionmaker()
    with sm() as session:
        t = session.get(DownloadTask, task_id)
        if t is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        if t.status in ("pending", "running"):
            queue.cancel(task_id)
            if t.status == "pending":
                t.status = "canceled"
                session.commit()
                bus.publish("task", task_snapshot(t))
            return {"canceled": True}
        session.delete(t)
        session.commit()
        return {"deleted": True}


@router.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: int, request: Request):
    sm = get_sessionmaker()
    with sm() as session:
        old = session.get(DownloadTask, task_id)
        if old is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        t = DownloadTask(url=old.url, platform=old.platform,
                         options=old.options, schedule_id=old.schedule_id)
        session.add(t)
        session.commit()
    request.app.state.queue.submit(t.id, t.platform)
    return {"task": task_snapshot(t)}
