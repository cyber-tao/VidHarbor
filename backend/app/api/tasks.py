"""任务 API：创建（含批量）、列表、取消/删除、重试。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import get_sessionmaker
from ..downloader.engine import detect_platform, task_snapshot
from ..events import bus
from ..models import DownloadTask

log = logging.getLogger("vidlib.api.tasks")
router = APIRouter()


class CreateTasksReq(BaseModel):
    urls: list[str] = Field(default_factory=list)


@router.post("/api/tasks")
def create_tasks(req: CreateTasksReq, request: Request):
    urls: list[str] = []
    seen: set[str] = set()
    for u in req.urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    if not urls:
        raise HTTPException(status_code=400, detail="没有可下载的 URL")
    if len(urls) > 200:
        raise HTTPException(status_code=400, detail="单次最多 200 条 URL")

    sm = get_sessionmaker()
    queue = request.app.state.queue
    with sm() as session:
        tasks = []
        for u in urls:
            t = DownloadTask(url=u[:1024], platform=detect_platform(u))
            session.add(t)
            tasks.append(t)
        session.commit()
        for t in tasks:
            queue.submit(t.id)
        snapshots = [task_snapshot(t) for t in tasks]
    log.info("创建 %d 个下载任务", len(snapshots))
    return {"tasks": snapshots}


@router.get("/api/tasks")
def list_tasks(limit: int = 200):
    if limit < 1 or limit > 1000:
        limit = 200
    sm = get_sessionmaker()
    with sm() as session:
        rows = (
            session.query(DownloadTask)
            .order_by(DownloadTask.id.desc())
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
        t = DownloadTask(url=old.url, platform=old.platform)
        session.add(t)
        session.commit()
    request.app.state.queue.submit(t.id)
    return {"task": task_snapshot(t)}
