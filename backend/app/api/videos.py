"""视频库 API：浏览/搜索/详情/流式播放(Range)/字幕(VTT)/缩略图/删除。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import or_

from ..config import get_settings
from ..db import get_sessionmaker
from ..downloader.postprocess import srt_to_vtt
from ..events import bus
from ..models import DownloadTask, Subtitle, Tag, Video

log = logging.getLogger("vidlib.api.videos")
router = APIRouter()

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _video_dict(v: Video, detail: bool = False) -> dict:
    d = {
        "id": v.id, "platform": v.platform, "source_id": v.source_id, "url": v.url,
        "title": v.title, "uploader": v.uploader, "upload_date": v.upload_date,
        "duration": v.duration, "file_size": v.file_size,
        "width": v.width, "height": v.height, "fps": v.fps,
        "vcodec": v.vcodec, "acodec": v.acodec,
        "view_count": v.view_count, "like_count": v.like_count,
        "has_thumbnail": bool(v.thumbnail_path),
        "subtitles_count": len(v.subtitles),
        "tags": [t.name for t in v.tags],
        "created_at": v.created_at.isoformat() if v.created_at else None,
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
    return d


@router.get("/api/videos")
def list_videos(
    q: str = "", platform: str = "", tag: str = "",
    page: int = 1, page_size: int = 48,
):
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    sm = get_sessionmaker()
    with sm() as session:
        query = session.query(Video)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(
                Video.title.like(like),
                Video.uploader.like(like),
                Video.description.like(like),
            ))
        if platform:
            query = query.filter(Video.platform == platform)
        if tag:
            query = query.filter(Video.tags.any(Tag.name == tag))
        total = query.count()
        rows = (
            query.order_by(Video.created_at.desc(), Video.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "page": page, "page_size": page_size,
                "items": [_video_dict(v) for v in rows]}


@router.get("/api/videos/{video_id}")
def video_detail(video_id: int):
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        return _video_dict(v, detail=True)


@router.get("/api/videos/{video_id}/file")
def video_file(video_id: int, request: Request):
    settings = get_settings()
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        path = settings.library_root / v.video_path
    if not path.exists():
        raise HTTPException(status_code=410, detail="视频文件缺失")
    size = path.stat().st_size
    range_header = request.headers.get("range")
    start, end = 0, size - 1
    status_code = 200
    headers = {"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}

    if range_header:
        m = RANGE_RE.match(range_header)
        if m:
            s_str, e_str = m.groups()
            start = int(s_str) if s_str else 0
            end = int(e_str) if e_str else size - 1
            end = min(end, size - 1)
            if start > end or start >= size:
                return StreamingResponse(iter(()), status_code=416,
                                         headers={"Content-Range": f"bytes */{size}"})
            status_code = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)

    def iter_file():
        remaining = end - start + 1
        with path.open("rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(iter_file(), status_code=status_code, headers=headers)


@router.get("/api/videos/{video_id}/thumbnail")
def video_thumbnail(video_id: int):
    settings = get_settings()
    sm = get_sessionmaker()
    with sm() as session:
        v = session.get(Video, video_id)
        if v is None or not v.thumbnail_path:
            raise HTTPException(status_code=404, detail="无缩略图")
        path = settings.library_root / v.thumbnail_path
    if not path.exists():
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
    if delete_files:
        for rel in rel_files:
            if not rel:
                continue
            p = settings.library_root / rel
            try:
                if p.exists():
                    p.unlink()
                    removed += 1
            except OSError as e:
                log.warning("删除文件失败 %s: %s", p, e)
        # 清理空目录
        for rel in {str(Path(r).parent) for r in rel_files if r}:
            d = settings.library_root / rel
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass
    log.info("删除视频 [%s] %s（清理 %d 个文件）", video_id, title[:50], removed)
    bus.mark_stats_dirty()
    return {"deleted": True, "files_removed": removed}
