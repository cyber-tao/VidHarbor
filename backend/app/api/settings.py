"""设置 API：读取生效配置（config.toml < 环境变量 < 设置页覆盖层）与元信息；Web 保存覆盖值。"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import (
    EDITABLE_FIELDS,
    ENCODERS,
    SECRET_FIELDS,
    VIDEO_CODECS,
    build_settings,
    editable_overlay,
    get_settings,
    invalidate_settings_cache,
    parse_timezone,
)
from ..db import get_sessionmaker
from ..models import AppSetting
from ..downloader.encoders import detect_hevc_encoder
from ..scheduler import register_all

log = logging.getLogger("vidharbor.api.settings")
router = APIRouter()


def _effective_dict() -> dict:
    """生效配置；密钥只写不读，只返回 <field>_set，不让任何能打开页面的人读走。"""
    data = get_settings().model_dump()
    for section, key in SECRET_FIELDS:
        data[section][f"{key}_set"] = bool(data[section].pop(key))
    return data


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
    """各段只放要修改的字段；值为 null 表示删除该覆盖项（回落到 config.toml / 环境变量）。"""

    model_config = {"extra": "forbid"}  # 未知 section 直接 422

    download: dict = Field(default_factory=dict)
    library: dict = Field(default_factory=dict)
    evil0ctal: dict = Field(default_factory=dict)
    youtube: dict = Field(default_factory=dict)
    scheduler: dict = Field(default_factory=dict)


def _apply_patch(current: dict, patch: dict) -> dict:
    out = editable_overlay(current)
    for section, fields in patch.items():
        for key, value in fields.items():
            if (section, key) not in EDITABLE_FIELDS:
                raise HTTPException(status_code=400, detail=f"字段不可修改: {section}.{key}")
            if value is None:
                out.get(section, {}).pop(key, None)
            else:
                out.setdefault(section, {})[key] = value
        if section in out and not out[section]:
            del out[section]
    return out


@router.put("/api/settings")
def update_settings(req: SettingsUpdate, request: Request):
    patch = {k: v for k, v in req.model_dump().items() if v}
    timezone = patch.get("scheduler", {}).get("timezone")
    if timezone is not None:
        try:
            parse_timezone(str(timezone))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    old_timezone = get_settings().scheduler.timezone
    sm = get_sessionmaker()
    with sm() as session:
        row = session.get(AppSetting, 1)
        current = json.loads(row.data) if (row and row.data) else {}
        overlay = _apply_patch(current, patch)
        try:
            build_settings(overlay)  # 先确认合并后能构造出合法配置，再落库
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"配置校验失败: {e}") from e
        data = json.dumps(overlay, ensure_ascii=False)
        if row is None:
            session.add(AppSetting(id=1, data=data))
        else:
            row.data = data
        session.commit()
    invalidate_settings_cache()
    settings = get_settings()
    # 转码上限即时生效（下载并发由调度器每轮重读 settings，无需额外通知）
    from ..downloader.postprocess import set_transcode_limit

    set_transcode_limit(settings.library.transcode_concurrency)
    # 触发器在注册时就绑定了时区，换时区后必须全部重新注册
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None and settings.scheduler.timezone != old_timezone:
        register_all(scheduler, request.app.state.queue)
    log.info("设置已更新: %s", ", ".join(f"{k}.{k2}" for k, v in patch.items() for k2 in v) or "(空)")
    return {"ok": True, "settings": _effective_dict()}
