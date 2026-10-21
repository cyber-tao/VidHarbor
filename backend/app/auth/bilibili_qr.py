"""B站扫码登录：passport 二维码接口 generate/poll（无 CORS 限制，由后端代理）。

成功后从 poll 响应（Set-Cookie + crossDomain URL 参数）提取 SESSDATA 等，
写入 data/cookies/bilibili.txt（Netscape 格式，供 yt-dlp 与榜单接口使用）。
接口文档：bilibili-API-collect login/QR.md（2026-10 实测）。
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

import httpx

from ..config import Settings
from . import cookies as cookies_mod

log = logging.getLogger("vidharbor.auth.bilibili_qr")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"

# 需要保留的登录态 cookie 名
WANTED_COOKIES = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid")


class QRLoginError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def generate_qr() -> dict:
    """申请二维码：{qrcode_key, url}（url 用于生成二维码图片）。"""
    r = httpx.get(GENERATE_URL, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"},
                  timeout=15)
    data = r.json()
    if data.get("code") != 0:
        raise QRLoginError(f"申请二维码失败: code={data.get('code')} {data.get('message')}")
    d = data.get("data") or {}
    if not d.get("qrcode_key") or not d.get("url"):
        raise QRLoginError("申请二维码返回为空")
    return {"qrcode_key": str(d["qrcode_key"]), "url": str(d["url"])}


def _extract_cookies(resp: httpx.Response, data_url: str) -> dict[str, str]:
    """从 Set-Cookie 响应头与 crossDomain URL 参数中提取登录 cookie。"""
    found: dict[str, str] = {}
    for raw in resp.headers.get_list("set-cookie"):
        name, _, rest = raw.partition("=")
        name = name.strip()
        if name in WANTED_COOKIES:
            found[name] = rest.split(";", 1)[0].strip()
    # 2025-08 起 poll 成功时 cookie 也可能挂在 data.url 的查询参数里
    try:
        for k, v in parse_qs(urlparse(data_url).query).items():
            if k in WANTED_COOKIES and k not in found:
                found[k] = v[0]
    except Exception:  # noqa: BLE001
        pass
    return found


def _write_netscape(settings: Settings, cookie_dict: dict[str, str]) -> int:
    lines = ["# Netscape HTTP Cookie File", "# VidHarbor B站扫码登录导出"]
    for name, value in cookie_dict.items():
        # domain  include_subdomains  path  secure  expiry  name  value
        lines.append(f".bilibili.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
    return cookies_mod.save_text(settings, "bilibili", "\n".join(lines) + "\n")


def poll_qr(settings: Settings, qrcode_key: str) -> dict:
    """轮询扫码状态。返回 {status: waiting|scanned|success|expired, nickname?}。"""
    r = httpx.get(POLL_URL, params={"qrcode_key": qrcode_key},
                  headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"}, timeout=15)
    data = r.json()
    if data.get("code") != 0:
        raise QRLoginError(f"轮询失败: code={data.get('code')} {data.get('message')}")
    d = data.get("data") or {}
    code = int(d.get("code") or 0)
    if code == 86101:
        return {"status": "waiting"}
    if code == 86090:
        return {"status": "scanned"}
    if code == 86038:
        return {"status": "expired"}
    if code == 0:
        cookie_dict = _extract_cookies(r, str(d.get("url") or ""))
        if "SESSDATA" not in cookie_dict:
            raise QRLoginError("登录成功但未拿到 SESSDATA（接口行为变化，请改用浏览器导入 cookies）")
        _write_netscape(settings, cookie_dict)
        nickname = _nickname(cookie_dict)
        return {"status": "success", "nickname": nickname}
    raise QRLoginError(f"未知扫码状态: code={code} {d.get('message') or ''}")


def _nickname(cookie_dict: dict[str, str]) -> str:
    header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    try:
        r = httpx.get(NAV_URL, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/",
                                        "Cookie": header}, timeout=10)
        data = r.json().get("data") or {}
        if data.get("isLogin"):
            return str(data.get("uname") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def login_nickname(settings: Settings) -> str:
    """用已保存的 cookies 探测 B站登录昵称（未登录返回空串），供状态接口展示。"""
    pairs = dict(cookies_mod.read_pairs(settings, "bilibili"))
    if "SESSDATA" not in pairs:
        return ""
    return _nickname(pairs)
