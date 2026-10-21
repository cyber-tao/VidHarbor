<div align="center">

# VidHarbor · 影坞

**A self-hosted, multi-platform video library with a full web console.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![yt-dlp](https://img.shields.io/badge/engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/license-TBD-gray)]()

**English** · [简体中文](README.zh-CN.md)

</div>

---

VidHarbor downloads videos from **YouTube / Bilibili / TikTok / Douyin**, normalizes everything
to MP4 (H.265/H.264 + AAC + faststart, hardware encoding first), stores them in a tidy local
library with consistent naming, and indexes all metadata & subtitles in SQLite. A built-in web
console provides a dashboard, trending charts (category × time period), scheduled jobs, login
management (Bilibili QR), a settings center, and live streaming logs.

Runs on **Windows / Linux / macOS**.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Vue 3 + Tailwind + Naive UI + ECharts)                │
│  Dashboard · Charts (category × period, batch download)         │
│  Tasks · Library (tag filtering) · Schedules · Settings · Logs  │
└───────────────┬──────────────────────── REST + SSE ─────────────┘
                FastAPI (uvicorn, single worker)
        ├── Download queue (thread pool, per-platform caps)
        │     ├── yt-dlp primary engine (quality / subtitles / audio-track options,
        │     │   pre-download dedup, auto-switch on failure)
        │     ├── Share-text cleaning: link extraction + short-link expansion
        │     │   (v.douyin / vm.tiktok)
        │     └── Evil0ctal v5 fallback (Douyin / TikTok)
        ├── Post-processing: ffprobe → remux (-c copy) / HEVC transcode
        │   (hardware first: NVENC/QSV/AMF/VideoToolbox) → normalized naming
        ├── Chart providers: Bilibili official API / YouTube (official or filter-based)
        │   / Douyin hot-search + keyword search / TikTok hashtag
        ├── Scheduler: APScheduler (multi-chart combos, skip items already in library)
        ├── Login management: Bilibili QR / browser-cookie import / cookies.txt upload
        └── SQLite (WAL): videos / subtitles / tags / tasks / charts_cache
                           / schedules / app_settings
```

## ✨ Features

- **Dashboard** — total videos, disk usage, new-today, platform distribution, 14-day intake
  trend, recent tasks, quick paste-to-download (with quality / subtitle / audio-track options)
- **Trending charts (category × period)** — Bilibili (site-wide + 8 categories, composite /
  3-day / weekly + must-watch lists), YouTube (today / week / month × 6 categories + keyword
  search), TikTok (hashtags), Douyin (hot / seeds / entertainment / society sub-charts);
  multi-select cards → **batch download**
- **Tasks page** — live progress bars (speed / ETA / stage: download → merge → transcode →
  done), failure reasons, option badges, cancel / retry / delete; duplicate URLs complete
  instantly if already in library
- **Library** — thumbnail grid, platform filter, full-text search, **tag aggregation filter**;
  detail page with built-in player + subtitle-track selection, one-click copy of the absolute
  file path, technical info, subtitle viewer; clickable tags
- **Schedules** — daily / weekly / interval / cron triggers; one job can combine multiple chart
  selections (platform × category × period × TopN); items already in library are skipped
  automatically; run-now, enable/disable, last-run stats
- **Settings** — download defaults (quality / subtitle languages / audio-track languages),
  encoding (H.265/H.264, hardware-encoder detection display), **login management** (Bilibili
  QR code; browser import / cookies.txt upload per platform), Douyin fallback engine, storage
  path, timezone
- **Live log drawer** — collapsible terminal at the bottom streaming all download / transcode /
  chart / schedule logs in real time, with pause & clear
- **Unified MP4** — with H.265 (default), remux the source HEVC stream directly when available
  (no transcode, `hvc1` tag); otherwise transcode via the best detected hardware encoder, or
  fall back to `libx265 CRF24`; switchable to H.264 (remux-first, `libx264 CRF18`); all with
  `+faststart`
- **Consistent naming** — `library/videos/{platform}/{uploader}/{YYYYMMDD} - {title} [{id}].mp4`
  (template configurable, illegal characters sanitized per platform); subtitle SRTs sit next to
  the video with the same name so any player auto-loads them
- **Subtitles in DB** — manual + auto subs (default `zh.* en.*`, configurable), full SRT text
  stored in SQLite, served to the browser as VTT `<track>`
- **Audio-track selection** — multi-audio videos download only one preferred track by language
  (e.g. `zh, ja, en`)
- **Deduplication** — resolvable video IDs are skipped *before* download (no wasted bandwidth);
  a platform+ID unique constraint backstops the library

## 🚀 Quick Start

Requirements: **Python 3.11+**, [uv](https://docs.astral.sh/uv/), **Node 18+**, and
**ffmpeg** (with ffprobe).

### Windows

```powershell
# 1. ffmpeg (skip if already installed)
winget install Gyan.FFmpeg

# 2. Backend deps + frontend build
cd backend; uv sync
cd ..\frontend; npm install; npm run build

# 3. Run (reads [server] from config.toml, default 127.0.0.1:8666)
cd ..\backend
uv run python run.py
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y ffmpeg  # or a static build: https://johnvansickle.com/ffmpeg/
curl -LsSf https://astral.sh/uv/install.sh | sh
cd vidlib/backend && uv sync
cd ../frontend && npm install && npm run build
cd ../backend && uv run python run.py
```

### macOS

```bash
brew install ffmpeg uv
cd vidlib/backend && uv sync
cd ../frontend && npm install && npm run build
cd ../backend && uv run python run.py
```

Then open <http://127.0.0.1:8666>.

> **Scheduler note**: the scheduler starts with the app — keep it to a **single worker**
> (the default for both `run.py` and `uvicorn`); multiple workers will trigger scheduled
> jobs more than once.

### Development

```bash
# backend (auto-reload)
cd backend && uv run uvicorn app.main:app --reload

# frontend (Vite dev server, /api proxied automatically)
cd frontend && npm run dev
```

Run tests — 136 pytest cases covering naming sanitization, subtitle parsing, chart period
parsing, format selectors, option resolution, encoder detection, cookie import and API
smoke tests:

```bash
cd backend && uv run pytest
```

### Autostart (optional)

Linux systemd (user unit):

```ini
# ~/.config/systemd/user/vidharbor.service
[Unit]
Description=VidHarbor
After=network.target

[Service]
WorkingDirectory=%h/vidlib/backend
ExecStart=%h/.local/bin/uv run python run.py
Restart=on-failure

[Install]
WantedBy=default.target
```

`systemctl --user enable --now vidharbor`. On macOS use launchd's `RunAtLoad` the same way.

## ⚙️ Configuration (Optional)

Copy `config.example.toml` to `config.toml`. Fields marked **[Web]** can also be changed in
the web **Settings** page (stored in the database, takes priority):

| Option | Description |
|---|---|
| `library.root` | Library root directory (default `<repo>/library`) |
| `library.name_template` | Filename template: `platform uploader upload_date title id` |
| `library.video_codec` [Web] | Target codec `h265` (default) / `h264` |
| `library.hw_encoder` [Web] | HEVC encoder `auto` (hardware first) / `libx265` / `hevc_nvenc` … |
| `download.concurrency` | Concurrent downloads (default 2, restart to apply) |
| `download.max_height` [Web] | Max resolution (default 1080, 0 = unlimited) |
| `download.sub_langs` [Web] | Subtitle languages (yt-dlp regex) |
| `download.audio_langs` [Web] | Audio-track language preference (ordered; empty = original) |
| `download.cookies_file` | Global fallback cookies.txt (per-platform cookies → Login Management) |
| `evil0ctal.*` [Web] | Douyin/TikTok fallback engine (base URL + API key) |
| `youtube.api_key` [Web] | YouTube Data API v3 key — enables official trending charts |
| `youtube.region_code` [Web] | Region for YouTube charts (US / JP / TW / HK …) |
| `server.host` / `server.port` | Bind address (default `127.0.0.1:8666`) |
| `scheduler.timezone` [Web] | Schedule timezone (default Asia/Shanghai) |

### Login Management (cookies)

The web **Settings → Login Management** page maintains independent cookies per platform
(`data/cookies/{platform}.txt`, takes priority over the global `cookies_file`):

- **Bilibili**: click *QR Login*, scan with the Bilibili mobile app — done. Required for the
  must-watch charts, 1080P+ and subtitles.
- **YouTube / TikTok / Douyin** — any of:
  1. **Import from browser**: log in to the site in a local browser first, then one-click
     import (server-side decryption; on Linux the system keyring must be available and the
     browser must not use a master password; Safari on macOS only)
  2. **Upload cookies.txt**: export with the
     [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
     extension, then upload
  3. Log in manually in the opened page, then return to 1/2

Why each platform wants cookies: YouTube — HD quality / PO-token checks, some videos require
login; Bilibili — 1080P+ and subtitles require login; TikTok — hashtag charts need cookies +
the Evil0ctal signing service (single-video downloads usually unaffected).

### Douyin / TikTok Fallback Engine (Evil0ctal v5)

yt-dlp's Douyin support is currently blocked by the `a_bogus` signature requirement (verified
2026-10). On failure VidHarbor automatically switches to a local deployment of
[Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
v5 (watermark-free direct links; also backs up TikTok):

```bash
# Full docker-compose stack (first run ~10 min build, ~5 GB disk / 8 GB RAM)
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git tools/dtk
cd tools/dtk
# Write .env per documents/zh/01-quickstart.md (DTK_SECRET_KEY / POSTGRES_PASSWORD /
#   REDIS_PASSWORD / DTK_DATABASE_URL / DTK_REDIS_URL), then:
CLOAKBROWSER_COMMIT=fbf005bc199920b592df17ac4d489324e29d56d8 \
  docker compose -p dtk -f docker/compose.yml --profile browser up -d --build
docker compose -p dtk -f docker/compose.yml logs api   # grab /setup?token= from the banner
```

Setup wizard (open the setup link in a browser): create admin → skip proxy → mint a *douyin*
identity (TikTok is auto-added) → smoke test. Then create an API key in the console under
`/api-keys` (check `douyin:read` + `tiktok:read`) and paste it into VidHarbor's Settings page,
*Fallback Engine* card.

- Default base URL `http://127.0.0.1:8000`; configure URL + key in Settings or `config.toml` `[evil0ctal]`
- Other platforms are unaffected if the service is down; Douyin/TikTok tasks fail with a clear message
- If the service's identity pool runs dry, mint identities in its console (`/identities`) or enable auto-replenish
- Photo posts are not supported; paste share text (garbled + short links) directly — VidHarbor extracts and expands the links

## 📊 Chart Data Sources (verified 2026-10)

Each platform exposes different time dimensions; period options are rendered per platform:

| Platform | Periods | Source | Status |
|---|---|---|---|
| Bilibili | Composite (site + category) / 3-day / weekly (category) | `ranking/v2` + `ranking/region?day=3\|7` (official daily/monthly endpoints are dead); plus *Must-Watch Weekly* (needs QR login) and *Classics* | ✅ stable |
| YouTube | Today / week / month | With API key: official Data API v3; otherwise search filters `sp=CAMSAggC/D/E` (sort by view count + upload date) via yt-dlp flat extraction | ✅ stable |
| Douyin | Real-time (no period) + keyword search | Hot search: official API (sub-chart params are ignored by Douyin, single list only); search: hot words or custom keywords → official search API (in-app cookies + Evil0ctal `/tools/sign`), returns real videos, selectable for batch download | ✅ search needs cookies + signing service |
| TikTok | Any time (no period) | No public charts; hashtag pages via official API (in-app cookies + Evil0ctal `/tools/sign` native X-Bogus/X-Gnarly signatures), returns real videos selectable for download | ✅ needs cookies + signing service |

Charts are cached 30 minutes (per platform + category + period); on fetch failure VidHarbor
falls back to the cache and shows a degradation banner without affecting anything else.

## 📁 Project Structure

```
vidlib/
├── backend/
│   ├── app/
│   │   ├── api/            # REST endpoints: tasks, videos, charts, schedules,
│   │   │                   # settings, auth, events (SSE), stats
│   │   ├── auth/           # Bilibili QR login, browser-cookie import & decryption
│   │   ├── charts/         # chart providers: bilibili, youtube, douyin, tiktok
│   │   ├── downloader/     # engine (queue), ytdlp, evil0ctal, options,
│   │   │                   # encoders, postprocess, urlnorm
│   │   ├── scheduler.py    # APScheduler-driven scheduled downloads
│   │   └── …               # config, db, models, events, logging, naming
│   ├── tests/              # 136 pytest cases
│   └── run.py              # cross-platform entry point
├── frontend/               # Vue 3 + Vite + Tailwind + Naive UI + ECharts + Pinia
├── config.example.toml     # copy to config.toml (git-ignored)
├── data/                   # runtime: SQLite DB, cookies, logs (git-ignored)
├── library/                # your video library (git-ignored)
└── tools/                  # local Evil0ctal fallback clone (git-ignored)
```

## ❓ FAQ

- **H.265 videos won't play in the browser** — browser HEVC support depends on system/hardware
  (Safari is native; Chrome/Edge need hardware decoding). The files themselves play fine in any
  local player (VLC/potplayer/IINA); switch Settings to H.264 for in-browser playback (applies
  to new downloads).
- **YouTube downloads fail / only low resolutions** — upgrade yt-dlp
  (`uv sync --upgrade-package yt-dlp`) and import cookies in Login Management; YouTube's
  anti-bot measures change frequently.
- **Bilibili subtitles missing / must-watch charts won't load** — they require a Bilibili
  login; use QR login in Settings.
- **"Import from browser" fails** — make sure the browser is actually logged in to the site;
  on Linux the keyring must be available (`secretstorage`); master-password-protected browsers
  cannot be decrypted.
- **Douyin tasks fail with "fallback service unreachable"** — start Evil0ctal as described
  above (including the browser container) and verify the URL and API key in Settings.
- **Scheduled jobs didn't run** — check the job is *enabled*, see the log drawer and the Tasks
  page (⏱ badge = from a schedule); multi-worker deployments trigger duplicates — use one worker.
- **Manually placed files** — files dropped into `library/videos/<platform>/<uploader>/`
  directly are not recognized; download via tasks to enter the library.
