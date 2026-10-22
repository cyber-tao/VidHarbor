"""跨平台启动入口：python run.py（读取 config.toml 的 [server] host/port）。"""
from __future__ import annotations

import uvicorn

from app.config import get_settings

# 前端的 SSE 长连接不会自己结束：不设上限时关闭会一直等它们断开，lifespan 收尾也就不会执行
GRACEFUL_SHUTDOWN_SECONDS = 5


def main() -> None:
    s = get_settings()
    uvicorn.run("app.main:app", host=s.server.host, port=s.server.port,
                timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS)


if __name__ == "__main__":
    main()
