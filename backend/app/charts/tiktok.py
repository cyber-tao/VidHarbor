"""TikTok 标签榜：官方 challenge 接口 + Evil0ctal 签名链路。

TikTok 无公开官方榜单，以热门标签的视频流为准（标签页顺序即平台自己的排序）。
2026-10 实测链路（yt-dlp 标签提取器已死、标签页 HTML 为客户端渲染无数据）：
应用内导入的 TikTok cookies + Evil0ctal 服务 /tools/sign 原生签名
（X-Bogus/X-Gnarly，毫秒级无需浏览器）→ challenge/detail 解析标签数字 ID
→ challenge/item_list 分页拉视频列表。
关键坑：请求缺 device_id 参数时 TikTok 返回 200 空 body（形似风控），
随机 19 位数字即可；base_params 全集照抄 TikTok web 端真实请求。
标签页无时间维度，period 恒为「不限」。
"""
from __future__ import annotations

import logging
import random
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from ..config import Settings
from ..downloader.evil0ctal import Evil0ctalClient, Evil0ctalError
from .base import ChartError, ChartProvider, TrendingItem, fmt_published

log = logging.getLogger("vidharbor.charts.tiktok")

DEFAULT_TAGS = ["funny", "music", "dance", "food", "gaming", "pets"]
PERIODS = [{"id": "default", "name": "不限"}]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

PAGE_SIZE = 30          # TikTok 对 count 上限 35，30 是官方 web 端的翻页值
MAX_PAGES = 3           # 3 页 × 30 = 90 条候选，截取前 50 足够
TARGET_COUNT = 50

_BASE_PARAMS: dict[str, str] = {
    "aid": "1988",
    "app_language": "en",
    "app_name": "tiktok_web",
    "browser_language": "en-US",
    "browser_name": "Mozilla",
    "browser_online": "true",
    "browser_platform": "Win32",
    "browser_version": "5.0 (Windows)",
    "channel": "tiktok_web",
    "cookie_enabled": "true",
    # device_id 必填（见模块头注释）：随机 19 位数字与真实设备效果相同
    "device_platform": "web_pc",
    "focus_state": "true",
    "from_page": "hashtag",
    "history_len": "4",
    "is_fullscreen": "false",
    "is_page_visible": "true",
    "language": "en",
    "os": "windows",
    "priority_region": "US",
    "referer": "",
    "region": "US",
    "root_referer": "https://www.tiktok.com/",
    "screen_height": "1080",
    "screen_width": "1920",
    "tz_name": "America/Los_Angeles",
    "webcast_language": "en",
}


def _device_id() -> str:
    first = random.randint(1, 9)
    rest = "".join(str(random.randint(0, 9)) for _ in range(18))
    return f"{first}{rest}"


def _api_params(**extra: str) -> dict[str, str]:
    return {**_BASE_PARAMS, "device_id": _device_id(), **extra}


class TikTokProvider(ChartProvider):
    name = "tiktok"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def categories(self) -> list[dict]:
        return [
            {"id": t, "name": f"#{t}", "periods": PERIODS, "allow_custom": True}
            for t in DEFAULT_TAGS
        ]

    def fetch(self, category: str, period: str = "") -> list[TrendingItem]:
        if category.startswith("custom:"):
            tag = category[len("custom:"):].strip()
            if not tag:
                raise ChartError("自定义标签为空")
            tag = tag.lstrip("#")
        else:
            tag = category if category in DEFAULT_TAGS else DEFAULT_TAGS[0]
        client, cookie_str = self._require_deps()
        challenge = self._challenge_detail(client, cookie_str, tag)
        return self._challenge_items(client, cookie_str, tag, challenge)

    # ---- 前置条件：Evil0ctal 签名服务 + TikTok 登录 cookies ----

    def _require_deps(self) -> tuple[Evil0ctalClient, str]:
        cfg = self.settings.evil0ctal
        if not cfg.enabled:
            raise ChartError(
                "TikTok 标签榜需要 Evil0ctal 签名服务：请在「设置 → 兜底引擎」启用并启动服务"
            )
        client = Evil0ctalClient(cfg.base_url, cfg.api_key)
        if not client.health():
            raise ChartError(f"Evil0ctal 签名服务不可达（{cfg.base_url}）：请先启动服务，见 README")
        cookies_path = self.settings.cookie_file_for("tiktok")
        if not cookies_path:
            raise ChartError(
                "TikTok 标签榜需要登录态：请在「设置 → 登录管理」导入或上传 TikTok cookies"
            )
        jar = self._read_cookie_jar(cookies_path)
        if not jar.get("ttwid"):
            raise ChartError("TikTok cookies 无效（缺 ttwid）：请重新在「设置 → 登录管理」导入")
        return client, "; ".join(f"{k}={v}" for k, v in jar.items())

    @staticmethod
    def _read_cookie_jar(path: Path) -> dict[str, str]:
        """Netscape cookies.txt → {name: value}（同名取后出现的，与浏览器行为一致）。"""
        jar: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                jar[parts[5]] = parts[6]
        return jar

    # ---- 官方接口 ----

    def _get_signed(
        self, client: Evil0ctalClient, cookie_str: str, url: str, referer: str
    ) -> dict:
        """签名并请求，返回 JSON；空 body（形似风控）抛 ChartError。"""
        try:
            signed = client.sign("tiktok", url, UA, cookie_str)
        except Evil0ctalError as e:
            raise ChartError(f"Evil0ctal 签名失败: {e}") from e
        headers = {
            "User-Agent": UA, "Cookie": cookie_str, "Referer": referer,
            "Origin": "https://www.tiktok.com",
            "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            r = httpx.get(signed, headers=headers, timeout=20,
                         proxy=self.settings.proxy_for("tiktok") or None)
            r.raise_for_status()
            body = r.json()
        except Exception as e:  # noqa: BLE001
            raise ChartError(
                f"TikTok 接口无响应：cookies 可能已过期，请重新在"
                f"「设置 → 登录管理」导入（{e}）"
            ) from e
        return body if isinstance(body, dict) else {}

    def _challenge_detail(self, client: Evil0ctalClient, cookie_str: str, tag: str) -> dict:
        params = _api_params(challengeName=tag)
        url = "https://www.tiktok.com/api/challenge/detail/?" + urlencode(params)
        body = self._get_signed(client, cookie_str, url, f"https://www.tiktok.com/tag/{quote(tag)}")
        info = (body.get("challengeInfo") or {}).get("challenge") or {}
        if not info.get("id"):
            raise ChartError(f"TikTok 标签 #{tag} 不存在或已下线")
        return info

    def _challenge_items(
        self, client: Evil0ctalClient, cookie_str: str, tag: str, challenge: dict
    ) -> list[TrendingItem]:
        cid = str(challenge.get("id"))
        referer = f"https://www.tiktok.com/tag/{quote(tag)}"
        items: list[TrendingItem] = []
        cursor = 0
        for _ in range(MAX_PAGES):
            params = _api_params(
                challengeID=cid, count=str(PAGE_SIZE), cursor=str(cursor)
            )
            url = "https://www.tiktok.com/api/challenge/item_list/?" + urlencode(params)
            body = self._get_signed(client, cookie_str, url, referer)
            for e in body.get("itemList") or []:
                it = self._to_item(e, tag, len(items) + 1)
                if it:
                    items.append(it)
                    if len(items) >= TARGET_COUNT:
                        break
            if len(items) >= TARGET_COUNT or not body.get("hasMore"):
                break
            try:
                cursor = int(body.get("cursor") or 0)
            except (TypeError, ValueError):
                break
        if not items:
            raise ChartError(
                f"TikTok 标签 #{tag} 未返回视频：cookies 可能已过期，"
                "请重新在「设置 → 登录管理」导入"
            )
        log.info("TikTok 标签榜 #%s 拉取成功：%d 条", tag, len(items))
        return items

    @staticmethod
    def _to_item(e: dict, tag: str, rank: int) -> TrendingItem | None:
        vid = str(e.get("id") or "")
        if not vid:
            return None
        author = e.get("author") or {}
        handle = str(author.get("uniqueId") or "")
        url = (
            f"https://www.tiktok.com/@{handle}/video/{vid}"
            if handle else f"https://www.tiktok.com/video/{vid}"
        )
        video = e.get("video") or {}
        stats = e.get("stats") or {}
        return TrendingItem(
            source_id=vid,
            title=" ".join(str(e.get("desc") or "").split()) or vid,
            author=str(author.get("nickname") or handle),
            url=url,
            cover=str(video.get("originCover") or video.get("cover") or ""),
            duration=float(video.get("duration") or 0),
            views=int(stats.get("playCount") or 0),
            likes=int(stats.get("diggCount") or 0),
            published=fmt_published(e.get("createTime")),
            downloadable=True,
            extra={"rank": rank, "tag": tag},
        )
