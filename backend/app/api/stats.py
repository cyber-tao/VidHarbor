"""Dashboard 统计 API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func

from ..config import local_timezone
from ..db import get_sessionmaker
from ..downloader.engine import task_snapshot
from ..models import DownloadTask, Video

router = APIRouter()


@router.get("/api/stats")
def stats():
    sm = get_sessionmaker()
    # “今日”边界用展示时区（scheduler.timezone）的本地日；DB 中存的是 naive UTC
    tz = local_timezone()
    now_local = datetime.now(tz)
    today_start = (
        now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc).replace(tzinfo=None)
    )
    with sm() as session:
        total = session.query(func.count(Video.id)).scalar() or 0
        total_size = session.query(func.coalesce(func.sum(Video.file_size), 0)).scalar() or 0
        today_count = (
            session.query(func.count(Video.id))
            .filter(Video.created_at >= today_start)
            .scalar() or 0
        )

        by_platform: dict[str, dict] = {}
        rows = (
            session.query(
                Video.platform,
                func.count(Video.id),
                func.coalesce(func.sum(Video.file_size), 0),
            )
            .group_by(Video.platform)
            .all()
        )
        for platform, cnt, size in rows:
            by_platform[platform] = {"count": cnt, "size": size}

        since14_local = (now_local - timedelta(days=13)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        since14 = since14_local.astimezone(timezone.utc).replace(tzinfo=None)
        date_rows = (
            session.query(Video.created_at)
            .filter(Video.created_at >= since14)
            .all()
        )
        counter: dict[str, int] = {}
        for (created_at,) in date_rows:
            if created_at is None:
                continue
            key = created_at.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%Y-%m-%d")
            counter[key] = counter.get(key, 0) + 1
        last14 = []
        for i in range(13, -1, -1):
            key = (now_local - timedelta(days=i)).strftime("%Y-%m-%d")
            last14.append({"date": key, "count": counter.get(key, 0)})

        task_counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "canceled": 0}
        for status, cnt in session.query(DownloadTask.status, func.count(DownloadTask.id)) \
                .group_by(DownloadTask.status).all():
            if status in task_counts:
                task_counts[status] = cnt

        recent_tasks = (
            session.query(DownloadTask)
            .order_by(DownloadTask.id.desc())
            .limit(8)
            .all()
        )

        return {
            "videos": {
                "total": total,
                "total_size": int(total_size),
                "today": today_count,
                "by_platform": by_platform,
                "last14": last14,
            },
            "tasks": task_counts,
            "recent_tasks": [task_snapshot(t) for t in recent_tasks],
        }
