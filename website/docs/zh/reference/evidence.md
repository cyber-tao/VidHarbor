# 实测验证与证据清单

本网站展示的所有技术特性均基于 **VidHarbor `v0.3.0`（commit `435b7ca` 及本次双语/双色主题更新）** 于 **2026-10-24** 完成源码核对、自动化测试执行与可复现基准测量。

## 1. 核心声明与证据映射表 {#evidence-map}

| 编号 | 声明内容 | 证据状态 | 源码位置 / 产物文件 | 验证方法与实测结果 |
| --- | --- | --- | --- | --- |
| **EV-01** | 当入库目标为 H.265（`video_codec = "h265"`）时，`ensure_mp4` 对已是 HEVC+AAC 的源流直接执行无损封装（`-c:v copy -tag:v hvc1 -movflags +faststart`），在 5 秒 1080p@30fps 负载下比 `libx265` 软件转码快 **3.9 倍**（中位数 `525.8 ms` vs `2033.2 ms`）。 | **已实测（Measured & Executed）** | `backend/app/downloader/postprocess.py` (`ensure_mp4`)、<a href="/VidHarbor/evidence/postprocess-benchmark.json" target="_blank"><code>/evidence/postprocess-benchmark.json</code></a> | 基于 FFmpeg 9.0 执行 1 次预热 + 5 次计时采样。无损 Remux 中位数：`525.75 ms`（标准差 `4.17 ms`，`action="remux"`，`codec_tag_string="hvc1"`）；软件 `libx265` 转码中位数：`2033.19 ms`（标准差 `1.28 ms`，`action="transcode"`）。 |
| **EV-02** | 下载前去重支持多形态链接归一化（`youtu.be/<id>`、`youtube.com/watch?v=<id>`、B站 `BV...` 与 `BV..._p1` 等价识别）及短链展开（`v.douyin.com`、`vm.tiktok.com`、`b23.tv`），在调用 `yt-dlp` 前跳过已在队列或库中的视频。 | **已执行验证（Executed & Source-Verified）** | `backend/app/downloader/urlnorm.py`、`options.py`、`engine.py`、`scheduler.py`、`backend/tests/test_urlnorm.py`、`test_options.py`、`test_api.py` | 运行 `uv run pytest`（`212 passed`），涵盖 `TestTaskDedup`、`TestScheduleDedup` 与 `TestScheduleConcurrency`。 |
| **EV-03** | 硬件 HEVC 编码器自动探测会对候选编码器（`hevc_nvenc`、`hevc_qsv`、`hevc_amf`、`hevc_videotoolbox`）执行真实的 1 帧 `640x360` 试编码，失败时自动回退 `libx265`。 | **已执行验证（Executed & Source-Verified）** | `backend/app/downloader/encoders.py` (`detect_hevc_encoder`, `_test_encode`)、`backend/tests/test_encoders.py` | 通过单元测试及本机运行时探测验证（`detect_hevc_encoder('auto')` 成功探测并验证 `hevc_nvenc`）。 |
| **EV-04** | 平台专属 cookies（`data/cookies/{platform}.txt`）完整保留 `#HttpOnly_` 条目（如 `SESSDATA` 与 `sessionid`），并按 `PLATFORM_DOMAINS` 严格过滤跨站域名。 | **已执行验证（Executed & Source-Verified）** | `backend/app/auth/cookies.py` (`parse_netscape`, `cookie_jar`)、`backend/tests/test_auth_cookies.py`、`test_charts.py` | 通过 `test_sends_httponly_sessdata` 与 `test_httponly_session_cookie_is_sent` 用例验证。 |
| **EV-05** | Web 控制台支持中英双语（`English` / `简体中文`）与深浅双色主题（`Dark` / `Light`），首次访问默认英文深色，并在 `localStorage` 中持久化用户选择。 | **浏览器实测（Browser Verified）** | `frontend/index.html`、`frontend/src/i18n.js`、`frontend/src/App.vue`、<a href="/VidHarbor/screenshots/dashboard-zh-dark.png" target="_blank"><code>/screenshots/dashboard-zh-dark.png</code></a> | 使用 Playwright 在无头 Chromium 中遍历验证 `en/dark`、`en/light`、`zh/dark`、`zh/light` 四种组合、系统浅色偏好下的默认深色首屏以及刷新保持行为。 |

## 2. 复现后处理基准测试（`EV-01`） {#reproduce-ev01}

### 测试环境

- **日期：** `2026-10-24`
- **操作系统：** `Windows 10.0.26200 (x86_64)`
- **运行环境：** `Python 3.14`（`uv` 管理），`FFmpeg 9.0-full_build-www.gyan.dev`
- **对比路径：**
  - **路径 A（无损 Remux）：** `ensure_mp4(hevc_src, out_dir, video_codec='h265', hw_encoder='libx265')`，输入为 5.0 秒 `1920x1080 @ 30fps` 的 `hevc` + `aac` `.mkv` 文件。
  - **路径 B（软件转码）：** `ensure_mp4(h264_src, out_dir, video_codec='h265', hw_encoder='libx265')`，输入为同规格 5.0 秒 `h264` + `aac` `.mkv` 文件，经 `libx265`（`-crf 24 -preset medium`）转码为 HEVC。

### 复现命令

在 `backend/` 目录下执行：

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

### 结果边界与适用条件说明

- `_run_ffmpeg` 采用 `500 ms` 轮询间隔（`time.sleep(0.5)`）检查子进程退出状态，因此任何 `ffmpeg` 调用均带有约 `500 ms` 的轮询下限。在实际长视频（如 10–60 分钟）中，无损 `remux` 仅受磁盘 I/O 限制（通常数秒内完成），而软件 `libx265` 转码耗时随视频时长与分辨率线性增长。
- 若源站下载流为 VP9 或 AV1（常见于 YouTube 4K 流），转换为 H.265 或 H.264 仍需经过硬件或软件转码；仅当下载流本身已匹配目标编码（目标 `h265` 且源为 `hevc`/`h265`，或目标 `h264` 且源为 `h264`）时触发无损 `remux`。

## 3. 运行后端完整自动化测试套件 {#pytest-suite}

```bash
cd backend
uv run pytest -q
```

实测结果（`2026-10-24`）：`212 passed`。
