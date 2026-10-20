"""后处理管线：ffprobe 探测 → 统一 faststart MP4（remux 优先）→ 规范命名 → 元数据/字幕入库。"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from ..config import Settings
from ..models import DownloadTask, Subtitle, Tag, Video
from ..naming import build_filename, build_relpath
from .ytdlp import RawDownload

log = logging.getLogger("vidlib.postprocess")

KNOWN_PLATFORMS = {"youtube", "bilibili", "tiktok", "douyin"}


def run_ffprobe(path: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {(p.stderr or '')[-500:]}")
    return json.loads(p.stdout or "{}")


def _first_stream(probe: dict, codec_type: str) -> dict | None:
    for s in probe.get("streams") or []:
        if s.get("codec_type") == codec_type:
            return s
    return None


def parse_fps(rate: str | None) -> float:
    try:
        if rate and "/" in rate:
            num, den = rate.split("/", 1)
            return round(float(num) / float(den), 3) if float(den) else 0.0
        return round(float(rate), 3)
    except (ValueError, TypeError):
        return 0.0


def ensure_mp4(src: Path, out_dir: Path) -> tuple[Path, str]:
    """统一为 faststart MP4。H.264+AAC 无损 remux；否则转码 libx264 CRF18 + AAC 192k。"""
    probe = run_ffprobe(src)
    streams = probe.get("streams") or []
    v = _first_stream(probe, "video")
    a = _first_stream(probe, "audio")
    if v is None:
        raise ValueError("文件中没有视频流（可能是纯音频或图集，暂不支持入库）")

    need_transcode = False
    args: list[str] = []
    if v.get("codec_name") == "h264":
        args += ["-c:v", "copy"]
    else:
        need_transcode = True
        args += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"]
    if a is None:
        args += ["-an"]
    elif a.get("codec_name") == "aac":
        args += ["-c:a", "copy"]
    else:
        need_transcode = True
        args += ["-c:a", "aac", "-b:a", "192k"]

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "final.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), *args,
           "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200)
    if p.returncode != 0 or not out.exists():
        raise RuntimeError(f"ffmpeg 失败: {(p.stderr or '')[-800:]}")
    action = "transcode" if need_transcode else "remux"
    log.info("后处理完成: %s → %s (%s)", src.name, out.name, action)
    return out, action


SRT_LANG_RE = re.compile(r"\.([A-Za-z0-9\-_]{2,20})\.srt$", re.IGNORECASE)


def _lang_of(path: Path) -> str:
    m = SRT_LANG_RE.search(path.name)
    return m.group(1) if m else "und"


def _norm_lang(x: str) -> str:
    return x.lower().replace("_", "-").split("-")[0]


def _is_auto(lang: str, info: dict) -> bool:
    manuals = info.get("subtitles") or {}
    if any(_norm_lang(k) == _norm_lang(lang) for k in manuals):
        return False
    autos = info.get("automatic_captions") or {}
    return any(_norm_lang(k) == _norm_lang(lang) for k in autos)


def srt_to_vtt(content: str) -> str:
    lines = [line.replace(",", ".") if "-->" in line else line for line in content.splitlines()]
    return "WEBVTT\n\n" + "\n".join(lines) + "\n"


def _resolve_platform(task: DownloadTask, info: dict) -> str:
    if task.platform in KNOWN_PLATFORMS:
        return task.platform
    key = str(info.get("extractor_key") or "").lower()
    if key in KNOWN_PLATFORMS:
        return key
    return "other"


def ingest(
    raw: RawDownload, task: DownloadTask, session, settings: Settings
) -> tuple[Video, bool]:
    """下载结果统一入库。若平台+视频 ID 已存在则直接返回已有条目（返回 created=False）。"""
    info = raw.info or {}
    platform = _resolve_platform(task, info)
    source_id = str(info.get("id") or "").strip()
    if not source_id:
        raise ValueError("视频缺少 id，无法入库")

    existing = session.query(Video).filter_by(platform=platform, source_id=source_id).first()
    if existing is not None:
        log.info("库中已存在 [%s] %s，跳过重复入库", platform, source_id)
        return existing, False

    final, action = ensure_mp4(raw.media_path, raw.temp_dir / "out")
    probe = run_ffprobe(final)
    v = _first_stream(probe, "video") or {}
    a = _first_stream(probe, "audio") or {}
    fmt = probe.get("format") or {}

    uploader = str(info.get("uploader") or info.get("channel") or "")
    upload_date = str(info.get("upload_date") or "")
    rel_dir = build_relpath(platform, uploader)
    filename = build_filename(
        settings.library.name_template, platform, uploader, upload_date,
        str(info.get("title") or ""), source_id,
    )
    target_dir = settings.videos_dir / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{filename}.mp4"
    n = 2
    while target.exists():
        target = target_dir / f"{filename} ({n}).mp4"
        n += 1
    shutil.move(str(final), str(target))

    def rel(p: Path) -> str:
        return p.resolve().relative_to(settings.library_root.resolve()).as_posix()

    thumbnail_rel = ""
    if raw.thumbnail_path and raw.thumbnail_path.exists():
        ext = raw.thumbnail_path.suffix.lower() or ".jpg"
        t_target = target.with_name(f"{target.stem}{ext}")
        shutil.move(str(raw.thumbnail_path), str(t_target))
        thumbnail_rel = rel(t_target)

    video = Video(
        platform=platform,
        source_id=source_id,
        url=str(info.get("webpage_url") or task.url),
        title=str(info.get("title") or source_id),
        uploader=uploader[:255],
        uploader_id=str(info.get("uploader_id") or info.get("channel_id") or "")[:255],
        upload_date=upload_date[:10],
        duration=float(fmt.get("duration") or info.get("duration") or 0),
        description=str(info.get("description") or "")[:20000],
        thumbnail_path=thumbnail_rel,
        video_path=rel(target),
        file_size=int(float(fmt.get("size") or 0)) or target.stat().st_size,
        width=int(v.get("width") or 0),
        height=int(v.get("height") or 0),
        fps=parse_fps(v.get("avg_frame_rate")),
        vcodec=str(v.get("codec_name") or ""),
        acodec=str(a.get("codec_name") or ""),
        view_count=int(info.get("view_count") or 0),
        like_count=int(info.get("like_count") or 0),
        raw_metadata=json.dumps(info, ensure_ascii=False, default=str),
    )
    session.add(video)
    session.flush()

    for srt in raw.subtitle_files:
        if not srt.exists():
            continue
        lang = _lang_of(srt)
        auto = _is_auto(lang, info)
        suffix = f"{lang}.auto" if auto else lang
        s_target = target.with_name(f"{target.stem}.{suffix}.srt")
        if s_target.exists():
            s_target.unlink()
        shutil.move(str(srt), str(s_target))
        content = srt.read_text(encoding="utf-8-sig", errors="replace")
        session.add(Subtitle(
            video_id=video.id, lang=lang, auto_generated=auto,
            format="srt", content=content, file_path=rel(s_target),
        ))
        log.info("字幕入库: %s [%s%s]", target.stem[:40], lang, " 自动" if auto else "")

    for tname in (info.get("tags") or [])[:12]:
        if isinstance(tname, str) and tname.strip():
            session.add(Tag(video_id=video.id, name=tname.strip()[:64]))

    session.commit()
    log.info(
        "入库: [%s] %s → %s (%s, %.1f MB)",
        platform, video.title[:50], rel(target), action, video.file_size / 1_048_576,
    )
    return video, True
