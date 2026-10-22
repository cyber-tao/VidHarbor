"""定时任务 API：CRUD、启停、立即运行；next_run_at 来自调度器。"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..charts import provider_for
from ..config import PLATFORMS
from ..db import get_sessionmaker
from ..models import Schedule
from ..scheduler import (
    claim_run,
    make_trigger,
    register,
    release_run,
    run_claimed_schedule,
    schedule_snapshot,
)

log = logging.getLogger("vidharbor.api.schedules")
router = APIRouter()

VALID_MODES = ("interval", "daily", "weekly", "cron")


class SelectionIn(BaseModel):
    platform: str
    category: str = ""
    period: str = ""
    limit: int = Field(default=10, ge=1, le=100)


class ScheduleIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # None = 编辑时保持原启停状态（启停走 /toggle）；新建默认启用
    enabled: bool | None = None
    mode: str = "daily"
    interval_minutes: int = Field(default=0, ge=0, le=525600)
    at_time: str = "09:00"
    weekdays: list[int] = Field(default_factory=list)
    cron: str = ""
    selections: list[SelectionIn] = Field(min_length=1)
    options: dict = Field(default_factory=dict)


def _validate(req: ScheduleIn) -> None:
    if req.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"无效触发模式: {req.mode}")
    for sel in req.selections:
        if sel.platform not in PLATFORMS:
            raise HTTPException(status_code=400, detail=f"不支持的平台: {sel.platform}")
        provider = provider_for(sel.platform)
        if provider is not None and not provider.is_downloadable(sel.category):
            raise HTTPException(
                status_code=400,
                detail=f"{sel.platform} 的「{sel.category or '默认'}」榜单条目不可直接下载"
                       "（如抖音热搜为话题榜），请改用自定义关键词",
            )
    if req.mode == "interval" and req.interval_minutes < 1:
        raise HTTPException(status_code=400, detail="interval 模式需要 interval_minutes ≥ 1")
    if req.mode in ("daily", "weekly"):
        try:
            hh, mm = req.at_time.split(":")
            assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="at_time 需为 HH:MM") from e
    if req.mode == "weekly":
        if not req.weekdays or any(d < 0 or d > 6 for d in req.weekdays):
            raise HTTPException(status_code=400, detail="weekly 模式需要 0-6 的星期列表（0=周一）")
    if req.mode == "cron":
        try:
            from apscheduler.triggers.cron import CronTrigger
            CronTrigger.from_crontab(req.cron)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"无效 cron 表达式: {e}") from e


def _apply(row: Schedule, req: ScheduleIn) -> None:
    row.name = req.name.strip()
    if req.enabled is not None:
        row.enabled = req.enabled
    row.mode = req.mode
    row.interval_minutes = req.interval_minutes
    row.at_time = req.at_time
    row.weekdays = json.dumps(sorted(set(req.weekdays)))
    row.cron = req.cron
    row.selections = json.dumps([s.model_dump() for s in req.selections], ensure_ascii=False)
    row.options = json.dumps(req.options or {}, ensure_ascii=False)


def _snap_with_next(request: Request, row: Schedule) -> dict:
    next_at = None
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        job = scheduler.get_job(f"schedule-{row.id}")
        if job is not None and job.next_run_time is not None:
            next_at = job.next_run_time
    return schedule_snapshot(row, next_at)


@router.get("/api/schedules")
def list_schedules(request: Request):
    sm = get_sessionmaker()
    with sm() as session:
        rows = session.query(Schedule).order_by(Schedule.id.desc()).all()
        return {"schedules": [_snap_with_next(request, r) for r in rows]}


@router.post("/api/schedules")
def create_schedule(req: ScheduleIn, request: Request):
    _validate(req)
    sm = get_sessionmaker()
    with sm() as session:
        row = Schedule(enabled=True)
        _apply(row, req)
        session.add(row)
        session.commit()
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is not None:
            register(scheduler, row, request.app.state.queue)
        return {"schedule": _snap_with_next(request, row)}


@router.put("/api/schedules/{schedule_id}")
def update_schedule(schedule_id: int, req: ScheduleIn, request: Request):
    _validate(req)
    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(Schedule, schedule_id)
        if row is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        _apply(row, req)
        session.commit()
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is not None:
            register(scheduler, row, request.app.state.queue)
        return {"schedule": _snap_with_next(request, row)}


@router.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, request: Request):
    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(Schedule, schedule_id)
        if row is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        session.delete(row)
        session.commit()
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        job = scheduler.get_job(f"schedule-{schedule_id}")
        if job is not None:
            job.remove()
    return {"deleted": True}


@router.post("/api/schedules/{schedule_id}/toggle")
def toggle_schedule(schedule_id: int, request: Request):
    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(Schedule, schedule_id)
        if row is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        row.enabled = not row.enabled
        session.commit()
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is not None:
            register(scheduler, row, request.app.state.queue)
        return {"schedule": _snap_with_next(request, row)}


@router.post("/api/schedules/{schedule_id}/run")
async def run_schedule_now(schedule_id: int, request: Request):
    """立即运行一次（后台线程执行，立即返回）；本轮或定时触发的一轮尚未结束时返回 409。"""
    import asyncio

    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(Schedule, schedule_id)
        if row is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        name = row.name
    if not claim_run(schedule_id):
        raise HTTPException(status_code=409, detail=f"「{name}」正在运行中，请等本轮结束后再试")
    queue = request.app.state.queue

    def _run() -> dict:
        try:
            return run_claimed_schedule(schedule_id, queue)
        finally:
            release_run(schedule_id)

    future = asyncio.get_running_loop().run_in_executor(None, _run)

    def _log_failure(f) -> None:
        exc = f.exception()
        if exc is not None:
            log.error("定时任务 #%d「%s」后台执行异常: %s", schedule_id, name, exc)

    future.add_done_callback(_log_failure)
    log.info("手动触发定时任务「%s」(#%d)", name, schedule_id)
    return {"ok": True, "message": f"「{name}」已开始后台运行，结果见列表与日志"}
