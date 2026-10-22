"""下载选项：设置页默认值 + 任务级覆盖 → yt-dlp 格式选择器；URL → source_id 解析（入库前去重）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..config import Settings


class DownloadOptions(BaseModel):
    """任务级下载选项；None 字段表示沿用全局设置。"""

    max_height: int | None = Field(default=None, ge=0, le=4320)
    audio_langs: list[str] | None = None
    sub_langs: list[str] | None = None
    codec: str | None = None  # "h264" | "h265"


@dataclass
class EffectiveOptions:
    max_height: int = 1080
    audio_langs: list[str] = field(default_factory=list)
    sub_langs: list[str] = field(default_factory=lambda: [
        # 锚定标准语言码：`zh.*` 这类宽松正则在 YouTube 会命中几十条
        # "zh-Hans-xx（中文翻译自xx语）"自动翻译字幕，逐条下载触发 429 限流后全部失败
        r"^zh(-CN|-Hans|-Hant|-TW|-HK)?$",
        r"^en(-US|-GB)?$",
    ])
    codec: str = "h265"

    def summary(self) -> str:
        h = f"{self.max_height}p" if self.max_height else "不限"
        parts = [h, self.codec]
        if self.audio_langs:
            parts.append("音轨:" + ",".join(self.audio_langs))
        return " / ".join(parts)


def resolve_options(settings: "Settings", options: DownloadOptions | None) -> EffectiveOptions:
    d = settings.download
    codec = (options.codec if options and options.codec else settings.library.video_codec) or "h265"
    return EffectiveOptions(
        max_height=(options.max_height if options and options.max_height is not None else d.max_height) or 0,
        audio_langs=list((options.audio_langs if options and options.audio_langs is not None else d.audio_langs) or []),
        sub_langs=list((options.sub_langs if options and options.sub_langs is not None else d.sub_langs) or []),
        codec="h264" if codec == "h264" else "h265",
    )


def parse_options_json(raw: str | None) -> DownloadOptions | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return DownloadOptions(**data) if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _audio_selector(audio_langs: list[str]) -> str:
    """单条首选音轨：按语言偏好择优，均无匹配回退任意 ba。

    每档优先 AAC（mp4a）：B站 Hi-Res(FLAC)/杜比全景声等音轨虽常封装在 m4s/m4a 容器里，
    但非 AAC 编码无法直接 copy 进 MP4 容器，合并阶段会以
    "Postprocessing: Stream copy" 失败收场。"""
    langs = [re.escape(l.strip()) for l in audio_langs if l and l.strip()]
    if not langs:
        return "(ba[acodec^=mp4a]/ba)"
    cands = [f"ba[language~={l}][acodec^=mp4a]" for l in langs]
    cands += [f"ba[language~={l}][ext=m4a]" for l in langs]
    cands += [f"ba[language~={l}]" for l in langs]
    cands += ["ba[acodec^=mp4a]", "ba"]
    return "(" + "/".join(cands) + ")"


def build_format_selector(eff: EffectiveOptions) -> str:
    """构造 yt-dlp -f 表达式：清晰度上限 + 目标编码偏好（h265 优先抓 HEVC 源免转码）+ 音轨语言。

    HEVC 匹配同时兼容 `vcodec^=hevc` 与 `vcodec^=hvc1`：B站的 HEVC 流 codec tag 是
    hvc1（如 hvc1.1.6.L150），只写 hevc 前缀在 B站从不命中，导致本可 remux 直存的
    HEVC 源退到 AVC 链全量转码。"""
    h = f"[height<={eff.max_height}]" if eff.max_height > 0 else ""
    audio = _audio_selector(eff.audio_langs)
    hevc = "(bv*[vcodec^=hevc]/bv*[vcodec^=hvc1])"
    hevc_single = "(b[vcodec^=hevc]/b[vcodec^=hvc1])"
    if eff.codec == "h265":
        chains = [
            f"{hevc}{h}+{audio}",
            f"{hevc_single}{h}",
            f"bv*[vcodec^=avc1][ext=mp4]{h}+{audio}",
            f"b[vcodec^=avc1][ext=mp4]{h}",
            f"bv*{h}+{audio}",
            f"b{h}",
        ]
    else:
        chains = [
            f"bv*[vcodec^=avc1][ext=mp4]{h}+{audio}",
            f"b[vcodec^=avc1][ext=mp4]{h}",
            f"bv*[ext=mp4]{h}+{audio}",
            f"bv*{h}+{audio}",
            f"b{h}",
        ]
    return "/".join(chains)


# ---- URL → source_id（下载前查库去重，避免重复下载整个视频） ----

_BILI_RE = re.compile(r"(?:/video/)?(BV[0-9A-Za-z]{10})(?:/|\?|$)|/video/av(\d+)", re.IGNORECASE)
_YT_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/|/live/)([0-9A-Za-z_-]{11})(?:[?&/]|$)")
_DY_TT_RE = re.compile(r"/video/(\d+)")

_SOURCE_PARSERS = {
    "bilibili": lambda u: next((m for m in _BILI_RE.search(u).groups() if m), "") if _BILI_RE.search(u) else "",
    "youtube": lambda u: (_YT_RE.search(u).group(1) if _YT_RE.search(u) else ""),
    "douyin": lambda u: (_DY_TT_RE.search(u).group(1) if _DY_TT_RE.search(u) else ""),
    "tiktok": lambda u: (_DY_TT_RE.search(u).group(1) if _DY_TT_RE.search(u) else ""),
}


def parse_source_id(platform: str, url: str) -> str:
    """从 URL 解析平台视频 id；无法解析返回空串。短链（b23.tv 等）无法解析。"""
    parser = _SOURCE_PARSERS.get(platform)
    if not parser:
        return ""
    try:
        return str(parser(url or "")).strip()
    except Exception:  # noqa: BLE001
        return ""
