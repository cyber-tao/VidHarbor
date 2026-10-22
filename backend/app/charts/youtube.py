"""YouTube 榜单：Trending 页已于 2025-07 下线，改用官方 Data API 或搜索结果。

三级数据源（按优先级，上一级失败或结果过少时降级）：
1. YouTube Data API v3（配置 api_key 后启用）：
   - 热门/音乐/游戏/科技/影视 → videos.list chart=mostPopular（真实热门榜，
     带点赞/播放/发布时间，单次 1 配额单位）；
   - 播客/自定义关键词 → search.list order=viewCount + publishedAfter 再
     videos.list 补全统计（单次约 101 配额单位，免费日配额个人够用）。
2. InnerTube 搜索接口（免登录、支持翻页，按相关度排序），服务端按 publishedTimeText
   过滤周期。
3. yt-dlp flat 提取普通搜索结果页（无时间字段，不按周期过滤）。
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import quote

import httpx
import yt_dlp

from ..config import Settings
from .base import ChartError, ChartProvider, TrendingItem, fmt_published

log = logging.getLogger("vidharbor.charts.youtube")

# 分类 → 搜索词
QUERIES = {
    "trending": "trending",
    "music": "music",
    "gaming": "gaming",
    "tech": "technology",
    "movie": "movie trailer",
    "podcast": "podcast",
}
CATEGORIES = [
    ("trending", "热门"), ("music", "音乐"), ("gaming", "游戏"),
    ("tech", "科技"), ("movie", "影视"), ("podcast", "播客"),
]
# 官方 API 的 mostPopular 榜可按视频分类拉取；无映射的分类走 search
CATEGORY_VIDEO_IDS = {"music": "10", "gaming": "20", "tech": "28", "movie": "1"}
PERIODS = [
    {"id": "day", "name": "今日"},
    {"id": "week", "name": "本周"},
    {"id": "month", "name": "本月", "default": True},
]
# 周期 → publishedTimeText 折算天数上限
PERIOD_MAX_DAYS = {"day": 1, "week": 7, "month": 31}

_INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/search"
_MAX_PAGES = 5
_DATA_API = "https://www.googleapis.com/youtube/v3"


def _find_continuation(obj) -> str | None:
    if isinstance(obj, dict):
        c = obj.get("continuationItemRenderer")
        if isinstance(c, dict):
            token = ((c.get("continuationEndpoint") or {})
                     .get("continuationCommand") or {}).get("token")
            if token:
                return str(token)
        for v in obj.values():
            found = _find_continuation(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_continuation(v)
            if found:
                return found
    return None


def _collect_video_renderers(obj, out: list) -> None:
    if isinstance(obj, dict):
        vr = obj.get("videoRenderer")
        if isinstance(vr, dict) and vr.get("videoId"):
            out.append(vr)
        for v in obj.values():
            _collect_video_renderers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_video_renderers(v, out)


def _text_to_days(text: str) -> float | None:
    """「3小时前」「2周前」→ 天数；解析不了返回 None。"""
    m = re.match(r"(\d+)\s*(分钟|小时|天|周|个月|年)", text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    mul = {"分钟": 1 / 1440, "小时": 1 / 24, "天": 1, "周": 7, "个月": 30, "年": 365}
    return n * mul[unit]


def _views_from_text(text: str) -> int:
    """「1,234,567 次观看」/「120万次观看」/「1.2亿」→ 整数。"""
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(亿|万)?", text or "")
    if not m:
        return 0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    if m.group(2) == "亿":
        n *= 1e8
    elif m.group(2) == "万":
        n *= 1e4
    return int(n)


def _duration_from_text(text: str) -> float:
    """「3:25」/「1:02:03」→ 秒。"""
    s = (text or "").strip()
    if not s:
        return 0.0
    try:
        secs = 0.0
        for p in s.split(":"):
            secs = secs * 60 + float(p)
        return secs
    except ValueError:
        return 0.0


def _runs_text(node) -> str:
    if not isinstance(node, dict):
        return ""
    return "".join(r.get("text") or "" for r in node.get("runs") or [])


def _item_from_renderer(rank: int, vr: dict) -> TrendingItem:
    vid = str(vr.get("videoId") or "")
    views_text = (vr.get("viewCountText") or {}).get("simpleText") or ""
    return TrendingItem(
        source_id=vid,
        title=_runs_text(vr.get("title")) or (vr.get("title") or {}).get("simpleText") or "",
        author=_runs_text(vr.get("ownerText")) or _runs_text(vr.get("longBylineText")),
        url=f"https://www.youtube.com/watch?v={vid}",
        cover=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        duration=_duration_from_text((vr.get("lengthText") or {}).get("simpleText") or ""),
        views=_views_from_text(views_text),
        published=(vr.get("publishedTimeText") or {}).get("simpleText") or "",
        extra={"rank": rank},
    )


def _innertube_search(query: str, max_pages: int = _MAX_PAGES, proxy: str = "") -> list[dict]:
    """InnerTube 搜索（免登录）+ 翻页，返回 videoRenderer 列表；失败抛 ChartError。"""
    base_body = {
        "context": {"client": {
            "clientName": "WEB", "clientVersion": "2.20260101.00.00",
            "hl": "zh-CN", "gl": "US",
        }},
        "query": query,
    }
    renderers: list[dict] = []
    seen: set[str] = set()
    continuation = None
    try:
        for _ in range(max_pages):
            body = dict(base_body)
            if continuation:
                body["continuation"] = continuation
            r = httpx.post(_INNERTUBE_URL, json=body, timeout=15, proxy=proxy or None)
            r.raise_for_status()
            data = r.json()
            found: list[dict] = []
            _collect_video_renderers(data, found)
            for vr in found:
                vid = str(vr.get("videoId") or "")
                if vid and vid not in seen:
                    seen.add(vid)
                    renderers.append(vr)
            continuation = _find_continuation(data)
            if not continuation:
                break
    except Exception as e:  # noqa: BLE001
        if not renderers:
            raise ChartError(f"YouTube 搜索接口请求失败: {e}") from e
        log.warning("InnerTube 翻页中断（返回已有 %d 条）: %s", len(renderers), e)
    return renderers


def _iso_duration_to_secs(raw: str) -> float:
    """ISO8601 时长「PT2M30S」→ 秒。"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", raw or "")
    if not m:
        return 0.0
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + s


def _rfc3339_epoch(raw: str) -> int:
    try:
        return int(datetime.fromisoformat((raw or "").replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _item_from_api_video(rank: int, v: dict) -> TrendingItem:
    vid = str(v.get("id") or "")
    sn = v.get("snippet") or {}
    stat = v.get("statistics") or {}
    ts = _rfc3339_epoch(sn.get("publishedAt") or "")
    return TrendingItem(
        source_id=vid,
        title=str(sn.get("title") or ""),
        author=str((sn.get("channelTitle")) or ""),
        url=f"https://www.youtube.com/watch?v={vid}",
        cover=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        duration=_iso_duration_to_secs((v.get("contentDetails") or {}).get("duration") or ""),
        views=int(stat.get("viewCount") or 0),
        likes=int(stat.get("likeCount") or 0),
        published=fmt_published(ts),
        extra={"rank": rank, "source": "api", "published_ts": ts},
    )


def _filter_by_ts(items: list[TrendingItem], period: str,
                  min_keep: int = 8) -> list[TrendingItem]:
    """按发布时间 epoch 过滤；过滤后不足 min_keep 条则保留完整列表。"""
    max_days = PERIOD_MAX_DAYS.get(period)
    if max_days is None:
        return items
    now = time.time()
    filtered = [it for it in items
                if (ts := it.extra.get("published_ts") or 0) <= 0
                or now - ts < max_days * 86400]
    return filtered if len(filtered) >= min_keep else items


class YoutubeProvider(ChartProvider):
    name = "youtube"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        return [
            {"id": cid, "name": cname, "periods": PERIODS, "allow_custom": True}
            for cid, cname in CATEGORIES
        ]

    def fetch(self, category: str, period: str = "") -> list[TrendingItem]:
        if category.startswith("custom:"):
            query = category[len("custom:"):].strip()
            if not query:
                raise ChartError("自定义关键词为空")
        else:
            query = QUERIES.get(category, "trending")

        # 1) 官方 Data API（配置 api_key 后启用）
        if self.settings.youtube.api_key:
            try:
                items = self._fetch_official(category, query, period)
                if items:
                    return items[:50]
                log.warning("官方 API 结果为空(%s/%s)，回退 InnerTube", category, period)
            except ChartError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("官方 API 失败，回退 InnerTube: %s", e)

        # 2) InnerTube
        try:
            items = self._fetch_innertube(query, period)
            if len(items) >= 3:
                return items[:50]
            log.warning("InnerTube 结果过少(%d)，回退 yt-dlp", len(items))
        except ChartError as e:
            log.warning("InnerTube 失败，回退 yt-dlp: %s", e.message)
        return self._fetch_ytdlp(query)[:50]

    # ---- 官方 Data API ----

    def _data_api_get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self.settings.youtube.api_key}
        r = httpx.get(f"{_DATA_API}/{path}", params=params, timeout=15,
                      proxy=self.settings.proxy_for("youtube") or None)
        if r.status_code != 200:
            detail = ""
            try:
                err = r.json().get("error") or {}
                detail = f": {(err.get('errors') or [{}])[0].get('reason', '')} {err.get('message', '')[:80]}"
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(f"YouTube Data API {r.status_code}{detail}")
        return r.json()

    def _fetch_official(self, category: str, query: str, period: str) -> list[TrendingItem]:
        use_chart = (category == "trending" or category in CATEGORY_VIDEO_IDS) \
            and not category.startswith("custom:")
        if use_chart:
            # 有官方热门榜的分类：chart=mostPopular（真实榜单，带完整统计）
            params = {
                "part": "snippet,statistics,contentDetails",
                "chart": "mostPopular", "maxResults": "50",
                "regionCode": self.settings.youtube.region_code or "US",
            }
            vid_cat = CATEGORY_VIDEO_IDS.get(category)
            if vid_cat:
                params["videoCategoryId"] = vid_cat
            data = self._data_api_get("videos", params)
            items = [_item_from_api_video(rank, v)
                     for rank, v in enumerate(data.get("items") or [], start=1)]
            return _filter_by_ts(items, period)
        # 其余分类/自定义关键词：search.list 按热度排序 + 周期publishedAfter
        days = PERIOD_MAX_DAYS.get(period) or 31
        published_after = (datetime.now(dt_timezone.utc) - timedelta(days=days)
                           ).strftime("%Y-%m-%dT%H:%M:%SZ")
        search = self._data_api_get("search", {
            "part": "id", "q": query, "type": "video",
            "order": "viewCount", "maxResults": "25",
            "publishedAfter": published_after,
            "regionCode": self.settings.youtube.region_code or "US",
        })
        ids = [str((it.get("id") or {}).get("videoId") or "")
               for it in search.get("items") or []]
        ids = [i for i in ids if i][:50]
        if not ids:
            return []
        detail = self._data_api_get("videos", {
            "part": "snippet,statistics,contentDetails", "id": ",".join(ids),
        })
        by_id = {str(v.get("id")): v for v in detail.get("items") or []}
        items = [_item_from_api_video(rank, by_id[i])
                 for rank, i in enumerate(ids, start=1) if i in by_id]
        return items

    def _fetch_innertube(self, query: str, period: str) -> list[TrendingItem]:
        renderers = _innertube_search(query, proxy=self.settings.proxy_for("youtube"))
        items = [_item_from_renderer(rank, vr)
                 for rank, vr in enumerate(renderers, start=1)]
        # 按周期过滤发布时间（解析不了时间的条目保留，避免误杀直播/新上传）；
        # 过滤后不足 8 条说明该周期相关性结果太少，退回完整列表更有用
        max_days = PERIOD_MAX_DAYS.get(period)
        if max_days is not None:
            filtered = [it for it in items
                        if not it.published
                        or (d := _text_to_days(it.published)) is None
                        or d < max_days]
            if len(filtered) >= 8:
                items = filtered
        return items

    def _fetch_ytdlp(self, query: str) -> list[TrendingItem]:
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        opts: dict = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "playlist_items": "1:50", "socket_timeout": 20,
        }
        cookies = self.settings.cookie_file_for("youtube")
        if cookies:
            opts["cookiefile"] = str(cookies)
        proxy = self.settings.proxy_for("youtube")
        if proxy:
            opts["proxy"] = proxy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "sign in" in msg.lower() or "cookies" in msg.lower():
                raise ChartError(
                    "YouTube 要求登录：请在「设置 → 登录管理」导入或上传 YouTube cookies"
                ) from e
            raise ChartError(f"YouTube 榜单获取失败: {msg[:200]}") from e
        items: list[TrendingItem] = []
        for rank, e in enumerate(info.get("entries") or [], start=1):
            vid = str(e.get("id") or "")
            if not vid:
                continue
            items.append(TrendingItem(
                source_id=vid,
                title=str(e.get("title") or ""),
                author=str(e.get("channel") or e.get("uploader") or ""),
                url=f"https://www.youtube.com/watch?v={vid}",
                cover=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                duration=float(e.get("duration") or 0),
                views=int(e.get("view_count") or 0),
                extra={"rank": rank},
            ))
        return items
