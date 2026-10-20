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
