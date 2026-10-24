# Architecture & Media Pipeline

VidHarbor is a single-process Python 3.11+ (`FastAPI` + `uvicorn`) and Vue 3 SPA system backed by SQLite in WAL mode (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON`).

## 1. Repository & Module Map {#module-map}

| Path | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI lifespan management, startup dependency self-checks, API router registration, and static SPA fallback |
| `backend/app/config.py` | Three-tier settings resolution (`config.toml` < `VIDHARBOR_*` env vars < SQLite `app_settings`), cookie file resolution, and timezone parsing |
| `backend/app/db.py` & `models.py` | SQLAlchemy 2.0 engine (`check_same_thread=False`, `busy_timeout=10000`) and 7 tables: `videos`, `subtitles`, `tags`, `tasks`, `charts_cache`, `schedules`, `app_settings` |
| `backend/app/downloader/urlnorm.py` | HTTP(S) URL extraction from messy share text and short-link expansion (`v.douyin.com`, `vm.tiktok.com`, `vt.tiktok.com`, `b23.tv`) |
| `backend/app/downloader/options.py` | `DownloadOptions` validation, format selector synthesis (`build_format_selector`), and canonical ID extraction (`extract_source_id`, `equivalent_source_ids`) |
| `backend/app/downloader/engine.py` | `TaskQueue` dispatcher thread, global and per-platform concurrency enforcement, pre-download deduplication, and `yt-dlp` → Evil0ctal v5 fallback |
| `backend/app/downloader/encoders.py` | Runtime `ffmpeg -encoders` parsing and 1-frame `640x360` hardware probe (`hevc_nvenc` → `hevc_qsv` → `hevc_amf` → `hevc_videotoolbox` → `libx265`) |
| `backend/app/downloader/postprocess.py` | `ffprobe` stream inspection, `ensure_mp4` remux/transcode pipeline, global `_Limiter` transcode semaphore, atomic file move + rollback, and SRT-to-VTT conversion |
| `backend/app/charts/` | Platform chart providers (`bilibili.py`, `youtube.py`, `douyin.py`, `tiktok.py`) |
| `backend/app/scheduler.py` | APScheduler job registration, single-flight `claim_run`, and deduplicated task creation |
| `frontend/src/` | Vue 3 + Vite + Tailwind CSS + Naive UI + ECharts + Pinia SPA with `i18n.js` (EN / 简体中文, Dark / Light theme) |

## 2. Two-Level Concurrency & Transcode Limiting {#concurrency}

VidHarbor separates network download concurrency from CPU/GPU transcode concurrency:

1. **Download Dispatcher (`TaskQueue._dispatch_loop` in `engine.py`):**
   - Reads `download.concurrency` (global cap, default `2`) and `download.per_platform_concurrency` (per-platform cap, default `2`) dynamically on every scheduling cycle.
   - If Bilibili has 2 active downloads, additional Bilibili tasks wait in `pending` while YouTube or TikTok tasks continue to dispatch up to the global limit.
2. **Transcode Limiter (`_transcode_limiter` in `postprocess.py`):**
   - Enforces `library.transcode_concurrency` (default `1`).
   - **Crucial design detail:** When `ensure_mp4` determines that a downloaded file can be **losslessly remuxed** (`need_transcode == False`), it bypasses `_transcode_limiter` entirely and runs `ffmpeg -c copy` immediately. Only actual re-encoding jobs acquire a transcode slot.

## 3. Pre-Download Deduplication & Equivalent IDs {#deduplication}

Deduplication happens at three boundaries (`options.py`, `engine.py`, `postprocess.py`):

1. **Queue submission (`POST /api/tasks` & `scheduler.py`):**
   `dedup_key(platform, url)` normalizes the URL into `<platform>:<source_id>` (for example, `https://youtu.be/dQw4w9WgXcQ` and `https://www.youtube.com/watch?v=dQw4w9WgXcQ` both resolve to `youtube:dQw4w9WgXcQ`). Tasks already in `pending` or `running` with the same key are skipped immediately.
2. **Pre-download library check (`TaskQueue._execute`):**
   Before invoking `yt-dlp`, the worker expands short links (`normalize_url`) and queries `videos` using `source_id_candidates(platform, url)`. For Bilibili, a bare URL `BV1xx` also matches `BV1xx_p1` (the ID `yt-dlp` assigns to multi-part videos). If a match exists on disk, the task completes instantaneously (`progress = 1.0`, `stage = "done"`) without downloading a single media byte.
3. **Database uniqueness backstop (`uq_video_platform_source`):**
   The `videos` table enforces `UniqueConstraint("platform", "source_id")`. If two concurrent downloads of the same video race to completion, `ingest()` catches the constraint conflict, rolls back the duplicate file move, and links the task to the winning `Video` row.

## 4. `ensure_mp4` Decision Tree {#ensure-mp4}

```text
Input media file (from yt-dlp or Evil0ctal)
  │
  ├─► ffprobe JSON inspection (video stream + audio stream)
  │     └── No video stream? → Reject (audio-only / photo posts not indexed)
  │
  ├─► Target = h265 (default)
  │     ├── Source vcodec in (hevc, h265)?
  │     │     └── YES → -c:v copy -tag:v hvc1 (Lossless Remux)
  │     └── NO  → detect_hevc_encoder() → hevc_nvenc / hevc_qsv / hevc_amf / hevc_videotoolbox / libx265 + -tag:v hvc1
  │
  ├─► Target = h264
  │     ├── Source vcodec == h264?
  │     │     └── YES → -c:v copy (Lossless Remux)
  │     └── NO  → -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p
  │
  ├─► Audio stream check
  │     ├── No audio stream → -an
  │     ├── Source acodec == aac → -c:a copy
  │     └── Otherwise → -c:a aac -b:a 192k
  │
  └─► Output: ffmpeg ... -movflags +faststart final.mp4
```
