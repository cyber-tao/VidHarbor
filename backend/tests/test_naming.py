from app.naming import build_filename, build_relpath, sanitize, sanitize_date


class TestSanitize:
    def test_strips_windows_illegal_chars(self):
        assert "/" not in sanitize('a/b\\c:d*e?f"g<h>i|j', 50, "fb")
        assert sanitize('a/b', 50, "fb") == "a b"

    def test_collapses_whitespace(self):
        assert sanitize("a   \t\n b", 50, "fb") == "a b"

    def test_strips_trailing_dots_spaces(self):
        assert sanitize("name...", 50, "fb") == "name"
        assert sanitize("name . ", 50, "fb") == "name"

    def test_empty_falls_back(self):
        assert sanitize("", 50, "fb") == "fb"
        assert sanitize(None, 50, "fb") == "fb"
        assert sanitize("///", 50, "fb") == "fb"

    def test_truncates(self):
        assert len(sanitize("x" * 300, 120, "fb")) == 120

    def test_chinese_preserved(self):
        assert sanitize("【4K】治愈系风景 / 第1期", 120, "fb") == "【4K】治愈系风景 第1期"


class TestSanitizeDate:
    def test_valid(self):
        assert sanitize_date("20260115") == "20260115"

    def test_garbage(self):
        assert sanitize_date("") == "undated"
        assert sanitize_date(None) == "undated"
        assert sanitize_date("2026") == "undated"


class TestBuildFilename:
    def test_default_template(self):
        name = build_filename(
            "{upload_date} - {title} [{id}]", "bilibili", "UP主", "20260101", "标题", "BV1xx"
        )
        assert name == "20260101 - 标题 [BV1xx]"

    def test_illegal_title_sanitized(self):
        name = build_filename(
            "{upload_date} - {title} [{id}]", "youtube", "chan", "20260101",
            'What? <Is> This: "Title"/|\\', "abc123"
        )
        for ch in '\\/:*?"<>|':
            assert ch not in name

    def test_missing_date_uses_undated(self):
        name = build_filename("{upload_date} - {title}", "tiktok", "u", "", "t", "id1")
        assert name.startswith("undated")

    def test_missing_uploader_uses_unknown(self):
        assert "unknown" in build_relpath("tiktok", "")

    def test_unknown_placeholder_in_template(self):
        # 模板含未知字段 → 回退默认模板
        name = build_filename("{bad_field} - {title}", "douyin", "u", "20260101", "标题", "id")
        assert "标题" in name and "bad_field" not in name

    def test_relpath(self):
        assert build_relpath("BiliBili", "某 UP") == "bilibili/某 UP"


class TestPlatform:
    def test_detect(self):
        from app.downloader.engine import detect_platform

        assert detect_platform("https://www.youtube.com/watch?v=x") == "youtube"
        assert detect_platform("https://youtu.be/x") == "youtube"
        assert detect_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
        assert detect_platform("https://b23.tv/abcd") == "bilibili"
        assert detect_platform("https://www.tiktok.com/@user/video/123") == "tiktok"
        assert detect_platform("https://v.douyin.com/abc/") == "douyin"
        assert detect_platform("https://example.com/video") == "other"
