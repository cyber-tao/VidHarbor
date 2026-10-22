"""榜单 API：分类+时间段 → TTL 缓存 + 失败降级（返回 degraded + message 而非 5xx）。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from ..charts import provider_for
from ..charts.base import ChartError
from ..db import get_sessionmaker
from ..models import ChartCache, utcnow

log = logging.getLogger("vidharbor.api.charts")
router = APIRouter()

TTL_SECONDS = 1800


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@router.get("/api/charts")
def list_platforms():
    return {"platforms": [
        {"id": "bilibili", "name": "哔哩哔哩"},
        {"id": "youtube", "name": "YouTube"},
        {"id": "tiktok", "name": "TikTok"},
        {"id": "douyin", "name": "抖音"},
    ]}


@router.get("/api/charts/{platform}")
def get_charts(platform: str, category: str = "", period: str = "", refresh: bool = False,
               meta: bool = False):
    provider = provider_for(platform)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")
    categories = provider.categories()
    if meta:
        return {"platform": platform, "categories": categories}
    category, period = provider.normalize(category, period)

    sm = get_sessionmaker()
    with sm() as session:
        cached = (
            session.query(ChartCache)
            .filter_by(platform=platform, category=category, period=period)
            .first()
        )
        fresh = (
            cached is not None
            and cached.fetched_at is not None
            and datetime.now(timezone.utc) - _as_utc(cached.fetched_at) < timedelta(seconds=TTL_SECONDS)
            and cached.payload
        )
        if fresh and not refresh:
            return {
                "platform": platform, "category": category, "period": period,
                "categories": categories,
                "fetched_at": cached.fetched_at.isoformat(),
                "cached": True, "degraded": False, "message": "",
                "items": json.loads(cached.payload),
            }

        try:
            items = [i.to_dict() for i in provider.fetch(category, period)]
            payload = json.dumps(items, ensure_ascii=False)
            now = utcnow()
            if cached is not None:
                cached.payload = payload
                cached.fetched_at = now
            else:
                session.add(ChartCache(platform=platform, category=category, period=period,
                                       payload=payload, fetched_at=now))
            session.commit()
            log.info("榜单刷新: %s/%s/%s (%d 条)", platform, category, period, len(items))
            return {
                "platform": platform, "category": category, "period": period,
                "categories": categories,
                "fetched_at": now.isoformat(), "cached": False,
                "degraded": False, "message": "", "items": items,
            }
        except ChartError as e:
            log.warning("榜单 %s/%s/%s 获取失败: %s", platform, category, period, e.message)
            if cached is not None and cached.payload:
                return {
                    "platform": platform, "category": category, "period": period,
                    "categories": categories,
                    "fetched_at": cached.fetched_at.isoformat(),
                    "cached": True, "degraded": True,
                    "message": f"{e.message}（展示缓存数据）",
                    "items": json.loads(cached.payload),
                }
            return {
                "platform": platform, "category": category, "period": period,
                "categories": categories,
                "fetched_at": None, "cached": False, "degraded": True,
                "message": e.message, "items": [],
            }
        except Exception as e:  # noqa: BLE001
            log.exception("榜单 %s/%s/%s 异常", platform, category, period)
            raise HTTPException(status_code=500, detail=f"榜单获取异常: {e}") from e
