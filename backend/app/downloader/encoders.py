"""HEVC 编码器探测与转码参数：硬件优先（NVENC/QSV/AMF/VideoToolbox），回退 libx265。"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading

log = logging.getLogger("vidharbor.encoders")

# 探测顺序：常见度优先；videotoolbox 仅 macOS
_HW_CANDIDATES = [
    ("hevc_nvenc", ("win32", "linux", "darwin")),
    ("hevc_qsv", ("win32", "linux", "darwin")),
    ("hevc_amf", ("win32", "linux")),
    ("hevc_videotoolbox", ("darwin",)),
]

# 各编码器的质量参数（约等于 libx265 CRF24 的码率效率不做严格对齐，够用即可）
ENCODER_ARGS: dict[str, list[str]] = {
    "libx265": ["-c:v", "libx265", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p"],
    "hevc_nvenc": ["-c:v", "hevc_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "26", "-b:v", "0"],
    "hevc_qsv": ["-c:v", "hevc_qsv", "-preset", "medium", "-global_quality", "26"],
    "hevc_amf": ["-c:v", "hevc_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"],
    "hevc_videotoolbox": ["-c:v", "hevc_videotoolbox", "-q:v", "35"],
}

_lock = threading.Lock()
# preference -> 探测结果（auto 与手动指定分开缓存，换设置后无需重启）
_detected: dict[str, str] = {}

# 行格式 ` V....D hevc_nvenc  描述`：首列 V + 5 个标志位，D/F/S 等是后缀，
# 不能只认 "V....."，否则 NVENC/AMF 等带 D 标志的硬件编码器会被漏掉
_ENCODER_LINE = re.compile(r"^V[.A-Z]{5}$")


def _parse_encoder_lines(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and _ENCODER_LINE.match(parts[0]) and parts[1] != "=":
            names.add(parts[1])
    return names


def _list_encoders() -> set[str]:
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        return _parse_encoder_lines(p.stdout or "")
    except Exception:  # noqa: BLE001
        return set()


def _test_encode(encoder: str) -> bool:
    """1 帧试编码，验证驱动/硬件真实可用（尺寸要够大：NVENC 有最小分辨率限制）。"""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", "color=black:s=640x360:d=0.1",
           "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return p.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def detect_hevc_encoder(preference: str = "auto") -> str:
    """返回可用的 HEVC 编码器名。preference 可指定具体编码器；auto = 硬件优先探测。"""
    with _lock:
        cached = _detected.get(preference)
        if cached is not None:
            return cached
        available = _list_encoders()
        result = "libx265"
        if preference and preference != "auto":
            if preference in ENCODER_ARGS and preference in available and _test_encode(preference):
                result = preference
            else:
                log.warning("指定编码器 %s 不可用，回退 libx265", preference)
        else:
            for enc, platforms in _HW_CANDIDATES:
                if sys.platform not in platforms or enc not in available:
                    continue
                if _test_encode(enc):
                    result = enc
                    break
                log.info("%s 在 -encoders 列表中但试编码失败（驱动/硬件不可用），跳过", enc)
        _detected[preference] = result
        log.info("HEVC 编码器[%s]: %s%s", preference, result,
                 "（硬件加速）" if result != "libx265" else "（软件）")
        return result
