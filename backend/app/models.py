from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """统一使用 naive UTC（SQLite DateTime 不保留时区）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("platform", "source_id", name="uq_video_platform_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(Text, default="")
    uploader: Mapped[str] = mapped_column(String(255), default="")
    uploader_id: Mapped[str] = mapped_column(String(255), default="")
    upload_date: Mapped[str] = mapped_column(String(10), default="")  # YYYYMMDD
    duration: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    thumbnail_path: Mapped[str] = mapped_column(String(1024), default="")
    video_path: Mapped[str] = mapped_column(String(1024), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0)
    vcodec: Mapped[str] = mapped_column(String(64), default="")
    acodec: Mapped[str] = mapped_column(String(64), default="")
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_metadata: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    subtitles: Mapped[list["Subtitle"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class Subtitle(Base):
    __tablename__ = "subtitles"
    __table_args__ = (
        UniqueConstraint("video_id", "lang", "auto_generated", name="uq_subtitle_video_lang"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    lang: Mapped[str] = mapped_column(String(32), default="")
    auto_generated: Mapped[bool] = mapped_column(default=False)
    format: Mapped[str] = mapped_column(String(8), default="srt")
    content: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(1024), default="")

    video: Mapped[Video] = relationship(back_populates="subtitles")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (Index("ix_tags_name", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")

    video: Mapped[Video] = relationship(back_populates="tags")


class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1024))
    platform: Mapped[str] = mapped_column(String(32), default="other", index=True)
    # pending | running | completed | failed | canceled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # downloading | merging | processing | done
    stage: Mapped[str] = mapped_column(String(32), default="")
    progress: Mapped[float] = mapped_column(Float, default=0)
    speed: Mapped[str] = mapped_column(String(32), default="")
    eta: Mapped[str] = mapped_column(String(32), default="")
    engine: Mapped[str] = mapped_column(String(16), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    # 本次下载选项（JSON：max_height/audio_langs/sub_langs/codec），空 = 全局默认
    options: Mapped[str] = mapped_column(Text, default="")
    # 来源定时任务 id（手动下载为空）
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ChartCache(Base):
    __tablename__ = "charts_cache"
    __table_args__ = (
        UniqueConstraint("platform", "category", "period", name="uq_chart_platform_category_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(64))
    # 时间周期 id（各平台自定义，如 bilibili: default/3d/week；无周期的平台为 ""）
    period: Mapped[str] = mapped_column(String(32), default="")
    payload: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSetting(Base):
    """Web 设置页覆盖值（id=1 单行，JSON：{section: {field: value}}）。"""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[str] = mapped_column(Text, default="")


class Schedule(Base):
    """定时下载任务：一个任务可组合多个榜单选择（平台×分类×周期×TopN）。"""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    # interval | daily | weekly | cron
    mode: Mapped[str] = mapped_column(String(16), default="daily")
    # interval 模式：间隔分钟数
    interval_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # daily/weekly 模式："HH:MM"
    at_time: Mapped[str] = mapped_column(String(5), default="09:00")
    # weekly 模式：星期列表 JSON（0=周一 … 6=周日）
    weekdays: Mapped[str] = mapped_column(Text, default="[]")
    # cron 模式：标准 5 段表达式
    cron: Mapped[str] = mapped_column(String(64), default="")
    # 榜单选择 JSON: [{platform, category, period, limit}]
    selections: Mapped[str] = mapped_column(Text, default="[]")
    # 下载选项 JSON（同 DownloadOptions，空对象 = 用全局默认）
    options: Mapped[str] = mapped_column(Text, default="{}")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 上次运行结果 JSON: {created, skipped, failed, error, at}
    last_result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
