"""平台 cookies 管理：每平台独立 Netscape cookies.txt（data/cookies/{platform}.txt）。

来源：B站扫码登录 / 浏览器导入（yt-dlp 解密）/ 手动上传。

浏览器导入的两个已知限制（都会转成可操作的中文提示）：
- Windows 上浏览器运行中会锁定 cookies 数据库（yt-dlp #7271），需完全退出后重试；
- Chrome/Edge 127+ 启用应用绑定加密（ABE），yt-dlp 无法解密（yt-dlp #10927），
  只能用扩展导出 cookies.txt 上传，或改从 Firefox 导入。
"""
from __future__ import annotations

import http.cookiejar
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import NamedTuple

from ..config import PLATFORMS, Settings

log = logging.getLogger("vidharbor.auth.cookies")

PLATFORM_NAMES = {
    "bilibili": "哔哩哔哩",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "douyin": "抖音",
}

# 各平台相关的 cookie 域（导入/上传时过滤，只保留本平台的 cookie）
PLATFORM_DOMAINS: dict[str, tuple[str, ...]] = {
    "bilibili": (".bilibili.com", ".biliapi.net", ".bilivideo.com", ".hdslb.com", ".acgvideo.com"),
    "youtube": (".youtube.com", ".google.com", ".googlevideo.com", ".youtube-nocookie.com"),
    "tiktok": (".tiktok.com", ".tiktokcdn.com", ".tiktokv.com"),
    "douyin": (".douyin.com", ".douyinpic.com", ".douyinvod.com", ".zjcdn.com", ".bytegoofp.com"),
}

BROWSER_NAMES = {
    "chrome": "Chrome", "edge": "Edge", "firefox": "Firefox", "brave": "Brave",
    "chromium": "Chromium", "opera": "Opera", "vivaldi": "Vivaldi", "safari": "Safari",
}

# Windows 上 Chromium 系浏览器用户数据目录（Local State 所在处，相对 %LOCALAPPDATA%；
# opera 的 Local State 直接在 profile 目录下，相对 %APPDATA%）
_CHROMIUM_DATA_DIRS = {
    "chrome": ("Google", "Chrome", "User Data"),
    "edge": ("Microsoft", "Edge", "User Data"),
    "brave": ("BraveSoftware", "Brave-Browser", "User Data"),
    "chromium": ("Chromium", "User Data"),
    "vivaldi": ("Vivaldi", "User Data"),
}
_OPERA_DATA_DIR = ("Opera Software", "Opera Stable")


HTTPONLY_PREFIX = "#HttpOnly_"


class NetscapeCookie(NamedTuple):
    domain: str
    name: str
    value: str
    line: str  # 原始行，保存时原样写回（保留 #HttpOnly_ 标记）


def parse_netscape(text: str, *, strict: bool = False) -> list[NetscapeCookie]:
    """解析 Netscape cookies.txt（全项目唯一实现）。

    `#HttpOnly_` 开头的行是 HttpOnly cookie（curl、标准库 MozillaCookieJar 等的写法），
    不是注释——SESSDATA / sessionid 这类登录态恰恰都是 HttpOnly。
    strict=True 时字段不足 7 列抛 ValueError（上传校验用），否则跳过该行。
    """
    cookies: list[NetscapeCookie] = []
    for raw in text.removeprefix("\ufeff").splitlines():
        line = raw.strip(" ")
        entry = line[len(HTTPONLY_PREFIX):] if line.startswith(HTTPONLY_PREFIX) else line
        if not entry.strip() or entry.startswith("#"):
            continue
        parts = entry.split("\t")
        if len(parts) < 7:
            if strict:
                raise ValueError(
                    "格式不符：需要 Netscape 格式 cookies.txt（推荐浏览器扩展 Get cookies.txt LOCALLY 导出）"
                )
            continue
        cookies.append(NetscapeCookie(domain=parts[0], name=parts[5], value=parts[6], line=line))
    return cookies


def cookie_path(settings: Settings, platform: str) -> Path:
    return settings.cookies_dir / f"{platform}.txt"


def _domain_allowed(domain: str, platform: str) -> bool:
    d = domain.lower().lstrip(".")
    return any(d == pat.lstrip(".") or d.endswith(pat) for pat in PLATFORM_DOMAINS[platform])


def read_cookies(path: Path | None, platform: str) -> list[NetscapeCookie]:
    """读取 cookies 文件中属于该平台域名的条目；文件缺失或不可读时返回空列表。"""
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [c for c in parse_netscape(text) if _domain_allowed(c.domain, platform)]


def cookie_jar(settings: Settings, platform: str) -> dict[str, str]:
    """平台生效的 cookies（专属文件优先，回退全局 cookies_file）→ {name: value}，同名取后者。

    按平台域名过滤：全局 cookies.txt 常混有其他站点（如 Google）的登录态，不能发给本平台。
    """
    return {c.name: c.value for c in read_cookies(settings.cookie_file_for(platform), platform)}


def cookie_header(jar: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in jar.items())


def save_text(settings: Settings, platform: str, text: str) -> int:
    """保存上传的 cookies.txt 内容（只保留该平台域名的行），返回 cookie 条数。"""
    kept = [c.line for c in parse_netscape(text, strict=True) if _domain_allowed(c.domain, platform)]
    if not kept:
        raise ValueError(
            f"文件中没有属于该平台域名（{'、'.join(PLATFORM_DOMAINS[platform])}）的 cookie"
        )
    path = cookie_path(settings, platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "# Netscape HTTP Cookie File (exported by VidHarbor)\n"
    path.write_text(header + "\n".join(kept) + "\n", encoding="utf-8")
    log.info("保存 %s cookies: %d 条 → %s", platform, len(kept), path)
    return len(kept)


def save_cookiejar(settings: Settings, platform: str, jar) -> int:
    """把 MozillaCookieJar/YoutubeDLCookieJar 写为平台 cookies 文件（按域名过滤）。"""
    filtered = http.cookiejar.MozillaCookieJar()
    for cookie in jar:
        if _domain_allowed(cookie.domain, platform):
            filtered.set_cookie(cookie)
    if not filtered:
        return 0
    path = cookie_path(settings, platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    filtered.save(filename=str(path), ignore_discard=True, ignore_expires=True)
    count = len(parse_netscape(path.read_text(encoding="utf-8", errors="replace")))
    log.info("保存 %s cookies: %d 条 → %s", platform, count, path)
    return count


def _local_state_path(browser: str) -> Path | None:
    """Windows 上 Chromium 系浏览器 Local State 路径；找不到返回 None。"""
    if sys.platform != "win32":
        return None
    if browser == "opera":
        base_env = os.environ.get("APPDATA")
        rel = _OPERA_DATA_DIR
    elif browser in _CHROMIUM_DATA_DIRS:
        base_env = os.environ.get("LOCALAPPDATA")
        rel = _CHROMIUM_DATA_DIRS[browser]
    else:
        return None
    if not base_env:
        return None
    path = Path(base_env).joinpath(*rel) / "Local State"
    return path if path.exists() else None


def _check_app_bound_encryption(browser: str) -> None:
    """Chrome/Edge 127+ 应用绑定加密（ABE）：v20 cookies 无法解密，直接给出替代方案。"""
    path = _local_state_path(browser)
    if path is None:
        return
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if "app_bound_encrypted_key" in state.get("os_crypt", {}):
        name = BROWSER_NAMES.get(browser, browser)
        raise ValueError(
            f"{name} 127+ 启用了应用绑定加密（App-Bound Encryption），yt-dlp 无法解密其 cookies。"
            "请改用浏览器扩展 Get cookies.txt LOCALLY 导出后上传，或在 Firefox 登录后从 Firefox 导入"
        )


def _friendly_browser_error(browser: str, exc: Exception) -> str:
    name = BROWSER_NAMES.get(browser, browser)
    text = str(exc)
    if "7271" in text or "Could not copy" in text:
        return f"{name} 正在运行，cookies 数据库被锁定。请完全退出 {name}（包括后台/托盘进程）后重试"
    if "10927" in text or "DPAPI" in text:
        return (
            f"无法解密 {name} 的 cookies（应用绑定加密）。"
            "请改用浏览器扩展 Get cookies.txt LOCALLY 导出后上传，或在 Firefox 登录后从 Firefox 导入"
        )
    if "could not find" in text.lower() or "could not locate" in text.lower():
        return f"未找到 {name} 的 cookies 数据（浏览器未安装、未登录或 profile 不存在）"
    return f"{type(exc).__name__}: {text}"


def import_from_browser(settings: Settings, platform: str, browser: str, profile: str = "") -> int:
    """从本机浏览器解密导出 cookies（yt-dlp 实现，跨平台；Linux 需可用密钥环）。"""
    from yt_dlp import cookies as ydl_cookies

    _check_app_bound_encryption(browser)
    try:
        jar = ydl_cookies.extract_cookies_from_browser(browser, profile=profile or None)
    except Exception as e:  # noqa: BLE001  统一转成可操作的提示
        raise ValueError(_friendly_browser_error(browser, e)) from e
    return save_cookiejar(settings, platform, jar)


def delete(settings: Settings, platform: str) -> bool:
    path = cookie_path(settings, platform)
    if path.exists():
        path.unlink()
        return True
    return False


def read_pairs(settings: Settings, platform: str) -> list[tuple[str, str]]:
    """读取平台专属 cookies 文件为 (name, value) 列表（不回退全局 cookies_file）。"""
    return [(c.name, c.value) for c in read_cookies(cookie_path(settings, platform), platform)]


def status(settings: Settings) -> dict:
    out: dict = {}
    for p in PLATFORMS:
        path = cookie_path(settings, p)
        entry: dict = {"platform": p, "name": PLATFORM_NAMES.get(p, p),
                       "exists": path.exists()}
        if path.exists():
            st = path.stat()
            entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            entry["size"] = st.st_size
        out[p] = entry
    return out
