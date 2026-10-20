"""B 站排行榜：官方 API /x/web-interface/ranking/v2（2026-10 实测可用，需浏览器 UA）。"""
from __future__ import annotations

import logging

import httpx

from .base import ChartError, ChartProvider, TrendingItem

log = logging.getLogger("vidlib.charts.bilibili")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# rid=0 为全站；分区 id 来自 bilibili-API-collect 文档
CATEGORIES = [
    ("all", "全站"), ("1", "动画"), ("3", "音乐"), ("4", "游戏"), ("5", "娱乐"),
    ("36", "知识"), ("188", "科技"), ("23", "电影"), ("119", "鬼畜"),
]


class BilibiliProvider(ChartProvider):
    name = "bilibili"

    def categories(self) -> list[dict]:
        return [{"id": cid, "name": cname} for cid, cname in CATEGORIES]

    def fetch(self, category: str) -> list[TrendingItem]:
        rid = "0" if category in ("", "all") else category
        try:
            r = httpx.get(
                "https://api.bilibili.com/x/web-interface/ranking/v2",
                params={"rid": rid, "type": "all"},
                headers=HEADERS, timeout=15,
            )
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise ChartError(f"B站排行榜接口请求失败: {e}") from e
        if data.get("code") != 0:
            raise ChartError(f"B站接口返回错误: code={data.get('code')} {data.get('message')}")
        items: list[TrendingItem] = []
        for rank, v in enumerate((data.get("data") or {}).get("list") or [], start=1):
            bvid = v.get("bvid") or ""
            aid = v.get("aid") or ""
            url = f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}"
            stat = v.get("stat") or {}
            items.append(TrendingItem(
                source_id=str(bvid or aid),
                title=str(v.get("title") or ""),
                author=str((v.get("owner") or {}).get("name") or ""),
                url=url,
                cover=str(v.get("pic") or ""),
                duration=float(v.get("duration") or 0),
                views=int(stat.get("view") or 0),
                extra={"rank": rank, "like": int(stat.get("like") or 0),
                       "danmaku": int(stat.get("danmaku") or 0)},
            ))
        return items[:50]
