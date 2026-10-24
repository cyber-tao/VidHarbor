# Docker, GPU & Evil0ctal Deployment

VidHarbor includes cross-platform deployment scripts (`deploy.sh` for Linux/macOS/WSL/Git Bash and `deploy.ps1` for Windows PowerShell) that compose `docker-compose.yml` with optional GPU and Evil0ctal fallback overrides.

## 1. Deploy Script Subcommands {#subcommands}

Both `./deploy.sh` and `.\deploy.ps1` accept the same operational subcommands:

| Command | Action |
| --- | --- |
| `./deploy.sh` (or `up`) | Check Docker, generate `.env`, provision Evil0ctal if enabled, build and start VidHarbor |
| `./deploy.sh status` | Show container health, port bindings, and disk usage of `./data` and `./library` |
| `./deploy.sh logs` | Stream live container logs (`docker compose logs -f`) |
| `./deploy.sh restart` | Restart the VidHarbor service container |
| `./deploy.sh update` | Pull latest git commits, rebuild the container image, and restart |
| `./deploy.sh backup` | Create a timestamped `.tar.gz` archive of `./data` (SQLite DB + cookies) under `./backup/` |
| `./deploy.sh down` | Stop and remove containers (`vidharbor` and `dtk` stack if managed) while keeping `./data` and `./library` |
| `./deploy.sh buildx <image:tag>` | Build and push a multi-architecture image (`linux/amd64` + `linux/arm64`) |

## 2. Hardware-Accelerated GPU Transcoding {#gpu-transcoding}

Set `GPU=` in `.env` before running `./deploy.sh` or `.\deploy.ps1`:

| `.env` `GPU` Value | Compose Override File | FFmpeg Encoder | Host Requirements |
| --- | --- | --- | --- |
| `auto` (default) | Auto-detected | `hevc_nvenc` → `hevc_qsv` → `libx265` | Uses NVIDIA runtime if `nvidia-smi` succeeds, else `/dev/dri` on Linux, else CPU |
| `nvidia` | `docker-compose.gpu-nvidia.yml` | `hevc_nvenc` | NVIDIA GPU driver + `nvidia-container-toolkit` (or Windows Docker Desktop ≥ 4.29; the compose override sets `NVIDIA_DRIVER_CAPABILITIES: compute,utility,video`) |
| `intel` | `docker-compose.gpu-intel.yml` | `hevc_qsv` | Linux host with Intel iGPU (`/dev/dri` device passthrough) |
| `cpu` | None | `libx265` | No GPU required |

At startup, `backend/app/downloader/encoders.py` runs a 1-frame `640x360` test encode (`_test_encode`) against each candidate encoder to confirm the driver is actually functional before selecting it.

::: warning AMD GPUs in Docker
The Debian Bookworm `ffmpeg` package inside the container does not bundle the proprietary AMD AMF runtime, so AMD GPUs inside Docker fall back to `libx265`. On bare-metal Windows, `hevc_amf` is probed and supported when available in your `ffmpeg` build.
:::

## 3. Evil0ctal v5 Fallback Engine (Douyin & TikTok) {#evil0ctal}

Douyin's web APIs enforce `a_bogus` request signatures that frequently block `yt-dlp`. VidHarbor integrates with a local deployment of [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) v5 for both:

1. **Watermark-free video download fallback** when `yt-dlp` fails on Douyin or TikTok URLs.
2. **Native request signing (`/tools/sign`)** for Douyin keyword video search (`a_bogus`) and TikTok hashtag charts (`X-Bogus` / `X-Gnarly`).

### Automatic Docker Provisioning (`WITH_EVIL0CTAL=1`)

When `WITH_EVIL0CTAL=1` (the default in `.env`), `./deploy.sh` / `.\deploy.ps1`:

- Clones `Evil0ctal/Douyin_TikTok_Download_API` into `tools/dtk`.
- Generates random credentials in `tools/dtk/.env` and starts its 4-container stack (`postgres`, `redis`, `api`, and `browser`).
- Automatically completes the `/setup` wizard, mints initial identities, creates a `douyin:read` + `tiktok:read` API key, and injects `EVIL0CTAL_BASE_URL=http://api:8000` + `EVIL0CTAL_API_KEY` over the shared Docker network (`docker-compose.evil0ctal.yml`).

### Bare-Metal or External Evil0ctal Instance

If you run VidHarbor bare-metal or host Evil0ctal separately:

```bash
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git tools/dtk
cd tools/dtk
# Create .env per Evil0ctal quickstart, then start with the browser profile:
COMPOSE_ENV_FILES=.env docker compose -p dtk -f docker/compose.yml \
  --profile browser up -d --build --wait
```

Then open **Settings → Douyin / TikTok Fallback Engine (Evil0ctal v5)** in the VidHarbor web console, set Base URL (`http://127.0.0.1:8000` on bare metal, or `http://host.docker.internal:8000` from Docker), and paste your `dtk_...` API key.

## 4. Access Control (`TOKEN` & `BIND_IP`) {#access-control}

By default, Docker binds `0.0.0.0:8666` with authentication disabled for local homelab convenience. When exposing VidHarbor on an untrusted LAN or reverse proxy, configure `.env`:

```ini
# Require authentication for all /api/* endpoints except /api/health and /api/auth/session
TOKEN=replace-with-a-long-random-secret

# Optional: bind only to localhost (e.g. behind a local reverse proxy or SSH tunnel)
BIND_IP=127.0.0.1
PORT=8666
```

### How Browser & API Token Authentication Works

- **Browser users:** Open `http://<host>:8666/#token=<TOKEN>` once (or type the token into the modal prompt). The URL hash fragment `#token=...` is never sent in HTTP requests or logged in server access logs; the frontend exchanges it via `POST /api/auth/session` for an `HttpOnly`, `SameSite=Lax` signed session cookie (`vidharbor_session`, 30-day max age) and strips the hash from the address bar.
- **Programmatic API clients:** Send the `X-Vidharbor-Token: <TOKEN>` request header on every API call. (`?token=` query parameters are rejected in `v0.3.0` to prevent token leakage in logs.)
