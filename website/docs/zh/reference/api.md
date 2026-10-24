# REST 与 SSE 接口参考

所有接口由 FastAPI 应用（`backend/app/main.py`，版本 `0.3.0`）提供。API 返回的所有时间字段均为带显式 UTC 偏移量的 ISO-8601 字符串（如 `2026-10-24T02:00:00.000+00:00`）。

## 1. 访问令牌与会话鉴权 (`backend/app/api/access.py`) {#auth-session}

当服务端配置了 `VIDHARBOR_TOKEN`（`.env` 中的 `TOKEN`）时，除 `/api/health` 与 `/api/auth/session` 外的所有 `/api/*` 请求必须携带以下任一凭证：

- 请求头：`X-Vidharbor-Token: <token>`
- 会话 Cookie：`vidharbor_session`（通过 `POST /api/auth/session` 换取）

| 方法与路径 | 是否需鉴权 | 说明 |
| --- | --- | --- |
| `GET /api/health` | 否 | 健康检查，返回 `{"ok": true, "version": "0.3.0"}` |
| `GET /api/auth/session` | 否 | 返回 `{"required": bool, "authenticated": bool}` |
| `POST /api/auth/session` | 否 | 请求体 `{"token": "..."}`，使用 `hmac.compare_digest` 校验并下发 30 天有效期的 `HttpOnly` `vidharbor_session` Cookie |
| `DELETE /api/auth/session` | 否 | 清除 `vidharbor_session` 会话 Cookie |

## 2. 下载任务接口 (`backend/app/api/tasks.py`) {#tasks-api}

| 方法与路径 | 请求体 / 查询参数 | 响应与行为说明 |
| --- | --- | --- |
| `POST /api/tasks` | `{"urls": ["..."], "options": {"max_height": 1080, "codec": "h265", "sub_langs": [...], "audio_langs": [...]}}`（`options` 可选） | 自动从粘贴文本提取 HTTP(S) 链接，与队列中活动任务（`pending` / `running`）去重，返回 `{"tasks": [...], "skipped": int}` |
| `GET /api/tasks` | `?limit=100&schedule_id=0` | 按 `id DESC` 返回任务列表 `{"tasks": [...]}` |
| `DELETE /api/tasks/{task_id}` | — | 若任务处于 `pending` 或 `running` 则发起取消（`{"canceled": true}`）；若已处于终态则删除记录（`{"deleted": true}`） |
| `POST /api/tasks/{task_id}/retry` | — | 重新排队 `failed` 或 `canceled` 任务；进行中任务返回 `400`，若同视频已有其他活动任务在队列则返回 `409` |

## 3. 视频库与标签接口 (`backend/app/api/videos.py`) {#videos-api}

| 方法与路径 | 查询参数 | 响应与行为说明 |
| --- | --- | --- |
| `GET /api/videos` | `q`、`platform`、`tag`（逗号分隔多标签 AND 过滤）、`page`（`1`）、`page_size`（`48`，上限 `200`） | 返回分页结果 `{"total": int, "page": int, "page_size": int, "items": [...]}`，预加载标签与字幕计数（无 N+1 查询，且不加载 `raw_metadata` 大字段） |
| `GET /api/videos/{video_id}` | — | 返回单条视频完整信息、绝对路径 `absolute_path`、`file_exists`、标签列表与字幕列表 |
| `GET /api/videos/{video_id}/file` | 支持 HTTP `Range` 请求头（含 `bytes=start-end` 与后缀 `bytes=-N`） | 流式返回 `.mp4` 视频文件（`206 Partial Content` / `200 OK`） |
| `GET /api/videos/{video_id}/thumbnail` | — | 返回视频缩略图文件；缺失时返回动态生成的 SVG 占位图 |
| `GET /api/videos/{video_id}/subtitles/{sub_id}` | — | 返回原始 `.srt` 字幕全文（`text/plain; charset=utf-8`） |
| `GET /api/videos/{video_id}/subtitles/{sub_id}/vtt` | — | 将 SRT 实时转换为 `text/vtt` 供浏览器 `<track>` 挂载显示 |
| `DELETE /api/videos/{video_id}` | `?delete_files=true` | 删除数据库记录并清理磁盘上的视频、缩略图与字幕文件（含 Windows 文件句柄占用重试机制） |
| `GET /api/tags` | `?platform=` | 返回按视频数量降序排列的标签聚合列表 `{"tags": [{"name": "...", "count": int}]}` |

## 4. 热门榜单与定时任务 (`charts.py`, `schedules.py`) {#charts-schedules-api}

| 方法与路径 | 参数 / 请求体 | 响应与行为说明 |
| --- | --- | --- |
| `GET /api/charts` | — | 返回支持的平台列表：`bilibili`、`youtube`、`tiktok`、`douyin` |
| `GET /api/charts/{platform}` | `?category=&period=&refresh=false&meta=false` | `meta=true` 时仅返回分类与周期定义；否则返回 30 分钟缓存或实时拉取的榜单数据（失败回退缓存时 `degraded: true`） |
| `GET /api/schedules` | — | 返回全部定时任务及 `next_run_at`、`last_run_at`、`trigger_desc`、`last_result` |
| `POST /api/schedules` | `ScheduleIn` JSON（`name`、`mode`、`at_time`、`weekdays`、`interval_minutes`、`cron`、`selections`、`options`） | 校验榜单可下载性（拒绝 `douyin/hot` 等纯话题榜），写入数据库并注册到 APScheduler |
| `PUT /api/schedules/{id}` | `ScheduleIn` JSON | 更新定时任务配置并重新注册调度器触发器 |
| `POST /api/schedules/{id}/toggle` | — | 切换启用/停用状态 |
| `POST /api/schedules/{id}/run` | — | 立即在后台线程触发一轮运行（若本轮已在运行中则返回 `409`） |
| `DELETE /api/schedules/{id}` | — | 删除定时任务并从调度器移除 |

## 5. 设置、登录管理、统计与 SSE 事件流 (`settings.py`, `auth.py`, `stats.py`, `events.py`) {#system-api}

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/settings` | 返回当前生效的 `settings`（密钥字段仅返回 `api_key_set: bool`）与系统元信息 `meta`（`library_root`、`hevc_encoder`、`encoders`、`editable`） |
| `PUT /api/settings` | 增量保存设置覆盖项（字段传 `null` 表示删除覆盖项），实时更新转码并发信号量与调度器时区 |
| `GET /api/auth/cookies` | 返回各平台 cookies 状态（`exists`、`updated_at`、`size`、B站 `nickname`）与支持的浏览器列表 |
| `POST /api/auth/bilibili/qr` | 生成 B站登录二维码（返回 `qrcode_key`、`qr_data_url`、`expires_in: 180`） |
| `GET /api/auth/bilibili/qr/{key}` | 轮询扫码状态（`waiting`、`scanned`、`expired`、`success`），成功时自动保存 `bilibili.txt` |
| `POST /api/auth/cookies/{platform}/upload` | 上传 Netscape 格式 `cookies.txt`（自动按平台域名过滤） |
| `POST /api/auth/cookies/{platform}/import` | 请求体 `{"browser": "firefox", "profile": ""}`，从本机浏览器解密导入 cookies |
| `DELETE /api/auth/cookies/{platform}` | 删除 `data/cookies/{platform}.txt` |
| `GET /api/stats` | 返回视频总数、磁盘总占用、今日新增（按 `scheduler.timezone` 本地日计算）、平台分布与近 14 天入库统计 |
| `GET /api/events` | Server-Sent Events (`text/event-stream`) 实时推送 `hello`、`tasks`（初始快照）、`task`（单任务进度）、`log`（最近 200 条日志缓冲）与 `stats_dirty` |
