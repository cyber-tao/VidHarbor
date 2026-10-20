from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


@dataclass
class TrendingItem:
    source_id: str = ""
    title: str = ""
    author: str = ""
    url: str = ""
    cover: str = ""
    duration: float = 0
    views: int = 0
    downloadable: bool = True
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ChartError(Exception):
    """榜单拉取失败（网络/反爬/需要 cookies），可向用户展示 message。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChartProvider(ABC):
    name: str = ""

    @abstractmethod
    def categories(self) -> list[dict]:
        """返回 [{"id": "...", "name": "..."}]"""

    @abstractmethod
    def fetch(self, category: str) -> list[TrendingItem]:
        """拉取指定分类榜单，失败抛 ChartError。"""
