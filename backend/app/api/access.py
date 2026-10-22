"""可选访问令牌：设置 VIDHARBOR_TOKEN 后，除 /api/health 与会话接口外的所有 API 需鉴权。

程序化调用带 X-Vidharbor-Token 头；浏览器用令牌换取 HttpOnly 会话 Cookie
（POST /api/auth/session），之后 fetch / SSE / <video> 等同源请求自动携带，
令牌不再出现在 URL 与访问日志里。不配置时不鉴权（本机部署默认）。
令牌不进 Settings/DB，避免被设置页回显或覆盖。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

_AUTH_TOKEN = os.environ.get("VIDHARBOR_TOKEN", "").strip()

SESSION_COOKIE = "vidharbor_session"
_SESSION_MAX_AGE = 365 * 24 * 3600

router = APIRouter()


def _token_matches(supplied: str | None) -> bool:
    # 按字节比较：compare_digest 对含非 ASCII 字符的 str 会抛 TypeError（变成 500）
    return bool(supplied) and secrets.compare_digest(_AUTH_TOKEN.encode(), supplied.encode())


def _session_value() -> str:
    """Cookie 里存令牌的 HMAC 派生值而非原文：值恒为 ASCII，令牌原文也不落在浏览器里。"""
    return hmac.new(_AUTH_TOKEN.encode(), b"vidharbor-session", hashlib.sha256).hexdigest()


def is_authenticated(request: Request) -> bool:
    if not _AUTH_TOKEN:
        return True
    if _token_matches(request.headers.get("X-Vidharbor-Token")):
        return True
    cookie = request.cookies.get(SESSION_COOKIE, "")
    return bool(cookie) and secrets.compare_digest(cookie.encode(), _session_value().encode())


async def require_token(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="缺少或无效的访问令牌")


class SessionIn(BaseModel):
    token: str


@router.get("/api/auth/session")
def session_status(request: Request):
    return {"required": bool(_AUTH_TOKEN), "authenticated": is_authenticated(request)}


@router.post("/api/auth/session")
def create_session(req: SessionIn, request: Request, response: Response):
    if not _AUTH_TOKEN:
        return {"required": False, "authenticated": True}
    if not _token_matches(req.token.strip()):
        raise HTTPException(status_code=401, detail="访问令牌无效")
    response.set_cookie(
        SESSION_COOKIE, _session_value(), max_age=_SESSION_MAX_AGE, path="/",
        httponly=True, samesite="strict", secure=request.url.scheme == "https",
    )
    return {"required": True, "authenticated": True}
