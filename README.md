# vidlib · 本地视频库

下载 YouTube / 哔哩哔哩 / TikTok / 抖音 视频，统一转为 MP4（H.264/AAC + faststart），以规范命名存入本地视频库；元数据与字幕全部入库（SQLite），并提供带仪表盘、热门榜单、批量下载、实时日志的 Web 控制台。

```
┌────────────────────────────────────────────────────────┐
│  浏览器 (Vue 3 + Tailwind + Naive UI + ECharts)         │
│  仪表盘 · 热门榜单(批量下载) · 任务进度 · 视频库 · 日志抽屉 │
└───────────────┬──────────────── REST + SSE ─────────────┘
        FastAPI (uvicorn)
        ├── 下载队列(线程池) ── yt-dlp 主引擎
        │                  └─ Evil0ctal 兜底(抖音, 自动切换)
        ├── 后处理: ffprobe → remux(-c copy)/转码(CRF18) → 规范命名
        ├── 榜单服务: B站官方API / YouTube月度热榜 / 抖音热搜 / TikTok标签
        └── SQLite(WAL): videos / subtitles / tags / tasks / charts_cache
```

## 快速开始

前置要求：Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node 18+、ffmpeg（含 ffprobe）。

```powershell
# 1. ffmpeg（已装可跳过）
winget install Gyan.FFmpeg

# 2. 后端依赖
cd backend
uv sync

# 3. 前端构建（已提交 dist 亦可跳过重新构建）
cd ../frontend
npm install
npm run build

# 4. 启动
cd ../backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8666
```

打开 <http://127.0.0.1:8666>。

开发模式：`uv run uvicorn app.main:app --reload` + 前端 `npm run dev`（自动代理 `/api`）。

测试：`cd backend && uv run pytest`（40 个用例，含命名清洗/字幕解析/榜单解析/API 冒烟）。

## 功能

- **仪表盘**：视频总数、存储占用、今日新增、平台分布、近 14 天入库趋势、最近任务、快速粘贴下载
- **热门榜单**：B站（全站+8 个分区官方排行榜）、YouTube（本月热门·按播放量，6 个分类）、TikTok（热门标签，需 cookies）、抖音（热搜榜）；卡片多选 → **批量下载**
- **任务页**：实时进度条（下载速度/剩余时间/阶段：下载→合并→转码→完成）、失败原因、取消/重试/删除
- **视频库**：缩略图网格、平台筛选、全文搜索、分页；详情页内置播放器（自动加载字幕）、技术信息、字幕查看、删除
- **日志抽屉**：底部全局可折叠终端，实时滚动全部下载/转码/榜单日志，支持暂停滚动与清空
- **统一 MP4**：优先下载 H.264 流仅做无损 remux（秒级），编码不兼容时自动转码 `libx264 CRF18 + AAC 192k`，全部 `+faststart`
- **规范命名**：`library/videos/{platform}/{uploader}/{YYYYMMDD} - {title} [{id}].mp4`（模板可在 `config.toml` 修改，Windows 非法字符自动清洗）；字幕 SRT 与视频同目录同名存放，方便任何播放器自动加载
- **字幕入库**：手动+自动字幕（默认 `zh.* en.*`），SRT 全文存数据库，前端可转 VTT 挂载到 `<track>`
- **去重**：平台+视频 ID 唯一约束，重复提交直接关联已有条目

## 配置（可选）

复制 `config.example.toml` 为 `config.toml`：

| 配置 | 说明 |
|---|---|
| `library.root` | 视频库根目录（默认 `<项目>/library`） |
| `library.name_template` | 命名模板，字段：`platform uploader upload_date title id` |
| `download.concurrency` | 同时下载任务数（默认 2） |
| `download.sub_langs` | 字幕语言（yt-dlp 正则） |
| `download.cookies_file` | Netscape 格式 cookies.txt 路径 |
| `evil0ctal.*` | 抖音兜底服务地址 |

### cookies（强烈建议配置）

- **YouTube**：高清画质/PO Token 校验、以及部分视频需要登录态
- **B站**：1080P+ 高清晰度与**字幕**（B站字幕必须登录才能拿到）
- **TikTok**：标签页榜单必须 cookies（否则榜单降级提示，单视频下载一般不受影响）

导出方法：浏览器装 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 扩展，登录对应网站后导出 Netscape 格式，保存路径填入 `download.cookies_file`。

### 抖音兜底引擎（Evil0ctal）

yt-dlp 的抖音支持常因反爬失效，失败时自动切换本地 [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)（无水印）：

```powershell
# 方式一：Docker
docker compose up -d   # 仓库自带 compose 文件，默认 8080 端口

# 方式二：源码
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git tools/Douyin_TikTok_Download_API
cd tools/Douyin_TikTok_Download_API
pip install -r requirements.txt
python run_server.py   # 默认 http://127.0.0.1:8080
```

服务未启动不影响其他平台；抖音任务失败时会明确提示。抖音图集作品暂不支持。

## 榜单数据源说明（2026-10 实测）

| 平台 | 方案 | 状态 |
|---|---|---|
| B站 | 官方排行榜 API `/x/web-interface/ranking/v2`（分区参数） | ✅ 稳定 |
| YouTube | Trending 页 2025-07 已下线；改用搜索过滤器「本月+按播放量」（`sp=CAMSBAgEEAE`）经 yt-dlp flat 提取 | ✅ 稳定 |
| 抖音 | 官方热搜接口（浏览器 UA + ttwid），返回热搜词+热度；条目不可直接下载，点击跳转抖音搜索 | ⚠️ 尽力而为 |
| TikTok | 无公开榜单；热门标签页经 yt-dlp（需 cookies） | ⚠️ 需 cookies |

榜单缓存 30 分钟；拉取失败自动回退缓存并显示降级横幅，不影响其他功能。

## 技术选型依据

- **yt-dlp**（活跃维护，2026.08+）作为 Python 库嵌入：进度钩子、info-json、字幕、缩略图一体化
- **Evil0ctal/Douyin_TikTok_Download_API**（20k★，活跃）作为抖音第二引擎，双引擎自动切换
- 已排除：BBDown（2026-05 已归档）、TikTokDownloader（核心加密算法停止维护）
- ffmpeg remux-first 策略：绝大多数视频无需转码，秒级完成且无损

## 常见问题

- **YouTube 下载失败/只有低清晰度**：升级 yt-dlp（`uv sync --upgrade-package yt-dlp`）+ 配置 cookies；YouTube 反爬变化快
- **B站字幕下载不到**：必须配置含登录态的 cookies
- **抖音任务失败且提示兜底服务不可达**：按上文启动 Evil0ctal
- **手动放置的文件**：直接放入 `library/videos/<平台>/<作者>/` 不会被识别，需通过任务下载入库
