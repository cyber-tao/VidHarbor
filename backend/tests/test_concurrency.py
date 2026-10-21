"""并发控制：下载调度（全局/每平台上限）+ 全局转码限流 + 设置往返。"""
import threading
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _acquire(lim, entered: threading.Event) -> None:
    with lim.slot():
        entered.set()


class TestLimiter:
    def test_caps_concurrency(self):
        from app.downloader.postprocess import _Limiter

        lim = _Limiter(2)
        active = 0
        peak = 0
        lock = threading.Lock()

        def work():
            nonlocal active, peak
            with lim.slot():
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.03)
                with lock:
                    active -= 1

        threads = [threading.Thread(target=work) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert peak == 2  # 6 个任务、上限 2 → 峰值恰好 2

    def test_set_limit_grow_frees_waiter(self):
        from app.downloader.postprocess import _Limiter

        lim = _Limiter(1)
        with lim.slot():
            entered = threading.Event()
            t = threading.Thread(target=_acquire, args=(lim, entered))
            t.start()
            assert not entered.wait(0.1)  # 上限 1、槽位被占 → 等待
            lim.set_limit(2)              # 动态放大 → 等待者立即进入
            assert entered.wait(1)
            t.join(1)

    def test_set_limit_shrink_only_blocks_new(self):
        from app.downloader.postprocess import _Limiter

        lim = _Limiter(3)
        s1, s2 = lim.slot(), lim.slot()
        s1.__enter__()
        s2.__enter__()  # 已占 2 个（旧上限允许）
        lim.set_limit(1)  # 缩到 1：在跑的不受影响，只挡新进入
        entered = threading.Event()
        t = threading.Thread(target=_acquire, args=(lim, entered))
        t.start()
        assert not entered.wait(0.1)  # used=2 ≥ 1 → 排队
        s2.__exit__(None, None, None)
        assert not entered.wait(0.1)  # used=1 仍 ≥ 1 → 继续排队
        s1.__exit__(None, None, None)
        assert entered.wait(1)        # used=0 < 1 → 进入
        t.join(1)


class TestDispatch:
    def _queue(self, monkeypatch, concurrency, per_platform):
        from app.config import Settings
        from app.downloader.engine import TaskQueue

        s = Settings()
        s.download.concurrency = concurrency
        s.download.per_platform_concurrency = per_platform
        q = TaskQueue(s)
        q._run = lambda tid: None  # 不触 DB，只测调度取件逻辑
        monkeypatch.setattr("app.downloader.engine.get_settings", lambda: s)
        return q

    def test_per_platform_limit(self, monkeypatch):
        q = self._queue(monkeypatch, concurrency=3, per_platform=1)
        try:
            q.submit(1, "bilibili")
            q.submit(2, "bilibili")
            q.submit(3, "bilibili")
            q.submit(4, "youtube")
            q.submit(5, "youtube")

            assert q._dispatch_one() is True   # 取 bilibili#1
            assert q._dispatch_one() is True   # bilibili 满员 → 跳过，取 youtube#4
            assert q._dispatch_one() is False  # 两平台都满员
            with q._lock:
                assert dict(q._running) == {1: "bilibili", 4: "youtube"}

            with q._lock:  # #1 跑完释放槽位
                q._running.pop(1)
            assert q._dispatch_one() is True   # 取 bilibili#2
            with q._lock:
                assert q._running.get(2) == "bilibili"
        finally:
            q.executor.shutdown(wait=False)

    def test_global_limit(self, monkeypatch):
        q = self._queue(monkeypatch, concurrency=2, per_platform=8)
        try:
            for i in range(1, 6):
                q.submit(i, f"p{i}")  # 各不同平台，只受全局上限
            assert q._dispatch_one() is True
            assert q._dispatch_one() is True
            assert q._dispatch_one() is False  # 全局 2 已满
            with q._lock:
                assert len(q._running) == 2
        finally:
            q.executor.shutdown(wait=False)

    def test_cancel_removes_pending(self, monkeypatch):
        q = self._queue(monkeypatch, concurrency=1, per_platform=1)
        try:
            q.submit(1, "bilibili")
            q.submit(2, "bilibili")
            assert q.cancel(2) is True
            with q._lock:
                assert list(q._pending) == [(1, "bilibili")]  # 只移除被取消的
                assert q.cancel_flags[2].is_set()
            assert q._dispatch_one() is True   # 取 #1
            assert q._dispatch_one() is False  # #2 已被取消出队
        finally:
            q.executor.shutdown(wait=False)


class TestRunFFmpeg:
    """_run_ffmpeg：取消立即 kill、超时终止、失败带 stderr。用 python 代替 ffmpeg 做长进程。"""

    SLEEP_30 = ["-c", "import time; time.sleep(30)"]

    def test_cancel_kills_subprocess(self):
        import sys

        from app.downloader.postprocess import _run_ffmpeg
        from app.downloader.ytdlp import DownloadCancelled

        ev = threading.Event()
        t = threading.Timer(0.3, ev.set)
        t.start()
        start = time.monotonic()
        with pytest.raises(DownloadCancelled):
            _run_ffmpeg([sys.executable, *self.SLEEP_30], cancel=ev)
        assert time.monotonic() - start < 10  # 没有傻等 30s，说明进程被 kill
        t.join()

    def test_timeout_kills_subprocess(self):
        import sys

        from app.downloader.postprocess import _run_ffmpeg

        start = time.monotonic()
        with pytest.raises(RuntimeError, match="超时"):
            _run_ffmpeg([sys.executable, *self.SLEEP_30], timeout=1)
        assert time.monotonic() - start < 10

    def test_failure_raises_with_stderr(self):
        import sys

        from app.downloader.postprocess import _run_ffmpeg

        cmd = ["-c", "import sys; sys.stderr.write('boom-detail'); sys.exit(3)"]
        with pytest.raises(RuntimeError, match="boom-detail"):
            _run_ffmpeg([sys.executable, *cmd])

    def test_limiter_slot_cancel_exits_wait(self):
        from app.downloader.postprocess import _Limiter
        from app.downloader.ytdlp import DownloadCancelled

        lim = _Limiter(1)
        ev = threading.Event()
        with lim.slot():  # 占满唯一槽位
            raised: list[BaseException] = []

            def waiter():
                try:
                    with lim.slot(cancel=ev):
                        pass
                except BaseException as e:  # noqa: BLE001
                    raised.append(e)

            t = threading.Thread(target=waiter)
            t.start()
            time.sleep(0.2)
            ev.set()  # 排队中取消 → 立即退出而不是等槽位
            t.join(2)
            assert not t.is_alive()
            assert len(raised) == 1 and isinstance(raised[0], DownloadCancelled)


class TestSettingsConcurrencyAPI:
    def test_roundtrip_and_restore(self, client):
        from app.config import invalidate_settings_cache
        from app.db import get_sessionmaker
        from app.models import AppSetting

        sm = get_sessionmaker()
        with sm() as s:
            row = s.get(AppSetting, 1)
            original = row.data if row is not None else None

        r = client.put("/api/settings", json={
            "download": {"concurrency": 5, "per_platform_concurrency": 1},
            "library": {"transcode_concurrency": 3},
        })
        assert r.status_code == 200
        d = r.json()["settings"]
        assert d["download"]["concurrency"] == 5
        assert d["download"]["per_platform_concurrency"] == 1
        assert d["library"]["transcode_concurrency"] == 3
        assert client.get("/api/settings").json()["settings"]["download"]["per_platform_concurrency"] == 1
        # 越界值被 pydantic 拒绝（400）
        assert client.put("/api/settings", json={"download": {"concurrency": 99}}).status_code == 400

        # 还原原始覆盖值
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
