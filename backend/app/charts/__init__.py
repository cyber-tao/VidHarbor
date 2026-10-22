"""榜单 provider 注册表：API 层与定时调度共用的唯一入口（核心层不得反向依赖 api 包）。"""
from __future__ import annotations

from ..config import get_settings
from .base import ChartProvider


def _registry() -> dict[str, ChartProvider]:
    settings = get_settings()
    from .bilibili import BilibiliProvider
    from .douyin import DouyinProvider
    from .tiktok import TikTokProvider
    from .youtube import YoutubeProvider

    return {
        "bilibili": BilibiliProvider(settings),
        "youtube": YoutubeProvider(settings),
        "tiktok": TikTokProvider(settings),
        "douyin": DouyinProvider(settings),
    }


def provider_for(platform: str) -> ChartProvider | None:
    return _registry().get(platform)
