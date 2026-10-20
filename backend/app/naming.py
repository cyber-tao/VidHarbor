"""规范命名：模板渲染 + 各平台文件名非法字符清洗（Windows 兼容）。"""
from __future__ import annotations

import re

INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
WS = re.compile(r"\s+")


def sanitize(text: str | None, max_len: int, fallback: str) -> str:
    if not text:
        return fallback
    s = INVALID_CHARS.sub(" ", str(text))
    s = WS.sub(" ", s).strip(" .")
    if not s:
        return fallback
    return s[:max_len].rstrip(" .") or fallback


def sanitize_date(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[:8] if len(digits) >= 8 else "undated"


def build_filename(template: str, platform: str, uploader: str, upload_date: str,
                   title: str, video_id: str) -> str:
    fields = {
        "platform": sanitize(platform, 32, "other"),
        "uploader": sanitize(uploader, 80, "unknown"),
        "upload_date": sanitize_date(upload_date),
        "title": sanitize(title, 120, "untitled"),
        "id": sanitize(video_id, 64, "na"),
    }
    try:
        name = template.format(**fields)
    except (KeyError, IndexError, ValueError):
        name = "{upload_date} - {title} [{id}]".format(**fields)
    return sanitize(name, 190, "untitled")


def build_relpath(platform: str, uploader: str) -> str:
    """相对 videos_dir 的子目录：{platform}/{uploader}。"""
    p = sanitize(platform, 32, "other").replace(" ", "_").lower()
    u = sanitize(uploader, 80, "unknown").strip()
    return f"{p}/{u}"
