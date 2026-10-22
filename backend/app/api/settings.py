"""设置 API：读取生效配置（config.toml + DB 覆盖）与元信息；Web 保存覆盖值。"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import (
    EDITABLE_FIELDS,
    ENCODERS,
    VIDEO_CODECS,
    get_settings,
    invalidate_settings_cache,
)
from ..db import get_sessionmaker
from ..models import AppSetting
from ..downloader.encoders import detect_hevc_encoder

log = logging.getLogger("vidharbor.api.settings")
router = APIRouter()


def _effective_dict() -> dict:
    s = get_settings()
    return {
        "download": {
            "concurrency": s.download.concurrency,
            "per_platform_concurrency": s.download.per_platform_concurrency,
            "sub_langs": list(s.download.sub_langs),
            "audio_langs": list(s.download.audio_langs),
            "max_height": s.download.max_height,
            "cookies_file": s.download.cookies_file,
            "proxy": s.download.proxy,
            "proxy_platforms": list(s.download.proxy_platforms),
        },
        "library": {
            "video_codec": s.library.video_codec,
            "hw_encoder": s.library.hw_encoder,
            "transcode_concurrency": s.library.transcode_concurrency,
            "name_template": s.library.name_template,
        },
        "evil0ctal": {
            "enabled": s.evil0ctal.enabled,
            "base_url": s.evil0ctal.base_url,
            "api_key": s.evil0ctal.api_key,
        },
        "youtube": {
            "api_key": s.youtube.api_key,
            "region_code": s.youtube.region_code,
        },
        "scheduler": {"timezone": s.scheduler.timezone},
        "server": {"host": s.server.host, "port": s.server.port},
    }


@router.get("/api/settings")
def read_settings():
    s = get_settings()
    return {
        "settings": _effective_dict(),
        "meta": {
            "library_root": str(s.library_root),
            "db_path": str(s.db_path),
            "cookies_dir": str(s.cookies_dir),
            "frontend_dist": str(s.frontend_dist),
            "video_codecs": list(VIDEO_CODECS),
            "encoders": list(ENCODERS),
            "hevc_encoder": detect_hevc_encoder(s.library.hw_encoder),
            "editable": [f"{a}.{b}" for a, b in sorted(EDITABLE_FIELDS)],
        },
    }


class SettingsUpdate(BaseModel):
    model_config = {"extra": "forbid"}  # 未知 section 直接 422

    download: dict = Field(default_factory=dict)
    library: dict = Field(default_factory=dict)
    evil0ctal: dict = Field(default_factory=dict)
    youtube: dict = Field(default_factory=dict)
    scheduler: dict = Field(default_factory=dict)


def _merge_overlay(current: dict, patch: dict) -> dict:
    out = json.loads(json.dumps(current)) if current else {}
    changed: list[str] = []
    for section, fields in patch.items():
        if not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            if (section, key) not in EDITABLE_FIELDS:
                raise HTTPException(status_code=400, detail=f"字段不可修改: {section}.{key}")
            out.setdefault(section, {})
            out[section][key] = value
            changed.append(f"{section}.{key}")
    return out


@router.put("/api/settings")
def update_settings(req: SettingsUpdate):
    patch = {k: v for k, v in req.model_dump().items() if v}
    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(AppSetting, 1)
        current = json.loads(row.data) if (row and row.data) else {}
        merged = _merge_overlay(current, patch)
        # 先校验整体能构造出合法 Settings，再落库
        from ..config import _load_file, _deep_merge
        raw = _deep_merge(_load_file(), merged)
        try:
            from ..config import Settings as _S
            sections = {n: raw[n] for n in ("library", "download", "evil0ctal", "youtube",
                                            "server", "scheduler")
                        if isinstance(raw.get(n), dict)}
            _S(**sections)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"配置校验失败: {e}") from e
        if row is None:
            row = AppSetting(id=1, data=json.dumps(merged, ensure_ascii=False))
            session.add(row)
        else:
            row.data = json.dumps(merged, ensure_ascii=False)
        session.commit()
    invalidate_settings_cache()
    # 转码上限即时生效（下载并发由调度器每轮重读 settings，无需额外通知）
    from ..downloader.postprocess import set_transcode_limit

    set_transcode_limit(get_settings().library.transcode_concurrency)
    log.info("设置已更新: %s", ", ".join(f"{k}.{k2}" for k, v in patch.items() for k2 in v) or "(空)")
    return {"ok": True, "settings": _effective_dict()}
