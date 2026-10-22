"""下载 worker（TaskQueue._run）状态机：同步跑单个任务，下载与入库全部打桩，不触网。"""
from __future__ import annotations

import threading

import pytest


@pytest.fixture
def queue():
    from app.config import get_settings
    from app.downloader.engine import TaskQueue

    q = TaskQueue(get_settings())
    yield q
    q.executor.shutdown(wait=False)


@pytest.fixture
def run_task(queue):
    """建一个 pending 任务并同步执行 _run，返回执行后的任务行；结束时清理任务行。"""
    from app.db import get_sessionmaker
    from app.models import DownloadTask

    sm = get_sessionmaker()
    created: list[int] = []

    def _run(url: str, platform: str) -> DownloadTask:
        with sm() as s:
            task = DownloadTask(url=url, platform=platform)
            s.add(task)
            s.commit()
            tid = task.id
        created.append(tid)
        queue.cancel_flags[tid] = threading.Event()
        queue._running[tid] = platform
        queue._run(tid)
        with sm() as s:
            return s.get(DownloadTask, tid)

    yield _run
    with sm() as s:
        for tid in created:
            row = s.get(DownloadTask, tid)
            if row is not None:
                s.delete(row)
        s.commit()


@pytest.fixture
def fake_ingest(monkeypatch):
    """入库打桩：按下载结果的 info.id 建一条 Video；结束时解除任务关联并删除这些 Video。"""
    from app.db import get_sessionmaker
    from app.downloader import postprocess
    from app.models import DownloadTask, Video

    created: list[int] = []

    def _ingest(raw, task, session, settings, eff=None, cancel=None):
        video = Video(platform=task.platform, source_id=raw.info["id"])
        session.add(video)
        session.flush()
        created.append(video.id)
        return video, True

    monkeypatch.setattr(postprocess, "ingest", _ingest)
    yield
    sm = get_sessionmaker()
    with sm() as s:
        s.query(DownloadTask).filter(DownloadTask.video_id.in_(created)).update(
            {"video_id": None}, synchronize_session=False)
        for vid in created:
            s.delete(s.get(Video, vid))
        s.commit()


def _must_not_call(reason: str):
    def _fail(*a, **k):
        raise AssertionError(reason)
    return _fail


def _downloaded(source_id: str, engine: str = "yt-dlp"):
    from app.downloader.ytdlp import RawDownload

    return RawDownload(ok=True, engine=engine, info={"id": source_id})


def _failed(error: str, leftovers: list):
    """模拟失败的下载：在临时目录留下残片（记下目录以便断言已清理），返回失败结果。"""
    from app.downloader.ytdlp import RawDownload

    def _download(url, settings, temp_dir, *a, **kw):
        (temp_dir / "partial.mp4.part").write_bytes(b"x")
        leftovers.append(temp_dir)
        return RawDownload(ok=False, error=error)
    return _download


class TestAlreadyInLibrary:
    def test_anthology_url_without_p_matches_stored_p1(self, run_task, monkeypatch):
        """合集链接不带 p 时 yt-dlp 存为 BVxxx_p1：再次提交同一链接要在下载前直接完成。"""
        from app.db import get_sessionmaker
        from app.downloader import engine
        from app.models import DownloadTask, Video

        monkeypatch.setattr(engine, "ytdlp_download", _must_not_call("库中已有的视频不应再下载"))
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


class TestDownloadOutcome:
    def test_success_ingests_and_cleans_temp(self, run_task, fake_ingest, monkeypatch):
        from app.downloader import engine

        temp_dirs: list = []

        def fake_download(url, settings, temp_dir, on_progress, on_stage, cancel, **kw):
            (temp_dir / "media.mp4").write_bytes(b"x")
            temp_dirs.append(temp_dir)
            on_progress(0.5, "1.0MiB/s", "00:01")
            return _downloaded("workerok001")

        monkeypatch.setattr(engine, "ytdlp_download", fake_download)
        task = run_task("https://www.youtube.com/watch?v=workerok001", "youtube")
        assert task.status == "completed" and task.stage == "done" and task.progress == 1.0
        assert task.engine == "yt-dlp" and task.video_id is not None and task.error == ""
        assert not temp_dirs[0].exists()

    def test_failure_records_error_without_fallback(self, run_task, monkeypatch):
        """YouTube 失败不走 Evil0ctal（只兜底抖音/TikTok）：直接记失败原因并清理临时目录。"""
        from app.downloader import engine

        leftovers: list = []
        monkeypatch.setattr(engine, "ytdlp_download", _failed("ERROR: Video unavailable", leftovers))
        monkeypatch.setattr(engine, "evil0ctal_download", _must_not_call("YouTube 不应走兜底"))
        task = run_task("https://www.youtube.com/watch?v=workerfail1", "youtube")
        assert task.status == "failed" and task.error == "ERROR: Video unavailable"
        assert task.engine == "yt-dlp" and task.video_id is None
        assert not leftovers[0].exists()

    def test_ingest_exception_marks_failed(self, run_task, monkeypatch):
        from app.downloader import engine, postprocess

        def broken_ingest(*a, **k):
            raise RuntimeError("ffmpeg exploded")

        monkeypatch.setattr(engine, "ytdlp_download", lambda *a, **k: _downloaded("workerboom1"))
        monkeypatch.setattr(postprocess, "ingest", broken_ingest)
        task = run_task("https://www.youtube.com/watch?v=workerboom1", "youtube")
        assert task.status == "failed" and task.stage == ""
        assert task.error == "RuntimeError: ffmpeg exploded"


class TestEvil0ctalFallback:
    def test_douyin_switches_to_evil0ctal(self, run_task, fake_ingest, monkeypatch):
        from app.downloader import engine

        leftovers: list = []
        calls: list[str] = []

        def fake_evil0ctal(url, settings, temp_dir, on_progress, cancel):
            calls.append(url)
            assert temp_dir.exists() and not any(temp_dir.iterdir())  # yt-dlp 的残片已清掉
            return _downloaded("7300000000000000001", engine="evil0ctal")

        monkeypatch.setattr(engine, "ytdlp_download",
                            _failed("ERROR: [Douyin] Fresh cookies are needed", leftovers))
        monkeypatch.setattr(engine, "evil0ctal_health", lambda settings: True)
        monkeypatch.setattr(engine, "evil0ctal_download", fake_evil0ctal)
        url = "https://www.douyin.com/video/7300000000000000001"
        task = run_task(url, "douyin")
        assert calls == [url]
        assert task.status == "completed" and task.engine == "evil0ctal"
        assert task.video_id is not None and task.error == ""

    def test_unreachable_fallback_keeps_ytdlp_error(self, run_task, monkeypatch):
        from app.downloader import engine

        leftovers: list = []
        monkeypatch.setattr(engine, "ytdlp_download", _failed("ERROR: [TikTok] blocked", leftovers))
        monkeypatch.setattr(engine, "evil0ctal_health", lambda settings: False)
        monkeypatch.setattr(engine, "evil0ctal_download", _must_not_call("服务不可达时不应调用兜底"))
        task = run_task("https://www.tiktok.com/@someone/video/7300000000000000002", "tiktok")
        assert task.status == "failed" and task.engine == "yt-dlp"
        assert task.error == "ERROR: [TikTok] blocked"


class TestCancellation:
    @staticmethod
    def _cancelled_download(queue, shutdown: bool):
        from app.downloader.ytdlp import DownloadCancelled

        def _download(url, settings, temp_dir, on_progress, on_stage, cancel, **kw):
            if shutdown:
                queue._stopped.set()  # stop() 先置位再发取消信号
            cancel.set()
            raise DownloadCancelled()
        return _download

    def test_user_cancel_marks_canceled(self, run_task, queue, monkeypatch):
        from app.downloader import engine

        monkeypatch.setattr(engine, "ytdlp_download", self._cancelled_download(queue, shutdown=False))
        task = run_task("https://www.youtube.com/watch?v=workercncl1", "youtube")
        assert task.status == "canceled" and task.error == ""

    def test_shutdown_marks_interrupted(self, run_task, queue, monkeypatch):
        from app.downloader import engine

        monkeypatch.setattr(engine, "ytdlp_download", self._cancelled_download(queue, shutdown=True))
        task = run_task("https://www.youtube.com/watch?v=workerstop1", "youtube")
        assert task.status == "failed" and task.error == engine.INTERRUPTED_ERROR

    def test_not_started_while_stopping(self, run_task, queue, monkeypatch):
        """关闭过程中才轮到的任务不开始：库里保持 pending，下次启动重新入队。"""
        from app.downloader import engine

        monkeypatch.setattr(engine, "ytdlp_download", _must_not_call("关闭中不应开始下载"))
        queue._stopped.set()
        task = run_task("https://www.youtube.com/watch?v=workerstop2", "youtube")
        assert task.status == "pending"
        assert task.id not in queue._running and task.id not in queue.cancel_flags
