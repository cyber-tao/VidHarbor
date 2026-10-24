# Verification & Evidence Registry

Every technical claim on the VidHarbor website is backed by source inspection, automated test execution, or repeatable measurement at revision **`v0.3.0` (`435b7ca` + bilingual/theme update)** on **2026-10-24**.

## 1. Evidence Map {#evidence-map}

| Claim ID | Claim Summary | Status | Source / Artifact | Verification Method & Result |
| --- | --- | --- | --- | --- |
| **EV-01** | When targeting H.265 (`video_codec = "h265"`), `ensure_mp4` remuxes existing HEVC+AAC streams losslessly (`-c:v copy -tag:v hvc1 -movflags +faststart`) rather than re-encoding, completing **3.9× faster** (`525.8 ms` vs `2033.2 ms` median) on a 5s 1080p@30fps workload. | **Measured & Executed** | `backend/app/downloader/postprocess.py` (`ensure_mp4`), <a href="/VidHarbor/evidence/postprocess-benchmark.json" target="_blank"><code>/evidence/postprocess-benchmark.json</code></a> | 1 warmup + 5 timed runs via `ffmpeg` 9.0 & `ffprobe`. Remux median: `525.75 ms` (stdev `4.17 ms`, `action="remux"`, `codec_tag_string="hvc1"`). Software `libx265` transcode median: `2033.19 ms` (stdev `1.28 ms`, `action="transcode"`). |
| **EV-02** | Pre-download deduplication normalizes multi-form URLs (`youtu.be/<id>`, `youtube.com/watch?v=<id>`, Bilibili `BV...` and `BV..._p1`), expands short links (`v.douyin.com`, `vm.tiktok.com`, `b23.tv`), and skips active or archived videos before invoking `yt-dlp`. | **Executed & Source-Verified** | `backend/app/downloader/urlnorm.py`, `options.py`, `engine.py`, `scheduler.py`, `backend/tests/test_urlnorm.py`, `test_options.py`, `test_api.py` | Verified via `uv run pytest` (`212 passed`), including `TestTaskDedup`, `TestScheduleDedup`, and `TestScheduleConcurrency`. |
| **EV-03** | Hardware HEVC encoder detection probes candidate encoders (`hevc_nvenc`, `hevc_qsv`, `hevc_amf`, `hevc_videotoolbox`) with a real 1-frame `640x360` test encode before falling back to `libx265`. | **Executed & Source-Verified** | `backend/app/downloader/encoders.py` (`detect_hevc_encoder`, `_test_encode`), `backend/tests/test_encoders.py` | Verified in unit tests and live runtime (`detect_hevc_encoder('auto')` probed and verified `hevc_nvenc` on test host). |
| **EV-04** | Per-platform cookies (`data/cookies/{platform}.txt`) preserve `#HttpOnly_` entries (such as `SESSDATA` and `sessionid`) and filter out cookies belonging to other domains (`PLATFORM_DOMAINS`). | **Executed & Source-Verified** | `backend/app/auth/cookies.py` (`parse_netscape`, `cookie_jar`), `backend/tests/test_auth_cookies.py`, `test_charts.py` | Verified by `test_sends_httponly_sessdata` and `test_httponly_session_cookie_is_sent` in `pytest`. |
| **EV-05** | Web console supports English (`en`) and Simplified Chinese (`zh-CN`) plus Dark and Light themes, defaulting to English + Dark on first visit and persisting user selection in `localStorage`. | **Executed (Browser Verified)** | `frontend/index.html`, `frontend/src/i18n.js`, `frontend/src/App.vue`, <a href="/VidHarbor/screenshots/dashboard-en-dark.png" target="_blank"><code>/screenshots/dashboard-en-dark.png</code></a> | Verified in headless Chromium via Playwright across `en/dark`, `en/light`, `zh/dark`, `zh/light` with OS `prefers-color-scheme: light` emulation and reload persistence checks. |

## 2. Reproducing the Post-Processing Measurement (`EV-01`) {#reproduce-ev01}

### Environment

- **Date:** `2026-10-24`
- **OS:** `Windows 10.0.26200 (x86_64)`
- **Python / Toolchain:** `Python 3.14` managed by `uv`, `FFmpeg 9.0-full_build-www.gyan.dev`
- **Compared paths:**
  - **Path A (Remux):** `ensure_mp4(hevc_src, out_dir, video_codec='h265', hw_encoder='libx265')` where `hevc_src` is a 5.0-second `1920x1080 @ 30fps` `hevc` + `aac` stream in Matroska (`.mkv`).
  - **Path B (Software Transcode):** `ensure_mp4(h264_src, out_dir, video_codec='h265', hw_encoder='libx265')` where `h264_src` is an equivalent 5.0-second `1920x1080 @ 30fps` `h264` + `aac` stream transcoded to HEVC via `libx265` (`-crf 24 -preset medium`).

### Reproduction Command

Run from `backend/`:

```bash
cd backend
uv run python -c "
import json, subprocess, tempfile, time, statistics
from pathlib import Path
from app.downloader.postprocess import ensure_mp4, run_ffprobe

with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    hevc_src = td_path / 'sample_hevc.mkv'
    h264_src = td_path / 'sample_h264.mkv'
    subprocess.run([
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=5',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=5',
        '-c:v', 'libx265', '-crf', '24', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', str(hevc_src)
    ], check=True)
    subprocess.run([
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=5',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=5',
        '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', str(h264_src)
    ], check=True)

    ensure_mp4(hevc_src, td_path / 'w_r', video_codec='h265', hw_encoder='libx265')
    ensure_mp4(h264_src, td_path / 'w_t', video_codec='h265', hw_encoder='libx265')

    remux_ms, trans_ms = [], []
    for i in range(5):
        t0 = time.perf_counter()
        ensure_mp4(hevc_src, td_path / f'r_{i}', video_codec='h265', hw_encoder='libx265')
        remux_ms.append(round((time.perf_counter() - t0) * 1000, 2))
        t0 = time.perf_counter()
        ensure_mp4(h264_src, td_path / f't_{i}', video_codec='h265', hw_encoder='libx265')
        trans_ms.append(round((time.perf_counter() - t0) * 1000, 2))
    print({'remux_ms': remux_ms, 'transcode_ms': trans_ms})
"
```

### Qualifications & Scope Limitations

- `ensure_mp4` polls `ffmpeg` process completion in `500 ms` intervals (`time.sleep(0.5)` in `_run_ffmpeg`), which establishes a ~500 ms floor for any `ffmpeg` invocation regardless of file size. On longer real-world videos (e.g., 10–60 minutes), stream-copy remuxing remains I/O-bound (seconds) whereas CPU `libx265` transcoding scales linearly with video duration and resolution.
- When source streams are VP9 or AV1 (common on YouTube 4K), targeting H.265 or H.264 requires transcoding (hardware encoder or CPU fallback); lossless remuxing applies only when the downloaded video stream already matches the target codec (`hevc`/`h265` for `h265`, or `h264` for `h264`).

## 3. Running the Full Backend Test Suite {#pytest-suite}

```bash
cd backend
uv run pytest -q
```

Verified output (`2026-10-24`): `212 passed`.
