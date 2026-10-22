"""VidHarbor 配置：config.toml 打底 + 环境变量 VIDHARBOR_<section>__<field> 覆盖 + DB app_settings 覆盖（Web 设置页可改）。"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger("vidharbor.config")

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # vidharbor/

ENV_PREFIX = "VIDHARBOR_"

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

DEFAULT_TIMEZONE = "Asia/Shanghai"
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
    # 锚定标准语言码；避免 zh.* 在 YouTube 命中大量"翻译自xx语"自动字幕导致 429 限流
    sub_langs: list[str] = Field(default_factory=lambda: [
        r"^zh(-CN|-Hans|-Hant|-TW|-HK)?$", r"^en(-US|-GB)?$",
    ])
    cookies_file: str = ""
    # 最高分辨率（像素高度），0 = 不限
    max_height: int = Field(default=1080, ge=0, le=4320)
    # 音轨语言偏好（按顺序），多音轨视频只下载一条首选音轨；空 = 原声/默认
    audio_langs: list[str] = Field(default_factory=list)
    # 出口代理（http://host:port 或 socks5://host:port），只对 proxy_platforms
    # 勾选的平台生效：下载（yt-dlp/Evil0ctal 兜底）与榜单请求均走该代理
    proxy: str = ""
    proxy_platforms: list[str] = Field(default_factory=list)


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
    timezone: str = DEFAULT_TIMEZONE


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

    def proxy_for(self, platform: str) -> str:
        """平台命中 proxy_platforms 时返回代理地址，否则空串（= 直连）。"""
        if self.download.proxy and platform in self.download.proxy_platforms:
            return self.download.proxy
        return ""

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
    ("download", "proxy"),
    ("download", "proxy_platforms"),
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


def _coerce_env_value(value: str):
    """环境变量值类型还原：优先 JSON 解析（bool/int/list），失败则保持字符串。"""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def _load_env_overrides() -> dict:
    """环境变量覆盖：VIDHARBOR_<section>__<field>（双下划线分隔），主要供容器部署注入。

    优先级低于 DB（Web 设置页），即页面上改过的字段不受环境变量影响。
    """
    out: dict = {}
    for key, raw in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        # 空值视为未设置：compose 可无条件注入 ${VAR:-}，避免空串覆盖
        # list/bool 字段导致 Settings 校验失败
        if not raw.strip():
            continue
        section, sep, field = key[len(ENV_PREFIX):].partition("__")
        if not sep or not section or not field:
            continue
        out.setdefault(section.lower(), {})[field.lower()] = _coerce_env_value(raw)
    return out


@lru_cache
def get_settings() -> Settings:
    raw = _load_file()
    env = _load_env_overrides()
    overlay = _load_overrides()
    merged = _deep_merge(_deep_merge(raw, env), overlay)
    sections = {}
    for name in ("library", "download", "evil0ctal", "youtube", "server", "scheduler"):
        if isinstance(merged.get(name), dict):
            sections[name] = merged[name]
    return Settings(**sections)


def invalidate_settings_cache() -> None:
    get_settings.cache_clear()


def parse_timezone(name: str):
    """IANA 时区名 → ZoneInfo；无效名抛 ValueError（设置页写入时校验）。"""
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo((name or "").strip())
    except Exception as e:  # noqa: BLE001  NotFound/ValueError/OSError 都意味着名称无效
        raise ValueError(f"无效时区: {name!r}（需为 IANA 时区名，如 Asia/Shanghai、UTC）") from e


@lru_cache
def _warn_invalid_timezone(name: str) -> None:
    log.warning("scheduler.timezone=%r 无效，按 %s 处理", name, DEFAULT_TIMEZONE)


def local_timezone():
    """定时任务与统计展示共用的时区（scheduler.timezone）。

    设置页写入时已校验；config.toml / 环境变量中的无效值在此回退默认时区并告警一次。
    """
    name = get_settings().scheduler.timezone or DEFAULT_TIMEZONE
    try:
        return parse_timezone(name)
    except ValueError:
        _warn_invalid_timezone(name)
        return parse_timezone(DEFAULT_TIMEZONE)


def ensure_dirs(settings: Settings) -> None:
    settings.library_root.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.cookies_dir.mkdir(parents=True, exist_ok=True)
