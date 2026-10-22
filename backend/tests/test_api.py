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
        assert len(client.get("/api/charts").json()["platforms"]) == 4

    def test_charts_unknown_platform(self, client):
        assert client.get("/api/charts/netflix").status_code == 404


class TestTaskValidation:
    def test_empty_urls_rejected(self, client):
        assert client.post("/api/tasks", json={"urls": []}).status_code == 400

    def test_task_404(self, client):
        assert client.post("/api/tasks/99999/retry").status_code == 404

    def test_create_with_options(self, client):
        """创建任务带下载选项；随后取消清理。"""
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

    def test_put_and_restore(self, client):
        import json as _json

        from app.db import get_sessionmaker
        from app.models import AppSetting

        sm = get_sessionmaker()
        with sm() as s:
            row = s.get(AppSetting, 1)
            original = row.data if row is not None else None
        r = client.put("/api/settings", json={"download": {"max_height": 480}})
        assert r.status_code == 200
        assert r.json()["settings"]["download"]["max_height"] == 480
        assert client.get("/api/settings").json()["settings"]["download"]["max_height"] == 480
        # 非法字段拒绝（未知 section 或未知字段 → 400/422）
        r1 = client.put("/api/settings", json={"server": {"port": 1234}})
        assert r1.status_code in (400, 422)
        # 还原测试前的原始覆盖值（直接删行会连带清掉用户保存的其它设置，如兜底 API key）
        from app.config import invalidate_settings_cache
        with sm() as s:
            row = s.get(AppSetting, 1)
            if original is None:
                if row is not None:
                    s.delete(row)
            else:
                if row is None:
                    s.add(AppSetting(id=1, data=original))
                else:
                    row.data = original
            s.commit()
        invalidate_settings_cache()
        expected = 1080 if original is None else _json.loads(original).get("download", {}).get("max_height", 1080)
        assert client.get("/api/settings").json()["settings"]["download"]["max_height"] == expected


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


class TestProxySettingsAPI:
    def test_put_proxy_settings(self, client):
        from app.config import invalidate_settings_cache
        from app.db import get_sessionmaker
        from app.models import AppSetting

        sm = get_sessionmaker()
        with sm() as s:
            row = s.get(AppSetting, 1)
            original = row.data if row is not None else None

        r = client.put("/api/settings", json={"download": {
            "proxy": "http://host.docker.internal:7890",
            "proxy_platforms": ["youtube", "tiktok"],
        }})
        assert r.status_code == 200
        d = r.json()["settings"]["download"]
        assert d["proxy"] == "http://host.docker.internal:7890"
        assert d["proxy_platforms"] == ["youtube", "tiktok"]

        # 还原测试前的原始覆盖值（不得把用户配置清成空值）
        with sm() as s:
            row = s.get(AppSetting, 1)
            if original is None:
                if row is not None:
                    s.delete(row)
            else:
                if row is None:
                    s.add(AppSetting(id=1, data=original))
                else:
                    row.data = original
            s.commit()
        invalidate_settings_cache()


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


class TestScheduleDedup:
    """定时任务两轮连跑：上一轮还在队列中的 URL 第二轮跳过，不重复下载。"""

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
            with sm() as s:
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
