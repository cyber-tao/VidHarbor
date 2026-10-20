"""任务队列与调度：平台识别、worker 线程池、取消、yt-dlp → Evil0ctal 自动切换。"""
from __future__ import annotations

import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..config import Settings
from ..db import get_sessionmaker
from ..events import bus
from ..models import DownloadTask
from .douyin_fallback import Evil0ctalClient, douyin_download
from .ytdlp import DownloadCancelled, ytdlp_download

log = logging.getLogger("vidlib.engine")

PLATFORM_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("youtube", ("youtube.com", "youtu.be")),
    ("bilibili", ("bilibili.com", "b23.tv", "bili22.cn", "bili2233.cn")),
    ("tiktok", ("tiktok.com",)),
    ("douyin", ("douyin.com", "iesdouyin.com")),
]


def detect_platform(url: str) -> str:
    u = (url or "").lower()
    for name, hosts in PLATFORM_RULES:
        if any(h in u for h in hosts):
            return name
    return "other"


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def task_snapshot(t: DownloadTask) -> dict:
    return {
        "id": t.id, "url": t.url, "platform": t.platform, "status": t.status,
        "stage": t.stage, "progress": round(t.progress or 0, 4), "speed": t.speed,
        "eta": t.eta, "engine": t.engine, "error": t.error, "video_id": t.video_id,
        "created_at": _iso(t.created_at), "updated_at": _iso(t.updated_at),
    }


_health_cache: dict = {"ts": 0.0, "ok": False}


def evil0ctal_health(settings: Settings) -> bool:
    now = time.time()
    if now - _health_cache["ts"] < 60:
        return _health_cache["ok"]
    ok = False
    if settings.evil0ctal.enabled:
        ok = Evil0ctalClient(settings.evil0ctal.base_url).health()
    _health_cache.update(ts=now, ok=ok)
    return ok


class TaskQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = ThreadPoolExecutor(
            max_workers=settings.download.concurrency, thread_name_prefix="vidlib-dl"
        )
        self.cancel_flags: dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        self._recover_interrupted()
        log.info("下载队列就绪（并发=%d）", self.settings.download.concurrency)
        if self.settings.evil0ctal.enabled:
            ok = evil0ctal_health(self.settings)
            if ok:
                log.info("Evil0ctal 兜底服务在线: %s", self.settings.evil0ctal.base_url)
            else:
                log.warning(
                    "Evil0ctal 兜底服务不可达: %s —— 抖音任务失败时无法自动兜底（部署方法见 README）",
                    self.settings.evil0ctal.base_url,
                )

    def stop(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _recover_interrupted(self) -> None:
        sm = get_sessionmaker()
        with sm() as session:
            stuck = session.query(DownloadTask).filter(
                DownloadTask.status.in_(["pending", "running"])
            ).all()
            for t in stuck:
                t.status = "failed"
                t.error = "服务重启，任务中断，请重试"
                session.commit()
                bus.publish("task", task_snapshot(t))

    def submit(self, task_id: int) -> None:
        ev = threading.Event()
        with self._lock:
            self.cancel_flags[task_id] = ev
        self.executor.submit(self._run, task_id)

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            ev = self.cancel_flags.get(task_id)
        if ev is not None:
            ev.set()
            return True
        return False

    # ---- worker ----

    def _run(self, task_id: int) -> None:
        session = get_sessionmaker()()
        temp_dir = self.settings.tmp_dir / f"task-{task_id}"
        try:
            with self._lock:
                cancel = self.cancel_flags.get(task_id)
            task = session.get(DownloadTask, task_id)
            if task is None or task.status != "pending":
                return

            task.status = "running"
            task.stage = "downloading"
            task.engine = "yt-dlp"
            task.progress = 0
            task.error = ""
            session.commit()
            bus.publish("task", task_snapshot(task))
            log.info("任务 #%d 开始: %s", task_id, task.url)

            temp_dir.mkdir(parents=True, exist_ok=True)
            last = {"t": 0.0}

            def on_progress(p: float, speed: str, eta: str) -> None:
                now = time.monotonic()
                if p < 1.0 and now - last["t"] < 0.4:
                    return
                last["t"] = now
                task.progress = max(0.0, min(1.0, p))
                task.speed = speed
                task.eta = eta
                session.commit()
                bus.publish("task", task_snapshot(task))

            def on_stage(stage: str) -> None:
                task.stage = stage
                session.commit()
                bus.publish("task", task_snapshot(task))

            raw = ytdlp_download(task.url, self.settings, temp_dir, on_progress, on_stage, cancel)

            if not raw.ok and task.platform == "douyin" and self.settings.evil0ctal.enabled:
                log.warning("任务 #%d yt-dlp 失败（%s），尝试 Evil0ctal 兜底", task_id, raw.error[:150])
                if evil0ctal_health(self.settings):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    task.engine = "evil0ctal"
                    task.stage = "downloading"
                    task.progress = 0
                    task.speed = task.eta = ""
                    session.commit()
                    bus.publish("task", task_snapshot(task))
                    raw = douyin_download(task.url, self.settings, temp_dir, on_progress, cancel)
                else:
                    log.warning("Evil0ctal 服务不可达，无法兜底（部署方法见 README）")

            if not raw.ok:
                task.status = "failed"
                task.stage = ""
                task.error = raw.error
                session.commit()
                bus.publish("task", task_snapshot(task))
                log.error("任务 #%d 失败: %s", task_id, raw.error[:300])
                return

            from .postprocess import ingest

            task.stage = "processing"
            task.progress = 0.97
            task.speed = task.eta = ""
            session.commit()
            bus.publish("task", task_snapshot(task))

            video, created = ingest(raw, task, session, self.settings)
            task.status = "completed"
            task.stage = "done"
            task.progress = 1.0
            task.video_id = video.id
            if not created:
                task.error = "已在库中，已关联现有条目"
            session.commit()
            bus.publish("task", task_snapshot(task))
            bus.mark_stats_dirty()
            log.info("任务 #%d 完成: %s", task_id, video.title[:60])
        except DownloadCancelled:
            task = session.get(DownloadTask, task_id)
            if task is not None:
                task.status = "canceled"
                task.stage = ""
                session.commit()
                bus.publish("task", task_snapshot(task))
            log.info("任务 #%d 已取消", task_id)
        except Exception as e:  # noqa: BLE001
            log.error("任务 #%d 异常: %s", task_id, e)
            task = session.get(DownloadTask, task_id)
            if task is not None and task.status == "running":
                task.status = "failed"
                task.stage = ""
                task.error = f"{type(e).__name__}: {e}"
                session.commit()
                bus.publish("task", task_snapshot(task))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            with self._lock:
                self.cancel_flags.pop(task_id, None)
            session.close()
