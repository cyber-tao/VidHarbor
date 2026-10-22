"""后处理管线：ffprobe 探测 → 统一 faststart MP4（remux 优先）→ 规范命名 → 元数据/字幕入库。"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from ..config import Settings
from ..models import DownloadTask, Subtitle, Tag, Video
from ..naming import build_filename, build_relpath
from .options import EffectiveOptions, equivalent_source_ids
from .ytdlp import DownloadCancelled, RawDownload

log = logging.getLogger("vidharbor.postprocess")

KNOWN_PLATFORMS = {"youtube", "bilibili", "tiktok", "douyin"}

# yt-dlp info 中只对本次下载有意义的数据：带签名会过期的地址、全部格式/分片清单、
# 字幕与缩略图地址等。入库后没有用处，却占 raw_metadata 的绝大部分体积（YouTube 单条数百 KB）
_TRANSIENT_INFO_KEYS = frozenset({
    "formats", "requested_formats", "requested_downloads", "requested_subtitles",
    "thumbnails", "subtitles", "automatic_captions", "heatmap",
    "http_headers", "fragments", "url", "manifest_url",
})


def archived_metadata(info: dict) -> str:
    kept = {k: v for k, v in info.items()
            if k not in _TRANSIENT_INFO_KEYS and not k.startswith("_")}
    return json.dumps(kept, ensure_ascii=False, default=str)


def _run_ffmpeg(cmd: list[str], cancel: threading.Event | None = None, timeout: int = 7200) -> None:
    """跑 ffmpeg 子进程：取消/超时立即 kill，失败抛 RuntimeError。

    stderr 落临时文件而不是 PIPE——轮询期间没人读管道，输出多了会撑爆缓冲区死锁。
    """
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as errf:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=errf)
        start = time.monotonic()
        while p.poll() is None:
            if cancel is not None and cancel.is_set():
                p.kill()
                p.wait()
                raise DownloadCancelled()
            if time.monotonic() - start > timeout:
                p.kill()
                p.wait()
                raise RuntimeError(f"ffmpeg 超时（>{timeout}s）已终止")
            time.sleep(0.5)
        code = p.returncode
        errf.seek(0)
        err = errf.read()
    if code != 0:
        raise RuntimeError(f"ffmpeg 失败: {err[-800:]}")


class _Limiter:
    """可动态调上限的信号量：上限改小不影响在跑的，超出的线程排队等待。"""

    def __init__(self, limit: int = 1) -> None:
        self._limit = max(1, int(limit))
        self._used = 0
        self._cond = threading.Condition()

    def set_limit(self, limit: int) -> None:
        with self._cond:
            new = max(1, int(limit))
            if new == self._limit:
                return
            self._limit = new
            self._cond.notify_all()

    @contextmanager
    def slot(self, cancel: threading.Event | None = None):
        with self._cond:
            while self._used >= self._limit:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                self._cond.wait(timeout=0.5)
            self._used += 1
        try:
            yield
        finally:
            with self._cond:
                self._used -= 1
                self._cond.notify()


# 全局转码限流：转码很吃 CPU/GPU，多个任务同时下载完也只允许 N 个同时转码
_transcode_limiter = _Limiter(1)


def set_transcode_limit(limit: int) -> None:
    _transcode_limiter.set_limit(limit)


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


def ensure_mp4(
    src: Path, out_dir: Path, video_codec: str = "h264", hw_encoder: str = "auto",
    cancel: threading.Event | None = None,
) -> tuple[Path, str]:
    """统一为 faststart MP4。目标编码匹配 + AAC → 无损 remux；否则转码。

    - 目标 h264：H.264+AAC remux；其余转码 libx264 CRF18。
    - 目标 h265：HEVC+AAC remux（补 hvc1 tag）；其余按探测到的编码器转码（硬件优先）。
    """
    from .encoders import ENCODER_ARGS, detect_hevc_encoder

    probe = run_ffprobe(src)
    streams = probe.get("streams") or []
    v = _first_stream(probe, "video")
    a = _first_stream(probe, "audio")
    if v is None:
        raise ValueError("文件中没有视频流（可能是纯音频或图集，暂不支持入库）")

    src_vcodec = str(v.get("codec_name") or "")
    target = "h265" if video_codec == "h265" else "h264"

    need_transcode = False
    args: list[str] = []
    if target == "h265":
        if src_vcodec in ("hevc", "h265"):
            args += ["-c:v", "copy", "-tag:v", "hvc1"]
        else:
            encoder = detect_hevc_encoder(hw_encoder)
            need_transcode = True
            args += ENCODER_ARGS[encoder] + ["-tag:v", "hvc1"]
    else:
        if src_vcodec == "h264":
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
    if need_transcode:
        # 全局转码限流：占满时在此排队（取消可立即退出队列）；转码中取消会立即 kill ffmpeg
        with _transcode_limiter.slot(cancel=cancel):
            _run_ffmpeg(cmd, cancel=cancel)
    else:
        _run_ffmpeg(cmd, cancel=cancel)
    if not out.exists():
        raise RuntimeError("ffmpeg 失败: 没有生成输出文件")
    action = "transcode" if need_transcode else "remux"
    log.info("后处理完成: %s → %s (%s, 目标=%s)", src.name, out.name, action, target)
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
    raw: RawDownload, task: DownloadTask, session, settings: Settings,
    eff: EffectiveOptions | None = None, cancel: threading.Event | None = None,
) -> tuple[Video, bool]:
    """下载结果统一入库。若平台+视频 ID 已存在则直接返回已有条目（返回 created=False）。"""
    info = raw.info or {}
    platform = _resolve_platform(task, info)
    source_id = str(info.get("id") or "").strip()
    if not source_id:
        raise ValueError("视频缺少 id，无法入库")

    same_video = (Video.platform == platform) & Video.source_id.in_(
        equivalent_source_ids(platform, source_id))
    existing = session.query(Video).filter(same_video).first()
    if existing is not None:
        log.info("库中已存在 [%s] %s，跳过重复入库", platform, existing.source_id)
        return existing, False

    codec = eff.codec if eff else settings.library.video_codec
    final, action = ensure_mp4(raw.media_path, raw.temp_dir / "out", codec,
                               settings.library.hw_encoder, cancel=cancel)
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

    def rel(p: Path) -> str:
        return p.resolve().relative_to(settings.library_root.resolve()).as_posix()

    # 文件先移入库目录、事务后提交：提交失败必须回收已移动文件，
    # 否则留下无 DB 记录的孤儿文件（如并发下载撞 uq_video_platform_source）
    moved: list[Path] = []
    try:
        shutil.move(str(final), str(target))
        moved.append(target)

        thumbnail_rel = ""
        if raw.thumbnail_path and raw.thumbnail_path.exists():
            ext = raw.thumbnail_path.suffix.lower() or ".jpg"
            t_target = target.with_name(f"{target.stem}{ext}")
            shutil.move(str(raw.thumbnail_path), str(t_target))
            moved.append(t_target)
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
            raw_metadata=archived_metadata(info),
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
            content = srt.read_text(encoding="utf-8-sig", errors="replace")
            shutil.move(str(srt), str(s_target))
            moved.append(s_target)
            session.add(Subtitle(
                video_id=video.id, lang=lang, auto_generated=auto,
                format="srt", content=content, file_path=rel(s_target),
            ))
            log.info("字幕入库: %s [%s%s]", target.stem[:40], lang, " 自动" if auto else "")

        for tname in (info.get("tags") or [])[:12]:
            if isinstance(tname, str) and tname.strip():
                session.add(Tag(video_id=video.id, name=tname.strip()[:64]))

        session.commit()
    except Exception:
        session.rollback()
        for p in moved:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                log.warning("入库失败后回收文件未成功: %s", p)
        try:
            if target_dir.is_dir() and not any(target_dir.iterdir()):
                target_dir.rmdir()
        except OSError:
            pass
        # 并发下载同视频时唯一约束冲突：此时库中已有同 ID 条目，按"已存在"收敛
        winner = session.query(Video).filter(same_video).first()
        if winner is not None:
            log.info("入库提交失败但库中已有 [%s] %s，关联现有条目", platform, source_id)
            return winner, False
        raise
    log.info(
        "入库: [%s] %s → %s (%s, %.1f MB)",
        platform, video.title[:50], rel(target), action, video.file_size / 1_048_576,
    )
    return video, True
