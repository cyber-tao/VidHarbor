"""线程安全的 SSE 事件总线 + 日志环形缓冲。

worker 线程（yt-dlp 下载/后处理）通过 publish() 发事件；
FastAPI 事件循环侧通过 subscribe() 拿到 asyncio.Queue 消费。
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger("vidharbor.events")


class EventBus:
    def __init__(self, log_capacity: int = 1000) -> None:
        self._subs: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self.logs: deque[dict] = deque(maxlen=log_capacity)
        self.stats_dirty = threading.Event()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, type_: str, data: Any) -> None:
        if type_ == "log":
            with self._lock:
                self.logs.append({"type": "log", "data": data, "ts": time.time()})
        self._dispatch({"type": type_, "data": data, "ts": time.time()})

    def mark_stats_dirty(self) -> None:
        self.stats_dirty.set()
        self._dispatch({"type": "stats_dirty", "data": None, "ts": time.time()})

    def _dispatch(self, event: dict) -> None:
        loop = self._loop
        if loop is None or not self._subs:
            return
        try:
            loop.call_soon_threadsafe(self._fanout, event)
        except RuntimeError:
            pass  # 循环已关闭（进程退出）

    def _fanout(self, event: dict) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # 慢消费者丢帧，SSE 端有 REST 快照兜底

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)


bus = EventBus()
