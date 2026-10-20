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
