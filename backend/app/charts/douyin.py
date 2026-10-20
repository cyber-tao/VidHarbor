"""抖音热搜榜：web 接口 + 浏览器 UA + 伪 ttwid（2026-10 实测可用）。

返回热搜词与热度值（无关联视频结构），downloader=False，
点击后跳转抖音搜索页，由用户复制具体视频链接下载。
"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from .base import ChartError, ChartProvider, TrendingItem

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.douyin.com/",
    "Cookie": "ttwid=1",
}


class DouyinProvider(ChartProvider):
    name = "douyin"

    def categories(self) -> list[dict]:
        return [{"id": "hot", "name": "热搜榜"}]

    def fetch(self, category: str) -> list[TrendingItem]:
        try:
            r = httpx.get(
                "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                headers=HEADERS, timeout=15,
            )
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise ChartError(f"抖音热搜接口请求失败: {e}") from e
        word_list = (data.get("data") or {}).get("word_list") or []
        if not word_list:
            raise ChartError("抖音热搜返回为空（接口可能临时失效，稍后重试）")
        items: list[TrendingItem] = []
        for i, w in enumerate(word_list[:50], start=1):
            word = str(w.get("word") or "").strip()
            if not word:
                continue
            items.append(TrendingItem(
                source_id=f"hot-{i}",
                title=word,
                author="",
                url=f"https://www.douyin.com/search/{quote(word)}",
                views=int(w.get("hot_value") or 0),
                downloadable=False,
                extra={"rank": i, "label": w.get("label") or ""},
            ))
        return items
