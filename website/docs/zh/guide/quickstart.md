# 快速开始

本指南带你从零克隆 **VidHarbor (`v0.3.0`)**，启动 Web 控制台，并完成第一条视频的下载、MP4 规范封装与入库验证。

## 1. 选择部署方式 {#choose-route}

| 部署方式 | 环境前置要求 | 适用场景 |
| --- | --- | --- |
| **Docker 部署（推荐）** | Docker Engine 24+ 与 Docker Compose v2（`docker compose`） | Linux / macOS / Windows（x86-64 与 ARM64）一条命令启动，默认自动完成 Evil0ctal v5 兜底服务部署与接线 |
| **裸机运行** | **Python 3.11+**、[uv](https://docs.astral.sh/uv/)、**Node.js 18+**（含 `npm`）、**ffmpeg**（含 `ffprobe` 且在 `PATH` 中） | 本地开发调试、macOS 原生 `hevc_videotoolbox` 硬解硬编、或不使用容器的环境 |

::: info 分发说明
VidHarbor `v0.3.0` 通过源码仓库分发，执行 `deploy.sh` / `deploy.ps1` 或 `docker compose up -d --build` 时会在本地构建多阶段镜像（`vidharbor:latest`）。
:::

## 2. 方式 A：Docker 一键启动 {#docker-start}

克隆仓库并在项目根目录执行对应系统的部署脚本：

```bash
git clone https://github.com/cyber-tao/VidHarbor.git
cd VidHarbor
./deploy.sh
```

Windows PowerShell 环境：

```powershell
git clone https://github.com/cyber-tao/VidHarbor.git
cd VidHarbor
.\deploy.ps1
```

### 部署脚本自动完成的步骤

1. 检查 Docker 与 Docker Compose v2 环境（Linux 下缺失时可代为安装）。
2. 自动生成 `.env` 配置文件（包含 `PORT=8666`、`BIND_IP=0.0.0.0`、`TZ`、`GPU=auto`、`WITH_EVIL0CTAL=1`）。
3. 当 `WITH_EVIL0CTAL=1`（默认）时，自动克隆 [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) v5 到 `tools/dtk`，启动其容器栈（`postgres`、`redis`、`api`、`browser`），自动完成初始化向导、创建 `douyin:read` + `tiktok:read` API Key 并写入 VidHarbor 配置。
   - *如果希望跳过约 5 GB 的 Evil0ctal 兜底栈快速启动：*
     ```bash
     WITH_EVIL0CTAL=0 ./deploy.sh
     ```
     或直接使用 Compose 启动核心容器：
     ```bash
     docker compose up -d --build
     ```
4. 构建多阶段镜像（Vue 3 前端构建 → Python 3.12 + FFmpeg 运行时）并启动服务，监听 `8666` 端口。

## 3. 方式 B：裸机运行 {#bare-metal-start}

### Windows (PowerShell)

```powershell
# 1. 安装 FFmpeg（已安装可跳过）
winget install Gyan.FFmpeg

# 2. 安装后端依赖并构建 Vue 3 前端
cd backend
uv sync
cd ..\frontend
npm install
npm run build

# 3. 启动服务（默认读取 config.toml 的 [server]，监听 127.0.0.1:8666）
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

## 4. 验证服务并完成第一次下载入库 {#first-task}

1. **检查健康状态接口：**

   ```bash
   curl http://127.0.0.1:8666/api/health
   ```

   预期返回 JSON：

   ```json
   {"ok":true,"version":"0.3.0"}
   ```

2. **打开 Web 控制台：**
   浏览器访问 `http://127.0.0.1:8666`。
   - 可在左侧边栏底部工具栏随时切换 **语言（`English` / `简体中文`）** 与 **外观主题（`深色` / `浅色`）**。

3. **提交第一个下载任务：**
   - 在 **仪表盘（Dashboard）** 的 **快速下载** 输入框中粘贴视频链接或 App 分享口令（或前往 **热门榜单** 勾选任意视频卡片），例如：
     ```text
     https://www.bilibili.com/video/BV1GJ411x7h7
     ```
   - 点击 **添加到下载队列**，在弹窗中保持勾选 **使用默认设置**（或自选 `1080p`、`H.265`），点击 **开始下载**。

4. **查看入库结果：**
   - 在 **下载任务** 页实时查看进度条经历 `下载中` → `合并流` → `转码/入库` → `完成`。
   - 点击已完成任务右侧的 **查看**（或进入 **视频库**），即可在内置播放器中播放视频、切换字幕轨、一键复制存储绝对路径，并在磁盘上看到规范命名的文件：
     ```text
     library/videos/bilibili/<UP主>/<YYYYMMDD> - <标题> [BV1GJ411x7h7].mp4
     ```

![VidHarbor 中文浅色主题仪表盘实拍](/screenshots/dashboard-zh-light.png)

## 5. 首次运行常见问题排查 {#troubleshooting}

- **日志提示 `未找到 ffmpeg, ffprobe`（裸机）：**
  确认 `ffmpeg` 与 `ffprobe` 已加入系统 `PATH`（执行 `ffmpeg -version && ffprobe -version` 检查），随后重启 `uv run python run.py`。
- **日志提示 `前端尚未构建` 或访问 `/` 返回 404（裸机）：**
  请先在 `frontend/` 目录执行 `npm install && npm run build` 生成 `frontend/dist`，再启动后端。
- **B站无法下载 1080P+ / 无字幕，或 YouTube 触发登录校验：**
  进入 Web 控制台 **设置 → 登录管理（cookies）**，使用 B站扫码登录或上传对应平台的 `cookies.txt`。详见 [登录管理与 Cookies](./cookies-and-auth)。
- **停止服务与清理：**
  - Docker：执行 `./deploy.sh down`（Windows PowerShell 执行 `.\deploy.ps1 down`）即可停止容器，数据目录 `./data` 与视频库 `./library` 会保留在宿主机绑定挂载目录中。
  - 裸机：在运行 `uv run python run.py` 的终端按 `Ctrl+C` 即可优雅停止下载队列与调度器。

## 下一步 {#next-steps}

- 配置 GPU 硬件转码、Evil0ctal v5 兜底栈与访问令牌：[Docker、GPU 与兜底部署](./deployment)
- 配置各平台登录态与 Cookies：[登录管理与 Cookies](./cookies-and-auth)
- 使用多平台榜单与定时自动追更：[热门榜单、定时与批量下载](./charts-and-schedules)
