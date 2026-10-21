"""Evil0ctal (Douyin_TikTok_Download_API) v5 客户端：抖音/TikTok 兜底引擎。

v5 是异步任务 API：POST /api/v1/parse?wait=N + Bearer API key，
wait 秒内等待结果直接返回。返回的规范化数据里 media.video.url 是无水印直链，
httpx 带 UA/Referer 即可独立下载（2026-10 实测验证）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..config import Settings
from .ytdlp import DownloadCancelled, RawDownload

log = logging.getLogger("vidharbor.evil0ctal")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_ERROR_HINTS = {
    "IDENTITY_POOL_EXHAUSTED": "服务身份池为空——在控制台 /identities 页铸造身份（或开启自动补充）",
    "FORBIDDEN_SCOPE": "API key 缺少对应平台 read 权限（控制台 /api-keys 勾选 douyin:read / tiktok:read）",
    "RATE_LIMITED": "触发服务限流，稍后重试",
    "UNAUTHORIZED": "API key 无效或已过期",
}

_PLATFORM_REFERER = {
    "douyin": "https://www.douyin.com/",
    "tiktok": "https://www.tiktok.com/",
}


class Evil0ctalError(Exception):
    """服务返回的业务错误（已映射为用户可读信息）。"""

    def __init__(self, code: str, message: str) -> None:
        hint = _ERROR_HINTS.get(code)
        super().__init__(hint or f"{code}: {message}" if message else code)
        self.code = code


class Evil0ctalClient:
    """对接 Evil0ctal v5 REST API。"""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/readyz", timeout=4)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def parse(self, url: str, wait: float = 30.0) -> dict:
        """解析任意支持平台的链接，返回 data 字段（normalized 结构）。"""
        headers = {"User-Agent": UA}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = httpx.post(
            f"{self.base_url}/api/v1/parse",
            params={"wait": wait},
            json={"url": url},
            headers=headers,
            timeout=wait + 30,
        )
        if r.status_code == 401:
            raise Evil0ctalError("UNAUTHORIZED", "API key 无效")
        if r.status_code == 403:
            raise Evil0ctalError("FORBIDDEN_SCOPE", "API key 权限不足")
        r.raise_for_status()
        body = r.json()
        if not body.get("success"):
            err = body.get("error") or {}
            raise Evil0ctalError(
                str(err.get("code") or "UPSTREAM_ERROR"),
                str(err.get("message") or "解析失败"),
            )
        data = body.get("data")
        if not isinstance(data, dict):
            raise Evil0ctalError("EMPTY_DATA", "服务未返回数据")
        return data

    def sign(self, platform: str, url: str, user_agent: str, cookies: str) -> str:
        """用服务的签名工具给平台 API URL 计算 a_bogus 签名，返回签名后的 URL。"""
        headers = {"User-Agent": UA}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = httpx.post(
            f"{self.base_url}/api/v1/tools/sign",
            json={"platform": platform, "url": url,
                  "user_agent": user_agent, "cookies": cookies},
            headers=headers,
            timeout=30,
        )
        if r.status_code == 401:
            raise Evil0ctalError("UNAUTHORIZED", "API key 无效")
        r.raise_for_status()
        body = r.json()
        signed = (body.get("data") or {}).get("signed_url")
        if not signed:
            raise Evil0ctalError("SIGN_FAILED", "服务未返回签名 URL")
        return signed


def _first_str(obj: Any, *keys: str) -> str:
    for k in keys:
        v = obj.get(k) if isinstance(obj, dict) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _pick_video_url(data: dict) -> str | None:
    media = data.get("media") or {}
    video = media.get("video") or {}
    u = _first_str(video, "url")
    if not u:
        for cand in video.get("urls") or []:
            if isinstance(cand, str) and cand.startswith("http"):
                u = cand
                break
    return u or None


def _upload_date(created_at: str) -> str:
    if not created_at:
        return ""
    try:
        # 平台 created_at 是 UTC；展示口径与页面一致，换算到北京时区
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    except ValueError:
        return ""


def evil0ctal_download(
    url: str,
    settings: Settings,
    temp_dir: Path,
    on_progress=None,
    cancel_event=None,
) -> RawDownload:
    """经 Evil0ctal v5 服务解析并下载（抖音/TikTok 通用）。"""
    temp_dir.mkdir(parents=True, exist_ok=True)
    cfg = settings.evil0ctal
    try:
        data = Evil0ctalClient(cfg.base_url, cfg.api_key).parse(url)
    except Evil0ctalError as e:
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error=f"Evil0ctal 解析失败: {e}",
        )
    except Exception as e:  # noqa: BLE001
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error=f"Evil0ctal 接口调用失败: {e}（请确认服务已启动，见 README）",
        )

    platform = str(data.get("platform") or "douyin")
    kind = str(data.get("kind") or "")
    if kind != "video":
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error=f"暂不支持的作品类型: {kind or '未知'}（当前仅支持视频）",
        )

    play = _pick_video_url(data)
    if not play:
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error="Evil0ctal 未返回可用视频地址",
        )

    aweme_id = str(data.get("content_id") or f"dtk{int(datetime.now().timestamp())}")
    stats = data.get("stats") or {}
    author = data.get("author") or {}
    duration_ms = data.get("duration_ms") or 0
    covers = (data.get("media") or {}).get("covers") or []
    cover_url = ""
    for c in covers:
        u = c.get("url") if isinstance(c, dict) else None
        if isinstance(u, str) and u.startswith("http"):
            cover_url = u
            break

    media = temp_dir / f"{aweme_id}.mp4"
    referer = _PLATFORM_REFERER.get(platform, "https://www.douyin.com/")
    try:
        with httpx.stream("GET", play, headers={"User-Agent": UA, "Referer": referer},
                          timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            with media.open("wb") as f:
                for chunk in r.iter_bytes(65536):
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled()
                    f.write(chunk)
                    done += len(chunk)
                    if total and on_progress:
                        on_progress(done / total, "", "")
    except DownloadCancelled:
        raise
    except Exception as e:  # noqa: BLE001
        return RawDownload(ok=False, engine="evil0ctal", temp_dir=temp_dir, error=f"视频下载失败: {e}")
    if on_progress:
        on_progress(1.0, "", "")

    thumbnail_path = None
    if cover_url:
        try:
            tp = temp_dir / f"{aweme_id}.jpeg"
            tr = httpx.get(cover_url, headers={"User-Agent": UA, "Referer": referer},
                           timeout=20, follow_redirects=True)
            if tr.status_code == 200:
                tp.write_bytes(tr.content)
                thumbnail_path = tp
        except Exception:  # noqa: BLE001
            pass

    info = {
        "id": aweme_id,
        "title": _first_str(data, "title", "description") or aweme_id,
        "description": str(data.get("description") or ""),
        "uploader": _first_str(author, "nickname", "unique_id"),
        "uploader_id": _first_str(author, "unique_id", "sec_uid", "uid")[:255],
        "upload_date": _upload_date(str(data.get("created_at") or "")),
        "duration": float(duration_ms) / 1000.0,
        "webpage_url": _first_str(data, "web_url") or url,
        "extractor_key": platform.capitalize(),
        "view_count": int(stats.get("play_count") or 0),
        "like_count": int(stats.get("digg_count") or 0),
        "comment_count": int(stats.get("comment_count") or 0),
        "tags": [t for t in (data.get("tags") or []) if isinstance(t, str)][:12],
    }
    log.info("Evil0ctal 兜底成功: %s (%s)", info["title"][:50], aweme_id)
    return RawDownload(
        ok=True,
        engine="evil0ctal",
        info=info,
        media_path=media,
        thumbnail_path=thumbnail_path,
        temp_dir=temp_dir,
    )
