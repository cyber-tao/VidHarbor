"""yt-dlp 引擎封装：单视频下载 + 元数据 + 字幕 + 缩略图 + 进度钩子。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp

from ..config import Settings
from .options import EffectiveOptions, build_format_selector, resolve_options

log = logging.getLogger("vidharbor.ytdlp")

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".flv", ".ts", ".m4v", ".avi"}
THUMB_EXTS = (".jpg", ".jpeg", ".webp", ".png")


class DownloadCancelled(Exception):
    """用户取消任务。"""


@dataclass
class RawDownload:
    ok: bool
    engine: str = "yt-dlp"
    info: dict = field(default_factory=dict)
    media_path: Path | None = None
    subtitle_files: list[Path] = field(default_factory=list)
    thumbnail_path: Path | None = None
    temp_dir: Path | None = None
    error: str = ""


class _YtdlpLogger:
    def debug(self, msg: str) -> None:
        log.debug("%s", msg)

    def info(self, msg: str) -> None:
        log.debug("%s", msg)

    def warning(self, msg: str) -> None:
        log.warning("%s", msg)

    def error(self, msg: str) -> None:
        log.error("%s", msg)


def _fmt_speed(bps) -> str:
    if not bps:
        return ""
    mb = bps / 1_000_000
    return f"{mb:.2f} MB/s" if mb >= 1 else f"{bps / 1000:.0f} KB/s"


def _fmt_eta(sec) -> str:
    if sec is None or sec < 0:
        return ""
    sec = int(sec)
    if sec >= 3600:
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    return f"{sec // 60:02d}:{sec % 60:02d}"


def ytdlp_download(
    url: str,
    settings: Settings,
    temp_dir: Path,
    on_progress: Callable[[float, str, str], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
    cancel_event=None,
    eff: EffectiveOptions | None = None,
    platform: str = "",
) -> RawDownload:
    """下载单个视频。成功返回媒体文件/字幕/缩略图；失败返回 error。取消抛 DownloadCancelled。"""

    def hook(d: dict) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled()
        if on_progress is None:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            on_progress(done / total if total else 0.0, _fmt_speed(d.get("speed")), _fmt_eta(d.get("eta")))
        elif d.get("status") == "finished":
            on_progress(1.0, "", "")

    def pp_hook(d: dict) -> None:
        if d.get("status") == "started" and on_stage is not None:
            on_stage("merging")

    if eff is None:
        eff = resolve_options(settings, None)
    opts: dict = {
        "format": build_format_selector(eff),
        "merge_output_format": "mp4",
        "outtmpl": {"default": str(temp_dir / "%(id)s.%(ext)s")},
        "writeinfojson": True,
        "writethumbnail": True,
        "writesubtitles": True,
        "writeautomaticsubs": True,
        "subtitleslangs": list(eff.sub_langs),
        "convertsubs": "srt",
        "progress_hooks": [hook],
        "postprocessor_hooks": [pp_hook],
        "noplaylist": True,
        # B站分P等 anthology 不受 noplaylist 拦截（URL 无 list 参数，extractor 直接返回
        # playlist），显式只取第 1 P，与下方 entries[0] 的单视频模型一致
        "playlist_items": "1",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "logger": _YtdlpLogger(),
    }
    cookies = settings.cookie_file_for(platform) if platform else settings.cookies_path
    if cookies:
        opts["cookiefile"] = str(cookies)
    if platform:
        proxy = settings.proxy_for(platform)
        if proxy:
            opts["proxy"] = proxy

    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadCancelled:
        raise
    except yt_dlp.utils.DownloadError as e:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled() from e
        return RawDownload(ok=False, error=str(e).strip()[:2000], temp_dir=temp_dir)
    except Exception as e:  # noqa: BLE001
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled() from e
        return RawDownload(ok=False, error=f"{type(e).__name__}: {e}", temp_dir=temp_dir)

    if not info:
        return RawDownload(ok=False, error="未获取到视频信息", temp_dir=temp_dir)
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            return RawDownload(ok=False, error="播放列表为空", temp_dir=temp_dir)
        info = entries[0]

    media: Path | None = None
    for rd in info.get("requested_downloads") or []:
        fp = rd.get("filepath")
        if fp and Path(fp).suffix.lower() in VIDEO_EXTS and Path(fp).exists():
            media = Path(fp)
            break

    subs = sorted(temp_dir.glob("*.srt"))
    thumb = next((p for p in sorted(temp_dir.iterdir()) if p.suffix.lower() in THUMB_EXTS), None)

    if media is None:
        return RawDownload(
            ok=False,
            info=info,
            temp_dir=temp_dir,
            thumbnail_path=thumb,
            error="未找到下载的视频文件（可能是图集/纯音频作品，暂不支持）",
        )
    return RawDownload(
        ok=True,
        info=info,
        media_path=media,
        subtitle_files=subs,
        thumbnail_path=thumb,
        temp_dir=temp_dir,
    )
