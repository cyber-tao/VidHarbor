from pathlib import Path

from app.downloader.postprocess import SRT_LANG_RE, _is_auto, _lang_of, parse_fps, srt_to_vtt


class TestLangOf:
    def test_normal(self):
        assert _lang_of(Path("BV1xx.zh-Hans.srt")) == "zh-Hans"
        assert _lang_of(Path("abc.en.srt")) == "en"

    def test_no_lang(self):
        assert _lang_of(Path("BV1xx.srt")) == "und"

    def test_regex_bounds(self):
        assert SRT_LANG_RE.search("video.id.srt") is None or _lang_of(Path("video.id.srt"))


class TestIsAuto:
    def test_manual_wins(self):
        info = {"subtitles": {"en": []}, "automatic_captions": {"en": []}}
        assert _is_auto("en", info) is False

    def test_auto_only(self):
        info = {"subtitles": {}, "automatic_captions": {"zh-Hans": []}}
        assert _is_auto("zh-Hans", info) is True
        assert _is_auto("zh", info) is True

    def test_neither(self):
        assert _is_auto("ja", {"subtitles": {}, "automatic_captions": {}}) is False


class TestParseFps:
    def test_fraction(self):
        assert parse_fps("30000/1001") == 29.97

    def test_integer(self):
        assert parse_fps("30/1") == 30.0

    def test_garbage(self):
        assert parse_fps(None) == 0.0
        assert parse_fps("N/A") == 0.0


class TestSrtToVtt:
    def test_conversion(self):
        srt = "1\n00:00:01,000 --> 00:00:02,500\n你好\n"
        vtt = srt_to_vtt(srt)
        assert vtt.startswith("WEBVTT")
        assert "00:00:01.000 --> 00:00:02.500" in vtt
        assert "," not in vtt.split("-->")[1].split("\n")[0]


class TestArchivedMetadata:
    def test_drops_transient_download_data(self):
        import json

        from app.downloader.postprocess import archived_metadata

        info = {
            "id": "x", "title": "T", "tags": ["a"], "chapters": [{"title": "c"}],
            "formats": [{"url": "https://cdn.example/x?sig=1"}] * 50,
            "automatic_captions": {"en": [{"url": "https://cdn.example/sub"}]},
            "requested_downloads": [{"filepath": "/tmp/x.mp4"}],
            "http_headers": {"User-Agent": "x"}, "url": "https://cdn.example/x?sig=1",
            "_type": "video", "_version": {"version": "2026.08.19"},
        }
        kept = json.loads(archived_metadata(info))
        assert kept == {"id": "x", "title": "T", "tags": ["a"], "chapters": [{"title": "c"}]}


class TestIngestRecovery:
    """入库提交失败（并发撞唯一约束）：回收已移动文件，关联抢先入库的条目。"""

    def test_conflict_rolls_back_files_and_links_existing(self, monkeypatch, tmp_path):
        from app.config import get_settings
        from app.db import get_sessionmaker
        from app.downloader import postprocess as pp
        from app.downloader.ytdlp import RawDownload
        from app.models import DownloadTask, Video

        settings = get_settings()
        sm = get_sessionmaker()

        def fake_ensure_mp4(src, out_dir, *a, **k):
            # 模拟并发赢家：转码期间另一任务抢先入库同 platform+source_id
            out_dir.mkdir(parents=True, exist_ok=True)
            f = out_dir / "final.mp4"
            f.write_bytes(b"x" * 8)
            with sm() as s:
                s.add(Video(platform="bilibili", source_id="sid-dup"))
                s.commit()
            return f, "remux"

        monkeypatch.setattr(pp, "ensure_mp4", fake_ensure_mp4)
        monkeypatch.setattr(pp, "run_ffprobe", lambda p: {"streams": [], "format": {}})

        raw = RawDownload(ok=True, info={"id": "sid-dup", "title": "T", "uploader": "UP"},
                          media_path=tmp_path / "src.mp4", temp_dir=tmp_path)
        task = DownloadTask(url="https://www.bilibili.com/video/BV1xx411c7mD",
                            platform="bilibili")
        with sm() as session:
            video, created = pp.ingest(raw, task, session, settings)
            assert created is False
            assert video.source_id == "sid-dup"
        # 不留孤儿文件：库目录中的产物已被回收
        assert not (settings.videos_dir / "bilibili" / "UP").exists()

    def test_single_part_p1_id_links_existing_entry(self, monkeypatch, tmp_path):
        """同一单 P 视频先以 BVxxx 入库，再经 ?p=1 链接下载得到 BVxxx_p1：关联已有条目，不重复入库。"""
        from app.config import get_settings
        from app.db import get_sessionmaker
        from app.downloader import postprocess as pp
        from app.downloader.ytdlp import RawDownload
        from app.models import DownloadTask, Video

        def must_not_postprocess(*a, **k):
            raise AssertionError("已在库中的视频不应再做后处理")

        monkeypatch.setattr(pp, "ensure_mp4", must_not_postprocess)
        sm = get_sessionmaker()
        with sm() as s:
            existing = Video(platform="bilibili", source_id="BV1EQUIV0001")
            s.add(existing)
            s.commit()
            vid = existing.id
        raw = RawDownload(ok=True, info={"id": "BV1EQUIV0001_p1", "title": "T"},
                          media_path=tmp_path / "x.mp4", temp_dir=tmp_path)
        task = DownloadTask(url="https://www.bilibili.com/video/BV1EQUIV0001?p=1", platform="bilibili")
        try:
            with sm() as session:
                video, created = pp.ingest(raw, task, session, get_settings())
                assert created is False and video.id == vid
        finally:
            with sm() as s:
                s.delete(s.get(Video, vid))
                s.commit()
