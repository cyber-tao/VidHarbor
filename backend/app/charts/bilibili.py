"""B 站排行榜（2026-10 实测）：

- 全站/分区综合榜: /x/web-interface/ranking/v2（动态综合，无时间参数）
- 分区三日榜/周榜: /x/web-interface/ranking/region?rid=&day=3|7（day=1/30 已失效）
- 每周必看: /x/web-interface/popular/series/*（需登录 cookies）
- 入站必刷: /x/web-interface/popular/precious
"""
from __future__ import annotations

import logging

import httpx

from ..auth import cookies as cookies_mod
from ..config import Settings
from .base import ChartError, ChartProvider, TrendingItem, fmt_published

log = logging.getLogger("vidharbor.charts.bilibili")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

DEFAULT_PERIODS = [{"id": "default", "name": "综合"}]
REGION_PERIODS = [
    {"id": "default", "name": "综合"},
    {"id": "3d", "name": "三日榜"},
    {"id": "week", "name": "周榜"},
]

# rid=0 为全站；分区 id 来自 bilibili-API-collect 文档
REGIONS = [
    ("all", "全站"), ("1", "动画"), ("3", "音乐"), ("4", "游戏"), ("5", "娱乐"),
    ("36", "知识"), ("188", "科技"), ("23", "电影"), ("119", "鬼畜"),
]


def _api(url: str, params: dict, cookie: str = "", proxy: str = "") -> dict:
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=15, proxy=proxy or None)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise ChartError(f"B站接口请求失败: {e}") from e
    if data.get("code") == -352:
        raise ChartError("B站接口风控(-352)：请在「设置 → 登录管理」扫码登录后刷新重试")
    if data.get("code") != 0:
        raise ChartError(f"B站接口返回错误: code={data.get('code')} {data.get('message')}")
    return data.get("data") or {}


def _item_from_v2(rank: int, v: dict) -> TrendingItem:
    bvid = v.get("bvid") or ""
    aid = v.get("aid") or ""
    url = f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}"
    stat = v.get("stat") or {}
    return TrendingItem(
        source_id=str(bvid or aid),
        title=str(v.get("title") or ""),
        author=str((v.get("owner") or {}).get("name") or ""),
        url=url,
        cover=str(v.get("pic") or ""),
        duration=float(v.get("duration") or 0),
        views=int(stat.get("view") or 0),
        likes=int(stat.get("like") or 0),
        published=fmt_published(v.get("pubdate")),
        extra={"rank": rank, "danmaku": int(stat.get("danmaku") or 0)},
    )


def _parse_duration(raw) -> float:
    """region 接口 duration 形如 "29:58"（MM:SS）/ "1:02:03"（HH:MM:SS），v2 为秒数。"""
    if isinstance(raw, (int, float)):
        return float(raw or 0)
    s = str(raw or "").strip()
    if not s:
        return 0.0
    parts = s.split(":")
    try:
        secs = 0.0
        for p in parts:
            secs = secs * 60 + float(p)
        return secs
    except ValueError:
        return 0.0


def _item_from_region(rank: int, v: dict) -> TrendingItem:
    """region 接口字段与 v2 不同：name=标题 author=UP play=播放 duration="MM:SS"。"""
    bvid = v.get("bvid") or ""
    aid = v.get("aid") or ""
    url = f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}"
    return TrendingItem(
        source_id=str(bvid or aid),
        title=str(v.get("name") or v.get("title") or ""),
        author=str(v.get("author") or ""),
        url=url,
        cover=str(v.get("pic") or ""),
        duration=_parse_duration(v.get("duration")),
        views=int(v.get("play") or (v.get("stat") or {}).get("view") or 0),
        extra={"rank": rank},
    )


def _item_from_popular(rank: int, v: dict) -> TrendingItem:
    bvid = v.get("bvid") or ""
    aid = v.get("aid") or ""
    stat = v.get("stat") or {}
    return TrendingItem(
        source_id=str(bvid or aid),
        title=str(v.get("title") or ""),
        author=str((v.get("owner") or {}).get("name") or ""),
        url=f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}",
        cover=str(v.get("pic") or ""),
        duration=float(v.get("duration") or 0),
        views=int(stat.get("view") or 0),
        likes=int(stat.get("like") or 0),
        published=fmt_published(v.get("pubdate")),
        extra={"rank": rank},
    )


class BilibiliProvider(ChartProvider):
    name = "bilibili"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        out = []
        for cid, cname in REGIONS:
            periods = DEFAULT_PERIODS if cid == "all" else REGION_PERIODS
            out.append({"id": cid, "name": cname, "periods": periods, "allow_custom": False})
        out.append({"id": "weekly", "name": "每周必看", "periods": DEFAULT_PERIODS, "allow_custom": False})
        out.append({"id": "precious", "name": "入站必刷", "periods": DEFAULT_PERIODS, "allow_custom": False})
        return out

    def fetch(self, category: str, period: str = "") -> list[TrendingItem]:
        rid = "0" if category in ("", "all") else category
        # 全部接口都带登录 cookies：既满足「每周必看」，也缓解游客请求的 -352 风控
        cookie = (cookies_mod.cookie_header(cookies_mod.cookie_jar(self.settings, "bilibili"))
                  if self.settings else "")
        proxy = self.settings.proxy_for("bilibili") if self.settings else ""

        if category == "weekly":
            return self._fetch_weekly(cookie, proxy)
        if category == "precious":
            return self._fetch_precious(cookie, proxy)
        if period in ("3d", "week") and rid != "0":
            return self._fetch_region(rid, period, cookie, proxy)

        data = _api(
            "https://api.bilibili.com/x/web-interface/ranking/v2",
            params={"rid": rid, "type": "all"}, cookie=cookie, proxy=proxy,
        )
        items = [
            _item_from_v2(rank, v)
            for rank, v in enumerate(data.get("list") or [], start=1)
        ]
        return items[:50]

    def _fetch_region(self, rid: str, period: str, cookie: str = "", proxy: str = "") -> list[TrendingItem]:
        data = _api(
            "https://api.bilibili.com/x/web-interface/ranking/region",
            params={"rid": rid, "day": "3" if period == "3d" else "7",
                    "original": "0", "web_location": "333.934"},
            cookie=cookie, proxy=proxy,
        )
        lst = data.get("list") if isinstance(data, dict) else data
        if not isinstance(lst, list):
            lst = data.get("list") or [] if isinstance(data, dict) else []
        items = [_item_from_region(rank, v) for rank, v in enumerate(lst or [], start=1)]
        return items[:50]

    def _fetch_weekly(self, cookie: str = "", proxy: str = "") -> list[TrendingItem]:
        if not cookie:
            raise ChartError("「每周必看」需要 B站登录：请在「设置 → 登录管理」扫码登录")
        series = _api(
            "https://api.bilibili.com/x/web-interface/popular/series/list",
            params={}, cookie=cookie, proxy=proxy,
        )
        lists = series.get("list") or []
        if not lists:
            raise ChartError("「每周必看」接口返回为空")
        number = int(lists[0].get("number") or 0)
        data = _api(
            "https://api.bilibili.com/x/web-interface/popular/series/one",
            params={"number": number}, cookie=cookie, proxy=proxy,
        )
        items = [
            _item_from_popular(rank, v)
            for rank, v in enumerate(data.get("list") or [], start=1)
        ]
        return items[:50]

    def _fetch_precious(self, cookie: str = "", proxy: str = "") -> list[TrendingItem]:
        data = _api(
            "https://api.bilibili.com/x/web-interface/popular/precious",
            params={"page_size": 50, "page": 1}, cookie=cookie, proxy=proxy,
        )
        items = [
            _item_from_popular(rank, v)
            for rank, v in enumerate(data.get("list") or [], start=1)
        ]
        return items[:50]
