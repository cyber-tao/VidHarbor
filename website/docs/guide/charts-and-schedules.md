# Trending Charts, Schedules & Batch Downloads

VidHarbor combines live multi-platform trending discovery with one-click batch downloading and APScheduler-driven recurring jobs.

![VidHarbor Trending Charts in English Dark theme](/screenshots/charts-en-dark.png)

## 1. Platform Chart Data Sources & Time Periods {#chart-sources}

Each platform exposes different ranking dimensions. The **Trending Charts** page dynamically renders category chips, period pills, and custom keyword/hashtag search boxes based on the active platform's metadata (`/api/charts/{platform}?meta=true`):

| Platform | Categories | Supported Periods | Upstream Source & Fallback Chain |
| --- | --- | --- | --- |
| **Bilibili** | `All` (`all`), 8 regions (`Anime`, `Music`, `Gaming`, `Entertainment`, `Knowledge`, `Tech`, `Movies`, `Kichiku`), plus `Weekly Must-Watch` (`weekly`) and `All-Time Classics` (`precious`) | `Overall` (`default`) for all; `3-Day` (`3d`) and `Weekly` (`week`) for the 8 regions | Official `ranking/v2`, `ranking/region?day=3\|7`, `popular/series/one` (requires Bilibili login), and `popular/precious` |
| **YouTube** | `Trending`, `Music`, `Gaming`, `Tech`, `Movies & TV`, `Podcasts`, plus custom keyword search (`custom:<keyword>`) | `Today` (`day`), `This Week` (`week`), `This Month` (`month`, default) | **Tier 1:** Official YouTube Data API v3 (`videos.list?chart=mostPopular` or `search.list` by viewCount) when `youtube.api_key` is set.<br>**Tier 2:** Login-free InnerTube `/youtubei/v1/search` filtered by relative publish time.<br>**Tier 3:** `yt-dlp` flat search extraction |
| **Douyin** | `Hot Search` (`hot`, topic list) + custom keyword video search (`custom:<keyword>`) | `Live` (`default`) | **Hot Search:** Official `aweme/v1/web/hot/search/list/` (topic items; clicking a topic drills into its video search).<br>**Video Search:** Official `aweme/v1/web/search/item/` signed via Evil0ctal `/tools/sign` + Douyin cookies |
| **TikTok** | `#funny`, `#music`, `#dance`, `#food`, `#gaming`, `#pets` + custom hashtag (`custom:<tag>`) | `All Time` (`default`) | Official `api/challenge/detail/` → `api/challenge/item_list/` (with required 19-digit `device_id`) signed via Evil0ctal `/tools/sign` + TikTok cookies |

### Caching & Graceful Degradation

Chart responses are cached in SQLite (`charts_cache`) for **30 minutes (`TTL_SECONDS = 1800`)** per `(platform, category, period)`. If an upstream request fails and a cached snapshot exists, VidHarbor serves the cached items with `degraded: true` and displays an amber warning banner in the UI instead of returning a `500` error.

## 2. Batch Download & Per-Task Options {#batch-download}

1. In **Trending Charts**, click the top-right checkbox on any downloadable video card (or click **Select All**), then click **Download Selected (N)**.
   *(Clicking the card body itself opens the original video page in a new tab; on Douyin Hot Search topic cards, clicking the card drills directly into the video search results for that topic.)*
2. In the **Download Options** dialog, either keep **Use default settings** checked or customize overrides for this batch:
   - **Max Resolution (`max_height`):** `0` (Unlimited), `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`
   - **Target Codec (`codec`):** `h265` (HEVC) or `h264` (AVC)
   - **Subtitle Languages (`sub_langs`):** Comma-separated `yt-dlp` regexes, e.g. `^zh(-CN|-Hans|-Hant|-TW|-HK)?$, ^en(-US|-GB)?$`
   - **Preferred Audio Languages (`audio_langs`):** Ordered preference list, e.g. `zh, ja, en`

## 3. Automated Scheduled Jobs (`Schedules`) {#schedules}

![VidHarbor Schedules view in Dark theme](/screenshots/schedules-en-dark.png)

A single scheduled job can combine **multiple chart selections** across platforms (`platform × category × period × TopN`) and trigger on:

- **Daily (`daily`):** Runs every day at `HH:MM` (e.g. `09:00`).
- **Weekly (`weekly`):** Runs on selected weekdays (`0 = Mon` … `6 = Sun`) at `HH:MM`.
- **Interval (`interval`):** Runs every `N` minutes (`1` to `525600`).
- **Cron (`cron`):** Standard 5-field crontab expression (e.g. `0 9 * * *`), evaluated in `scheduler.timezone` (default `Asia/Shanghai`).

### Scheduled Job Rules & Deduplication

- **Automatic deduplication:** On each run, `scheduler.py` resolves candidate IDs (`source_id_candidates`, including Bilibili `BVxxx` ↔ `BVxxx_p1` equivalence) and checks both active tasks and the `videos` table. Videos already in the library or currently queued are counted as `skipped` without creating duplicate download tasks.
- **Single-flight execution:** `claim_run(schedule_id)` ensures that if a scheduled job is already running (or triggered manually via **Run Now**), overlapping triggers are skipped (`409 Conflict` on manual trigger).
- **Douyin topic guard:** Because Douyin's `hot` list contains topics rather than direct video URLs (`downloadable: false`), the schedule editor and API (`POST /api/schedules`) reject `douyin/hot` and require a custom keyword (`custom:<keyword>`) for Douyin schedules.
