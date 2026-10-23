"""抖音热搜榜 + 关键词搜索（custom:<词> 返回可下载的真实视频）。

热搜榜：web 接口 + 浏览器 UA + 伪 ttwid（2026-10 实测可用），返回话题级数据。
搜索：抖音 web 搜索接口需要 a_bogus 签名（2026-10 起 Argus 强制），服务端无法
自行计算；链路 = 应用内导入的抖音登录 cookies + Evil0ctal 服务 /tools/sign 签名
→ 官方 search/item 接口 → 真实视频列表（downloadable=True，走正常下载管线）。
"""
from __future__ import annotations

import random
import time
from urllib.parse import quote, urlencode

import httpx

from ..auth import cookies as cookies_mod
from ..config import Settings
from ..downloader.evil0ctal import Evil0ctalClient, Evil0ctalError
from .base import ChartError, ChartProvider, TrendingItem, fmt_published

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.douyin.com/",
    "Cookie": "ttwid=1",
}

SEARCH_UA = HEADERS["User-Agent"]

PERIODS = [{"id": "default", "name": "实时"}]

# 单一热搜榜：官方接口的 board_sub_type（种草/娱乐/社会子榜）已被抖音忽略，
# 各子榜返回完全相同的数据（2026-10 实测），不再区分。
CATEGORY = {"id": "hot", "name": "热搜榜"}

# 热搜词条标签：1=热 2=新 3=爆 4=首发（与官方 label_url 徽章一致）
LABELS = {1: "热", 2: "新", 3: "爆", 4: "首发"}


def _first_cover(w: dict) -> str:
    cover = w.get("word_cover")
    if isinstance(cover, dict):
        for u in cover.get("url_list") or []:
            if isinstance(u, str) and u.startswith("http"):
                return u
    return ""


class DouyinProvider(ChartProvider):
    name = "douyin"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        return [{
            **CATEGORY, "periods": PERIODS,
            # 开放自定义关键词搜索（custom:<词> → 可下载视频列表）
            "allow_custom": True,
            # 热搜条目是话题而非视频
            "downloadable": False,
        }]

    def _proxy(self) -> str | None:
        return (self.settings.proxy_for("douyin") or None) if self.settings else None

    def fetch(self, category: str, period: str = "") -> list[TrendingItem]:
        if category.startswith("custom:"):
            keyword = category[len("custom:"):].strip()
            if keyword:
                return self.search_videos(keyword)
        params = {"board_type": "0", "board_sub_type": "", "source": "6"}
        try:
            r = httpx.get(
                "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                params=params, headers=HEADERS, timeout=15,
                proxy=self._proxy(),
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
            rank = int(w.get("position") or i)
            sentence_id = str(w.get("sentence_id") or "").strip()
            # 话题视频聚合页；无 sentence_id 时退回搜索页
            url = (
                f"https://www.douyin.com/hot/{sentence_id}"
                if sentence_id else f"https://www.douyin.com/search/{quote(word)}"
            )
            try:
                label_code = int(w.get("label") or 0)
            except (TypeError, ValueError):
                label_code = 0
            items.append(TrendingItem(
                source_id=f"hot-{sentence_id or i}",
                title=word,
                author="",
                url=url,
                cover=_first_cover(w),
                views=int(w.get("hot_value") or 0),
                published=fmt_published(w.get("event_time")),
                downloadable=False,
                extra={
                    "rank": rank,
                    "label": LABELS.get(label_code, ""),
                    "label_url": w.get("label_url") or "",
                    "video_count": int(w.get("video_count") or 0),
                    "sentence_id": sentence_id,
                },
            ))
        return items

    # ---- 关键词搜索（custom:<词>）：真实视频，可勾选下载 ----

    def _require_search_deps(self) -> tuple[Evil0ctalClient, dict[str, str]]:
        """搜索的前置条件：Evil0ctal 服务（签名）+ 抖音登录 cookies。"""
        if self.settings is None:
            raise ChartError("抖音搜索不可用：缺少配置")
        cfg = self.settings.evil0ctal
        if not cfg.enabled:
            raise ChartError("抖音搜索需要 Evil0ctal 兜底服务签名：请在「设置 → 兜底引擎」启用")
        client = Evil0ctalClient(cfg.base_url, cfg.api_key)
        if not client.health():
            raise ChartError(f"Evil0ctal 签名服务不可达（{cfg.base_url}）：请先启动服务，见 README")
        jar = cookies_mod.cookie_jar(self.settings, "douyin")
        if not jar:
            raise ChartError(
                "抖音搜索需要登录态：请在「设置 → 登录管理」导入或上传抖音 cookies"
            )
        if not jar.get("ttwid"):
            raise ChartError("抖音 cookies 无效（缺 ttwid）：请重新在「设置 → 登录管理」导入")
        return client, jar

    def search_videos(self, keyword: str, count: int = 20) -> list[TrendingItem]:
        """官方 search/item 接口（签名链路见模块头注释）。"""
        client, jar = self._require_search_deps()
        cookie_str = cookies_mod.cookie_header(jar)
        params = {
            "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
            "search_channel": "aweme_video_web", "enable_history": "1",
            "search_source": "normal_search", "query_correct_type": "1",
            "is_filter_search": "0", "from_group_id": "", "disable_rs": "0",
            "offset": "0", "count": str(count), "need_filter_settings": "0",
            "list_type": "single",
            "search_id": time.strftime("%Y%m%d%H%M%S")
            + "".join(random.choices("0123456789ABCDEF", k=16)),
            "update_version_code": "170400", "pc_client_type": "2",
            "version_code": "170400", "version_name": "17.4.0",
            "cookie_enabled": "true", "platform": "PC", "downlink": "10",
            "effective_type": "4g",
        }
        for qk, ck in (("webid", "webid"), ("uifid", "UIFID"), ("verifyFp", "s_v_web_id")):
            if jar.get(ck):
                params[qk] = jar[ck]
                if qk == "verifyFp":
                    params["fp"] = jar[ck]
        # keyword 用原始中文拼 URL：sign 服务会统一编码，预编码会被二次编码导致搜索词错乱
        base = ("https://www.douyin.com/aweme/v1/web/search/item/?"
                + urlencode(params, quote_via=quote) + "&keyword=" + keyword)

        try:
            signed = client.sign("douyin", base, SEARCH_UA, cookie_str)
        except Evil0ctalError as e:
            raise ChartError(f"Evil0ctal 签名失败: {e}") from e

        headers = {"User-Agent": SEARCH_UA, "Cookie": cookie_str,
                   "Referer": f"https://www.douyin.com/search/{quote(keyword)}?type=video"}
        try:
            r = httpx.get(signed, headers=headers, timeout=20,
                         proxy=self._proxy())
            r.raise_for_status()
            body = r.json()
        except Exception as e:  # noqa: BLE001
            raise ChartError(f"抖音搜索接口请求失败: {e}") from e

        raw = body.get("data")
        chunks = raw if isinstance(raw, list) else ((raw or {}).get("data") or [])
        items: list[TrendingItem] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            aw = chunk.get("aweme_info") or {}
            aweme_id = str(aw.get("aweme_id") or "")
            video = aw.get("video") or {}
            # 只保留真实视频（跳过广告/图集/已删除条目）
            if not aweme_id or not (video.get("play_addr") or aw.get("desc")):
                continue
            if aw.get("images"):
                continue
            stats = aw.get("statistics") or {}
            cover_urls = ((video.get("cover") or {}).get("url_list")) or []
            desc = " ".join(str(aw.get("desc") or "").split())
            items.append(TrendingItem(
                source_id=aweme_id,
                title=desc or aweme_id,
                author=str((aw.get("author") or {}).get("nickname") or ""),
                url=f"https://www.douyin.com/video/{aweme_id}",
                cover=cover_urls[0] if cover_urls else "",
                duration=float(video.get("duration") or 0) / 1000.0,
                views=int(stats.get("play_count") or 0),
                likes=int(stats.get("digg_count") or 0),
                published=fmt_published(aw.get("create_time")),
                downloadable=True,
                extra={"rank": len(items) + 1, "keyword": keyword},
            ))
            if len(items) >= count:
                break
        if not items:
            status = body.get("status_code")
            if status not in (0, None):
                raise ChartError(
                    f"抖音搜索被拦截（status {status}）：cookies 可能过期，"
                    "请在「设置 → 登录管理」重新导入抖音 cookies"
                )
            raise ChartError(f"关键词「{keyword}」没有搜到视频")
        return items
