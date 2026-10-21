"""cookies 管理：平台域名过滤、ABE 预检、浏览器导入错误映射。"""
import http.cookiejar
import json

import pytest

from app.auth import cookies as cookies_mod
from app.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "data_dir", property(lambda self: tmp_path))
    return Settings()


def _make_cookie(domain, name="SESSDATA", value="x"):
    return http.cookiejar.Cookie(
        version=0, name=name, value=value, port=None, port_specified=False,
        domain=domain, domain_specified=True, domain_initial_dot=domain.startswith("."),
        path="/", path_specified=True, secure=True, expires=None, discard=False,
        comment=None, comment_url=None, rest={}, rfc2109=False,
    )


class TestDomainFilter:
    def test_save_text_keeps_only_platform_domains(self, settings):
        text = "\n".join([
            "# Netscape HTTP Cookie File",
            ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tabc",
            "www.bilibili.com\tFALSE\t/\tFALSE\t0\tbuvid3\tdef",
            ".google.com\tTRUE\t/\tTRUE\t0\tSID\txyz",
            "evilbilibili.com\tTRUE\t/\tTRUE\t0\ta\tb",
        ])
        assert cookies_mod.save_text(settings, "bilibili", text) == 2
        lines = [l for l in (settings.cookies_dir / "bilibili.txt")
                 .read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert len(lines) == 2
        assert all("bilibili.com" in l for l in lines)

    def test_save_text_rejects_no_platform_cookies(self, settings):
        with pytest.raises(ValueError, match="平台域名"):
            cookies_mod.save_text(settings, "tiktok", ".example.com\tTRUE\t/\tTRUE\t0\ta\tb")

    def test_save_text_rejects_bad_format(self, settings):
        with pytest.raises(ValueError, match="Netscape"):
            cookies_mod.save_text(settings, "douyin", "not\ta\tcookie\tline")

    def test_save_cookiejar_filters_foreign_domains(self, settings):
        jar = http.cookiejar.MozillaCookieJar()
        jar.set_cookie(_make_cookie(".douyin.com", "sessionid", "1"))
        jar.set_cookie(_make_cookie(".bank.example", "token", "2"))
        assert cookies_mod.save_cookiejar(settings, "douyin", jar) == 1
        content = (settings.cookies_dir / "douyin.txt").read_text(encoding="utf-8")
        assert "sessionid" in content and "token" not in content

    def test_save_cookiejar_zero_when_nothing_matches(self, settings):
        jar = http.cookiejar.MozillaCookieJar()
        jar.set_cookie(_make_cookie(".douyin.com", "sessionid", "1"))
        assert cookies_mod.save_cookiejar(settings, "youtube", jar) == 0
        assert not (settings.cookies_dir / "youtube.txt").exists()


class TestAppBoundPrecheck:
    def test_raises_when_abe_key_present(self, tmp_path, monkeypatch):
        local_state = tmp_path / "Local State"
        local_state.write_text(
            json.dumps({"os_crypt": {"app_bound_encrypted_key": "AA"}}), encoding="utf-8")
        monkeypatch.setattr(cookies_mod, "_local_state_path",
                            lambda browser: local_state if browser == "chrome" else None)
        with pytest.raises(ValueError, match="应用绑定加密"):
            cookies_mod._check_app_bound_encryption("chrome")

    def test_passes_without_abe_key(self, tmp_path, monkeypatch):
        local_state = tmp_path / "Local State"
        local_state.write_text(json.dumps({"os_crypt": {}}), encoding="utf-8")
        monkeypatch.setattr(cookies_mod, "_local_state_path", lambda browser: local_state)
        cookies_mod._check_app_bound_encryption("chrome")
        cookies_mod._check_app_bound_encryption("firefox")  # 非 chromium 直接跳过


class TestFriendlyErrors:
    def test_locked_database_hint(self):
        e = Exception("ERROR: Could not copy Chrome cookie database. See  "
                      "https://github.com/yt-dlp/yt-dlp/issues/7271  for more info")
        assert "完全退出 Chrome" in cookies_mod._friendly_browser_error("chrome", e)

    def test_dpabi_hint(self):
        e = Exception("Failed to decrypt with DPAPI. See "
                      "https://github.com/yt-dlp/yt-dlp/issues/10927 for more info")
        msg = cookies_mod._friendly_browser_error("edge", e)
        assert "Get cookies.txt LOCALLY" in msg and "Firefox" in msg

    def test_not_found_hint(self):
        msg = cookies_mod._friendly_browser_error("firefox", Exception("could not find firefox database"))
        assert "未找到" in msg

    def test_fallback_keeps_original_text(self):
        msg = cookies_mod._friendly_browser_error("opera", Exception("boom"))
        assert "boom" in msg


def test_import_from_browser_filters_and_saves(monkeypatch, settings):
    from yt_dlp import cookies as ydl_cookies
    jar = http.cookiejar.MozillaCookieJar()
    jar.set_cookie(_make_cookie(".tiktok.com", "tt_webid", "1"))
    jar.set_cookie(_make_cookie(".unrelated.example", "x", "2"))
    monkeypatch.setattr(ydl_cookies, "extract_cookies_from_browser", lambda *a, **k: jar)
    monkeypatch.setattr(cookies_mod, "_check_app_bound_encryption", lambda b: None)
    assert cookies_mod.import_from_browser(settings, "tiktok", "chrome") == 1
