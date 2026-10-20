"""TikTok 榜单：无公开官方榜单；用热门标签页经 yt-dlp flat 提取。

TikTok 2026 年要求登录 cookies 才能拉取标签页列表（实测无 cookies 报
"No working app info"），未配置时抛 ChartError 引导用户配置。
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import yt_dlp

from ..config import Settings
from .base import ChartError, ChartProvider, TrendingItem

log = logging.getLogger("vidlib.charts.tiktok")

DEFAULT_TAGS = ["funny", "music", "dance", "food", "gaming", "pets"]


class TikTokProvider(ChartProvider):
    name = "tiktok"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        return [{"id": t, "name": f"#{t}"} for t in DEFAULT_TAGS]

    def fetch(self, category: str) -> list[TrendingItem]:
        tag = category if category in DEFAULT_TAGS else DEFAULT_TAGS[0]
        url = f"https://www.tiktok.com/tag/{quote(tag)}"
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
            if not cookies:
                raise ChartError(
                    "TikTok 标签页需要登录 cookies：请在 config.toml 配置含 TikTok 登录态的 "
                    "cookies.txt（导出方法见 README），或直接粘贴视频链接下载"
                ) from e
            raise ChartError(f"TikTok 标签页获取失败: {msg[:200]}") from e
        items: list[TrendingItem] = []
        for rank, e in enumerate(info.get("entries") or [], start=1):
            vid = str(e.get("id") or "")
            if not vid:
                continue
            author = str(e.get("channel") or e.get("uploader") or "")
            item_url = str(e.get("url") or f"https://www.tiktok.com/@{author}/video/{vid}")
            items.append(TrendingItem(
                source_id=vid,
                title=str(e.get("title") or ""),
                author=author,
                url=item_url,
                cover=str(e.get("thumbnails", [{}])[0].get("url") or "") if e.get("thumbnails") else "",
                duration=float(e.get("duration") or 0),
                views=int(e.get("view_count") or 0),
                extra={"rank": rank, "tag": tag},
            ))
        return items[:50]
