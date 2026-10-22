"""视频库 API：浏览/搜索/详情/流式播放(Range)/字幕(VTT)/缩略图/删除。"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import defer, selectinload

from ..config import get_settings
from ..db import get_sessionmaker
from ..downloader.postprocess import srt_to_vtt
from ..events import bus
from ..models import DownloadTask, Subtitle, Tag, Video, iso_utc

log = logging.getLogger("vidharbor.api.videos")
router = APIRouter()


def _unlink_retry(p: Path, tries: int = 5, delay: float = 0.4) -> bool:
    """Windows 下流式播放可能短暂占用文件句柄，短暂重试后再放弃。"""
    for i in range(tries):
        try:
            if p.exists():
                p.unlink()
            return True
        except OSError:
            if i == tries - 1:
                return False
            time.sleep(delay)
    return False


def _video_dict(v: Video, subtitles_count: int, detail: bool = False) -> dict:
    d = {
        "id": v.id, "platform": v.platform, "source_id": v.source_id, "url": v.url,
        "title": v.title, "uploader": v.uploader, "upload_date": v.upload_date,
        "duration": v.duration, "file_size": v.file_size,
        "width": v.width, "height": v.height, "fps": v.fps,
        "vcodec": v.vcodec, "acodec": v.acodec,
        "view_count": v.view_count, "like_count": v.like_count,
        "has_thumbnail": bool(v.thumbnail_path),
        "subtitles_count": subtitles_count,
        "tags": [t.name for t in v.tags],
        "created_at": iso_utc(v.created_at),
    }
    if detail:
        d["description"] = v.description
        d["video_path"] = v.video_path
        d["subtitles"] = [
            {"id": s.id, "lang": s.lang, "auto_generated": s.auto_generated, "format": s.format}
            for s in v.subtitles
        ]
        settings = get_settings()
        p = settings.library_root / v.video_path
        d["file_exists"] = p.exists()
        if v.video_path:
            try:
                d["absolute_path"] = str(p.resolve())
            except OSError:
                d["absolute_path"] = str(p)
        else:
            d["absolute_path"] = ""
    return d


@router.get("/api/videos")
def list_videos(
    q: str = "", platform: str = "", tag: str = "",
    page: int = 1, page_size: int = 48,
):
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    sm = get_sessionmaker()
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(
            Video.title.like(like),
            Video.uploader.like(like),
            Video.description.like(like),
        ))
    if platform:
        filters.append(Video.platform == platform)
    # 支持逗号分隔多标签（AND 语义）
    for tname in [t.strip() for t in tag.split(",") if t.strip()]:
        filters.append(Video.tags.any(Tag.name == tname))
    with sm() as session:
        total = session.query(func.count(Video.id)).filter(*filters).scalar() or 0
        # 列表用不到的大字段不加载；标签一次性预取，字幕只要条数（不能为计数加载 SRT 全文）
        rows = (
            session.query(Video)
            .options(defer(Video.raw_metadata), defer(Video.description),
                     selectinload(Video.tags))
            .filter(*filters)
            .order_by(Video.created_at.desc(), Video.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        sub_counts = dict(
            session.query(Subtitle.video_id, func.count(Subtitle.id))
            .filter(Subtitle.video_id.in_([v.id for v in rows]))
            .group_by(Subtitle.video_id)
            .all()
        ) if rows else {}
        return {"total": total, "page": page, "page_size": page_size,
                "items": [_video_dict(v, sub_counts.get(v.id, 0)) for v in rows]}


@router.get("/api/tags")
def list_tags(platform: str = "", q: str = ""):
    """标签聚合（按视频数排序），供视频库筛选条使用。"""
    sm = get_sessionmaker()
    with sm() as session:
        query = (
            session.query(Tag.name, func.count(Tag.id).label("count"))
            .join(Video, Video.id == Tag.video_id)
            .group_by(Tag.name)
        )
        if platform:
            query = query.filter(Video.platform == platform)
        if q:
            query = query.filter(Tag.name.like(f"%{q}%"))
        rows = query.order_by(func.count(Tag.id).desc(), Tag.name.asc()).limit(200).all()
        return {"tags": [{"name": name, "count": count} for name, count in rows]}


@router.get("/api/videos/{video_id}")
def video_detail(video_id: int):
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        return _video_dict(v, len(v.subtitles), detail=True)


def _safe_exists(path) -> bool:
    """exists() 在个别挂载卷上可能直接抛 OSError（如 Windows 宿主卷超长路径 ENAMETOOLONG），按不存在处理。"""
    try:
        return path.exists()
    except OSError:
        return False


@router.get("/api/videos/{video_id}/file")
def video_file(video_id: int):
    """播放/拖动进度：FileResponse 自带 Range 支持（单段、后缀 bytes=-N、多段、416）。"""
    settings = get_settings()
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        path = settings.library_root / v.video_path
    if not _safe_exists(path):
        raise HTTPException(status_code=410, detail="视频文件缺失")
    return FileResponse(path, media_type="video/mp4")


@router.get("/api/videos/{video_id}/thumbnail")
def video_thumbnail(video_id: int):
    settings = get_settings()
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None or not v.thumbnail_path:
            raise HTTPException(status_code=404, detail="无缩略图")
        path = settings.library_root / v.thumbnail_path
    if not _safe_exists(path):
        raise HTTPException(status_code=404, detail="无缩略图")
    return FileResponse(path)


@router.get("/api/videos/{video_id}/subtitles/{sub_id}")
def subtitle_content(video_id: int, sub_id: int):
    sm = get_sessionmaker()
    with sm() as session:
        s = session.get(Subtitle, sub_id)
        if s is None or s.video_id != video_id:
            raise HTTPException(status_code=404, detail="字幕不存在")
        return PlainTextResponse(s.content, media_type="text/plain; charset=utf-8")


@router.get("/api/videos/{video_id}/subtitles/{sub_id}/vtt")
def subtitle_vtt(video_id: int, sub_id: int):
    sm = get_sessionmaker()
    with sm() as session:
        s = session.get(Subtitle, sub_id)
        if s is None or s.video_id != video_id:
            raise HTTPException(status_code=404, detail="字幕不存在")
        return PlainTextResponse(
            srt_to_vtt(s.content), media_type="text/vtt; charset=utf-8"
        )


@router.delete("/api/videos/{video_id}")
def delete_video(video_id: int, delete_files: bool = True):
    settings = get_settings()
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        rel_files = [v.video_path, v.thumbnail_path] + [s.file_path for s in v.subtitles]
        title = v.title
        session.query(DownloadTask).filter(DownloadTask.video_id == v.id).update(
            {"video_id": None}
        )
        session.delete(v)
        session.commit()
    removed = 0
    failed: list[str] = []
    if delete_files:
        for rel in rel_files:
            if not rel:
                continue
            p = settings.library_root / rel
            if not p.exists():
                continue
            if _unlink_retry(p):
                removed += 1
            else:
                failed.append(str(p))
                log.warning("删除文件失败（可能仍被占用）: %s", p)
        # 清理空目录
        for rel in {str(Path(r).parent) for r in rel_files if r}:
            d = settings.library_root / rel
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass
    log.info("删除视频 [%s] %s（清理 %d 个文件%s）", video_id, title[:50], removed,
             f"，{len(failed)} 个失败" if failed else "")
    bus.mark_stats_dirty()
    return {"deleted": True, "files_removed": removed, "files_failed": len(failed)}
