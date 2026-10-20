"""SSE 事件流：task 进度 / 日志 / 统计刷新信号。连接时先回放最近日志与任务快照。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from ..db import get_sessionmaker
from ..downloader.engine import task_snapshot
from ..events import bus
from ..models import DownloadTask

router = APIRouter()


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _tasks_snapshot(limit: int = 50) -> list[dict]:
    sm = get_sessionmaker()
    with sm() as session:
        rows = (
            session.query(DownloadTask)
            .order_by(DownloadTask.id.desc())
            .limit(limit)
            .all()
        )
        return [task_snapshot(t) for t in rows]


@router.get("/api/events")
async def event_stream():
    q = bus.subscribe()

    async def gen():
        try:
            yield _sse("hello", {"ok": True})
            for entry in list(bus.logs)[-200:]:
                yield _sse("log", entry["data"])
            tasks = await run_in_threadpool(_tasks_snapshot)
            yield _sse("tasks", tasks)
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except (asyncio.TimeoutError, TimeoutError):
                    yield ": ping\n\n"
                    continue
                if event["type"] == "stats_dirty":
                    yield _sse("stats_dirty", None)
                else:
                    yield _sse(event["type"], event["data"])
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
