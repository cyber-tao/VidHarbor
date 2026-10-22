"""粘贴文本清洗：URL 提取 + 短链展开。"""
import httpx
import pytest

from app.downloader.urlnorm import (
    expand_short_url,
    extract_urls,
    is_short_url,
    normalize_inputs,
    short_url_platform,
)


class TestExtract:
    def test_plain_url(self):
        assert extract_urls("https://www.douyin.com/video/123") == [
            "https://www.douyin.com/video/123"
        ]

    def test_douyin_share_text(self):
        text = "7.35 p@e.Bt 12/14 ztc:/ 11/15 复制打开抖音 https://v.douyin.com/iAbCdEf/ 快来看"
        assert extract_urls(text) == ["https://v.douyin.com/iAbCdEf/"]

    def test_url_glued_to_cjk(self):
        # 分享文案里链接后常直接跟中文，无空格
        assert extract_urls("看https://v.douyin.com/iAbCdEf/复制打开抖音") == [
            "https://v.douyin.com/iAbCdEf/"
        ]

    def test_trailing_punctuation_stripped(self):
        assert extract_urls("链接是 https://youtu.be/abc123。") == ["https://youtu.be/abc123"]

    def test_multiple_and_dedupe(self):
        urls = extract_urls("a https://a.com/1 b https://b.com/2 c https://a.com/1")
        assert urls == ["https://a.com/1", "https://b.com/2"]

    def test_no_url_returns_empty(self):
        assert extract_urls("纯文字没有链接") == []

    def test_scheme_required(self):
        assert extract_urls("www.douyin.com/video/1") == []


class TestShortUrl:
    def test_known_short_hosts(self):
        assert is_short_url("https://v.douyin.com/iAbCdEf/")
        assert is_short_url("https://vm.tiktok.com/ZM12345/")
        assert is_short_url("https://vt.tiktok.com/ZM12345/")
        assert is_short_url("https://www.tiktok.com/t/ZTRC5xgJp")
        assert not is_short_url("https://www.douyin.com/video/123")
        assert not is_short_url("https://www.youtube.com/watch?v=x")

    def test_expand_follows_redirects(self, monkeypatch):
        hops = [
            ("https://v.douyin.com/abc/", "https://www.iesdouyin.com/share/video/1/"),
            ("https://www.iesdouyin.com/share/video/1/", "https://www.douyin.com/video/7638421607305230298"),
        ]
        table = {h[0]: h[1] for h in hops}

        def handler(request):
            target = table.get(str(request.url))
            if target:
                return httpx.Response(302, headers={"location": target})
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)

        class _Client(httpx.Client):
            def __init__(self, **kw):
                kw.pop("follow_redirects", None)
                super().__init__(transport=transport, **kw)

        monkeypatch.setattr("app.downloader.urlnorm.httpx.Client", _Client)
        got = expand_short_url("https://v.douyin.com/abc/")
        assert got == "https://www.douyin.com/video/7638421607305230298"

    def test_expand_failure_returns_original(self, monkeypatch):
        def handler(request):
            return httpx.Response(500)

        transport = httpx.MockTransport(handler)

        class _Client(httpx.Client):
            def __init__(self, **kw):
                kw.pop("follow_redirects", None)
                super().__init__(transport=transport, **kw)

        monkeypatch.setattr("app.downloader.urlnorm.httpx.Client", _Client)
        url = "https://v.douyin.com/abc/"
        assert expand_short_url(url) == url

    def test_non_short_passthrough(self):
        assert expand_short_url("https://www.douyin.com/video/1") == "https://www.douyin.com/video/1"

    def test_expand_uses_given_proxy(self, monkeypatch):
        seen = {}

        class _Client(httpx.Client):
            def __init__(self, **kw):
                seen["proxy"] = kw.get("proxy")
                kw.pop("follow_redirects", None)
                kw.pop("proxy", None)
                super().__init__(transport=httpx.MockTransport(lambda r: httpx.Response(200)), **kw)

        monkeypatch.setattr("app.downloader.urlnorm.httpx.Client", _Client)
        expand_short_url("https://vm.tiktok.com/ZM1/", proxy="http://proxy.test:7890")
        assert seen["proxy"] == "http://proxy.test:7890"

    def test_short_url_platform(self):
        assert short_url_platform("https://v.douyin.com/abc/") == "douyin"
        assert short_url_platform("https://vm.tiktok.com/ZM1/") == "tiktok"
        assert short_url_platform("https://www.youtube.com/watch?v=x") == ""


class TestNormalizeInputs:
    def test_share_text_to_canonical(self, monkeypatch):
        monkeypatch.setattr(
            "app.downloader.urlnorm.expand_short_url",
            lambda u, **kw: "https://www.douyin.com/video/7638421607305230298" if is_short_url(u) else u,
        )
        out = normalize_inputs(["7.35 复制打开抖音 https://v.douyin.com/iAbCdEf/ 关注"])
        assert out == ["https://www.douyin.com/video/7638421607305230298"]

    def test_expansion_goes_through_platform_proxy(self, monkeypatch):
        seen = {}

        def fake_expand(u, **kw):
            seen[u] = kw.get("proxy")
            return u

        monkeypatch.setattr("app.downloader.urlnorm.expand_short_url", fake_expand)
        normalize_inputs(["https://vm.tiktok.com/ZM1/", "https://v.douyin.com/abc/"],
                         proxy_for=lambda platform: "http://proxy.test:7890" if platform == "tiktok" else "")
        assert seen == {"https://vm.tiktok.com/ZM1/": "http://proxy.test:7890",
                        "https://v.douyin.com/abc/": ""}

    def test_line_without_url_kept(self):
        assert normalize_inputs(["not a url"]) == ["not a url"]

    def test_dedupe_after_expansion(self, monkeypatch):
        monkeypatch.setattr(
            "app.downloader.urlnorm.expand_short_url",
            lambda u, **kw: "https://www.tiktok.com/@a/video/1" if is_short_url(u) else u,
        )
        out = normalize_inputs([
            "https://vm.tiktok.com/ZM1/",
            "https://www.tiktok.com/@a/video/1",
        ])
        assert out == ["https://www.tiktok.com/@a/video/1"]
