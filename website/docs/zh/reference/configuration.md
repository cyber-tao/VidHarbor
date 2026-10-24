# 配置项完整参考

VidHarbor 的配置由三层合并而成（优先级从低到高）：

```text
config.toml  <  环境变量 (VIDHARBOR_<SECTION>__<FIELD>)  <  Web 设置页覆盖层 (SQLite app_settings)
```

在 Web **设置** 页保存时，仅会将改动过的字段写入 SQLite（`app_settings.id = 1`），未改动的字段继续实时跟随 `config.toml` 与环境变量；在 `PUT /api/settings` 中将某字段设为 `null` 可移除数据库覆盖项并回落至底层默认值。

## 1. `config.toml` 字段完整对照表 {#config-toml}

可将仓库根目录下的 `config.example.toml` 复制为 `config.toml`（或放在 `~/.vidharbor/config.toml`）。`config.toml` 为可选文件且被 Git 忽略。

| 配置键 | 类型 | 默认值 | Web 可改 | 对应环境变量 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `library.root` | `string` | `""`（`<项目>/library`） | 否 | `VIDHARBOR_LIBRARY__ROOT` | 视频库根目录路径 |
| `library.name_template` | `string` | `"{upload_date} - {title} [{id}]"` | 否 | `VIDHARBOR_LIBRARY__NAME_TEMPLATE` | `library/videos/{platform}/{uploader}/` 下的文件名模板，可用字段：`{platform}`、`{uploader}`、`{upload_date}`、`{title}`、`{id}` |
| `library.video_codec` | `"h265"` \| `"h264"` | `"h265"` | **是** | `VIDHARBOR_LIBRARY__VIDEO_CODEC` | 入库目标编码（`h265` 优先无损 remux 并补 `hvc1` tag；`h264` 优先 remux 或转码 `libx264` CRF 18） |
| `library.hw_encoder` | `string` | `"auto"` | **是** | `VIDHARBOR_LIBRARY__HW_ENCODER` | HEVC 编码器：`auto`、`libx265`、`hevc_nvenc`、`hevc_qsv`、`hevc_amf`、`hevc_videotoolbox` |
| `library.transcode_concurrency` | `int` (`1..8`) | `1` | **是** | `VIDHARBOR_LIBRARY__TRANSCODE_CONCURRENCY` | 全局同时转码任务上限（无损 remux 不占用槽位） |
| `download.concurrency` | `int` (`1..8`) | `2` | **是** | `VIDHARBOR_DOWNLOAD__CONCURRENCY` | 跨平台全局同时下载任务数上限 |
| `download.per_platform_concurrency` | `int` (`1..8`) | `2` | **是** | `VIDHARBOR_DOWNLOAD__PER_PLATFORM_CONCURRENCY` | 单一平台同时下载任务数上限 |
| `download.sub_langs` | `list[str]` | `["^zh(-CN\|-Hans\|-Hant\|-TW\|-HK)?$", "^en(-US\|-GB)?$"]` | **是** | `VIDHARBOR_DOWNLOAD__SUB_LANGS` | `yt-dlp` 字幕语言正则列表（同时抓取手动与自动字幕） |
| `download.max_height` | `int` (`0..4320`) | `1080` | **是** | `VIDHARBOR_DOWNLOAD__MAX_HEIGHT` | 最高垂直分辨率（`0` = 不限制） |
| `download.audio_langs` | `list[str]` | `[]` | **是** | `VIDHARBOR_DOWNLOAD__AUDIO_LANGS` | 多音轨视频的语言优先级列表（如 `["zh", "ja", "en"]`）；空列表表示下载默认原声音轨 |
| `download.cookies_file` | `string` | `""` | 否（服务端路径） | `VIDHARBOR_DOWNLOAD__COOKIES_FILE` | 全局兜底 Netscape `cookies.txt` 服务端路径（优先级低于 `data/cookies/{platform}.txt`） |
| `download.proxy` | `string` | `""` | **是** | `VIDHARBOR_DOWNLOAD__PROXY` | 出口代理地址（`http://host:port` 或 `socks5://host:port`） |
| `download.proxy_platforms` | `list[str]` | `[]` | **是** | `VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS` | 走出口代理的平台列表（`bilibili` / `youtube` / `tiktok` / `douyin`） |
| `evil0ctal.enabled` | `bool` | `true` | **是** | `VIDHARBOR_EVIL0CTAL__ENABLED` | 是否启用抖音/TikTok Evil0ctal v5 兜底与签名服务 |
| `evil0ctal.base_url` | `string` | `"http://127.0.0.1:8000"` | **是** | `VIDHARBOR_EVIL0CTAL__BASE_URL` | Evil0ctal v5 服务地址（Docker 共享网络下为 `http://api:8000`） |
| `evil0ctal.api_key` | `string` | `""` | **是（只写不读）** | `VIDHARBOR_EVIL0CTAL__API_KEY` | Evil0ctal v5 API Key（需 `douyin:read` + `tiktok:read`），`GET /api/settings` 仅返回 `api_key_set` |
| `youtube.api_key` | `string` | `""` | **是（只写不读）** | `VIDHARBOR_YOUTUBE__API_KEY` | YouTube Data API v3 密钥，`GET /api/settings` 仅返回 `api_key_set` |
| `youtube.region_code` | `string` | `"US"` | **是** | `VIDHARBOR_YOUTUBE__REGION_CODE` | YouTube 热门榜地区代码（如 `US`、`JP`、`TW`、`HK`） |
| `server.host` | `string` | `"127.0.0.1"` | 否 | `VIDHARBOR_SERVER__HOST` | 裸机 `python run.py` 监听地址（Docker 容器内固定绑定 `0.0.0.0:8666`） |
| `server.port` | `int` | `8666` | 否 | `VIDHARBOR_SERVER__PORT` | 裸机 `python run.py` 监听端口 |
| `scheduler.timezone` | `string` | `"Asia/Shanghai"` | **是** | `VIDHARBOR_SCHEDULER__TIMEZONE` | APScheduler 定时触发与仪表盘「今日新增」边界使用的 IANA 时区名 |

## 2. Docker `.env` 部署变量参考 {#docker-env}

使用 `./deploy.sh`、`.\deploy.ps1` 或 `docker compose` 部署时，根目录 `.env` 控制宿主机端口、GPU 与兜底栈编排：

| `.env` 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8666` | 映射到容器 `8666` 的宿主机端口 |
| `BIND_IP` | `0.0.0.0` | 宿主机监听网卡 IP（仅本机访问可设为 `127.0.0.1`） |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `TOKEN` | *(空)* | 可选访问令牌，注入为容器内 `VIDHARBOR_TOKEN` |
| `GPU` | `auto` | 硬件转码模式（`auto`、`nvidia`、`intel`、`cpu`） |
| `WITH_EVIL0CTAL` | `1` | `1` 自动部署并接线 Evil0ctal v5 兜底栈；`0` 跳过 |
| `EVIL0CTAL_BASE_URL` | 独立运行默认 `http://host.docker.internal:8000`；脚本联动为 `http://api:8000` | 注入为 `VIDHARBOR_EVIL0CTAL__BASE_URL` |
| `EVIL0CTAL_API_KEY` | `WITH_EVIL0CTAL=1` 时自动生成 | 注入为 `VIDHARBOR_EVIL0CTAL__API_KEY` |
| `PROXY` | *(空)* | 注入为 `VIDHARBOR_DOWNLOAD__PROXY` |
| `PROXY_PLATFORMS` | *(空)* | JSON 数组字符串（如 `["youtube","tiktok"]`），注入为 `VIDHARBOR_DOWNLOAD__PROXY_PLATFORMS` |
