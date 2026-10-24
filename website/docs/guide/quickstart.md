# Quickstart

This guide walks you from a clean checkout of **VidHarbor (`v0.3.0`)** to a running web console and your first indexed MP4 video in `library/videos/`.

## 1. Choose Your Installation Route {#choose-route}

| Route | Prerequisites | Best For |
| --- | --- | --- |
| **Docker (Recommended)** | Docker Engine 24+ with Docker Compose v2 (`docker compose`) | One-command setup on Linux, macOS, or Windows (x86-64 / ARM64), including automatic Evil0ctal v5 fallback provisioning |
| **Bare Metal** | **Python 3.11+**, [uv](https://docs.astral.sh/uv/), **Node.js 18+** (with `npm`), and **ffmpeg** (with `ffprobe` on `PATH`) | Local development, direct host GPU access on macOS (`hevc_videotoolbox`) or Windows, or running without containers |

::: info Distribution Note
VidHarbor `v0.3.0` is distributed from source and builds its Docker image locally (`vidharbor:latest`) via `deploy.sh` / `deploy.ps1` or `docker compose up -d --build`.
:::

## 2. Option A: Docker One-Command Start {#docker-start}

Clone the repository and run the platform deployment script from the repository root:

```bash
git clone https://github.com/cyber-tao/VidHarbor.git
cd VidHarbor
./deploy.sh
```

On Windows PowerShell:

```powershell
git clone https://github.com/cyber-tao/VidHarbor.git
cd VidHarbor
.\deploy.ps1
```

### What the Deploy Script Does

1. Verifies Docker and Docker Compose v2.
2. Creates `.env` if missing (`PORT=8666`, `BIND_IP=0.0.0.0`, `TZ`, `GPU=auto`, `WITH_EVIL0CTAL=1`).
3. When `WITH_EVIL0CTAL=1` (default), clones [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) v5 into `tools/dtk`, starts its stack (`postgres`, `redis`, `api`, `browser`), completes its first-run setup wizard, creates a `douyin:read` + `tiktok:read` API key, and wires it into VidHarbor automatically.
   - *Want a fast, lightweight start without the ~5 GB Evil0ctal stack?* Run with `WITH_EVIL0CTAL=0`:
     ```bash
     WITH_EVIL0CTAL=0 ./deploy.sh
     ```
     or manual Compose:
     ```bash
     docker compose up -d --build
     ```
4. Builds the multi-stage VidHarbor image (Vue 3 frontend build → Python 3.12 + FFmpeg runtime) and starts the container on port `8666`.

## 3. Option B: Bare-Metal Start {#bare-metal-start}

### Windows (PowerShell)

```powershell
# 1. Install FFmpeg if not already on PATH
winget install Gyan.FFmpeg

# 2. Sync Python dependencies and build the Vue 3 frontend
cd backend
uv sync
cd ..\frontend
npm install
npm run build

# 3. Start the server (binds 127.0.0.1:8666 by default)
cd ..\backend
uv run python run.py
```

### Linux (Debian / Ubuntu)

```bash
sudo apt update && sudo apt install -y ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
cd backend && uv sync
cd ../frontend && npm install && npm run build
cd ../backend && uv run python run.py
```

### macOS

```bash
brew install ffmpeg uv node
cd backend && uv sync
cd ../frontend && npm install && npm run build
cd ../backend && uv run python run.py
```

## 4. Verify the Service & Complete Your First Task {#first-task}

1. **Check the health endpoint:**

   ```bash
   curl http://127.0.0.1:8666/api/health
   ```

   Expected JSON response:

   ```json
   {"ok":true,"version":"0.3.0"}
   ```

2. **Open the Web Console:**
   Navigate to `http://127.0.0.1:8666` in your browser.
   - Use the **Language** control (`English` / `简体中文`) and **Theme** switch (`Dark` / `Light`) in the bottom-left sidebar toolbar to customize the console appearance.

3. **Download your first video:**
   - On the **Dashboard**, locate the **Quick Download** card (or navigate to **Trending Charts** and check a Bilibili or YouTube card).
   - Paste a video URL or share text — for example:
     ```text
     https://www.bilibili.com/video/BV1GJ411x7h7
     ```
   - Click **Add to Download Queue**, keep **Use default settings** checked (or select a resolution cap such as `1080p` and codec `H.265`), and click **Start Download**.

4. **Inspect the result:**
   - On the **Download Tasks** page, watch the live SSE progress bar transition through `Downloading` → `Merging` → `Transcoding` → `Completed`.
   - Click **View** on the completed task (or open **Video Library**) to play the video in the built-in player, switch subtitle tracks, copy the absolute file path, and verify the normalized file on disk:
     ```text
     library/videos/bilibili/<uploader>/<YYYYMMDD> - <title> [BV1GJ411x7h7].mp4
     ```

![VidHarbor Dashboard in English Light theme](/screenshots/dashboard-en-light.png)

## 5. Common First-Run Troubleshooting {#troubleshooting}

- **`未找到 ffmpeg, ffprobe` warning in logs (Bare Metal):**
  Ensure both `ffmpeg` and `ffprobe` are installed and reachable on your system `PATH` (`ffmpeg -version && ffprobe -version`), then restart `uv run python run.py`.
- **`前端尚未构建` warning / 404 on `/` (Bare Metal):**
  You started the backend before building `frontend/dist`. Run `cd frontend && npm install && npm run build`, then restart the backend.
- **Bilibili 1080P+ / subtitles missing, or YouTube bot check:**
  Open **Settings → Login Management (Cookies)** in the web console to scan the Bilibili QR code or upload platform `cookies.txt`. See [Cookies & Login Management](./cookies-and-auth).
- **Cleanup / Stopping the service:**
  - Docker: `./deploy.sh down` (or `.\deploy.ps1 down` on Windows PowerShell) stops the containers while preserving `./data` and `./library`.
  - Bare Metal: Press `Ctrl+C` in the terminal running `uv run python run.py`.

## Next Steps {#next-steps}

- Configure GPU hardware transcoding, Evil0ctal v5, and token authentication in [Docker, GPU & Evil0ctal Deployment](./deployment).
- Set up platform cookies in [Cookies & Login Management](./cookies-and-auth).
- Automate recurring chart downloads in [Charts, Schedules & Batch Downloads](./charts-and-schedules).
