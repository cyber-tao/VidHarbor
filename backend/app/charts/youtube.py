"""YouTube 榜单：Trending 页已于 2025-07 下线，改用搜索过滤器「本月 + 按播放量排序」。

sp=CAMSBAgEEAE%3D 为 YouTube 搜索过滤器参数（2026-10 实测可用），
经 yt-dlp flat 提取，与下载引擎共享 cookies 配置。
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import yt_dlp

from ..config import Settings
from .base import ChartError, ChartProvider, TrendingItem

log = logging.getLogger("vidlib.charts.youtube")

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
SP_FILTER = "CAMSBAgEEAE%3D"  # 上传时间:本月 + 排序:播放量


class YoutubeProvider(ChartProvider):
    name = "youtube"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        return [{"id": cid, "name": cname} for cid, cname in CATEGORIES]

    def fetch(self, category: str) -> list[TrendingItem]:
        query = QUERIES.get(category, "trending")
        url = f"https://www.youtube.com/results?search_query={quote(query)}&sp={SP_FILTER}"
        opts: dict = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "playlist_items": "1:50", "socket_timeout": 20,
        }
        cookies = self.settings.cookies_path
        if cookies:
            opts["cookiefile"] = str(cookies)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "sign in" in msg.lower() or "cookies" in msg.lower():
                raise ChartError("YouTube 要求登录：请在 config.toml 配置 cookies.txt（方法见 README）") from e
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
        return items[:50]
