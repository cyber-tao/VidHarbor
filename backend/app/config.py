"""vidlib 配置：config.toml（可选）覆盖默认值。"""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # vidlib/


class LibraryCfg(BaseModel):
    root: str = ""
    name_template: str = "{upload_date} - {title} [{id}]"


class DownloadCfg(BaseModel):
    concurrency: int = Field(default=2, ge=1, le=8)
    sub_langs: list[str] = Field(default_factory=lambda: ["zh.*", "en.*"])
    cookies_file: str = ""


class Evil0ctalCfg(BaseModel):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:8080"


class ServerCfg(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8666


class Settings(BaseModel):
    library: LibraryCfg = Field(default_factory=LibraryCfg)
    download: DownloadCfg = Field(default_factory=DownloadCfg)
    evil0ctal: Evil0ctalCfg = Field(default_factory=Evil0ctalCfg)
    server: ServerCfg = Field(default_factory=ServerCfg)

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
        return self.data_dir / "vidlib.db"

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
    for candidate in (PROJECT_ROOT / "config.toml", Path.home() / ".vidlib" / "config.toml"):
        if candidate.exists():
            with candidate.open("rb") as f:
                return tomllib.load(f)
    return {}


@lru_cache
def get_settings() -> Settings:
    raw = _load_file()
    sections = {}
    for name in ("library", "download", "evil0ctal", "server"):
        if isinstance(raw.get(name), dict):
            sections[name] = raw[name]
    return Settings(**sections)


def ensure_dirs(settings: Settings) -> None:
    settings.library_root.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
