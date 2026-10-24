# Configuration Reference

VidHarbor merges configuration from three layers (lowest to highest priority):

```text
config.toml  <  Environment Variables (VIDHARBOR_<SECTION>__<FIELD>)  <  Web Settings UI (SQLite app_settings)
```

Fields modified in the **Settings** page are stored in SQLite (`app_settings.id = 1`); unmodified fields continue to follow `config.toml` and environment variables dynamically. Sending `null` for a field in `PUT /api/settings` removes the database override and reverts that field to `config.toml` / environment variables.

## 1. Complete `config.toml` Reference {#config-toml}

Copy `config.example.toml` to `config.toml` in the repository root (or `~/.vidharbor/config.toml`). `config.toml` is optional and git-ignored.

| Key | Type | Default | Web Editable | Env Override Variable | Description |
| --- | --- | --- | --- | --- | --- |
| `library.root` | `string` | `""` (`<repo>/library`) | No | `VIDHARBOR_LIBRARY__ROOT` | Absolute or relative path to the video library directory |
| `library.name_template` | `string` | `"{upload_date} - {title} [{id}]"` | No | `VIDHARBOR_LIBRARY__NAME_TEMPLATE` | Filename template under `library/videos/{platform}/{uploader}/`. Tokens: `{platform}`, `{uploader}`, `{upload_date}`, `{title}`, `{id}` |
| `library.video_codec` | `"h265"` \| `"h264"` | `"h265"` | **Yes** | `VIDHARBOR_LIBRARY__VIDEO_CODEC` | Target MP4 video codec (`h265` remuxes HEVC or encodes with `hvc1` tag; `h264` remuxes AVC or encodes `libx264` CRF 18) |
| `library.hw_encoder` | `string` | `"auto"` | **Yes** | `VIDHARBOR_LIBRARY__HW_ENCODER` | HEVC encoder: `auto`, `libx265`, `hevc_nvenc`, `hevc_qsv`, `hevc_amf`, `hevc_videotoolbox` |
| `library.transcode_concurrency` | `int` (`1..8`) | `1` | **Yes** | `VIDHARBOR_LIBRARY__TRANSCODE_CONCURRENCY` | Max simultaneous FFmpeg transcodes (lossless remuxing does not consume a slot) |
| `download.concurrency` | `int` (`1..8`) | `2` | **Yes** | `VIDHARBOR_DOWNLOAD__CONCURRENCY` | Global simultaneous download tasks across all platforms |
| `download.per_platform_concurrency` | `int` (`1..8`) | `2` | **Yes** | `VIDHARBOR_DOWNLOAD__PER_PLATFORM_CONCURRENCY` | Max simultaneous downloads for any single platform |
| `download.sub_langs` | `list[str]` | `["^zh(-CN\|-Hans\|-Hant\|-TW\|-HK)?$", "^en(-US\|-GB)?$"]` | **Yes** | `VIDHARBOR_DOWNLOAD__SUB_LANGS` | `yt-dlp` subtitle language regexes (fetches both manual and auto-generated captions) |
| `download.max_height` | `int` (`0..4320`) | `1080` | **Yes** | `VIDHARBOR_DOWNLOAD__MAX_HEIGHT` | Maximum vertical resolution in pixels (`0` = unlimited) |
| `download.audio_langs` | `list[str]` | `[]` | **Yes** | `VIDHARBOR_DOWNLOAD__AUDIO_LANGS` | Ordered preferred audio track language prefixes (e.g. `["zh", "ja", "en"]`); empty = default/original audio |
| `download.cookies_file` | `string` | `""` | No (server path) | `VIDHARBOR_DOWNLOAD__COOKIES_FILE` | Global fallback Netscape `cookies.txt` path on the server (per-platform `data/cookies/{platform}.txt` takes priority) |
| `download.proxy` | `string` | `""` | **Yes** | `VIDHARBOR_DOWNLOAD__PROXY` | Egress proxy URL (`http://host:port` or `socks5://host:port`) |
| `download.proxy_platforms` | `list[str]` | `[]` | **Yes** | `VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS` | Subset of `["bilibili", "youtube", "tiktok", "douyin"]` routed through `download.proxy` |
| `evil0ctal.enabled` | `bool` | `true` | **Yes** | `VIDHARBOR_EVIL0CTAL__ENABLED` | Enable Evil0ctal v5 fallback for Douyin/TikTok downloads and chart signing |
| `evil0ctal.base_url` | `string` | `"http://127.0.0.1:8000"` | **Yes** | `VIDHARBOR_EVIL0CTAL__BASE_URL` | Base URL of the Evil0ctal v5 service (`http://api:8000` on shared Docker network) |
| `evil0ctal.api_key` | `string` | `""` | **Yes (write-only)** | `VIDHARBOR_EVIL0CTAL__API_KEY` | Evil0ctal v5 API key (`douyin:read` + `tiktok:read`). Never echoed back by `GET /api/settings` |
| `youtube.api_key` | `string` | `""` | **Yes (write-only)** | `VIDHARBOR_YOUTUBE__API_KEY` | YouTube Data API v3 key. Never echoed back by `GET /api/settings` |
| `youtube.region_code` | `string` | `"US"` | **Yes** | `VIDHARBOR_YOUTUBE__REGION_CODE` | ISO 3166-1 alpha-2 region code for YouTube trending charts |
| `server.host` | `string` | `"127.0.0.1"` | No | `VIDHARBOR_SERVER__HOST` | Bind address for bare-metal `python run.py` (Docker always binds `0.0.0.0:8666` inside container) |
| `server.port` | `int` | `8666` | No | `VIDHARBOR_SERVER__PORT` | Bind port for bare-metal `python run.py` |
| `scheduler.timezone` | `string` | `"Asia/Shanghai"` | **Yes** | `VIDHARBOR_SCHEDULER__TIMEZONE` | IANA timezone name used for APScheduler triggers and daily intake statistics |

## 2. Docker `.env` Deployment Variables {#docker-env}

When using `./deploy.sh`, `.\deploy.ps1`, or `docker compose`, the root `.env` file controls container port bindings and service composition:

| `.env` Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8666` | Host port mapped to container port `8666` |
| `BIND_IP` | `0.0.0.0` | Host interface IP (`127.0.0.1` for localhost-only) |
| `TZ` | `Asia/Shanghai` | Container timezone |
| `TOKEN` | *(empty)* | Optional access token mapped to `VIDHARBOR_TOKEN` |
| `GPU` | `auto` | Hardware transcoding mode (`auto`, `nvidia`, `intel`, `cpu`) |
| `WITH_EVIL0CTAL` | `1` | `1` deploys and wires the Evil0ctal v5 stack; `0` skips it |
| `EVIL0CTAL_BASE_URL` | `http://host.docker.internal:8000` (standalone) or `http://api:8000` (with `WITH_EVIL0CTAL=1`) | Mapped to `VIDHARBOR_EVIL0CTAL__BASE_URL` |
| `EVIL0CTAL_API_KEY` | Auto-generated when `WITH_EVIL0CTAL=1` | Mapped to `VIDHARBOR_EVIL0CTAL__API_KEY` |
| `PROXY` | *(empty)* | Mapped to `VIDHARBOR_DOWNLOAD__PROXY` |
| `PROXY_PLATFORMS` | *(empty)* | JSON array string (e.g. `["youtube","tiktok"]`) mapped to `VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS` |
