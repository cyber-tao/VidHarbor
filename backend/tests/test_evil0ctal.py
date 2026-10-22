"""Evil0ctal v5 客户端：响应映射 + 错误处理（mock 服务响应）。"""
import httpx
import pytest

from app.config import Settings
from app.downloader import evil0ctal as mod
from app.downloader.evil0ctal import (
    Evil0ctalClient,
    Evil0ctalError,
    evil0ctal_download,
)


def _client_with(handler):
    transport = httpx.MockTransport(handler)

    def _post(url, **kw):
        kw.pop("timeout", None)
        return httpx.Client(transport=transport).post(url, **kw)

    return _post


PARSE_OK = {
    "success": True,
    "data": {
        "kind": "video",
        "platform": "douyin",
        "content_id": "7638421607305230298",
        "title": "你说它是憨呢还是犟",
        "description": "描述文字",
        "created_at": "2026-05-11T00:17:00Z",
        "duration_ms": 12067,
        "web_url": "https://www.douyin.com/video/7638421607305230298",
        "tags": ["小奶包猫咪", "蓝金渐层"],
        "stats": {"digg_count": 1153083, "play_count": None, "comment_count": 20064},
        "author": {"nickname": "豆包是只猫", "unique_id": "97242682195"},
        "media": {
            "video": {"url": "http://cdn.test/video.mp4", "urls": [], "watermark": False},
            "covers": [],
        },
    },
    "error": None,
}


class TestSocksDependency:
    def test_socks_proxy_client_constructible(self):
        """socks5:// 代理是文档/设置页承诺的能力：httpx 需 socksio（httpx[socks] extra），
        缺失时 Client 构造即抛 ImportError，榜单与 Evil0ctal 兜底全部不可用。"""
        httpx.Client(proxy=httpx.Proxy("socks5://127.0.0.1:1080"))


class TestClient:
    def test_parse_success(self, monkeypatch):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers.get("authorization")
            seen["path"] = request.url.path
            return httpx.Response(200, json=PARSE_OK)

        monkeypatch.setattr(mod.httpx, "post", _client_with(handler))
        data = Evil0ctalClient("http://svc", "dtk_key").parse("https://www.douyin.com/video/1")
        assert data["content_id"] == "7638421607305230298"
        assert seen["auth"] == "Bearer dtk_key"
        assert seen["path"] == "/api/v1/parse"

    def test_parse_business_error(self, monkeypatch):
        body = {"success": False, "error": {"code": "IDENTITY_POOL_EXHAUSTED", "message": "no identity"}}

        def handler(request):
            return httpx.Response(200, json=body)

        monkeypatch.setattr(mod.httpx, "post", _client_with(handler))
        with pytest.raises(Evil0ctalError) as ei:
            Evil0ctalClient("http://svc").parse("https://www.douyin.com/video/1")
        assert ei.value.code == "IDENTITY_POOL_EXHAUSTED"
        assert "身份池" in str(ei.value)

    def test_parse_401(self, monkeypatch):
        def handler(request):
            return httpx.Response(401)

        monkeypatch.setattr(mod.httpx, "post", _client_with(handler))
        with pytest.raises(Evil0ctalError) as ei:
            Evil0ctalClient("http://svc", "bad").parse("https://www.douyin.com/video/1")
        assert ei.value.code == "UNAUTHORIZED"

    def test_health(self, monkeypatch):
        def handler(request):
            return httpx.Response(200) if request.url.path == "/readyz" else httpx.Response(404)

        transport = httpx.MockTransport(handler)

        def _get(url, **kw):
            kw.pop("timeout", None)
            return httpx.Client(transport=transport).get(url, **kw)

        monkeypatch.setattr(mod.httpx, "get", _get)
        assert Evil0ctalClient("http://svc").health() is True


class TestDownload:
    def test_full_mapping_and_download(self, monkeypatch, tmp_path):
        def post_handler(request):
            return httpx.Response(200, json=PARSE_OK)

        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"v" * 64

        def stream_handler(request):
            return httpx.Response(
                200, content=mp4,
                headers={"content-length": str(len(mp4))},
            )

        post_transport = httpx.MockTransport(post_handler)
        stream_transport = httpx.MockTransport(stream_handler)

        def fake_post(url, **kw):
            kw.pop("timeout", None)
            return httpx.Client(transport=post_transport).post(url, **kw)

        class FakeStream:
            def __init__(self, method, url, **kw):
                self._r = httpx.Response(
                    200, content=mp4,
                    headers={"content-length": str(len(mp4))},
                    request=httpx.Request(method, url),
                )

            def __enter__(self):
                return self._r

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        monkeypatch.setattr(mod.httpx, "stream", lambda m, u, **kw: FakeStream(m, u))

        raw = evil0ctal_download("https://www.douyin.com/video/7638421607305230298",
                                 Settings(), tmp_path)
        assert raw.ok, raw.error
        assert raw.engine == "evil0ctal"
        assert raw.media_path.read_bytes() == mp4

        info = raw.info
        assert info["id"] == "7638421607305230298"
        assert info["title"] == "你说它是憨呢还是犟"
        assert info["uploader"] == "豆包是只猫"
        assert info["uploader_id"] == "97242682195"
        assert info["upload_date"] == "20260511"  # UTC+8 换算后
        assert info["duration"] == pytest.approx(12.067)
        assert info["like_count"] == 1153083
        assert info["comment_count"] == 20064
        assert info["tags"] == ["小奶包猫咪", "蓝金渐层"]
        assert info["extractor_key"] == "Douyin"

    def test_cover_fetch_uses_platform_proxy(self, monkeypatch, tmp_path):
        import copy

        body = copy.deepcopy(PARSE_OK)
        body["data"]["media"]["covers"] = [{"url": "http://cdn.test/cover.jpeg"}]
        seen = {}

        class FakeStream:
            def __init__(self, method, url, **kw):
                seen["video_proxy"] = kw.get("proxy")
                self._r = httpx.Response(200, content=b"v" * 16, request=httpx.Request(method, url))

            def __enter__(self):
                return self._r

            def __exit__(self, *a):
                return False

        def fake_get(url, **kw):
            seen["cover_proxy"] = kw.get("proxy")
            return httpx.Response(200, content=b"jpeg", request=httpx.Request("GET", url))

        monkeypatch.setattr(mod.httpx, "post", _client_with(lambda r: httpx.Response(200, json=body)))
        monkeypatch.setattr(mod.httpx, "stream", FakeStream)
        monkeypatch.setattr(mod.httpx, "get", fake_get)
        s = Settings(download={"proxy": "http://proxy.test:7890", "proxy_platforms": ["douyin"]})
        raw = evil0ctal_download("https://www.douyin.com/video/7638421607305230298", s, tmp_path)
        assert raw.ok and raw.thumbnail_path is not None
        assert seen == {"video_proxy": "http://proxy.test:7890", "cover_proxy": "http://proxy.test:7890"}

    def test_image_kind_rejected(self, monkeypatch, tmp_path):
        body = {"success": True, "data": {"kind": "images", "platform": "douyin"}}

        def handler(request):
            return httpx.Response(200, json=body)

        monkeypatch.setattr(mod.httpx, "post", _client_with(handler))
        raw = evil0ctal_download("https://www.douyin.com/video/1", Settings(), tmp_path)
        assert not raw.ok
        assert "图集" in raw.error or "images" in raw.error

    def test_service_down(self, monkeypatch, tmp_path):
        def handler(request):
            raise httpx.ConnectError("refused")

        def fake_post(url, **kw):
            return httpx.Client(transport=httpx.MockTransport(handler)).post(url)

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        raw = evil0ctal_download("https://www.douyin.com/video/1", Settings(), tmp_path)
        assert not raw.ok
        assert "Evil0ctal" in raw.error
