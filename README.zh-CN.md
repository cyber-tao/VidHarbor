<div align="center">

# VidHarbor · 影坞

**自托管多平台视频库，自带完整 Web 控制台。**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![yt-dlp](https://img.shields.io/badge/engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/license-TBD-gray)]()

[English](README.md) · **简体中文**

</div>

---

VidHarbor（影坞）下载 **YouTube / 哔哩哔哩 / TikTok / 抖音** 视频，统一转为 MP4
（H.265/H.264 + AAC + faststart，硬件编码优先），以规范命名存入本地视频库；元数据与
字幕全部入库（SQLite），并提供带仪表盘、热门榜单（分类×时间段）、定时任务、登录管理
（B站扫码）、设置中心、实时日志的 Web 控制台。支持 **Windows / Linux / macOS**。

```
┌─────────────────────────────────────────────────────────────────┐
│  浏览器 (Vue 3 + Tailwind + Naive UI + ECharts)                  │
│  仪表盘 · 热门榜单(分类×时间段,批量下载) · 任务 · 视频库(标签筛选)  │
│  定时任务 · 设置(登录管理/扫码) · 日志抽屉                          │
└───────────────┬──────────────────────── REST + SSE ─────────────┘
                FastAPI (uvicorn，单 worker)
        ├── 下载队列(线程池，按平台限流)
        │     ├── yt-dlp 主引擎（清晰度/字幕/音轨选项, 下载前去重, 失败自动切换）
        │     ├── 文案清洗: 分享文案提取链接 + 短链展开(v.douyin/vm.tiktok)
        │     └── Evil0ctal v5 兜底(抖音/TikTok, 无水印直链)
        ├── 后处理: ffprobe → remux(-c copy)/HEVC转码(硬件优先: NVENC/QSV/AMF/
        │   VideoToolbox) → 规范命名
        ├── 榜单服务: B站官方API(综合/三日/周榜/每周必看/入站必刷) / YouTube(官方API
        │   或过滤参数) / 抖音热搜+关键词搜索 / TikTok标签
        ├── 定时任务: APScheduler（多榜单组合, 自动跳过库中已有）
        ├── 登录管理: B站扫码登录 / 浏览器 cookies 导入 / 上传 cookies.txt
        └── SQLite(WAL): videos / subtitles / tags / tasks / charts_cache
                          / schedules / app_settings
```

## ✨ 功能

- **仪表盘**：视频总数、存储占用、今日新增、平台分布、近 14 天入库趋势、最近任务、快速粘贴下载（可选清晰度/字幕/音轨）
- **热门榜单（分类 × 时间段）**：B站（全站+8 分区，综合/三日榜/周榜 + 每周必看/入站必刷）、YouTube（今日/本周/本月 × 6 分类 + 自定义关键词）、TikTok（热门标签 + 自定义标签）、抖音（热点/种草/娱乐/社会 4 个子榜，实时）；卡片多选 → **批量下载**（下载前可选清晰度/编码/字幕/音轨语言）
- **任务页**：实时进度条（下载速度/剩余时间/阶段：下载→合并→转码→完成）、失败原因、选项徽标、取消/重试/删除；重复 URL 自动秒完成（已在库）
- **视频库**：缩略图网格、平台筛选、全文搜索、**标签聚合筛选**（多选=同时满足，来自视频标签自动聚合）；详情页内置播放器 + **字幕轨选择**、**存储绝对路径一键复制**、技术信息、字幕查看、删除；标签可点击跳转筛选
- **定时任务**：每天/每周/间隔/Cron 触发；一个任务可组合多个榜单选择（平台×分类×周期×TopN）；到点自动抓取入库，**库中已有的视频自动跳过**；支持立即运行、启停、上次结果统计
- **设置页**：下载默认（清晰度/字幕语言/音轨语言）、编码（H.265/H.264、硬件编码器探测展示）、**登录管理**（B站扫码登录；各平台浏览器导入/上传 cookies.txt）、抖音兜底、存储路径展示复制、时区
- **日志抽屉**：底部全局可折叠终端，实时滚动全部下载/转码/榜单/定时任务日志，支持暂停滚动与清空
- **统一 MP4**：目标编码 H.265（默认）时优先抓取源站 HEVC 流直接封装（免转码、`hvc1` tag），非 HEVC 源按探测到的硬件编码器（NVENC/QSV/AMF/VideoToolbox）转码，无硬件回退 `libx265 CRF24`；也可切回 H.264（remux 优先，转码 `libx264 CRF18`）；全部 `+faststart`
- **规范命名**：`library/videos/{platform}/{uploader}/{YYYYMMDD} - {title} [{id}].mp4`（模板可改，跨平台非法字符自动清洗）；字幕 SRT 与视频同目录同名存放，方便任何播放器自动加载
- **字幕入库**：手动+自动字幕（默认 `zh.* en.*`，可改），SRT 全文存数据库，前端可转 VTT 挂载到 `<track>`
- **音轨语言**：多音轨视频按语言偏好只下载一条首选音轨（如 `zh, ja, en`）
- **去重**：URL 可解析出视频 ID 时下载前直接跳过（不浪费带宽）；入库按平台+ID 唯一约束兜底

## 🚀 快速开始

前置要求：**Python 3.11+**、[uv](https://docs.astral.sh/uv/)、**Node 18+**、**ffmpeg**（含 ffprobe）。

### Windows

```powershell
# 1. ffmpeg（已装可跳过）
winget install Gyan.FFmpeg

# 2. 后端依赖 + 前端构建
cd backend; uv sync
cd ..\frontend; npm install; npm run build

# 3. 启动（读取 config.toml 的 [server]，默认 127.0.0.1:8666）
cd ..\backend
uv run python run.py
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y ffmpeg  # 或静态构建: https://johnvansickle.com/ffmpeg/
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

打开 <http://127.0.0.1:8666>。

> **定时任务注意**：调度器随应用启动，请保持**单 worker** 运行（默认 `run.py`/`uvicorn`
> 均为单 worker）；多 worker 会导致定时任务重复触发。

### 开发模式

```bash
# 后端（自动重载）
cd backend && uv run uvicorn app.main:app --reload

# 前端（Vite 开发服务器，自动代理 /api）
cd frontend && npm run dev
```

运行测试 —— 136 个 pytest 用例，覆盖命名清洗/字幕解析/榜单周期解析/格式选择器/选项
解析/编码器探测/cookies 导入/API 冒烟：

```bash
cd backend && uv run pytest
```

### 开机自启（可选）

Linux systemd（用户级服务）：

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

`systemctl --user enable --now vidharbor`。macOS 用 launchd 的 `RunAtLoad` 同理。

## ⚙️ 配置（可选）

复制 `config.example.toml` 为 `config.toml`；标注 **[Web]** 的字段也可在 Web「设置」页
修改（存数据库，优先生效）：

| 配置 | 说明 |
|---|---|
| `library.root` | 视频库根目录（默认 `<项目>/library`） |
| `library.name_template` | 命名模板，字段：`platform uploader upload_date title id` |
| `library.video_codec` [Web] | 入库目标编码 `h265`(默认)/`h264` |
| `library.hw_encoder` [Web] | HEVC 编码器 `auto`(硬件优先)/`libx265`/`hevc_nvenc` 等 |
| `download.concurrency` | 同时下载任务数（默认 2，重启生效） |
| `download.max_height` [Web] | 最高分辨率（默认 1080，0=不限） |
| `download.sub_langs` [Web] | 字幕语言（yt-dlp 正则） |
| `download.audio_langs` [Web] | 音轨语言偏好（按顺序，空=原声） |
| `download.cookies_file` | 全局兜底 cookies.txt（平台专属 cookies 见登录管理） |
| `evil0ctal.*` [Web] | 抖音/TikTok 兜底服务（地址 + API key） |
| `youtube.api_key` [Web] | YouTube Data API v3 密钥（配置后榜单优先走官方 API） |
| `youtube.region_code` [Web] | YouTube 榜单地区代码（US / JP / TW / HK 等） |
| `server.host` / `server.port` | 监听地址（默认 `127.0.0.1:8666`） |
| `scheduler.timezone` [Web] | 定时任务时区（默认 Asia/Shanghai） |

### 登录管理（cookies）

Web「设置 → 登录管理」为每个平台维护独立 cookies（`data/cookies/{platform}.txt`，优先于全局 `cookies_file`）：

- **B站**：点击「扫码登录」弹出二维码，手机 B站 App 扫码确认即自动获取登录态（每周必看榜单、1080P+、字幕需要）
- **YouTube / TikTok / 抖音**：三种方式任选
  1. **从浏览器导入**：先在本机浏览器登录对应网站，再选浏览器一键导入（服务端解密读取；Linux 需系统密钥环可用且浏览器未加主密码，Safari 仅 macOS）
  2. **上传 cookies.txt**：浏览器装 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 扩展导出后上传
  3. 打开登录页手动登录后回到 1/2

各平台为什么需要登录态：**YouTube** 高清画质/PO Token 校验、部分视频需要登录；**B站**
1080P+ 与**字幕**必须登录才能拿到；**TikTok** 标签榜需要 cookies + Evil0ctal 签名服务
（单视频下载一般不受影响）。

### 抖音 / TikTok 兜底引擎（Evil0ctal v5）

yt-dlp 的抖音支持已被 `a_bogus` 签名拦截失效（2026-10 实测），失败时自动切换本地
[Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
v5（无水印直链，TikTok 同样可兜底）：

```bash
# Docker 全栈部署（首次约 10 分钟 + 镜像构建，需 ~5GB 磁盘 / 8GB 内存）
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git tools/dtk
cd tools/dtk
# 按 documents/zh/01-quickstart.md 写 .env（DTK_SECRET_KEY / POSTGRES_PASSWORD / REDIS_PASSWORD
#   / DTK_DATABASE_URL / DTK_REDIS_URL），然后：
CLOAKBROWSER_COMMIT=fbf005bc199920b592df17ac4d489324e29d56d8 \
  docker compose -p dtk -f docker/compose.yml --profile browser up -d --build
docker compose -p dtk -f docker/compose.yml logs api   # 从日志横幅拿 /setup?token= 初始化链接
```

初始化向导（浏览器打开 setup 链接）：创建管理员 → 跳过代理 → 铸造 douyin 身份（TikTok
身份会自动补充）→ 冒烟测试。然后在控制台 `/api-keys` 创建密钥（勾选 `douyin:read` +
`tiktok:read`），填进 VidHarbor 设置页「兜底引擎」卡片。

- 服务地址默认 `http://127.0.0.1:8000`，API Key 在 VidHarbor 设置页或 `config.toml` `[evil0ctal]` 配置
- 服务未启动不影响其他平台；抖音/TikTok 任务失败时会明确提示
- 服务自身的身份池耗尽时，去其控制台 `/identities` 铸造身份或开启自动补充
- 图集作品暂不支持；分享文案（乱码+短链）粘贴即可，VidHarbor 自动提取链接并展开短链

## 📊 榜单数据源与时间段说明（2026-10 实测）

各平台时间维度不同，前端按平台动态渲染周期选项：

| 平台 | 时间段 | 数据源 | 状态 |
|---|---|---|---|
| B站 | 综合（全站+分区）/ 三日榜 / 周榜（分区）| `ranking/v2` + `ranking/region?day=3\|7`（日榜/月榜官方接口已失效）；另有「每周必看」（需扫码登录）与「入站必刷」 | ✅ 稳定 |
| YouTube | 今日 / 本周 / 本月 | 配置 API key 走官方 Data API v3；否则搜索过滤器 `sp=CAMSAggC/D/E`（热度排序+上传时间）经 yt-dlp flat 提取 | ✅ 稳定 |
| 抖音 | 实时（无周期）+ 关键词搜索 | 热搜：官方接口（子榜参数已被抖音忽略，仅单一榜单）；搜索：点击热搜词或输入关键词 → 官方搜索接口（应用内抖音 cookies + Evil0ctal `/tools/sign` 签名）返回真实视频，可勾选批量下载 | ✅ 搜索需 cookies + 签名服务 |
| TikTok | 不限（无周期）| 无公开榜单；热门/自定义标签页官方接口（应用内 TikTok cookies + Evil0ctal `/tools/sign` 原生签名 X-Bogus/X-Gnarly），返回真实视频可勾选批量下载 | ✅ 需 cookies + 签名服务 |

榜单缓存 30 分钟（按 平台+分类+周期）；拉取失败自动回退缓存并显示降级横幅，不影响其他功能。

## 📁 目录结构

```
vidlib/
├── backend/
│   ├── app/
│   │   ├── api/            # REST 接口: tasks / videos / charts / schedules /
│   │   │                   # settings / auth / events(SSE) / stats
│   │   ├── auth/           # B站扫码登录、浏览器 cookies 导入与解密
│   │   ├── charts/         # 榜单服务: bilibili / youtube / douyin / tiktok
│   │   ├── downloader/     # engine(队列) / ytdlp / evil0ctal / options /
│   │   │                   # encoders / postprocess / urlnorm
│   │   ├── scheduler.py    # APScheduler 定时下载
│   │   └── …               # config / db / models / events / logging / naming
│   ├── tests/              # 136 个 pytest 用例
│   └── run.py              # 跨平台启动入口
├── frontend/               # Vue 3 + Vite + Tailwind + Naive UI + ECharts + Pinia
├── config.example.toml     # 复制为 config.toml（git 忽略）
├── data/                   # 运行时: SQLite 数据库 / cookies / 日志（git 忽略）
├── library/                # 本地视频库（git 忽略）
└── tools/                  # Evil0ctal 兜底服务本地克隆目录（git 忽略）
```

## ❓ 常见问题

- **网页里 H.265 视频无法播放**：浏览器 HEVC 支持取决于系统/硬件（Safari 原生支持；Chrome/Edge 依赖硬件解码）。库中文件本身可用任意本地播放器（VLC/potplayer/IINA）播放；需要网页播放请把设置切到 H.264（新下载生效）
- **YouTube 下载失败/只有低清晰度**：升级 yt-dlp（`uv sync --upgrade-package yt-dlp`）+ 在登录管理导入 cookies；YouTube 反爬变化快
- **B站字幕下载不到 / 每周必看榜单打不开**：需要 B站登录态，设置页扫码登录
- **「从浏览器导入」失败**：确认浏览器已登录该网站；Linux 需密钥环可用（`secretstorage`）；加了主密码的浏览器无法解密
- **抖音任务失败且提示兜底服务不可达**：按上文启动 Evil0ctal（含浏览器容器），并在设置页确认地址与 API key
- **定时任务没跑**：确认任务「启用」、看日志抽屉与任务页（含 ⏱ 徽标的即来自定时任务）；多 worker 部署会重复触发，请单 worker
- **手动放置的文件**：直接放入 `library/videos/<平台>/<作者>/` 不会被识别，需通过任务下载入库
