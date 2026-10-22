import json

from app.charts.base import ChartError
from app.charts.bilibili import BilibiliProvider
from app.charts.douyin import DouyinProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class TestBilibili:
    SAMPLE = {
        "code": 0, "message": "OK",
        "data": {"list": [
            {
                "aid": 117466583799078, "bvid": "BV1kMJv6pEPK", "tid": 95,
                "pic": "http://i2.hdslb.com/bfs/archive/1.jpg",
                "title": "测试视频标题", "duration": 19, "pubdate": 1792400400,
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
        assert it.likes == 88888
        assert it.published  # pubdate → 相对时间文本
        assert it.downloadable is True

    def test_category_rid_mapping(self, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["params"] = kw.get("params")
            return _FakeResponse(self.SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        BilibiliProvider().fetch("4")
        assert captured["params"]["rid"] == "4"

    def test_sends_httponly_sessdata(self, tmp_path, monkeypatch):
        from pathlib import Path

        from app.config import Settings

        cookie_file = tmp_path / "bilibili.txt"
        cookie_file.write_text(
            "# Netscape HTTP Cookie File\n"
            "#HttpOnly_.bilibili.com\tTRUE\t/\tTRUE\t1999999999\tSESSDATA\tsess\n"
            ".google.com\tTRUE\t/\tTRUE\t1999999999\tSID\tgoogle-secret\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(Settings, "cookie_file_for",
                            lambda self, platform, _p=str(cookie_file): Path(_p))
        captured = {}

        def fake_get(url, **kw):
            captured["cookie"] = kw["headers"].get("Cookie", "")
            return _FakeResponse(self.SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        BilibiliProvider(Settings()).fetch("all")
        assert captured["cookie"] == "SESSDATA=sess"

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


class TestBilibiliPeriods:
    """时间段：分区三日榜/周榜走 ranking/region 接口。"""

    REGION_SAMPLE = {
        "code": 0,
        "data": {"list": [
            {
                "aid": 1, "bvid": "BV1region0001", "name": "分区周榜视频",
                "author": "UP", "pic": "http://i2.hdslb.com/bfs/archive/x.jpg",
                "duration": "29:58", "play": 424242,
            },
        ]},
    }

    def test_region_week_params(self, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["url"] = url
            captured["params"] = kw.get("params")
            return _FakeResponse(self.REGION_SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        items = BilibiliProvider().fetch("4", "week")
        assert "ranking/region" in captured["url"]
        assert captured["params"]["day"] == "7"
        assert captured["params"]["rid"] == "4"
        assert items[0].source_id == "BV1region0001"
        assert items[0].title == "分区周榜视频"
        assert items[0].views == 424242
        assert items[0].duration == 29 * 60 + 58

    def test_region_3d(self, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["params"] = kw.get("params")
            return _FakeResponse(self.REGION_SAMPLE)

        monkeypatch.setattr("app.charts.bilibili.httpx.get", fake_get)
        BilibiliProvider().fetch("3", "3d")
        assert captured["params"]["day"] == "3"

    def test_categories_have_periods(self):
        cats = {c["id"]: c for c in BilibiliProvider().categories()}
        assert [p["id"] for p in cats["all"]["periods"]] == ["default"]
        assert {p["id"] for p in cats["4"]["periods"]} == {"default", "3d", "week"}
        assert "weekly" in cats and "precious" in cats

    def test_normalize_fallback(self):
        p = BilibiliProvider()
        assert p.normalize("nonexistent", "bad") == ("all", "default")
        assert p.normalize("4", "week") == ("4", "week")


class TestYoutubeDouyinMeta:
    def test_youtube_custom_and_periods(self):
        from app.charts.youtube import YoutubeProvider
        from app.config import Settings
        p = YoutubeProvider(Settings())
        cat, period = p.normalize("custom:AI 科技", "week")
        assert cat == "custom:AI 科技"
        assert period == "week"
        assert p.normalize("", "") == ("trending", "month")

    def test_douyin_single_board_with_custom(self):
        cats = DouyinProvider().categories()
        assert len(cats) == 1  # 子榜参数已被抖音忽略，只保留单一热搜榜
        assert cats[0]["id"] == "hot"
        assert cats[0]["periods"][0]["name"] == "实时"
        assert cats[0]["allow_custom"] is True

    def test_downloadable_flags(self):
        # 抖音热搜是话题榜（不可直接下载），关键词搜索结果可下载
        assert DouyinProvider().is_downloadable("hot") is False
        assert DouyinProvider().is_downloadable("") is False
        assert DouyinProvider().is_downloadable("custom:猫咪") is True
        assert BilibiliProvider().is_downloadable("all") is True


class TestDouyin:
    SAMPLE = {
        "status_code": 0,
        "data": {"word_list": [
            {
                "position": 1, "word": "测试热搜词", "hot_value": 12345678,
                "sentence_id": "2704161", "label": 3, "video_count": 6,
                "event_time": 1792472616,
                "word_cover": {"url_list": ["https://p3-sign.douyinpic.com/cover.jpeg"]},
            },
            {"position": 2, "word": "第二个词", "hot_value": 999},
        ]},
    }

    def test_fetch_words(self, monkeypatch):
        monkeypatch.setattr(
            "app.charts.douyin.httpx.get", lambda *a, **kw: _FakeResponse(self.SAMPLE)
        )
        items = DouyinProvider().fetch("hot")
        assert len(items) == 2
        first = items[0]
        assert first.title == "测试热搜词"
        assert first.views == 12345678
        assert first.downloadable is False
        # 话题视频聚合页（不再是裸搜索链接）
        assert first.url == "https://www.douyin.com/hot/2704161"
        assert first.cover == "https://p3-sign.douyinpic.com/cover.jpeg"
        assert first.extra["label"] == "爆"
        assert first.extra["video_count"] == 6
        assert first.source_id == "hot-2704161"
        assert first.published  # event_time → 相对时间

    def test_word_without_sentence_id_falls_back_to_search(self, monkeypatch):
        monkeypatch.setattr(
            "app.charts.douyin.httpx.get", lambda *a, **kw: _FakeResponse(self.SAMPLE)
        )
        items = DouyinProvider().fetch("hot")
        assert "douyin.com/search/" in items[1].url
        assert items[1].extra["label"] == ""

    def test_label_mapping(self):
        from app.charts.douyin import LABELS
        assert LABELS[1] == "热" and LABELS[2] == "新"
        assert LABELS[3] == "爆" and LABELS[4] == "首发"

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

        d = TrendingItem(source_id="x", title="t", views=5, likes=2,
                         published="3天前", extra={"rank": 1}).to_dict()
        dumped = json.loads(json.dumps(d))
        assert dumped["views"] == 5
        assert dumped["likes"] == 2
        assert dumped["published"] == "3天前"


class TestFmtPublished:
    def test_epoch_to_relative(self):
        import time as _time
        from app.charts.base import fmt_published

        now = _time.time()
        assert fmt_published(None) == ""
        assert fmt_published(0) == ""
        assert "分钟前" in fmt_published(now - 120)
        assert "小时前" in fmt_published(now - 7200)
        assert "天前" in fmt_published(now - 5 * 86400)
        assert fmt_published(now - 90 * 86400).count("-") == 2  # 久远 → 日期


class TestYoutubeInnertube:
    def test_text_to_days(self):
        from app.charts.youtube import _text_to_days

        assert _text_to_days("30分钟前") < 0.1
        assert _text_to_days("5小时前") < 1
        assert _text_to_days("3天前") == 3
        assert _text_to_days("2周前") == 14
        assert _text_to_days("6个月前") == 180
        assert _text_to_days("1年前") == 365
        assert _text_to_days("") is None
        assert _text_to_days("直播中") is None

    def test_views_and_duration_parse(self):
        from app.charts.youtube import _duration_from_text, _views_from_text

        assert _views_from_text("1,234,567 次观看") == 1234567
        assert _views_from_text("120万次观看") == 1_200_000
        assert _views_from_text("1.2亿次观看") == 120_000_000
        assert _views_from_text("") == 0
        assert _duration_from_text("3:25") == 205
        assert _duration_from_text("1:02:03") == 3723
        assert _duration_from_text("") == 0

    def test_item_from_renderer(self):
        from app.charts.youtube import _item_from_renderer

        vr = {
            "videoId": "abc123",
            "title": {"runs": [{"text": "测试"}, {"text": "视频"}]},
            "ownerText": {"runs": [{"text": "频道名"}]},
            "lengthText": {"simpleText": "2:30"},
            "viewCountText": {"simpleText": "10,000 次观看"},
            "publishedTimeText": {"simpleText": "3天前"},
        }
        it = _item_from_renderer(7, vr)
        assert it.source_id == "abc123"
        assert it.title == "测试视频"
        assert it.author == "频道名"
        assert it.duration == 150
        assert it.views == 10000
        assert it.published == "3天前"
        assert it.url == "https://www.youtube.com/watch?v=abc123"

    def test_fetch_with_mocked_innertube(self, monkeypatch):
        from app.charts import youtube as ym
        from app.charts.youtube import YoutubeProvider
        from app.config import Settings

        def make_search(items_spec):
            def fake_search(query, max_pages=5, proxy=""):
                return [
                    {"videoId": f"vid{i}",
                     "title": {"runs": [{"text": f"视频{i}"}]},
                     "ownerText": {"runs": [{"text": "频道"}]},
                     "lengthText": {"simpleText": "1:00"},
                     "viewCountText": {"simpleText": f"{1000 + i} 次观看"},
                     "publishedTimeText": {"simpleText": pub}}
                    for i, pub in enumerate(items_spec)
                ]
            return fake_search

        # 过滤结果足够多（≥8）→ 真正按周期过滤：12 条中 10 条 <7 天
        spec = [f"{d}天前" for d in [1, 2, 3, 4, 5, 6, 2, 3, 4, 5]] + ["30天前", "40天前"]
        monkeypatch.setattr(ym, "_innertube_search", make_search(spec))
        items = YoutubeProvider(Settings()).fetch("trending", "week")
        assert len(items) == 10
        assert all(not it.published or it.published != "30天前" for it in items)

        # 过滤后太少（<8）→ 保留完整列表
        spec2 = [f"{i + 1}天前" for i in range(10)]
        monkeypatch.setattr(ym, "_innertube_search", make_search(spec2))
        items2 = YoutubeProvider(Settings()).fetch("trending", "week")
        assert len(items2) == 10
        assert items2[0].published == "1天前"

    def test_innertube_failure_falls_back(self, monkeypatch):
        from app.charts import youtube as ym
        from app.charts.base import ChartError
        from app.charts.youtube import YoutubeProvider
        from app.config import Settings

        def boom(query, max_pages=5, proxy=""):
            raise ChartError("network down")

        monkeypatch.setattr(ym, "_innertube_search", boom)

        def fake_ytdlp(self, query):
            from app.charts.base import TrendingItem
            return [TrendingItem(source_id="x1", title="回退结果", views=1)]

        monkeypatch.setattr(YoutubeProvider, "_fetch_ytdlp", fake_ytdlp)
        items = YoutubeProvider(Settings()).fetch("trending")
        assert len(items) == 1 and items[0].title == "回退结果"


class TestYoutubeOfficialApi:
    def _provider(self):
        from app.charts.youtube import YoutubeProvider
        from app.config import Settings
        s = Settings(youtube={"api_key": "test-key", "region_code": "US"})
        return YoutubeProvider(s)

    def test_iso_duration_and_rfc3339(self):
        from app.charts.youtube import _iso_duration_to_secs, _rfc3339_epoch

        assert _iso_duration_to_secs("PT2M30S") == 150
        assert _iso_duration_to_secs("PT1H2M3S") == 3723
        assert _iso_duration_to_secs("") == 0
        ts = _rfc3339_epoch("2026-10-19T08:15:22Z")
        assert 1792300000 < ts < 1792600000
        assert _rfc3339_epoch("") == 0

    def test_most_popular_chart(self, monkeypatch):
        captured = {}

        class _Resp:
            status_code = 200

            def __init__(self, payload):
                self._p = payload

            def json(self):
                return self._p

        api_video = {
            "id": "vid1",
            "snippet": {"title": "官方榜视频", "channelTitle": "官方频道",
                        "publishedAt": "2026-10-19T00:00:00Z"},
            "statistics": {"viewCount": "9876543", "likeCount": "123456"},
            "contentDetails": {"duration": "PT4M5S"},
        }

        def fake_get(url, params=None, **kw):
            captured["url"] = url
            captured["params"] = params
            return _Resp({"items": [api_video]})

        monkeypatch.setattr("app.charts.youtube.httpx.get", fake_get)
        items = self._provider().fetch("trending", "month")
        assert "googleapis.com/youtube/v3/videos" in captured["url"]
        assert captured["params"]["chart"] == "mostPopular"
        assert captured["params"]["key"] == "test-key"
        assert captured["params"]["regionCode"] == "US"
        assert len(items) == 1
        it = items[0]
        assert it.title == "官方榜视频"
        assert it.author == "官方频道"
        assert it.views == 9876543
        assert it.likes == 123456
        assert it.duration == 245
        assert it.published
        assert it.extra["source"] == "api"

    def test_category_uses_video_category_id(self, monkeypatch):
        captured = {}

        class _Resp:
            status_code = 200

            def __init__(self, payload):
                self._p = payload

            def json(self):
                return self._p

        monkeypatch.setattr(
            "app.charts.youtube.httpx.get",
            lambda url, params=None, **kw: (captured.update(params=params), _Resp({"items": []}))[1],
        )
        self._provider().fetch("gaming", "week")
        assert captured["params"]["videoCategoryId"] == "20"

    def test_custom_keyword_search_then_videos(self, monkeypatch):
        calls = []

        class _Resp:
            status_code = 200

            def __init__(self, payload):
                self._p = payload

            def json(self):
                return self._p

        def fake_get(url, params=None, **kw):
            calls.append(url)
            if url.endswith("/search"):
                assert params["order"] == "viewCount"
                assert params["publishedAfter"]
                return _Resp({"items": [{"id": {"videoId": "s1"}}, {"id": {"videoId": "s2"}}]})
            assert params["id"] == "s1,s2"
            return _Resp({"items": [
                {"id": "s1", "snippet": {"title": "搜索结果1", "channelTitle": "频道",
                                         "publishedAt": "2026-10-20T00:00:00Z"},
                 "statistics": {"viewCount": "100", "likeCount": "10"},
                 "contentDetails": {"duration": "PT1M"}},
                {"id": "s2", "snippet": {"title": "搜索结果2", "channelTitle": "频道",
                                         "publishedAt": "2026-10-20T01:00:00Z"},
                 "statistics": {"viewCount": "200", "likeCount": "20"},
                 "contentDetails": {"duration": "PT2M"}},
            ]})

        monkeypatch.setattr("app.charts.youtube.httpx.get", fake_get)
        items = self._provider().fetch("custom:AI", "week")
        assert len(calls) == 2  # search → videos
        assert [i.source_id for i in items] == ["s1", "s2"]
        assert items[0].title == "搜索结果1"

    def test_api_error_falls_back_to_innertube(self, monkeypatch):
        from app.charts import youtube as ym
        from app.charts.youtube import YoutubeProvider

        class _BadResp:
            status_code = 403

            def json(self):
                return {"error": {"errors": [{"reason": "quotaExceeded"}], "message": ""}}

        monkeypatch.setattr("app.charts.youtube.httpx.get", lambda *a, **kw: _BadResp())

        def fake_innertube(query, max_pages=5, proxy=""):
            return [{"videoId": f"iv{i}",
                     "title": {"runs": [{"text": f"回退{i}"}]},
                     "ownerText": {"runs": [{"text": "频道"}]},
                     "publishedTimeText": {"simpleText": "2天前"}}
                    for i in range(3)]

        def no_network(self, query, proxy=""):
            raise AssertionError("不应再回退到 yt-dlp（InnerTube 已有 3 条）")

        monkeypatch.setattr(ym, "_innertube_search", fake_innertube)
        monkeypatch.setattr(YoutubeProvider, "_fetch_ytdlp", no_network)
        items = self._provider().fetch("trending", "month")
        assert len(items) == 3 and items[0].title == "回退0"


class TestTikTokTagChart:
    """标签榜：challenge/detail 解析 ID → item_list 分页（Evil0ctal 签名链路）。"""

    DETAIL_SAMPLE = {
        "challengeInfo": {
            "challenge": {"id": 5424, "title": "funny",
                          "desc": "funny videos"},
            "stats": {"viewCount": 8774100000000},
        },
    }
    ITEM_SAMPLE = {
        "itemList": [
            {
                "id": "7057727079848103169",
                "desc": "Breaking up via Wordle #wordle\n#fyp",
                "createTime": 1792400000,
                "author": {"uniqueId": "tom.cashman", "nickname": "cashman.tom"},
                "video": {"duration": 26,
                          "originCover": "https://p16.tiktokcdn-us.com/cover.jpeg"},
                "stats": {"playCount": 3600000, "diggCount": 466000},
            },
            {  # 无 uniqueId → 链接退回 /video/<id>
                "id": "7000000000000000002",
                "desc": "",
                "author": {"nickname": "无 handle 作者"},
                "video": {"duration": 10, "cover": "https://p16.tiktokcdn-us.com/c2.jpeg"},
                "stats": {"playCount": 100, "diggCount": 5},
            },
            {"desc": "无 id 条目应被跳过", "author": {}, "stats": {}},
        ],
        "hasMore": False, "cursor": 3,
    }

    def _provider(self, tmp_path, monkeypatch):
        from pathlib import Path

        from app.charts.tiktok import TikTokProvider
        from app.config import Settings

        cookie_file = tmp_path / "tiktok.txt"
        cookie_file.write_text(
            "# Netscape HTTP Cookie File\n"
            ".tiktok.com\tTRUE\t/\tTRUE\t1999999999\tttwid\t1%7Cabc\n"
            ".tiktok.com\tTRUE\t/\tTRUE\t1999999999\tmsToken\tfake-token\n",
            encoding="utf-8",
        )
        # 必须显式指向临时文件：cookie_file_for 会优先命中本机真实
        # data/cookies/tiktok.txt（测试与开发库同机）
        monkeypatch.setattr(
            Settings, "cookie_file_for",
            lambda self, platform, _p=str(cookie_file): Path(_p),
        )
        s = Settings()
        monkeypatch.setattr("app.charts.tiktok.Evil0ctalClient.health", lambda self: True)
        monkeypatch.setattr(
            "app.charts.tiktok.Evil0ctalClient.sign",
            lambda self, platform, url, user_agent, cookies: url + "&X-Bogus=fake",
        )
        return TikTokProvider(s)

    def test_fetch_maps_items(self, tmp_path, monkeypatch):
        captured = {"urls": []}

        def fake_get(url, **kw):
            captured["urls"].append(url)
            captured["cookie"] = kw["headers"]["Cookie"]
            if "challenge/detail" in url:
                return _FakeResponse(self.DETAIL_SAMPLE)
            return _FakeResponse(self.ITEM_SAMPLE)

        monkeypatch.setattr("app.charts.tiktok.httpx.get", fake_get)
        items = self._provider(tmp_path, monkeypatch).fetch("funny")
        assert len(items) == 2  # 无 id 条目被跳过
        first = items[0]
        assert first.source_id == "7057727079848103169"
        assert first.title == "Breaking up via Wordle #wordle #fyp"  # 换行折叠
        assert first.author == "cashman.tom"
        assert first.url == "https://www.tiktok.com/@tom.cashman/video/7057727079848103169"
        assert first.cover == "https://p16.tiktokcdn-us.com/cover.jpeg"
        assert first.duration == 26
        assert first.views == 3600000 and first.likes == 466000
        assert first.published  # createTime → 相对时间
        assert first.downloadable is True
        assert first.extra == {"rank": 1, "tag": "funny"}
        assert items[1].url == "https://www.tiktok.com/video/7000000000000000002"
        # 两次调用：detail + item_list，均带签名与 cookies
        assert len(captured["urls"]) == 2
        assert all("X-Bogus=fake" in u for u in captured["urls"])
        assert "challengeName=funny" in captured["urls"][0]
        assert "challengeID=5424" in captured["urls"][1]
        assert "ttwid=1%7Cabc" in captured["cookie"]
        # device_id 必填（缺失时 TikTok 返回空 body）
        from urllib.parse import parse_qs, urlsplit
        q = parse_qs(urlsplit(captured["urls"][1]).query)
        assert len(q["device_id"][0]) == 19 and q["device_id"][0].isdigit()

    def test_custom_tag_resolved_via_detail(self, tmp_path, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            if "challenge/detail" in url:
                captured["detail"] = url
                return _FakeResponse(self.DETAIL_SAMPLE)
            return _FakeResponse(self.ITEM_SAMPLE)

        monkeypatch.setattr("app.charts.tiktok.httpx.get", fake_get)
        items = self._provider(tmp_path, monkeypatch).fetch("custom:caturday")
        assert items and items[0].extra["tag"] == "caturday"
        assert "challengeName=caturday" in captured["detail"]

    def test_unknown_tag_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.charts.tiktok.httpx.get",
            lambda *a, **kw: _FakeResponse({"challengeInfo": {}}),
        )
        try:
            self._provider(tmp_path, monkeypatch).fetch("funny")
            raise AssertionError("应当抛出 ChartError")
        except ChartError as e:
            assert "不存在" in e.message

    def test_empty_feed_hints_cookie_expiry(self, tmp_path, monkeypatch):
        def fake_get(url, **kw):
            return _FakeResponse(
                self.DETAIL_SAMPLE if "challenge/detail" in url
                else {"itemList": [], "hasMore": False}
            )

        monkeypatch.setattr("app.charts.tiktok.httpx.get", fake_get)
        try:
            self._provider(tmp_path, monkeypatch).fetch("funny")
            raise AssertionError("应当抛出 ChartError")
        except ChartError as e:
            assert "cookies" in e.message

    def test_requires_cookies(self, tmp_path, monkeypatch):
        from app.charts.tiktok import TikTokProvider
        from app.config import Settings

        monkeypatch.setattr(Settings, "cookie_file_for", lambda self, platform: None)
        monkeypatch.setattr("app.charts.tiktok.Evil0ctalClient.health", lambda self: True)
        try:
            TikTokProvider(Settings()).fetch("funny")
            raise AssertionError("应当抛出 ChartError")
        except ChartError as e:
            assert "登录管理" in e.message

    def test_requires_evil0ctal(self, tmp_path, monkeypatch):
        from app.charts.tiktok import TikTokProvider
        from app.config import Settings

        monkeypatch.setattr("app.charts.tiktok.Evil0ctalClient.health", lambda self: False)
        try:
            TikTokProvider(Settings(evil0ctal={"enabled": True})).fetch("funny")
            raise AssertionError("应当抛出 ChartError")
        except ChartError as e:
            assert "不可达" in e.message

    def test_httponly_session_cookie_is_sent(self, tmp_path, monkeypatch):
        """`#HttpOnly_` 行（sessionid 等登录态）必须进 Cookie 头，其他站点的 cookie 不得外发。"""
        provider = self._provider(tmp_path, monkeypatch)
        (tmp_path / "tiktok.txt").write_text(
            "# Netscape HTTP Cookie File\n"
            ".tiktok.com\tTRUE\t/\tTRUE\t1999999999\tttwid\t1%7Cabc\n"
            "#HttpOnly_.tiktok.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tsid-value\n"
            ".google.com\tTRUE\t/\tTRUE\t1999999999\tSID\tgoogle-secret\n",
            encoding="utf-8",
        )
        captured = {}

        def fake_get(url, **kw):
            captured["cookie"] = kw["headers"]["Cookie"]
            if "challenge/detail" in url:
                return _FakeResponse(self.DETAIL_SAMPLE)
            return _FakeResponse(self.ITEM_SAMPLE)

        monkeypatch.setattr("app.charts.tiktok.httpx.get", fake_get)
        provider.fetch("funny")
        assert "sessionid=sid-value" in captured["cookie"]
        assert "google-secret" not in captured["cookie"]

    def test_pagination_until_target(self, tmp_path, monkeypatch):
        pages = [
            {"itemList": [
                {"id": str(7300000000000000000 + i), "desc": f"视频{i}",
                 "createTime": 1792400000,
                 "author": {"uniqueId": f"u{i}", "nickname": f"作者{i}"},
                 "video": {"duration": 5}, "stats": {"playCount": i, "diggCount": 0}}
                for i in range(30)
            ], "hasMore": 1, "cursor": 30},
            {"itemList": [
                {"id": str(7400000000000000000 + i), "desc": f"第二页{i}",
                 "createTime": 1792400000,
                 "author": {"uniqueId": f"v{i}", "nickname": f"作者B{i}"},
                 "video": {"duration": 5}, "stats": {"playCount": i, "diggCount": 0}}
                for i in range(30)
            ], "hasMore": 0, "cursor": 60},
        ]
        state = {"n": 0}

        def fake_get(url, **kw):
            if "challenge/detail" in url:
                return _FakeResponse(self.DETAIL_SAMPLE)
            body = pages[state["n"]]
            state["n"] += 1
            return _FakeResponse(body)

        monkeypatch.setattr("app.charts.tiktok.httpx.get", fake_get)
        items = self._provider(tmp_path, monkeypatch).fetch("funny")
        assert len(items) == 50  # 90 条候选截取 TARGET_COUNT
        assert state["n"] == 2   # 拿满 50 即停止，不再请求第三页
        assert items[49].extra["rank"] == 50


class TestDouyinSearch:
    SEARCH_SAMPLE = {
        "status_code": 0,
        "data": [
            {"type": 1, "aweme_info": {
                "aweme_id": "7600000000000000001",
                "desc": "猫咪视频\n多行标题",
                "create_time": 1792400000,
                "author": {"nickname": "猫主人"},
                "video": {
                    "duration": 12345,
                    "cover": {"url_list": ["https://p3.douyinpic.com/c.jpeg"]},
                    "play_addr": {"url_list": ["https://v.douyinvod.com/x.mp4"]},
                },
                "statistics": {"play_count": 456, "digg_count": 789},
            }},
            {"type": 1, "aweme_info": {  # 图集应被跳过
                "aweme_id": "7600000000000000002",
                "desc": "图集", "images": [{"display_url": "x"}],
                "video": {"play_addr": {"url_list": ["x"]}},
            }},
        ],
    }

    def _provider(self, tmp_path, monkeypatch, with_cookies=True):
        from pathlib import Path

        from app.config import Settings
        cookie_file = tmp_path / "douyin.txt"
        if with_cookies:
            cookie_file.write_text(
                "# Netscape HTTP Cookie File\n"
                ".douyin.com\tTRUE\t/\tTRUE\t1999999999\tttwid\t1%7Cabc\n"
                ".douyin.com\tTRUE\t/\tTRUE\t1999999999\tUIFID\tuif-value\n",
                encoding="utf-8",
            )
            # 必须显式指向临时文件：cookie_file_for 会优先命中本机真实
            # data/cookies/douyin.txt（测试与开发库同机）
            monkeypatch.setattr(
                Settings, "cookie_file_for",
                lambda self, platform, _p=str(cookie_file): Path(_p),
            )
        else:
            monkeypatch.setattr(Settings, "cookie_file_for", lambda self, platform: None)
        s = Settings(download={"cookies_file": str(cookie_file)} if with_cookies else {})
        monkeypatch.setattr("app.charts.douyin.Evil0ctalClient.health", lambda self: True)
        monkeypatch.setattr(
            "app.charts.douyin.Evil0ctalClient.sign",
            lambda self, platform, url, ua, cookies: url + "&a_bogus=fake",
        )
        return DouyinProvider(s)

    def test_search_success(self, tmp_path, monkeypatch):
        captured = {}

        def fake_get(url, **kw):
            captured["url"] = url
            captured["cookie"] = kw["headers"]["Cookie"]
            return _FakeResponse(self.SEARCH_SAMPLE)

        monkeypatch.setattr("app.charts.douyin.httpx.get", fake_get)
        items = self._provider(tmp_path, monkeypatch).search_videos("猫咪")
        assert len(items) == 1  # 图集被过滤
        it = items[0]
        assert it.downloadable is True
        assert it.source_id == "7600000000000000001"
        assert it.url == "https://www.douyin.com/video/7600000000000000001"
        assert it.title == "猫咪视频 多行标题"  # 换行折叠
        assert it.author == "猫主人"
        assert it.duration == 12.345
        assert it.likes == 789 and it.views == 456
        assert it.cover == "https://p3.douyinpic.com/c.jpeg"
        assert it.extra["keyword"] == "猫咪"
        # 签名 URL 与 cookies 正确传递
        assert "a_bogus=fake" in captured["url"]
        assert "ttwid=1%7Cabc" in captured["cookie"]

    def test_custom_category_dispatch(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.charts.douyin.httpx.get", lambda *a, **kw: _FakeResponse(self.SEARCH_SAMPLE))
        p = self._provider(tmp_path, monkeypatch)
        items = p.fetch("custom:猫咪")
        assert len(items) == 1 and items[0].downloadable

    def test_search_requires_cookies(self, tmp_path, monkeypatch):
        p = self._provider(tmp_path, monkeypatch, with_cookies=False)
        try:
            p.search_videos("猫咪")
            assert False, "should raise"
        except ChartError as e:
            assert "登录管理" in e.message

    def test_search_blocked_maps_to_cookies_hint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.charts.douyin.httpx.get",
            lambda *a, **kw: _FakeResponse({"status_code": 2483, "data": []}),
        )
        p = self._provider(tmp_path, monkeypatch)
        try:
            p.search_videos("猫咪")
            assert False, "should raise"
        except ChartError as e:
            assert "拦截" in e.message and "cookies" in e.message
