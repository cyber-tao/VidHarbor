"""HEVC 编码器探测：-encoders 输出解析 + auto 探测与按偏好缓存。"""


class TestParseEncoderLines:
    def test_flags_suffix_is_recognized(self):
        """NVENC/AMF 等带 D 标志后缀的硬件编码器不能被漏掉（历史 bug）。"""
        from app.downloader.encoders import _parse_encoder_lines

        text = "\n".join([
            "Encoders:",
            " V..... = Video",
            " A..... = Audio",
            " ------",
            " V....D hevc_nvenc           NVIDIA NVENC hevc encoder",
            " V..... hevc_qsv             HEVC (Intel Quick Sync Video acceleration)",
            " V....D hevc_amf             AMD AMF HEVC encoder",
            " V....D libx265              libx265 H.265",
            " V..... libx264              libx264 H.264",
            " A..... aac                  AAC (Advanced Audio Coding)",
        ])
        names = _parse_encoder_lines(text)
        assert {"hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265", "libx264"} <= names
        assert "aac" not in names
        assert "=" not in names  # 图例行不进结果


class TestDetect:
    def test_auto_prefers_hw_and_caches_per_preference(self, monkeypatch):
        import app.downloader.encoders as enc

        monkeypatch.setattr(enc, "_list_encoders", lambda: {"hevc_nvenc", "libx265"})
        monkeypatch.setattr(enc, "_test_encode", lambda e: e == "hevc_nvenc")
        monkeypatch.setattr(enc, "_detected", {})
        assert enc.detect_hevc_encoder("auto") == "hevc_nvenc"
        assert enc.detect_hevc_encoder("auto") == "hevc_nvenc"  # 命中缓存
        # 手动指定另一个编码器不应读到 auto 的缓存
        assert enc.detect_hevc_encoder("libx265") == "libx265"

    def test_auto_falls_back_when_hw_test_fails(self, monkeypatch):
        import app.downloader.encoders as enc

        monkeypatch.setattr(enc, "_list_encoders", lambda: {"hevc_nvenc", "libx265"})
        monkeypatch.setattr(enc, "_test_encode", lambda e: False)  # 驱动不可用
        monkeypatch.setattr(enc, "_detected", {})
        assert enc.detect_hevc_encoder("auto") == "libx265"
