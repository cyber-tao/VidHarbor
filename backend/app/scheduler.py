"""定时下载：APScheduler 驱动；一个任务可组合多个榜单选择（平台×分类×周期×TopN）。

注意：uvicorn 需单 worker 运行（多 worker 会重复触发）；时区取设置 scheduler.timezone。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .charts import provider_for
from .config import get_settings, local_timezone
from .db import get_sessionmaker
from .downloader.engine import TaskQueue, active_task_urls, detect_platform
from .downloader.options import parse_source_id
from .events import bus
from .models import DownloadTask, Schedule, Video, utcnow

log = logging.getLogger("vidharbor.scheduler")

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def make_trigger(row: Schedule):
    tz = local_timezone()
    if row.mode == "interval":
        return IntervalTrigger(minutes=max(1, row.interval_minutes or 60), timezone=tz)
    if row.mode == "cron":
        return CronTrigger.from_crontab(row.cron, timezone=tz)
    hh, mm = (row.at_time or "09:00").split(":", 1)
    dow = "*"
    if row.mode == "weekly":
        try:
            weekdays = sorted(json.loads(row.weekdays or "[]"))
        except Exception:  # noqa: BLE001
            weekdays = [0]
        dow = ",".join(str(d) for d in weekdays) if weekdays else "*"
    return CronTrigger(hour=int(hh), minute=int(mm), day_of_week=dow, timezone=tz)


def describe_trigger(row: Schedule) -> str:
    if row.mode == "interval":
        m = max(1, row.interval_minutes or 60)
        return f"每 {m // 60} 小时" if m >= 60 and m % 60 == 0 else f"每 {m} 分钟"
    if row.mode == "cron":
        return f"cron: {row.cron}"
    try:
        weekdays = sorted(json.loads(row.weekdays or "[]"))
    except Exception:  # noqa: BLE001
        weekdays = []
    days = "/".join(WEEKDAY_NAMES[d] for d in weekdays) if weekdays else "每天"
    return f"{days} {row.at_time}"


def schedule_snapshot(row: Schedule, next_run_at=None) -> dict:
    try:
        selections = json.loads(row.selections or "[]")
    except Exception:  # noqa: BLE001
        selections = []
    try:
        last_result = json.loads(row.last_result) if row.last_result else None
    except Exception:  # noqa: BLE001
        last_result = None
    return {
        "id": row.id, "name": row.name, "enabled": row.enabled,
        "mode": row.mode, "interval_minutes": row.interval_minutes,
        "at_time": row.at_time,
        "weekdays": _safe_weekdays(row.weekdays),
        "cron": row.cron,
        "trigger_desc": describe_trigger(row),
        "selections": selections,
        "options": _safe_options(row.options),
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_result": last_result,
        "next_run_at": next_run_at.isoformat() if next_run_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _safe_weekdays(raw: str) -> list[int]:
    try:
        return sorted({int(d) for d in json.loads(raw or "[]") if 0 <= int(d) <= 6})
    except Exception:  # noqa: BLE001
        return []


def _safe_options(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def register(scheduler: AsyncIOScheduler, row: Schedule, queue: TaskQueue) -> None:
    job_id = f"schedule-{row.id}"
    if not row.enabled:
        job = scheduler.get_job(job_id)
        if job is not None:
            job.remove()
        return
    scheduler.add_job(
        run_schedule, trigger=make_trigger(row), args=[row.id, queue],
        id=job_id, replace_existing=True, max_instances=1, coalesce=True,
        misfire_grace_time=3600,
    )


def register_all(scheduler: AsyncIOScheduler, queue: TaskQueue) -> None:
    sm = get_sessionmaker()
    with sm() as session:
        rows = session.query(Schedule).all()
        for row in rows:
            register(scheduler, row, queue)
    log.info("定时任务已注册: %d 个（启用 %d）",
             len(rows), sum(1 for r in rows if r.enabled))


def start_scheduler(queue: TaskQueue) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=local_timezone())
    scheduler.start()
    register_all(scheduler, queue)
    return scheduler


def run_schedule(schedule_id: int, queue: TaskQueue) -> dict:
    """执行一次定时任务：逐榜单抓取 → TopN → 去重 → 创建下载任务。"""
    sm = get_sessionmaker()
    session = sm()
    try:
        row = session.get(Schedule, schedule_id)
        if row is None:
            return {"created": 0, "skipped": 0, "failed": 0, "error": "定时任务不存在"}
        try:
            selections = json.loads(row.selections or "[]")
        except Exception:  # noqa: BLE001
            selections = []
        opts_json = row.options if (row.options and row.options.strip() not in ("{}", "")) else ""

        total_created, total_skipped, total_failed = 0, 0, 0
        errors: list[str] = []
        per_selection: list[dict] = []
        # 上一轮任务可能尚未下载完成：队列中的 URL 直接跳过，防止重复下载
        active_urls = active_task_urls(session)
        log.info("定时任务「%s」开始: %d 个榜单", row.name, len(selections))
        for sel in selections:
            platform = str(sel.get("platform") or "")
            category = str(sel.get("category") or "")
            period = str(sel.get("period") or "")
            limit = max(1, min(100, int(sel.get("limit") or 10)))
            provider = provider_for(platform)
            error = ""
            items = []
            if provider is None:
                error = "不支持的平台"
            else:
                category, period = provider.normalize(category, period)
                if not provider.is_downloadable(category):
                    # 校验上线前创建的旧任务可能仍带着话题榜
                    error = "榜单条目不可直接下载（话题榜），请改用自定义关键词"
                else:
                    try:
                        items = provider.fetch(category, period)
                    except Exception as e:  # noqa: BLE001
                        error = str(getattr(e, "message", e))[:200]
            if error:
                total_failed += 1
                errors.append(f"{platform}/{category}: {error}")
                per_selection.append({"platform": platform, "category": category,
                                      "period": period, "created": 0, "skipped": 0,
                                      "error": error})
                continue
            created = skipped = 0
            for item in items:
                if not getattr(item, "downloadable", True) or not item.url:
                    continue
                if created + skipped >= limit:
                    break
                if item.url[:1024] in active_urls:
                    skipped += 1
                    continue
                sid = parse_source_id(detect_platform(item.url), item.url) or item.source_id
                exists = False
                if sid:
                    exists = session.query(Video).filter_by(
                        platform=detect_platform(item.url), source_id=str(sid)
                    ).first() is not None
                if exists:
                    skipped += 1
                    continue
                t = DownloadTask(
                    url=item.url[:1024], platform=detect_platform(item.url),
                    schedule_id=row.id, options=opts_json,
                )
                session.add(t)
                session.commit()
                queue.submit(t.id, t.platform)
                active_urls.add(t.url)
                created += 1
            total_created += created
            total_skipped += skipped
            per_selection.append({"platform": platform, "category": category,
                                  "period": period, "created": created, "skipped": skipped})
            log.info("定时任务「%s」%s/%s/%s: 新建 %d，跳过 %d",
                     row.name, platform, category, period, created, skipped)

        result = {
            "at": utcnow().isoformat(), "created": total_created,
            "skipped": total_skipped, "failed": total_failed,
            "errors": errors[:10], "selections": per_selection,
        }
        row.last_run_at = utcnow()
        row.last_result = json.dumps(result, ensure_ascii=False)
        session.commit()
        bus.mark_stats_dirty()
        log.info("定时任务「%s」完成: 新建 %d / 跳过 %d / 失败 %d",
                 row.name, total_created, total_skipped, total_failed)
        return result
    finally:
        session.close()
