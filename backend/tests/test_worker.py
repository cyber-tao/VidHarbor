"""下载 worker（TaskQueue._run）状态机：同步跑单个任务，下载与入库全部打桩，不触网。"""
from __future__ import annotations

import threading

import pytest


@pytest.fixture
def run_task():
    """建一个 pending 任务并同步执行 _run，返回执行后的任务行；结束时清理任务行。"""
    from app.config import get_settings
    from app.db import get_sessionmaker
    from app.downloader import engine
    from app.models import DownloadTask

    sm = get_sessionmaker()
    created: list[int] = []

    def _run(url: str, platform: str, cancel: threading.Event | None = None) -> DownloadTask:
        with sm() as s:
            task = DownloadTask(url=url, platform=platform)
            s.add(task)
            s.commit()
            tid = task.id
        created.append(tid)
        q = engine.TaskQueue(get_settings())
        try:
            q.cancel_flags[tid] = cancel or threading.Event()
            q._running[tid] = platform
            q._run(tid)
        finally:
            q.executor.shutdown(wait=False)
        with sm() as s:
            return s.get(DownloadTask, tid)

    yield _run
    with sm() as s:
        for tid in created:
            row = s.get(DownloadTask, tid)
            if row is not None:
                s.delete(row)
        s.commit()


def _must_not_download(*a, **k):
    raise AssertionError("库中已有的视频不应再下载")


class TestAlreadyInLibrary:
    def test_anthology_url_without_p_matches_stored_p1(self, run_task, monkeypatch):
        """合集链接不带 p 时 yt-dlp 存为 BVxxx_p1：再次提交同一链接要在下载前直接完成。"""
        from app.db import get_sessionmaker
        from app.downloader import engine
        from app.models import DownloadTask, Video

        monkeypatch.setattr(engine, "ytdlp_download", _must_not_download)
        sm = get_sessionmaker()
        with sm() as s:
            video = Video(platform="bilibili", source_id="BV1WORKER001_p1")
            s.add(video)
            s.commit()
            vid = video.id
        try:
            task = run_task("https://www.bilibili.com/video/BV1WORKER001", "bilibili")
            assert task.status == "completed" and task.video_id == vid
            assert "已在库中" in task.error
        finally:
            with sm() as s:
                s.query(DownloadTask).filter(DownloadTask.video_id == vid).update({"video_id": None})
                s.delete(s.get(Video, vid))
                s.commit()
