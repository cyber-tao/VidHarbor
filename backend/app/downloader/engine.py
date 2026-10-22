"""任务队列与调度：平台识别、worker 线程池、取消、yt-dlp → Evil0ctal 自动切换。"""
from __future__ import annotations

import logging
import shutil
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from ..config import Settings, get_settings
from ..db import get_sessionmaker
from ..events import bus
from ..models import DownloadTask, Video
from .evil0ctal import Evil0ctalClient, evil0ctal_download
from .options import parse_options_json, parse_source_id, resolve_options
from .ytdlp import DownloadCancelled, ytdlp_download

log = logging.getLogger("vidharbor.engine")

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


def active_task_urls(session) -> set[str]:
    """当前排队/下载中任务的 URL 集合（创建新任务前去重，防止同一视频并发下载两份）。"""
    rows = session.query(DownloadTask.url).filter(
        DownloadTask.status.in_(("pending", "running"))
    ).all()
    return {u for (u,) in rows if u}


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def task_snapshot(t: DownloadTask) -> dict:
    import json as _json

    try:
        opts = _json.loads(t.options) if t.options else None
    except Exception:  # noqa: BLE001
        opts = None
    return {
        "id": t.id, "url": t.url, "platform": t.platform, "status": t.status,
        "stage": t.stage, "progress": round(t.progress or 0, 4), "speed": t.speed,
        "eta": t.eta, "engine": t.engine, "error": t.error, "video_id": t.video_id,
        "options": opts, "schedule_id": t.schedule_id,
        "created_at": _iso(t.created_at), "updated_at": _iso(t.updated_at),
    }


_health_cache: dict = {"ts": 0.0, "ok": False}


def evil0ctal_health(settings: Settings) -> bool:
    now = time.time()
    if now - _health_cache["ts"] < 60:
        return _health_cache["ok"]
    ok = False
    if settings.evil0ctal.enabled:
        ok = Evil0ctalClient(
            settings.evil0ctal.base_url, settings.evil0ctal.api_key
        ).health()
    _health_cache.update(ts=now, ok=ok)
    return ok


class TaskQueue:
    # 线程池只提供容量，真正的并发上限由调度线程按 settings 实时控制（改设置即时生效）
    _EXECUTOR_CAPACITY = 8

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = ThreadPoolExecutor(
            max_workers=max(self._EXECUTOR_CAPACITY, settings.download.concurrency),
            thread_name_prefix="vidharbor-dl",
        )
        self.cancel_flags: dict[int, threading.Event] = {}
        self._pending: deque[tuple[int, str]] = deque()  # (task_id, platform) 等待调度
        self._running: dict[int, str] = {}               # task_id -> platform
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopped = threading.Event()
        self._dispatcher: threading.Thread | None = None

    def start(self) -> None:
        self._recover_interrupted()
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop, name="vidharbor-dispatch", daemon=True)
        self._dispatcher.start()
        log.info("下载队列就绪（全局并发=%d，每平台并发=%d）",
                 self.settings.download.concurrency,
                 self.settings.download.per_platform_concurrency)
        if self.settings.evil0ctal.enabled:
            ok = evil0ctal_health(self.settings)
            if ok:
                log.info("Evil0ctal 兜底服务在线: %s", self.settings.evil0ctal.base_url)
            else:
                log.warning(
                    "Evil0ctal 兜底服务不可达: %s —— 抖音/TikTok 任务失败时无法自动兜底（部署方法见 README）",
                    self.settings.evil0ctal.base_url,
                )

    def stop(self) -> None:
        self._stopped.set()
        self._wake.set()
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

    def submit(self, task_id: int, platform: str = "other") -> None:
        ev = threading.Event()
        with self._lock:
            self.cancel_flags[task_id] = ev
            self._pending.append((task_id, platform))
        self._wake.set()

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            ev = self.cancel_flags.get(task_id)
            if ev is not None:
                ev.set()
            # 还没轮到执行的任务直接出队（DB 状态由调用方更新）
            if any(tid == task_id for tid, _ in self._pending):
                self._pending = deque(x for x in self._pending if x[0] != task_id)
        return ev is not None

    # ---- 调度：全局 + 每平台并发上限，每轮重新读 settings ----

    def _dispatch_loop(self) -> None:
        while not self._stopped.is_set():
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            while not self._stopped.is_set() and self._dispatch_one():
                pass

    def _dispatch_one(self) -> bool:
        """取一个满足并发上限的等待任务执行（同平台满员时跳过、不阻塞后面的其他平台任务）。"""
        settings = get_settings()
        with self._lock:
            if len(self._running) >= settings.download.concurrency:
                return False
            plat_counts: dict[str, int] = {}
            for plat in self._running.values():
                plat_counts[plat] = plat_counts.get(plat, 0) + 1
            for i, (tid, plat) in enumerate(self._pending):
                if plat_counts.get(plat, 0) >= settings.download.per_platform_concurrency:
                    continue
                del self._pending[i]
                self._running[tid] = plat
                self.executor.submit(self._run, tid)
                return True
            return False

    # ---- worker ----

    def _run(self, task_id: int) -> None:
        # 每个任务重新解析配置：Web 设置页修改（兜底服务地址/API key 等）即时生效
        settings = get_settings()
        session = get_sessionmaker()()
        temp_dir = settings.tmp_dir / f"task-{task_id}"
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

            # 下载前查库去重：URL 能解析出 source_id 且库中已有 → 直接完成
            sid = parse_source_id(task.platform, task.url)
            if sid:
                existing = session.query(Video).filter_by(
                    platform=task.platform, source_id=sid
                ).first()
                if existing is not None:
                    task.status = "completed"
                    task.stage = "done"
                    task.progress = 1.0
                    task.video_id = existing.id
                    task.error = "已在库中，未重复下载"
                    session.commit()
                    bus.publish("task", task_snapshot(task))
                    log.info("任务 #%d 跳过: [%s] %s 已在库中", task_id, task.platform, sid)
                    return

            eff = resolve_options(settings, parse_options_json(task.options))
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

            raw = ytdlp_download(task.url, settings, temp_dir, on_progress, on_stage, cancel,
                                 eff=eff, platform=task.platform)

            if not raw.ok and task.platform in ("douyin", "tiktok") and settings.evil0ctal.enabled:
                log.warning("任务 #%d yt-dlp 失败（%s），尝试 Evil0ctal 兜底", task_id, raw.error[:150])
                if evil0ctal_health(settings):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    task.engine = "evil0ctal"
                    task.stage = "downloading"
                    task.progress = 0
                    task.speed = task.eta = ""
                    session.commit()
                    bus.publish("task", task_snapshot(task))
                    raw = evil0ctal_download(task.url, settings, temp_dir, on_progress, cancel)
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

            video, created = ingest(raw, task, session, settings, eff=eff, cancel=cancel)
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
                self._running.pop(task_id, None)
            session.close()
            self._wake.set()  # 腾出的槽位立即调度下一个任务
