"""API 集成冒烟（只读端点 + 任务参数校验）。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


class TestReadOnly:
    def test_health(self, client):
        assert client.get("/api/health").json()["ok"] is True

    def test_stats_shape(self, client):
        data = client.get("/api/stats").json()
        assert "videos" in data and "tasks" in data
        assert data["videos"]["total"] >= 0
        assert len(data["videos"]["last14"]) == 14

    def test_videos_list(self, client):
        res = client.get("/api/videos").json()
        assert res["total"] >= 0
        assert isinstance(res["items"], list)

    def test_video_404(self, client):
        assert client.get("/api/videos/99999").status_code == 404

    def test_charts_platform_list(self, client):
        assert client.get("/api/charts").json()["platforms"] == [
            {"id": "bilibili", "name": "哔哩哔哩"},
            {"id": "youtube", "name": "YouTube"},
            {"id": "tiktok", "name": "TikTok"},
            {"id": "douyin", "name": "抖音"},
        ]

    def test_charts_unknown_platform(self, client):
        assert client.get("/api/charts/netflix").status_code == 404


class TestTaskValidation:
    def test_empty_urls_rejected(self, client):
        assert client.post("/api/tasks", json={"urls": []}).status_code == 400

    def test_task_404(self, client):
        assert client.post("/api/tasks/99999/retry").status_code == 404

    def test_invalid_options_rejected(self, client):
        r = client.post("/api/tasks", json={
            "urls": ["https://www.youtube.com/watch?v=badoptions1"], "options": {"codec": "vp9"}})
        assert r.status_code == 422

    def test_create_with_options(self, client, monkeypatch):
        """创建任务带下载选项；随后取消清理（不真正入队，避免测试发起网络下载）。"""
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        res = client.post("/api/tasks", json={
            "urls": ["https://www.youtube.com/watch?v=nevergonnahappen1"],
            "options": {"max_height": 720, "codec": "h265"},
        })
        assert res.status_code == 200
        t = res.json()["tasks"][0]
        assert t["options"]["max_height"] == 720
        client.delete(f"/api/tasks/{t['id']}")


class TestSettingsAPI:
    def test_get_settings(self, client):
        res = client.get("/api/settings").json()
        assert res["settings"]["download"]["max_height"] >= 0
        assert res["meta"]["hevc_encoder"] in ("libx265", "hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox")

    def test_put_settings(self, client, restore_settings_overlay):
        r = client.put("/api/settings", json={"download": {"max_height": 480}})
        assert r.status_code == 200
        assert r.json()["settings"]["download"]["max_height"] == 480
        assert client.get("/api/settings").json()["settings"]["download"]["max_height"] == 480
        # 非法字段拒绝（未知 section 或未知字段 → 400/422）
        r1 = client.put("/api/settings", json={"server": {"port": 1234}})
        assert r1.status_code in (400, 422)


class TestSettingsWritePath:
    """设置页只存改动过的字段、null 删除覆盖项、密钥只写不读、cookies_file 不可远程修改。"""

    @staticmethod
    def _overlay() -> dict:
        import json as _json

        from app.db import get_sessionmaker
        from app.models import AppSetting

        with get_sessionmaker()() as s:
            row = s.get(AppSetting, 1)
            return _json.loads(row.data) if row is not None and row.data else {}

    def test_only_changed_field_stored_and_null_reverts(self, client, restore_settings_overlay):
        before = self._overlay()
        assert client.put("/api/settings", json={"download": {"max_height": 720}}).status_code == 200
        after = self._overlay()
        expected = dict(before, download={**before.get("download", {}), "max_height": 720})
        assert after == expected  # 只多了这一项，别的字段没有被冻结进覆盖层

        r = client.put("/api/settings", json={"download": {"max_height": None}})
        assert r.status_code == 200
        assert "max_height" not in self._overlay().get("download", {})
        assert r.json()["settings"]["download"]["max_height"] == 1080  # 回落到默认值

    def test_env_value_not_frozen_by_saving_other_fields(self, client, monkeypatch,
                                                         restore_settings_overlay):
        from app.config import invalidate_settings_cache

        monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY", "http://env-proxy:7890")
        invalidate_settings_cache()
        try:
            assert client.put("/api/settings", json={"download": {"max_height": 480}}).status_code == 200
            monkeypatch.setenv("VIDHARBOR_DOWNLOAD__PROXY", "http://env-proxy-2:7890")
            invalidate_settings_cache()
            proxy = client.get("/api/settings").json()["settings"]["download"]["proxy"]
            assert proxy == "http://env-proxy-2:7890"
        finally:
            monkeypatch.delenv("VIDHARBOR_DOWNLOAD__PROXY")
            invalidate_settings_cache()

    def test_api_keys_are_write_only(self, client, restore_settings_overlay):
        from app.config import get_settings

        r = client.put("/api/settings", json={"youtube": {"api_key": "AIzaSECRET123"}})
        assert r.status_code == 200 and "AIzaSECRET123" not in r.text
        body = client.get("/api/settings")
        assert "AIzaSECRET123" not in body.text
        youtube = body.json()["settings"]["youtube"]
        assert youtube["api_key_set"] is True and "api_key" not in youtube
        assert get_settings().youtube.api_key == "AIzaSECRET123"  # 生效但不回显

    def test_cookies_file_not_editable(self, client):
        r = client.put("/api/settings", json={"download": {"cookies_file": "/etc/passwd"}})
        assert r.status_code == 400


class TestTagsAPI:
    def test_tags_shape(self, client):
        res = client.get("/api/tags").json()
        assert isinstance(res["tags"], list)
        if res["tags"]:
            assert set(res["tags"][0]) == {"name", "count"}


class TestSchedulesAPI:
    PAYLOAD = {
        "name": "测试任务", "mode": "weekly", "at_time": "08:30", "weekdays": [0, 5],
        "selections": [
            {"platform": "bilibili", "category": "4", "period": "week", "limit": 5},
            {"platform": "youtube", "category": "custom:music", "period": "month", "limit": 3},
        ],
    }

    def test_crud(self, client):
        r = client.post("/api/schedules", json=self.PAYLOAD)
        assert r.status_code == 200
        row = r.json()["schedule"]
        assert row["trigger_desc"].startswith("周一")
        sid = row["id"]
        # 列表带 next_run_at（调度器在 lifespan 中已启动）
        lst = client.get("/api/schedules").json()["schedules"]
        assert any(s["id"] == sid and s["next_run_at"] for s in lst)
        # 开关
        assert client.post(f"/api/schedules/{sid}/toggle").json()["schedule"]["enabled"] is False
        # 更新
        upd = dict(self.PAYLOAD, name="改名", mode="interval", interval_minutes=120)
        assert client.put(f"/api/schedules/{sid}", json=upd).status_code == 200
        # 删除
        assert client.delete(f"/api/schedules/{sid}").json()["deleted"] is True

    def test_validation(self, client):
        r = client.post("/api/schedules", json={"name": "x", "mode": "bad", "selections": []})
        assert r.status_code in (400, 422)
        bad_cron = dict(self.PAYLOAD, mode="cron", cron="not a cron")
        assert client.post("/api/schedules", json=bad_cron).status_code == 400
        bad_platform = dict(self.PAYLOAD)
        bad_platform["selections"] = [{"platform": "netflix", "category": "x", "limit": 1}]
        assert client.post("/api/schedules", json=bad_platform).status_code == 400


class TestScheduleState:
    PAYLOAD = {
        "name": "状态测试", "mode": "daily", "at_time": "09:00",
        "selections": [{"platform": "bilibili", "category": "all", "period": "", "limit": 3}],
    }

    @staticmethod
    def _next_run(client, sid):
        from datetime import datetime

        row = next(s for s in client.get("/api/schedules").json()["schedules"] if s["id"] == sid)
        return datetime.fromisoformat(row["next_run_at"])

    def test_edit_keeps_disabled_state(self, client):
        sid = client.post("/api/schedules", json=self.PAYLOAD).json()["schedule"]["id"]
        try:
            assert client.post(f"/api/schedules/{sid}/toggle").json()["schedule"]["enabled"] is False
            r = client.put(f"/api/schedules/{sid}", json=dict(self.PAYLOAD, name="改名"))
            assert r.status_code == 200
            assert r.json()["schedule"]["enabled"] is False
            assert r.json()["schedule"]["next_run_at"] is None  # 停用任务不进调度器
        finally:
            client.delete(f"/api/schedules/{sid}")

    def test_options_validated_and_stored(self, client):
        bad = dict(self.PAYLOAD, options={"codec": "vp9"})
        assert client.post("/api/schedules", json=bad).status_code == 422
        r = client.post("/api/schedules", json=dict(self.PAYLOAD, options={"max_height": 720}))
        assert r.status_code == 200
        try:
            assert r.json()["schedule"]["options"] == {"max_height": 720}
        finally:
            client.delete(f"/api/schedules/{r.json()['schedule']['id']}")

    def test_douyin_hot_list_rejected(self, client):
        hot = dict(self.PAYLOAD, selections=[{"platform": "douyin", "category": "hot", "limit": 5}])
        assert client.post("/api/schedules", json=hot).status_code == 400
        keyword = dict(self.PAYLOAD, selections=[
            {"platform": "douyin", "category": "custom:猫咪", "limit": 5}])
        r = client.post("/api/schedules", json=keyword)
        assert r.status_code == 200
        client.delete(f"/api/schedules/{r.json()['schedule']['id']}")

    def test_timezone_change_reschedules_jobs(self, client, restore_settings_overlay):
        sid = client.post("/api/schedules", json=self.PAYLOAD).json()["schedule"]["id"]
        try:
            before = self._next_run(client, sid)  # 隔离库默认 Asia/Shanghai
            assert (before.hour, before.utcoffset().total_seconds()) == (9, 8 * 3600)
            assert client.put("/api/settings", json={"scheduler": {"timezone": "UTC"}}).status_code == 200
            after = self._next_run(client, sid)
            assert (after.hour, after.utcoffset().total_seconds()) == (9, 0)
            assert client.put("/api/settings",
                              json={"scheduler": {"timezone": "Mars/Base"}}).status_code == 400
        finally:
            client.put("/api/settings", json={"scheduler": {"timezone": "Asia/Shanghai"}})
            client.delete(f"/api/schedules/{sid}")


class TestTimestampsCarryOffset:
    """API 时间字段必须带时区偏移：无偏移的 ISO 串会被浏览器当本地时间，显示差一个时区。"""

    def test_iso_utc(self):
        from datetime import datetime, timedelta, timezone

        from app.models import iso_utc

        assert iso_utc(None) is None
        assert iso_utc(datetime(2026, 10, 22, 2, 0, 0, 123456)) == "2026-10-22T02:00:00.123+00:00"
        aware = datetime(2026, 10, 23, 9, 0, tzinfo=timezone(timedelta(hours=8)))
        assert iso_utc(aware) == "2026-10-23T09:00:00.000+08:00"

    def test_task_video_schedule_payloads(self, client, monkeypatch):
        from app.db import get_sessionmaker
        from app.models import Schedule, Video, utcnow

        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        task = client.post("/api/tasks", json={
            "urls": ["https://www.youtube.com/watch?v=offsetcheck"]}).json()["tasks"][0]
        client.delete(f"/api/tasks/{task['id']}")
        assert task["created_at"].endswith("+00:00")

        sm = get_sessionmaker()
        with sm() as s:
            v = Video(platform="other", source_id="tz-offset-1", title="tz")
            row = Schedule(name="tz", selections="[]", last_run_at=utcnow())
            s.add_all([v, row])
            s.commit()
            vid, sid = v.id, row.id
        try:
            assert client.get(f"/api/videos/{vid}").json()["created_at"].endswith("+00:00")
            snap = next(x for x in client.get("/api/schedules").json()["schedules"] if x["id"] == sid)
            assert snap["last_run_at"].endswith("+00:00")
        finally:
            with sm() as s:
                s.delete(s.get(Video, vid))
                s.delete(s.get(Schedule, sid))
                s.commit()


class TestEvents:
    def test_sse_stream(self, client):
        with client.stream("GET", "/api/events") as res:
            assert res.status_code == 200
            buf = ""
            for chunk in res.iter_text():
                buf += chunk
                if "event: hello" in buf and "event: tasks" in buf:
                    break
                if len(buf) > 200000:
                    raise AssertionError("SSE 未按预期输出 hello/tasks 事件")
            assert "event: hello" in buf
            assert "event: tasks" in buf


class TestVideoDelete:
    """删除视频：文件被短暂占用（Windows 流式播放句柄）时重试后仍能删掉。"""

    def _make_dummy(self):
        import uuid
        from app.config import get_settings
        from app.db import get_sessionmaker
        from app.models import Video

        settings = get_settings()
        rel = f"videos/_test/{uuid.uuid4().hex}.mp4"
        p = settings.library_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
        sm = get_sessionmaker()
        with sm() as s:
            v = Video(platform="other", source_id=rel, url="https://example.com",
                      title="删除重试测试", video_path=rel)
            s.add(v)
            s.commit()
            vid = v.id
        return vid, p

    def test_delete_removes_file(self, client):
        vid, p = self._make_dummy()
        r = client.delete(f"/api/videos/{vid}")
        assert r.status_code == 200
        body = r.json()
        assert body["deleted"] is True
        assert body["files_removed"] == 1
        assert not p.exists()

    def test_delete_with_locked_file_retries(self, client):
        """模拟流式播放占用：先持句柄删除失败，0.5s 后释放，重试应成功。"""
        import threading
        vid, p = self._make_dummy()
        fh = open(p, "rb")
        try:
            timer = threading.Timer(1.0, fh.close)
            timer.start()
            r = client.delete(f"/api/videos/{vid}")
            timer.join()
            assert r.status_code == 200
            assert r.json()["files_removed"] == 1
            assert not p.exists()
        finally:
            if not fh.closed:
                fh.close()
            if p.exists():
                p.unlink(missing_ok=True)


class TestVideoStreaming:
    """播放与拖动进度：Range 请求（含后缀 bytes=-N）由 FileResponse 处理。"""

    @pytest.fixture
    def video(self, client):
        import uuid

        from app.config import get_settings
        from app.db import get_sessionmaker
        from app.models import Video

        data = bytes(range(256)) * 4  # 1024 字节，按位置可校验
        rel = f"videos/_test/{uuid.uuid4().hex}.mp4"
        path = get_settings().library_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        sm = get_sessionmaker()
        with sm() as s:
            v = Video(platform="other", source_id=rel, title="range", video_path=rel)
            s.add(v)
            s.commit()
            vid = v.id
        yield vid, data
        with sm() as s:
            s.delete(s.get(Video, vid))
            s.commit()
        path.unlink(missing_ok=True)

    def test_full_and_range_requests(self, client, video):
        vid, data = video
        url = f"/api/videos/{vid}/file"
        full = client.get(url)
        assert full.status_code == 200 and full.content == data
        assert full.headers["accept-ranges"] == "bytes"
        head = client.get(url, headers={"Range": "bytes=0-99"})
        assert head.status_code == 206 and head.content == data[:100]
        assert head.headers["content-range"] == "bytes 0-99/1024"
        tail = client.get(url, headers={"Range": "bytes=-100"})  # 后缀范围：最后 100 字节
        assert tail.status_code == 206 and tail.content == data[-100:]
        assert client.get(url, headers={"Range": "bytes=5000-6000"}).status_code == 416


class TestLibraryListQueries:
    """视频库列表：SQL 次数与页大小无关（标签预取、字幕只计数），不加载 raw_metadata/简介。"""

    def test_query_count_independent_of_page_size(self, client):
        from sqlalchemy import event

        from app.db import get_engine, get_sessionmaker
        from app.models import Subtitle, Tag, Video

        sm = get_sessionmaker()
        with sm() as s:
            for i in range(6):
                v = Video(platform="other", source_id=f"qcount-{i}", title=f"q{i}",
                          raw_metadata="x" * 10000)
                v.tags = [Tag(name="qcount-tag")]
                v.subtitles = [Subtitle(lang="en", content="1\n00:00:01,000 --> 00:00:02,000\nhi\n")]
                s.add(v)
            s.commit()
        statements: list[str] = []

        def record(conn, cursor, statement, *args):
            statements.append(statement)

        engine = get_engine()
        event.listen(engine, "before_cursor_execute", record)
        try:
            six = client.get("/api/videos", params={"tag": "qcount-tag", "page_size": 6}).json()
            n_six = len(statements)
            statements.clear()
            client.get("/api/videos", params={"tag": "qcount-tag", "page_size": 1})
            n_one = len(statements)
            selects = list(statements)
        finally:
            event.remove(engine, "before_cursor_execute", record)
            with sm() as s:
                for v in s.query(Video).filter(Video.source_id.like("qcount-%")):
                    s.delete(v)
                s.commit()
        assert n_six == n_one  # 没有按条目数增长的 N+1 查询
        assert not any("raw_metadata" in sql for sql in selects)
        assert len(six["items"]) == 6
        assert all(it["subtitles_count"] == 1 and it["tags"] == ["qcount-tag"] for it in six["items"])


class TestProxySettingsAPI:
    def test_put_proxy_settings(self, client, restore_settings_overlay):
        r = client.put("/api/settings", json={"download": {
            "proxy": "http://host.docker.internal:7890",
            "proxy_platforms": ["youtube", "tiktok"],
        }})
        assert r.status_code == 200
        d = r.json()["settings"]["download"]
        assert d["proxy"] == "http://host.docker.internal:7890"
        assert d["proxy_platforms"] == ["youtube", "tiktok"]


class TestTaskDedup:
    """进行中去重：已在队列（pending/running）的 URL 不重复建任务，retry 撞车返回 409。"""

    def test_create_skips_active_and_retry_conflicts(self, client, monkeypatch):
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        url = "https://www.youtube.com/watch?v=dedup123456"
        r1 = client.post("/api/tasks", json={"urls": [url]})
        assert r1.status_code == 200
        body1 = r1.json()
        assert len(body1["tasks"]) == 1 and body1["skipped"] == 0

        r2 = client.post("/api/tasks", json={"urls": [url]})
        body2 = r2.json()
        assert body2["tasks"] == [] and body2["skipped"] == 1

        tid = body1["tasks"][0]["id"]
        # pending 任务本身不可 retry
        assert client.post(f"/api/tasks/{tid}/retry").status_code == 400

        # 终态任务 retry 时，若同 URL 又有新任务在队列 → 409
        client.delete(f"/api/tasks/{tid}")  # → canceled
        r3 = client.post("/api/tasks", json={"urls": [url]})
        assert len(r3.json()["tasks"]) == 1  # canceled 不算 active，可新建
        assert client.post(f"/api/tasks/{tid}/retry").status_code == 409
        client.delete(f"/api/tasks/{r3.json()['tasks'][0]['id']}")  # 清理

    def test_same_video_with_different_url_forms(self, client, monkeypatch):
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        r1 = client.post("/api/tasks", json={
            "urls": ["https://www.youtube.com/watch?v=formcheck01"]}).json()
        r2 = client.post("/api/tasks", json={"urls": ["https://youtu.be/formcheck01"]}).json()
        try:
            assert len(r1["tasks"]) == 1
            assert r2["tasks"] == [] and r2["skipped"] == 1
        finally:
            client.delete(f"/api/tasks/{r1['tasks'][0]['id']}")


class TestScheduleConcurrency:
    """并发运行（榜单重叠的两个定时任务、立即运行撞上定时触发）不得为同一视频重复建任务。"""

    URLS = [f"https://www.bilibili.com/video/BV1RACE000{i}x" for i in range(5)]

    def _setup(self, client, monkeypatch, n_schedules):
        import json as _json
        import time as _time

        from app import scheduler as sched
        from app.charts.base import TrendingItem
        from app.db import get_sessionmaker
        from app.models import Schedule

        urls = self.URLS

        class SlowProvider:
            def normalize(self, category, period):
                return category or "hot", period

            def is_downloadable(self, category):
                return True

            def fetch(self, category, period):
                _time.sleep(0.3)  # 模拟抓榜单的网络耗时，让两轮运行重叠
                return [TrendingItem(source_id=u.rsplit("/", 1)[1], url=u) for u in urls]

        monkeypatch.setattr(sched, "provider_for", lambda p: SlowProvider())
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        sm = get_sessionmaker()
        ids = []
        with sm() as s:
            for i in range(n_schedules):
                row = Schedule(name=f"并发{i}", mode="daily", selections=_json.dumps(
                    [{"platform": "bilibili", "category": "hot", "period": "", "limit": 10}]))
                s.add(row)
                s.commit()
                ids.append(row.id)
        return sched, sm, ids

    def _task_urls(self, sm):
        from app.models import DownloadTask

        with sm() as s:
            return [u for (u,) in s.query(DownloadTask.url).filter(DownloadTask.url.in_(self.URLS))]

    def _cleanup(self, sm, ids):
        from app.models import DownloadTask, Schedule

        with sm() as s:
            s.query(DownloadTask).filter(DownloadTask.url.in_(self.URLS)).delete(
                synchronize_session=False)
            for sid in ids:
                s.delete(s.get(Schedule, sid))
            s.commit()

    def test_overlapping_schedules_do_not_duplicate(self, client, monkeypatch):
        import threading

        sched, sm, ids = self._setup(client, monkeypatch, 2)
        try:
            threads = [threading.Thread(target=sched.run_schedule,
                                        args=(sid, client.app.state.queue)) for sid in ids]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert sorted(self._task_urls(sm)) == sorted(self.URLS)  # 每个视频恰好一个任务
        finally:
            self._cleanup(sm, ids)

    def test_same_schedule_runs_one_round_at_a_time(self, client, monkeypatch):
        sched, sm, ids = self._setup(client, monkeypatch, 1)
        sid = ids[0]
        try:
            assert sched.claim_run(sid)  # 模拟本轮正在运行
            try:
                assert sched.run_schedule(sid, client.app.state.queue)["error"] == "上一轮仍在运行"
                assert client.post(f"/api/schedules/{sid}/run").status_code == 409
            finally:
                sched.release_run(sid)
            assert self._task_urls(sm) == []
        finally:
            self._cleanup(sm, ids)


class TestScheduleDedup:
    """定时任务两轮连跑：上一轮还在队列中的 URL 第二轮跳过，不重复下载。"""

    def test_run_skips_video_stored_under_equivalent_id(self, client, monkeypatch):
        """榜单给的是不带 p 的链接，库里存的是 yt-dlp 给的 BVxxx_p1：应计为跳过而不是再下一遍。"""
        import json as _json

        from app import scheduler as sched
        from app.charts.base import TrendingItem
        from app.db import get_sessionmaker
        from app.models import DownloadTask, Schedule, Video

        class FakeProvider:
            def normalize(self, category, period):
                return category or "hot", period

            def is_downloadable(self, category):
                return True

            def fetch(self, category, period):
                return [TrendingItem(source_id="BV1EQSCHED01",
                                     url="https://www.bilibili.com/video/BV1EQSCHED01")]

        monkeypatch.setattr(sched, "provider_for", lambda p: FakeProvider())
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)
        sm = get_sessionmaker()
        with sm() as s:
            video = Video(platform="bilibili", source_id="BV1EQSCHED01_p1")
            row = Schedule(name="等价 id", mode="daily", selections=_json.dumps(
                [{"platform": "bilibili", "category": "hot", "period": "", "limit": 5}]))
            s.add_all([video, row])
            s.commit()
            vid, sid = video.id, row.id
        try:
            result = sched.run_schedule(sid, client.app.state.queue)
            assert (result["created"], result["skipped"]) == (0, 1)
        finally:
            with sm() as s:
                s.query(DownloadTask).filter(DownloadTask.schedule_id == sid).delete(
                    synchronize_session=False)
                s.delete(s.get(Schedule, sid))
                s.delete(s.get(Video, vid))
                s.commit()

    def test_run_skips_urls_already_queued(self, client, monkeypatch):
        import json as _json

        from app import scheduler as sched
        from app.charts.base import TrendingItem
        from app.db import get_sessionmaker
        from app.models import Schedule

        class FakeProvider:
            def normalize(self, category, period):
                return category or "hot", period

            def is_downloadable(self, category):
                return True

            def fetch(self, category, period):
                return [TrendingItem(source_id="BV1TEST0000x", title="t",
                                     url="https://www.bilibili.com/video/BV1TEST0000x")]

        monkeypatch.setattr(sched, "provider_for", lambda p: FakeProvider())
        monkeypatch.setattr(client.app.state.queue, "submit", lambda *a, **k: None)

        sm = get_sessionmaker()
        with sm() as s:
            row = Schedule(
                name="去重测试", mode="daily",
                selections=_json.dumps([{"platform": "bilibili", "category": "hot",
                                         "period": "", "limit": 5}]))
            s.add(row)
            s.commit()
            sid = row.id
        try:
            r1 = sched.run_schedule(sid, client.app.state.queue)
            assert r1["created"] == 1
            r2 = sched.run_schedule(sid, client.app.state.queue)
            assert r2["created"] == 0
            assert r2["skipped"] == 1
        finally:
            from app.models import DownloadTask

            with sm() as s:
                # 遗留的 pending 任务会在下一个测试模块启动时被重新入队并真的去下载
                s.query(DownloadTask).filter(DownloadTask.schedule_id == sid).delete(
                    synchronize_session=False)
                s.delete(s.get(Schedule, sid))
                s.commit()


class TestStatsLocalDayBoundary:
    """“今日”按 scheduler.timezone 的本地日为界：本地 00:30 入库（= UTC 前一日 16:30）计入今日。"""

    def test_early_local_morning_counts_as_today(self, client):
        from datetime import datetime, timezone as tzmod
        from zoneinfo import ZoneInfo

        from app.db import get_sessionmaker
        from app.models import Video

        tz = ZoneInfo("Asia/Shanghai")  # 隔离库默认 scheduler.timezone
        local_0030 = datetime.now(tz).replace(hour=0, minute=30, second=0, microsecond=0)
        naive_utc = local_0030.astimezone(tzmod.utc).replace(tzinfo=None)

        sm = get_sessionmaker()
        with sm() as s:
            v = Video(platform="other", source_id="tz-boundary-1", title="tz",
                      created_at=naive_utc, updated_at=naive_utc)
            s.add(v)
            s.commit()
            vid = v.id
        try:
            data = client.get("/api/stats").json()
            assert data["videos"]["today"] >= 1
            assert data["videos"]["last14"][-1]["date"] == datetime.now(tz).strftime("%Y-%m-%d")
            assert data["videos"]["last14"][-1]["count"] >= 1
        finally:
            with sm() as s:
                s.delete(s.get(Video, vid))
                s.commit()
