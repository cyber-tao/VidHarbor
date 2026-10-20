import json

from app.charts.base import ChartError
from app.charts.bilibili import BilibiliProvider
from app.charts.douyin import DouyinProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestBilibili:
    SAMPLE = {
        "code": 0, "message": "OK",
        "data": {"list": [
            {
                "aid": 117466583799078, "bvid": "BV1kMJv6pEPK", "tid": 95,
                "pic": "http://i2.hdslb.com/bfs/archive/1.jpg",
                "title": "测试视频标题", "duration": 19,
                "owner": {"name": "测试UP主"},
                "stat": {"view": 1234567, "like": 88888, "danmaku": 999},
            },
        ]},
    }

    def test_fetch(self, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["url"] = url
            captured["params"] = kw.get("params")
            return _FakeResponse(self.SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        items = BilibiliProvider().fetch("all")
        assert captured["params"]["rid"] == "0"
        assert len(items) == 1
        it = items[0]
        assert it.source_id == "BV1kMJv6pEPK"
        assert it.title == "测试视频标题"
        assert it.author == "测试UP主"
        assert it.url == "https://www.bilibili.com/video/BV1kMJv6pEPK"
        assert it.views == 1234567
        assert it.downloadable is True

    def test_category_rid_mapping(self, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["params"] = kw.get("params")
            return _FakeResponse(self.SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        BilibiliProvider().fetch("4")
        assert captured["params"]["rid"] == "4"

    def test_error_code_raises(self, monkeypatch):
        monkeypatch.setattr(
            "app.charts.bilibili.httpx.get",
            lambda *a, **kw: _FakeResponse({"code": -352, "message": "风控"}),
        )
        try:
            BilibiliProvider().fetch("all")
            raise AssertionError("应当抛出 ChartError")
        except ChartError as e:
            assert "-352" in str(e)


class TestDouyin:
    SAMPLE = {
        "status_code": 0,
        "data": {"word_list": [
            {"position": 1, "word": "测试热搜词", "hot_value": 12345678, "label": "热"},
            {"position": 2, "word": "第二个词", "hot_value": 999},
        ]},
    }

    def test_fetch_words(self, monkeypatch):
        monkeypatch.setattr(
            "app.charts.douyin.httpx.get", lambda *a, **kw: _FakeResponse(self.SAMPLE)
        )
        items = DouyinProvider().fetch("hot")
        assert len(items) == 2
        assert items[0].title == "测试热搜词"
        assert items[0].views == 12345678
        assert items[0].downloadable is False
        assert "douyin.com/search" in items[0].url

    def test_empty_raises(self, monkeypatch):
        monkeypatch.setattr(
            "app.charts.douyin.httpx.get", lambda *a, **kw: _FakeResponse({"data": {}})
        )
        try:
            DouyinProvider().fetch("hot")
            raise AssertionError("应当抛出 ChartError")
        except ChartError:
            pass


class TestTrendingItem:
    def test_to_dict_roundtrip(self):
        from app.charts.base import TrendingItem

        d = TrendingItem(source_id="x", title="t", views=5, extra={"rank": 1}).to_dict()
        assert json.loads(json.dumps(d))["views"] == 5
