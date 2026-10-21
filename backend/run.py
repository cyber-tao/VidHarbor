"""跨平台启动入口：python run.py（读取 config.toml 的 [server] host/port）。"""
from __future__ import annotations

import uvicorn

from app.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run("app.main:app", host=s.server.host, port=s.server.port)


if __name__ == "__main__":
    main()
