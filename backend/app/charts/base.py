from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


def fmt_published(ts: int | float | None) -> str:
    """epoch 秒 → 中文相对时间（>30 天显示日期）。"""
    if not ts or ts <= 0:
        return ""
    delta = max(0, int(time.time()) - int(ts))
    if delta < 3600:
        return f"{max(1, delta // 60)}分钟前"
    if delta < 86400:
        return f"{delta // 3600}小时前"
    if delta < 30 * 86400:
        return f"{delta // 86400}天前"
    return time.strftime("%Y-%m-%d", time.localtime(ts))


@dataclass
class TrendingItem:
    source_id: str = ""
    title: str = ""
    author: str = ""
    url: str = ""
    cover: str = ""
    duration: float = 0
    views: int = 0
    likes: int = 0
    published: str = ""   # 展示用时间文本（如「3小时前」/「3天前」）
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
        """返回 [{"id", "name", "periods": [{"id", "name"}], "allow_custom": bool}]。

        periods 为该分类可用的时间周期（各平台/分类不同，如 B站分区有
        三日榜/周榜而 YouTube 搜索有今日/本周/本月）；无时间维度的平台
        也应返回单元素列表（如 [{"id": "default", "name": "实时"}]）。
        allow_custom 表示接受 "custom:<词>" 形式的自定义分类（关键词/标签）。
        """

    @abstractmethod
    def fetch(self, category: str, period: str = "") -> list[TrendingItem]:
        """拉取指定分类+周期榜单，失败抛 ChartError。period 为 categories 声明的周期 id。"""

    # ---- 供 API 层与定时任务复用的校验工具 ----

    def find_category(self, category: str) -> dict | None:
        for c in self.categories():
            if c["id"] == category:
                return c
        return None

    def normalize(self, category: str, period: str) -> tuple[str, str]:
        """校验并回退 category/period 到合法值；custom:<词> 透传。"""
        cats = self.categories()
        allow_custom = any(c.get("allow_custom") for c in cats)
        if category.startswith("custom:") and allow_custom:
            kw = category[len("custom:"):].strip()[:60]
            category = f"custom:{kw}" if kw else cats[0]["id"]
            return category, self._norm_period(cats, category, period)
        if self.find_category(category) is None:
            category = cats[0]["id"]
        return category, self._norm_period(cats, category, period)

    @staticmethod
    def _norm_period(cats: list[dict], category: str, period: str) -> str:
        if category.startswith("custom:"):
            pool = next((c["periods"] for c in cats if c.get("allow_custom")), [])
        else:
            pool = next((c.get("periods") for c in cats if c["id"] == category), [])
        if not pool:
            return ""
        valid = {p["id"] for p in pool}
        if period in valid:
            return period
        # 默认周期：标了 default 的优先，否则取第一个
        for p in pool:
            if p.get("default"):
                return p["id"]
        return pool[0]["id"]
