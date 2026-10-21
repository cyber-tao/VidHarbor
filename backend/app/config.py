"""VidHarbor 配置：config.toml 打底 + DB app_settings 覆盖（Web 设置页可改）。"""
from __future__ import annotations

import json
import logging
import sqlite3
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger("vidharbor.config")

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # vidharbor/

DB_FILENAME = "vidharbor.db"
# vidlib 时期的旧库文件名，首次访问时自动改名迁移
LEGACY_DB_FILENAME = "vidlib.db"


@lru_cache
def _resolve_db_filename(data_dir: Path) -> str:
    """旧库存在且新库不存在时一次性改名（含 -wal/-shm）；文件被占用则沿用旧名，下次启动再迁。"""
    legacy = data_dir / LEGACY_DB_FILENAME
    new = data_dir / DB_FILENAME
    if legacy.exists() and not new.exists():
        try:
            legacy.rename(new)
            for suffix in ("-wal", "-shm"):
                side = data_dir / (LEGACY_DB_FILENAME + suffix)
                if side.exists():
                    side.rename(data_dir / (DB_FILENAME + suffix))
            log.info("数据库已迁移改名: %s → %s", legacy, new)
        except OSError:
            return LEGACY_DB_FILENAME
    return DB_FILENAME

VIDEO_CODECS = ("h265", "h264")
ENCODERS = ("auto", "libx265", "hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox")
PLATFORMS = ("bilibili", "youtube", "tiktok", "douyin")


class LibraryCfg(BaseModel):
    root: str = ""
    name_template: str = "{upload_date} - {title} [{id}]"
    # 入库目标视频编码：h265（默认，更省空间）或 h264（兼容性最好）
    video_codec: str = "h265"
    # h265 转码编码器：auto = 硬件优先(NVENC/QSV/AMF/VideoToolbox)回退 libx265
    hw_encoder: str = "auto"
    # 全局同时转码任务数（ffmpeg 转码很吃 CPU/GPU，超出的任务排队等待；remux 不占槽位）
    transcode_concurrency: int = Field(default=1, ge=1, le=8)


class DownloadCfg(BaseModel):
    concurrency: int = Field(default=2, ge=1, le=8)
    # 同一平台同时下载的任务数上限（防风控/限速；调度器实时读取，改完即时生效）
    per_platform_concurrency: int = Field(default=2, ge=1, le=8)
    sub_langs: list[str] = Field(default_factory=lambda: ["zh.*", "en.*"])
    cookies_file: str = ""
    # 最高分辨率（像素高度），0 = 不限
    max_height: int = Field(default=1080, ge=0, le=4320)
    # 音轨语言偏好（按顺序），多音轨视频只下载一条首选音轨；空 = 原声/默认
    audio_langs: list[str] = Field(default_factory=list)


class Evil0ctalCfg(BaseModel):
    enabled: bool = True
    # Douyin_TikTok_Download_API v5 默认发布在 127.0.0.1:8000
    base_url: str = "http://127.0.0.1:8000"
    # v5 需要 API key（控制台 /api-keys 创建，勾选 douyin:read + tiktok:read）
    api_key: str = ""


class YoutubeCfg(BaseModel):
    # YouTube Data API v3 key（Google Cloud Console 创建，免费额度个人够用）；
    # 留空时榜单走 InnerTube/yt-dlp 免登录通道
    api_key: str = ""
    # regionCode：影响热门榜与搜索偏好（US / JP / TW / HK 等）
    region_code: str = "US"


class ServerCfg(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8666


class SchedulerCfg(BaseModel):
    timezone: str = "Asia/Shanghai"


class Settings(BaseModel):
    library: LibraryCfg = Field(default_factory=LibraryCfg)
    download: DownloadCfg = Field(default_factory=DownloadCfg)
    evil0ctal: Evil0ctalCfg = Field(default_factory=Evil0ctalCfg)
    youtube: YoutubeCfg = Field(default_factory=YoutubeCfg)
    server: ServerCfg = Field(default_factory=ServerCfg)
    scheduler: SchedulerCfg = Field(default_factory=SchedulerCfg)

    @property
    def library_root(self) -> Path:
        root = Path(self.library.root) if self.library.root else PROJECT_ROOT / "library"
        return root.resolve()

    @property
    def videos_dir(self) -> Path:
        return self.library_root / "videos"

    @property
    def tmp_dir(self) -> Path:
        return self.library_root / ".tmp"

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / _resolve_db_filename(self.data_dir)

    @property
    def cookies_dir(self) -> Path:
        return self.data_dir / "cookies"

    def cookie_file_for(self, platform: str) -> Path | None:
        """平台专属 cookies 优先（扫码登录/上传/浏览器导入生成），否则回退全局配置。"""
        p = self.cookies_dir / f"{platform}.txt"
        if p.exists():
            return p
        return self.cookies_path

    @property
    def cookies_path(self) -> Path | None:
        if not self.download.cookies_file:
            return None
        p = Path(self.download.cookies_file)
        return p if p.exists() else None


    @property
    def frontend_dist(self) -> Path:
        return PROJECT_ROOT / "frontend" / "dist"


def _load_file() -> dict:
    # ~/.vidlib/config.toml 为 vidlib 时期旧路径，保留兼容
    for candidate in (
        PROJECT_ROOT / "config.toml",
        Path.home() / ".vidharbor" / "config.toml",
        Path.home() / ".vidlib" / "config.toml",
    ):
        if candidate.exists():
            with candidate.open("rb") as f:
                return tomllib.load(f)
    return {}


# Web 设置页可修改的字段白名单（两级路径）
EDITABLE_FIELDS: set[tuple[str, str]] = {
    ("download", "sub_langs"),
    ("download", "cookies_file"),
    ("download", "max_height"),
    ("download", "audio_langs"),
    ("download", "concurrency"),
    ("download", "per_platform_concurrency"),
    ("library", "video_codec"),
    ("library", "hw_encoder"),
    ("library", "transcode_concurrency"),
    ("evil0ctal", "enabled"),
    ("evil0ctal", "base_url"),
    ("evil0ctal", "api_key"),
    ("youtube", "api_key"),
    ("youtube", "region_code"),
    ("scheduler", "timezone"),
}


def _load_overrides() -> dict:
    """直连 SQLite 读取 Web 设置页保存的覆盖值（表可能尚未创建，异常时忽略）。"""
    data = PROJECT_ROOT / "data"
    db = data / _resolve_db_filename(data)
    if not db.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
        try:
            row = conn.execute("SELECT data FROM app_settings WHERE id = 1").fetchone()
        finally:
            conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache
def get_settings() -> Settings:
    raw = _load_file()
    overlay = _load_overrides()
    merged = _deep_merge(raw, overlay)
    sections = {}
    for name in ("library", "download", "evil0ctal", "youtube", "server", "scheduler"):
        if isinstance(merged.get(name), dict):
            sections[name] = merged[name]
    return Settings(**sections)


def invalidate_settings_cache() -> None:
    get_settings.cache_clear()


def ensure_dirs(settings: Settings) -> None:
    settings.library_root.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.cookies_dir.mkdir(parents=True, exist_ok=True)
