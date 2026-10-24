# REST & SSE API Reference

All endpoints are served by the FastAPI application (`backend/app/main.py`, version `0.3.0`). All timestamps in API responses are ISO-8601 strings carrying an explicit UTC offset (e.g. `2026-10-24T02:00:00.000+00:00`).

## 1. Authentication & Session (`backend/app/api/access.py`) {#auth-session}

When `VIDHARBOR_TOKEN` (`TOKEN` in `.env`) is set, every `/api/*` endpoint except `/api/health` and `/api/auth/session` requires either:

- Header: `X-Vidharbor-Token: <token>`
- Cookie: `vidharbor_session` (obtained via `POST /api/auth/session`)

| Method & Path | Auth Required | Description |
| --- | --- | --- |
| `GET /api/health` | No | Returns `{"ok": true, "version": "0.3.0"}` |
| `GET /api/auth/session` | No | Returns `{"required": bool, "authenticated": bool}` |
| `POST /api/auth/session` | No | Body: `{"token": "..."}`. Validates token with `hmac.compare_digest` and sets the `HttpOnly` `vidharbor_session` cookie (30 days) |
| `DELETE /api/auth/session` | No | Clears the `vidharbor_session` cookie |

## 2. Download Tasks (`backend/app/api/tasks.py`) {#tasks-api}

| Method & Path | Request Body / Query | Response & Behavior |
| --- | --- | --- |
| `POST /api/tasks` | `{"urls": ["..."], "options": {"max_height": 1080, "codec": "h265", "sub_langs": [...], "audio_langs": [...]}}` (`options` is optional) | Extracts HTTP(S) URLs from raw share text, deduplicates against active queue (`pending` / `running`), creates `DownloadTask` rows, and returns `{"tasks": [...], "skipped": int}` |
| `GET /api/tasks` | `?limit=100&schedule_id=0` | Returns `{"tasks": [...]}` ordered by `id DESC` |
| `DELETE /api/tasks/{task_id}` | — | If `pending` or `running`, signals cancellation (`{"canceled": true}`); if already in a terminal state (`completed`, `failed`, `canceled`), deletes the task row (`{"deleted": true}`) |
| `POST /api/tasks/{task_id}/retry` | — | Re-queues a `failed` or `canceled` task. Returns `400` if task is active, or `409` if another active task for the same video is already queued |

## 3. Video Library & Tags (`backend/app/api/videos.py`) {#videos-api}

| Method & Path | Query Parameters | Response & Behavior |
| --- | --- | --- |
| `GET /api/videos` | `q`, `platform`, `tag` (comma-separated AND filter), `page` (`1`), `page_size` (`48`, max `200`) | Returns `{"total": int, "page": int, "page_size": int, "items": [...]}` with preloaded tags and subtitle counts (no N+1 queries) |
| `GET /api/videos/{video_id}` | — | Returns full video metadata, `absolute_path`, `file_exists`, `tags`, and `subtitles` list |
| `GET /api/videos/{video_id}/file` | Supports HTTP `Range` (`bytes=start-end` and `bytes=-suffix`) | Streams the `.mp4` file (`206 Partial Content` / `200 OK`) |
| `GET /api/videos/{video_id}/thumbnail` | — | Serves the local cover image or a generated SVG placeholder if missing |
| `GET /api/videos/{video_id}/subtitles/{sub_id}` | — | Returns raw `.srt` text (`text/plain; charset=utf-8`) |
| `GET /api/videos/{video_id}/subtitles/{sub_id}/vtt` | — | Converts and serves the subtitle track as `text/vtt` for HTML5 `<track>` |
| `DELETE /api/videos/{video_id}` | `?delete_files=true` | Deletes the database record and removes video/thumbnail/subtitle files from disk (with Windows file-lock retry) |
| `GET /api/tags` | `?platform=` | Returns aggregated tag counts `{"tags": [{"name": "...", "count": int}]}` |

## 4. Trending Charts & Schedules (`charts.py`, `schedules.py`) {#charts-schedules-api}

| Method & Path | Parameters / Body | Response & Behavior |
| --- | --- | --- |
| `GET /api/charts` | — | Lists supported platforms: `bilibili`, `youtube`, `tiktok`, `douyin` |
| `GET /api/charts/{platform}` | `?category=&period=&refresh=false&meta=false` | When `meta=true`, returns category/period definitions. Otherwise returns 30-min cached or live chart items (`degraded: true` on fallback) |
| `GET /api/schedules` | — | Lists all schedules with `next_run_at`, `last_run_at`, `trigger_desc`, and `last_result` |
| `POST /api/schedules` | `ScheduleIn` JSON (`name`, `mode`, `at_time`, `weekdays`, `interval_minutes`, `cron`, `selections`, `options`) | Validates selections (rejects non-downloadable topic boards like `douyin/hot`), saves to SQLite, and registers with APScheduler |
| `PUT /api/schedules/{id}` | `ScheduleIn` JSON | Updates schedule and re-registers APScheduler job |
| `POST /api/schedules/{id}/toggle` | — | Toggles `enabled` state |
| `POST /api/schedules/{id}/run` | — | Triggers an immediate background run (`409` if already running) |
| `DELETE /api/schedules/{id}` | — | Removes schedule from SQLite and APScheduler |

## 5. Settings, Cookies, Stats & Live SSE (`settings.py`, `auth.py`, `stats.py`, `events.py`) {#system-api}

| Method & Path | Description |
| --- | --- |
| `GET /api/settings` | Returns effective `settings` (with `api_key_set: bool` instead of secret values) and `meta` (`library_root`, `hevc_encoder`, `encoders`, `editable`) |
| `PUT /api/settings` | Applies partial settings overrides to SQLite (`null` removes an override), updates transcode concurrency and scheduler timezone live |
| `GET /api/auth/cookies` | Returns per-platform cookie status (`exists`, `updated_at`, `size`, Bilibili `nickname`) and supported browser names |
| `POST /api/auth/bilibili/qr` | Generates a Bilibili login QR code (`qrcode_key`, `qr_data_url`, `expires_in: 180`) |
| `GET /api/auth/bilibili/qr/{key}` | Polls QR login status (`waiting`, `scanned`, `expired`, `success`) and saves `bilibili.txt` on success |
| `POST /api/auth/cookies/{platform}/upload` | Multipart `file` upload of Netscape `cookies.txt` (filtered by platform domain) |
| `POST /api/auth/cookies/{platform}/import` | Body `{"browser": "firefox", "profile": ""}` — imports cookies from local browser |
| `DELETE /api/auth/cookies/{platform}` | Deletes `data/cookies/{platform}.txt` |
| `GET /api/stats` | Returns video count, total disk bytes, today's intake count (in `scheduler.timezone`), platform breakdown, and 14-day intake series |
| `GET /api/events` | Server-Sent Events (`text/event-stream`) emitting `hello`, `tasks` (initial snapshot), `task` (progress updates), `log` (ring buffer of 200 entries), and `stats_dirty` |
