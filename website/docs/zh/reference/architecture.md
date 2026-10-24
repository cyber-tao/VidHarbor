# 系统架构与媒体管线

VidHarbor 采用单进程 Python 3.11+（`FastAPI` + `uvicorn`）与 Vue 3 单页应用架构，底层使用开启 WAL 模式的 SQLite 数据库（`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON`）。

## 1. 核心模块职责映射 {#module-map}

| 源码路径 | 核心职责 |
| --- | --- |
| `backend/app/main.py` | FastAPI 生命周期管理、启动依赖自检、API 路由挂载与前端构建产物 SPA 回退托管 |
| `backend/app/config.py` | 三层配置合并（`config.toml` < `VIDHARBOR_*` 环境变量 < SQLite `app_settings`）、平台专属 cookies 路径解析与时区校验 |
| `backend/app/db.py` 与 `models.py` | SQLAlchemy 2.0 引擎（`check_same_thread=False`, `busy_timeout=10000`）及 7 张核心表：`videos`、`subtitles`、`tags`、`tasks`、`charts_cache`、`schedules`、`app_settings` |
| `backend/app/downloader/urlnorm.py` | 从杂乱分享文案提取 HTTP(S) 链接，并自动展开 `v.douyin.com`、`vm.tiktok.com`、`vt.tiktok.com`、`b23.tv` 短链 |
| `backend/app/downloader/options.py` | `DownloadOptions` 校验、`yt-dlp` 格式选择器拼装（`build_format_selector`）与规范视频 ID 提取（`extract_source_id`、`equivalent_source_ids`） |
| `backend/app/downloader/engine.py` | `TaskQueue` 调度线程、全局与分平台并发控制、下载前去重，以及 `yt-dlp` → Evil0ctal v5 自动切换 |
| `backend/app/downloader/encoders.py` | 运行时解析 `ffmpeg -encoders` 并执行 1 帧 `640x360` 试编码探测（`hevc_nvenc` → `hevc_qsv` → `hevc_amf` → `hevc_videotoolbox` → `libx265`） |
| `backend/app/downloader/postprocess.py` | `ffprobe` 流信息探测、`ensure_mp4` 封装/转码决策、全局 `_Limiter` 转码信号量、文件原子入库回滚与 SRT 转 VTT |
| `backend/app/charts/` | 四平台榜单适配器（`bilibili.py`、`youtube.py`、`douyin.py`、`tiktok.py`） |
| `backend/app/scheduler.py` | APScheduler 定时任务注册、`claim_run` 单轮互斥锁与去重入队 |
| `frontend/src/` | Vue 3 + Vite + Tailwind CSS + Naive UI + ECharts + Pinia 前端控制台，内置 `i18n.js`（中英双语与深浅双色主题） |

## 2. 双层并发控制与独立转码限流 {#concurrency}

VidHarbor 将网络下载并发与耗时的 CPU/GPU 转码并发完全解耦：

1. **下载调度器（`engine.py` 中的 `TaskQueue._dispatch_loop`）：**
   - 每轮调度动态读取 `download.concurrency`（全局上限，默认 `2`）和 `download.per_platform_concurrency`（单平台上限，默认 `2`）。
   - 若 B站已有 2 个下载任务正在进行，后续 B站任务保持 `pending` 排队，而 YouTube 或 TikTok 任务仍可在全局额度内正常启动。
2. **转码限流器（`postprocess.py` 中的 `_transcode_limiter`）：**
   - 严格限制整个系统同时执行的 FFmpeg 转码进程数（`library.transcode_concurrency`，默认 `1`）。
   - **关键设计：** 当 `ensure_mp4` 判定源视频可以直接 **无损封装（`remux`）** 时，完全不占用 `_transcode_limiter` 槽位，直接执行 `ffmpeg -c copy` 秒级完成入库。

## 3. 下载前三级去重与等价 ID 识别 {#deduplication}

系统在三个阶段执行去重（`options.py`、`engine.py`、`postprocess.py`）：

1. **入队去重（`POST /api/tasks` 与 `scheduler.py`）：**
   `dedup_key(platform, url)` 将不同形态的链接归一为 `<platform>:<source_id>`（例如 `https://youtu.be/dQw4w9WgXcQ` 与 `https://www.youtube.com/watch?v=dQw4w9WgXcQ` 均归一为 `youtube:dQw4w9WgXcQ`），已在队列中（`pending` / `running`）的视频不重复建任务。
2. **下载前查库（`TaskQueue._execute`）：**
   工作线程在调用 `yt-dlp` 前先展开短链，并通过 `source_id_candidates(platform, url)` 查询 `videos` 表。针对 B站分 P 视频，不带 `p` 的 `BV1xx` 链接会同时匹配库中的 `BV1xx_p1`；若文件已在库中，任务直接标记为 `completed` 并关联已有 `video_id`，零网络流量消耗。
3. **数据库唯一约束兜底（`uq_video_platform_source`）：**
   `videos` 表强制 `(platform, source_id)` 唯一约束。若极端并发下两个相同视频同时完成下载，`ingest()` 捕获冲突后会回滚并清理多余文件，自动收敛到已入库记录。

## 4. `ensure_mp4` 封装与转码决策树 {#ensure-mp4}

```text
下载完成的原始媒体文件 (来自 yt-dlp 或 Evil0ctal)
  │
  ├─► ffprobe JSON 流探测 (检查视频流与音频流)
  │     └── 无视频流？ → 拒绝入库 (纯音频或图集作品不入库)
  │
  ├─► 目标编码 = h265 (默认)
  │     ├── 源视频编码为 hevc / h265？
  │     │     └── 是 → -c:v copy -tag:v hvc1 (无损封装 Remux)
  │     └── 否 → detect_hevc_encoder() → hevc_nvenc / hevc_qsv / hevc_amf / hevc_videotoolbox / libx265 + -tag:v hvc1
  │
  ├─► 目标编码 = h264
  │     ├── 源视频编码为 h264？
  │     │     └── 是 → -c:v copy (无损封装 Remux)
  │     └── 否 → -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p
  │
  ├─► 音频流处理
  │     ├── 无音频流 → -an
  │     ├── 源音频编码为 aac → -c:a copy
  │     └── 其他音频编码 → -c:a aac -b:a 192k
  │
  └─► 输出：ffmpeg ... -movflags +faststart final.mp4
```
