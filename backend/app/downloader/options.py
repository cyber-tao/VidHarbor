"""下载选项：设置页默认值 + 任务级覆盖 → yt-dlp 格式选择器；URL → source_id 解析（入库前去重）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..config import Settings


class DownloadOptions(BaseModel):
    """任务级下载选项（手动提交与定时任务共用）；None 字段表示沿用全局设置。"""

    max_height: int | None = Field(default=None, ge=0, le=4320)
    audio_langs: list[str] | None = None
    sub_langs: list[str] | None = None
    codec: Literal["h264", "h265"] | None = None

    def to_json(self) -> str:
        """持久化到任务/定时任务：只存显式指定的项，空串表示全部沿用全局设置。"""
        data = self.model_dump(exclude_none=True)
        return json.dumps(data, ensure_ascii=False) if data else ""


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
    if h:
        # 竖屏视频（如 9:16 的 360x640）最小流的 height 也可能大于 max_height（如 360），
        # 所有带 height<= 的分支均不命中时回退到最低分辨率流，避免直接报 format not available
        chains += [f"wv*+{audio}", "w"]
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


def _bilibili_part(url: str) -> int:
    try:
        return int(parse_qs(urlsplit(url).query).get("p", ["1"])[0])
    except ValueError:
        return 1


def equivalent_source_ids(platform: str, source_id: str) -> list[str]:
    """同一视频在库里可能存成的 source_id（入库与下载前查重共用）。

    B站：yt-dlp 对带 ?p=N 的链接与多 P 合集给出 BVxxx_pN，单 P 视频不带 p 时给 BVxxx，
    因此单 P 视频的 BVxxx 与 BVxxx_p1 是同一个视频。
    """
    if platform == "bilibili" and source_id.startswith("BV"):
        base, _, part = source_id.partition("_p")
        if not part:
            return [source_id, f"{source_id}_p1"]
        if part == "1":
            return [source_id, base]
    return [source_id]


def source_id_candidates(platform: str, url: str) -> list[str]:
    """URL 在库里可能对应的 source_id（首项作规范去重键）；无法解析返回空列表。"""
    sid = parse_source_id(platform, url)
    if not sid:
        return []
    if platform == "bilibili" and sid.startswith("BV") and _bilibili_part(url) > 1:
        sid = f"{sid}_p{_bilibili_part(url)}"
    return equivalent_source_ids(platform, sid)
