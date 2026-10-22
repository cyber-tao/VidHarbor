"""粘贴文本规范化：从分享文案中提取 URL，并展开短链。

用户从抖音/TikTok 手机 App 分享得到的是「乱码文案 + 短链」混合文本，
直接交给 yt-dlp 会报 "is not a valid URL"。这里统一在任务创建时清洗。
"""
from __future__ import annotations

import logging
import re
from typing import Callable

import httpx

log = logging.getLogger("vidharbor.urlnorm")

# URL 字符集排除 CJK 与常见中文标点（分享文案里链接常紧跟中文，无空格分隔）
_URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")

# 需要跟随 302 展开的短链/中转域名 → 所属平台（其余平台 yt-dlp 自身能处理重定向；
# 展开请求按所属平台走出口代理）
_SHORT_HOSTS: tuple[tuple[str, str], ...] = (
    ("v.douyin.com", "douyin"),
    ("iesdouyin.com/share/video", "douyin"),
    ("vm.tiktok.com", "tiktok"),
    ("vt.tiktok.com", "tiktok"),
    ("www.tiktok.com/t/", "tiktok"),
    ("m.tiktok.com/v/", "tiktok"),
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 某些短链（尤其 vm.tiktok.com）用浏览器 UA 会返回 200 落地页而非 302，
# 爬虫 UA 才给出纯重定向
_EXPAND_HEADERS = {"User-Agent": "facebookexternalhit/1.1"}


def extract_urls(text: str) -> list[str]:
    """从任意粘贴文本提取 http(s) 链接，按出现顺序去重。"""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for m in _URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;:!?)]}>'\"`|")
        if u not in seen:
            seen.add(u)
            found.append(u)
    return found


def short_url_platform(url: str) -> str:
    """短链所属平台；不是需要展开的短链时返回空串。"""
    u = (url or "").lower()
    return next((platform for host, platform in _SHORT_HOSTS if host in u), "")


def is_short_url(url: str) -> bool:
    return bool(short_url_platform(url))


def expand_short_url(url: str, timeout: float = 8.0, max_hops: int = 4, proxy: str = "") -> str:
    """展开 v.douyin.com / vm.tiktok.com 等短链为规范视频 URL。

    展开失败（网络错误/无限循环/落地页）时原样返回，交由后续引擎报错。
    """
    if not is_short_url(url):
        return url
    current = url
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout,
                          headers=_EXPAND_HEADERS, proxy=proxy or None) as client:
            for _ in range(max_hops):
                if not is_short_url(current):
                    break
                r = client.get(current)
                loc = r.headers.get("location")
                if not loc or r.status_code not in (301, 302, 303, 307, 308):
                    break
                if loc.startswith("/"):
                    base = httpx.URL(current)
                    loc = str(base.join(loc))
                current = loc
    except Exception as e:  # noqa: BLE001
        log.warning("短链展开失败 %s: %s", url, e)
        return url
    if current != url:
        log.info("短链展开: %s -> %s", url, current[:120])
    return current


def normalize_inputs(lines: list[str], expand: bool = True,
                     proxy_for: Callable[[str], str] | None = None) -> list[str]:
    """任务创建入口的统一清洗：逐行提取 URL、展开短链、去重。

    没提取到 URL 的行原样保留（维持旧行为，不静默丢弃用户输入）。
    proxy_for(platform) 给出短链所属平台的出口代理（与该平台的下载走同一个代理）。
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        for u in extract_urls(raw) or [raw.strip()]:
            if not u or u in seen:
                continue
            if expand and is_short_url(u):
                proxy = proxy_for(short_url_platform(u)) if proxy_for else ""
                u = expand_short_url(u, proxy=proxy)
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
    return out
