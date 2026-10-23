"""下载选项：格式选择器构造 + URL → source_id 解析。"""
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.downloader.options import (
    DownloadOptions,
    build_format_selector,
    equivalent_source_ids,
    parse_options_json,
    parse_source_id,
    resolve_options,
    source_id_candidates,
)


def _eff(**kw):
    s = Settings()
    return resolve_options(s, DownloadOptions(**kw) if kw else None)


class TestFormatSelector:
    def test_default_h265_prefers_hevc(self):
        eff = _eff(codec="h265")
        sel = build_format_selector(eff)
        # B站 HEVC 流的 codec tag 是 hvc1，两个前缀都要能命中
        assert sel.startswith("(bv*[vcodec^=hevc]/bv*[vcodec^=hvc1])")

    def test_audio_prefers_aac_over_container(self):
        # B站 Hi-Res(FLAC) 封装在 m4a 容器里但无法 copy 进 MP4，必须优先 AAC 编码
        eff = _eff()
        sel = build_format_selector(eff)
        first_audio = sel.split("+", 1)[1]
        assert first_audio.startswith("(ba[acodec^=mp4a]")

    def test_h264_prefers_avc(self):
        eff = _eff(codec="h264")
        sel = build_format_selector(eff)
        assert "avc1" in sel.split("/")[0]

    def test_height_cap_applied(self):
        eff = _eff(max_height=720)
        sel = build_format_selector(eff)
        assert "[height<=720]" in sel
        assert sel.endswith("/w")
        eff0 = _eff(max_height=0)
        assert "height<=" not in build_format_selector(eff0)
        assert not build_format_selector(eff0).endswith("/w")

    def test_audio_lang_chain(self):
        eff = _eff(audio_langs=["zh", "ja"])
        sel = build_format_selector(eff)
        assert "ba[language~=zh]" in sel
        assert "ba[language~=ja]" in sel
        # 无语言偏好时不包含 language 过滤
        assert "language~=" not in build_format_selector(_eff())

    def test_options_override_settings(self):
        s = Settings()
        s.download.max_height = 2160
        eff = resolve_options(s, DownloadOptions(max_height=480))
        assert eff.max_height == 480
        eff2 = resolve_options(s, None)
        assert eff2.max_height == 2160

    def test_parse_options_json(self):
        assert parse_options_json(None) is None
        assert parse_options_json("") is None
        assert parse_options_json("{bad") is None
        o = parse_options_json('{"max_height": 1080}')
        assert o.max_height == 1080


class TestParseSourceId:
    def test_bilibili_bv(self):
        assert parse_source_id("bilibili", "https://www.bilibili.com/video/BV1kMJv6pEPK?p=1") == "BV1kMJv6pEPK"

    def test_bilibili_av(self):
        assert parse_source_id("bilibili", "https://www.bilibili.com/video/av170001") == "170001"

    def test_youtube(self):
        assert parse_source_id("youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert parse_source_id("youtube", "https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert parse_source_id("youtube", "https://www.youtube.com/shorts/abcdefGHIjk") == "abcdefGHIjk"

    def test_douyin_tiktok(self):
        assert parse_source_id("douyin", "https://www.douyin.com/video/7345678901234567890") == "7345678901234567890"
        assert parse_source_id("tiktok", "https://www.tiktok.com/@user/video/7345678901234567890") == "7345678901234567890"

    def test_unparseable(self):
        assert parse_source_id("bilibili", "https://b23.tv/abc123") == ""
        assert parse_source_id("other", "https://example.com/x") == ""


class TestSourceIdEquivalence:
    """B站：yt-dlp 对 ?p=N 链接与多 P 合集给出 BVxxx_pN，单 P 视频不带 p 时给 BVxxx（2026-10 实测）。"""

    BASE = "https://www.bilibili.com/video/BV1bK411W797"

    def test_candidates(self):
        assert source_id_candidates("bilibili", self.BASE) == ["BV1bK411W797", "BV1bK411W797_p1"]
        assert source_id_candidates("bilibili", self.BASE + "?p=1") == ["BV1bK411W797", "BV1bK411W797_p1"]
        assert source_id_candidates("bilibili", self.BASE + "/?p=3&spm_id_from=x") == ["BV1bK411W797_p3"]
        assert source_id_candidates("youtube", "https://youtu.be/dQw4w9WgXcQ") == ["dQw4w9WgXcQ"]
        assert source_id_candidates("bilibili", "https://b23.tv/abc123") == []

    def test_equivalent_ids(self):
        assert equivalent_source_ids("bilibili", "BV1bK411W797") == ["BV1bK411W797", "BV1bK411W797_p1"]
        assert equivalent_source_ids("bilibili", "BV1bK411W797_p1") == ["BV1bK411W797_p1", "BV1bK411W797"]
        assert equivalent_source_ids("bilibili", "BV1bK411W797_p2") == ["BV1bK411W797_p2"]
        assert equivalent_source_ids("youtube", "dQw4w9WgXcQ") == ["dQw4w9WgXcQ"]

    def test_dedup_key_separates_anthology_parts(self):
        from app.downloader.engine import dedup_key

        assert dedup_key("bilibili", self.BASE) == dedup_key("bilibili", self.BASE + "?p=1")
        assert dedup_key("bilibili", self.BASE + "?p=2") != dedup_key("bilibili", self.BASE + "?p=1")


class TestDownloadOptionsModel:
    def test_codec_validated(self):
        with pytest.raises(ValidationError):
            DownloadOptions(codec="vp9")

    def test_to_json_keeps_only_explicit_fields(self):
        assert DownloadOptions().to_json() == ""
        assert DownloadOptions(codec="h264", max_height=720).to_json() == '{"max_height": 720, "codec": "h264"}'
