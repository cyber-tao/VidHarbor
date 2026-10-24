# Docker、GPU 与兜底服务部署

VidHarbor 提供跨平台一键部署脚本（Linux / macOS / WSL / Git Bash 使用 `deploy.sh`，Windows PowerShell 使用 `deploy.ps1`），通过组合 `docker-compose.yml` 与可选的 GPU / Evil0ctal 覆盖文件完成编排。

## 1. 部署脚本管理命令 {#subcommands}

`./deploy.sh` 与 `.\deploy.ps1` 支持相同的子命令：

| 命令 | 说明 |
| --- | --- |
| `./deploy.sh`（或 `up`） | 检查 Docker 环境、生成 `.env`、按需部署 Evil0ctal 兜底栈、构建并启动 VidHarbor |
| `./deploy.sh status` | 查看容器运行状态、端口映射以及 `./data` 和 `./library` 的磁盘占用 |
| `./deploy.sh logs` | 实时查看容器日志（`docker compose logs -f`） |
| `./deploy.sh restart` | 重启 VidHarbor 容器 |
| `./deploy.sh update` | 拉取最新 Git 提交、重新构建镜像并重启 |
| `./deploy.sh backup` | 将 `./data`（SQLite 数据库与平台 cookies）打包备份至 `./backup/` 目录 |
| `./deploy.sh down` | 停止并移除容器（含脚本托管的 `dtk` 栈），保留 `./data` 与 `./library` 数据 |
| `./deploy.sh buildx <image:tag>` | 构建并推送多架构镜像（`linux/amd64` + `linux/arm64`） |

## 2. GPU 硬件加速转码配置 {#gpu-transcoding}

在 `.env` 中设置 `GPU=` 后运行 `./deploy.sh` 或 `.\deploy.ps1`：

| `.env` 中 `GPU` 取值 | Compose 覆盖文件 | FFmpeg 编码器 | 宿主机要求 |
| --- | --- | --- | --- |
| `auto`（默认） | 自动探测选择 | `hevc_nvenc` → `hevc_qsv` → `libx265` | `nvidia-smi` 可用且 Docker 支持 nvidia runtime 时启用 NVIDIA；Linux 存在 `/dev/dri` 时启用 Intel；否则回退 CPU |
| `nvidia` | `docker-compose.gpu-nvidia.yml` | `hevc_nvenc` | NVIDIA 驱动 + `nvidia-container-toolkit`（Windows Docker Desktop ≥ 4.29 自动支持，覆盖文件已开启 `compute,utility,video` 驱动能力） |
| `intel` | `docker-compose.gpu-intel.yml` | `hevc_qsv` | Linux 宿主机 + Intel 核显（直通 `/dev/dri`） |
| `cpu` | 无 | `libx265` | 无显卡要求 |

应用启动或首次转码时，`backend/app/downloader/encoders.py` 会执行 1 帧 `640x360` 试编码（`_test_encode`），确认驱动与硬件真实可用后才会采用该编码器。

::: warning AMD 显卡说明
Docker 镜像内置的 Debian Bookworm `ffmpeg` 不包含 AMD AMF 专有编码器，容器内 AMD 显卡会回退 `libx265` CPU 转码；Windows 裸机运行若安装了完整版 `ffmpeg`，可自动探测并使用 `hevc_amf`。
:::

## 3. Evil0ctal v5 兜底引擎（抖音 / TikTok） {#evil0ctal}

目前抖音 Web 接口强制校验 `a_bogus` 签名，`yt-dlp` 直接提取抖音常被拦截。VidHarbor 集成了 [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) v5 本地部署，用于：

1. **无水印直链下载兜底：** 当 `yt-dlp` 下载抖音或 TikTok 失败时自动切换。
2. **原生接口签名（`/tools/sign`）：** 为抖音关键词视频搜索（`a_bogus`）与 TikTok 标签榜（`X-Bogus` / `X-Gnarly`）生成毫秒级签名。

### Docker 自动部署与接线（`WITH_EVIL0CTAL=1`）

默认 `WITH_EVIL0CTAL=1` 时，`./deploy.sh` / `.\deploy.ps1` 会全自动完成：

- 克隆 `Evil0ctal/Douyin_TikTok_Download_API` 到 `tools/dtk`。
- 在 `tools/dtk/.env` 生成随机密钥并启动 `postgres`、`redis`、`api`、`browser` 四个容器。
- 自动跑完首次 `/setup` 初始化向导、铸造身份、创建带 `douyin:read` + `tiktok:read` 权限的 API Key，并通过共享 Docker 网络（`http://api:8000`）自动写入 VidHarbor。

### 裸机或外部独立部署 Evil0ctal

若裸机运行 VidHarbor 或独立维护 Evil0ctal：

```bash
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git tools/dtk
cd tools/dtk
# 按 Evil0ctal 文档创建 .env 后启动含 browser 的完整栈：
COMPOSE_ENV_FILES=.env docker compose -p dtk -f docker/compose.yml \
  --profile browser up -d --build --wait
```

随后在 VidHarbor Web 控制台 **设置 → 抖音 / TikTok 兜底引擎（Evil0ctal v5）** 卡片中填入服务地址（裸机填 `http://127.0.0.1:8000`，容器访问宿主机填 `http://host.docker.internal:8000`）与 `dtk_...` API Key。

## 4. 访问控制（`TOKEN` 与 `BIND_IP`） {#access-control}

默认情况下，Docker 部署监听 `0.0.0.0:8666` 且不开启令牌校验。若部署在非完全可信的局域网或公网反向代理后，请在 `.env` 中配置：

```ini
# 除 /api/health 与 /api/auth/session 外的所有 API 均需鉴权
TOKEN=请替换为足够长的随机密钥字符串

# 可选：仅绑定本机回环地址（配合本机反向代理或 SSH 隧道使用）
BIND_IP=127.0.0.1
PORT=8666
```

### 浏览器与 API 客户端鉴权方式

- **浏览器访问：** 首次打开 `http://<host>:8666/#token=<TOKEN>`（或在弹出的访问令牌对话框中输入令牌）。`#token=...` 片段不会发送到服务器或写入访问日志；前端通过 `POST /api/auth/session` 换取 `HttpOnly`、`SameSite=Lax` 会话 Cookie（有效期 30 天），并立即从地址栏抹除令牌。
- **脚本与 API 调用：** 在请求头中携带 `X-Vidharbor-Token: <TOKEN>`（自 `v0.3.0` 起不再接受 `?token=` 查询参数，避免令牌泄露到日志）。
