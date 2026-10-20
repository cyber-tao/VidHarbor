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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ChartCache(Base):
    __tablename__ = "charts_cache"
    __table_args__ = (UniqueConstraint("platform", "category", name="uq_chart_platform_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
