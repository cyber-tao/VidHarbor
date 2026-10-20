"""抖音兜底引擎：调用本地部署的 Evil0ctal/Douyin_TikTok_Download_API。

响应结构随版本可能变化，解析采用防御式递归查找。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from .ytdlp import DownloadCancelled, RawDownload

log = logging.getLogger("vidlib.douyin")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _find_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key(v, key)
            if found is not None:
                return found
    return None


class Evil0ctalClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/docs", timeout=4)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def hybrid_video_data(self, url: str) -> dict:
        r = httpx.get(
            f"{self.base_url}/api/hybrid/video_data",
            params={"url": url, "minimal": "false"},
            headers={"User-Agent": UA},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


def _pick_play_url(data: dict) -> str | None:
    vd = _find_key(data, "video_data")
    if isinstance(vd, dict):
        for k in ("nwm_video_url", "nwm_video_url_H265", "wm_video_url"):
            u = vd.get(k)
            if isinstance(u, str) and u.startswith("http"):
                return u
    pa = _find_key(data, "play_addr")
    if isinstance(pa, dict):
        for u in pa.get("url_list") or []:
            if isinstance(u, str) and u.startswith("http"):
                return u
    return None


def douyin_download(
    url: str,
    settings: Settings,
    temp_dir: Path,
    on_progress=None,
    cancel_event=None,
) -> RawDownload:
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = Evil0ctalClient(settings.evil0ctal.base_url).hybrid_video_data(url)
    except Exception as e:  # noqa: BLE001
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error=f"Evil0ctal 接口调用失败: {e}（请确认兜底服务已启动，见 README）",
        )

    play = _pick_play_url(data)
    if not play:
        return RawDownload(
            ok=False, engine="evil0ctal", temp_dir=temp_dir,
            error="Evil0ctal 未返回可用视频地址（可能是图集作品，暂不支持）",
        )

    detail = _find_key(data, "aweme_detail") or {}
    if not isinstance(detail, dict):
        detail = {}
    aweme_id = str(detail.get("aweme_id") or detail.get("id") or f"dy{int(time.time())}")
    desc = str(detail.get("desc") or "抖音视频").strip()
    author_info = detail.get("author") or {}
    author = str(author_info.get("nickname") or "").strip()
    create_time = detail.get("create_time") or 0
    upload_date = time.strftime("%Y%m%d", time.localtime(create_time)) if create_time else ""
    stats = detail.get("statistics") or {}
    video_info = detail.get("video") or {}
    duration = float(video_info.get("duration") or 0) / 1000.0

    media = temp_dir / f"{aweme_id}.mp4"
    try:
        with httpx.stream("GET", play, headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as r:
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
    cover = video_info.get("cover") or video_info.get("origin_cover") or {}
    cover_urls = cover.get("url_list") or [] if isinstance(cover, dict) else []
    if cover_urls:
        try:
            tp = temp_dir / f"{aweme_id}.jpeg"
            tr = httpx.get(cover_urls[0], headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
            if tr.status_code == 200:
                tp.write_bytes(tr.content)
                thumbnail_path = tp
        except Exception:  # noqa: BLE001
            pass

    tags = [
        t.get("hashtag_name")
        for t in (detail.get("text_extra") or [])
        if isinstance(t, dict) and t.get("hashtag_name")
    ][:10]

    info = {
        "id": aweme_id,
        "title": desc or aweme_id,
        "description": desc,
        "uploader": author,
        "uploader_id": str(author_info.get("unique_id") or author_info.get("short_id") or ""),
        "upload_date": upload_date,
        "duration": duration,
        "webpage_url": url,
        "extractor_key": "Douyin",
        "view_count": int(stats.get("play_count") or 0),
        "like_count": int(stats.get("digg_count") or 0),
        "comment_count": int(stats.get("comment_count") or 0),
        "tags": tags,
    }
    log.info("Evil0ctal 兜底成功: %s (%s)", (desc or aweme_id)[:50], aweme_id)
    return RawDownload(
        ok=True,
        engine="evil0ctal",
        info=info,
        media_path=media,
        thumbnail_path=thumbnail_path,
        temp_dir=temp_dir,
    )
