"""登录/cookies API：B站扫码、上传 cookies.txt、浏览器导入、状态查询。"""
from __future__ import annotations

import logging

import segno
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from ..auth import bilibili_qr
from ..auth import cookies as cookies_mod
from ..config import PLATFORMS, get_settings

log = logging.getLogger("vidharbor.api.auth")
router = APIRouter()

SUPPORTED_BROWSERS = ("chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi", "safari")


def _check_platform(platform: str) -> None:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")


@router.get("/api/auth/cookies")
def cookies_status():
    settings = get_settings()
    out = cookies_mod.status(settings)
    try:
        out["bilibili"]["nickname"] = bilibili_qr.login_nickname(settings)
    except Exception:  # noqa: BLE001
        out["bilibili"]["nickname"] = ""
    return {"platforms": out, "browsers": list(SUPPORTED_BROWSERS)}


@router.post("/api/auth/bilibili/qr")
def bilibili_qr_create():
    try:
        data = bilibili_qr.generate_qr()
    except bilibili_qr.QRLoginError as e:
        raise HTTPException(status_code=502, detail=e.message) from e
    qr = segno.make(data["url"], error="m")
    return {"qrcode_key": data["qrcode_key"], "qr_data_url": qr.png_data_uri(scale=6),
            "expires_in": 180}


@router.get("/api/auth/bilibili/qr/{qrcode_key}")
def bilibili_qr_poll(qrcode_key: str):
    settings = get_settings()
    try:
        return bilibili_qr.poll_qr(settings, qrcode_key)
    except bilibili_qr.QRLoginError as e:
        raise HTTPException(status_code=502, detail=e.message) from e


@router.post("/api/auth/cookies/{platform}/upload")
async def cookies_upload(platform: str, file: UploadFile):
    _check_platform(platform)
    settings = get_settings()
    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        count = cookies_mod.save_text(settings, platform, text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "count": count}


class ImportReq(BaseModel):
    browser: str = "chrome"
    profile: str = ""


@router.post("/api/auth/cookies/{platform}/import")
def cookies_import(platform: str, req: ImportReq):
    _check_platform(platform)
    if req.browser not in SUPPORTED_BROWSERS:
        raise HTTPException(status_code=400, detail=f"不支持的浏览器: {req.browser}")
    settings = get_settings()
    try:
        count = cookies_mod.import_from_browser(settings, platform, req.browser, req.profile)
    except Exception as e:  # noqa: BLE001
        log.warning("浏览器导入 %s/%s 失败: %s", platform, req.browser, e)
        raise HTTPException(status_code=400, detail=f"导入失败: {e}") from e
    if count == 0:
        raise HTTPException(status_code=400, detail="未从浏览器导出任何 cookie（该浏览器可能未登录此网站）")
    return {"ok": True, "count": count}


@router.delete("/api/auth/cookies/{platform}")
def cookies_delete(platform: str):
    _check_platform(platform)
    settings = get_settings()
    return {"deleted": cookies_mod.delete(settings, platform)}
