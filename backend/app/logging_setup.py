"""日志：控制台 + 环形缓冲/事件总线桥接（前端日志抽屉数据源）。"""
from __future__ import annotations

import logging
import time

from .events import bus

_FORMAT = "%(levelname)s %(name)s: %(message)s"


class BusLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = record.msg if isinstance(record.msg, str) else repr(record.msg)
        bus.publish(
            "log",
            {
                "level": record.levelname,
                "name": record.name,
                "message": message,
                "ts": time.time(),
            },
        )


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger("vidlib")
    if any(isinstance(h, BusLogHandler) for h in root.handlers):
        return
    root.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)
    root.addHandler(BusLogHandler())
    root.propagate = False
