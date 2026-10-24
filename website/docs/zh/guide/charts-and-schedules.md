# 热门榜单、定时任务与批量下载

VidHarbor 将四平台热门榜单浏览、多选批量下载与 APScheduler 定时自动追更融为一体。

![VidHarbor 热门榜单英文深色模式实拍](/screenshots/charts-en-dark.png)

## 1. 四平台榜单数据源与时间周期 {#chart-sources}

不同平台开放的排行维度不同，**热门榜单** 页面会根据后端元数据接口（`/api/charts/{platform}?meta=true`）动态渲染分类标签、时间周期按钮与自定义搜索框：

| 平台 | 分类 | 支持的时间周期 | 数据源与多级降级链路 |
| --- | --- | --- | --- |
| **哔哩哔哩 (`bilibili`)** | `全站` (`all`)、8 个分区（`动画`、`音乐`、`游戏`、`娱乐`、`知识`、`科技`、`电影`、`鬼畜`），以及 `每周必看` (`weekly`)、`入站必刷` (`precious`) | 全站/必看/必刷为 `综合` (`default`)；8 个分区支持 `综合`、`三日榜` (`3d`)、`周榜` (`week`) | 官方 `ranking/v2`、`ranking/region?day=3\|7`、`popular/series/one`（需扫码登录）与 `popular/precious` |
| **YouTube (`youtube`)** | `热门`、`音乐`、`游戏`、`科技`、`影视`、`播客`，以及自定义关键词（`custom:<词>`） | `今日` (`day`)、`本周` (`week`)、`本月` (`month`，默认) | **第一级：** 配置 `youtube.api_key` 后走官方 Data API v3（`videos.list?chart=mostPopular` 或按播放量排序的 `search.list`）。<br>**第二级：** 免登录 InnerTube `/youtubei/v1/search` 并按相对发布时间过滤周期。<br>**第三级：** `yt-dlp` 搜索页 flat 提取 |
| **抖音 (`douyin`)** | `热搜榜` (`hot`，话题榜) + 自定义关键词视频搜索 (`custom:<词>`) | `实时` (`default`) | **热搜榜：** 官方 `aweme/v1/web/hot/search/list/`（返回热搜话题，点击卡片自动钻取该词的视频结果）。<br>**关键词视频搜索：** 应用内抖音 cookies + Evil0ctal `/tools/sign` 签名请求官方 `search/item` 接口 |
| **TikTok (`tiktok`)** | `#funny`、`#music`、`#dance`、`#food`、`#gaming`、`#pets` + 自定义标签 (`custom:<tag>`) | `不限` (`default`) | 应用内 TikTok cookies + Evil0ctal `/tools/sign` 原生签名请求 `api/challenge/detail/` 与 `api/challenge/item_list/`（自动携带必填的 19 位随机 `device_id`） |

### 30 分钟缓存与失败优雅降级

每个 `(platform, category, period)` 组合拉取成功后会在 SQLite `charts_cache` 表中缓存 **30 分钟（`TTL_SECONDS = 1800`）**。当上游接口波动或限流时，若存在历史缓存，API 会返回缓存数据并标记 `degraded: true`，前端顶部展示琥珀色降级提示横幅，不会中断页面使用。

## 2. 批量选择下载与单次下载选项 {#batch-download}

1. 在 **热门榜单** 页勾选可下载视频卡片右上角的复选框（或点击 **全选**），然后点击右上角 **下载所选 (N)**。
   *（直接点击视频卡片空白处会在新标签页打开源视频网页；点击抖音热搜话题卡片则会原地钻取该话题下的可下载视频列表。）*
2. 在弹出的 **下载选项** 窗口中，可保持勾选 **使用默认设置**，也可针对本次任务单独指定：
   - **最高清晰度（`max_height`）：** `0`（最佳/不限）、`2160p`、`1440p`、`1080p`、`720p`、`480p`、`360p`
   - **目标编码（`codec`）：** `h265`（HEVC，省空间）或 `h264`（兼容性最好）
   - **字幕语言（`sub_langs`）：** 逗号分隔的 `yt-dlp` 正则，如 `^zh(-CN|-Hans|-Hant|-TW|-HK)?$, ^en(-US|-GB)?$`
   - **音轨语言偏好（`audio_langs`）：** 按优先级排列的语言代码，如 `zh, ja, en`

## 3. 定时任务（`Schedules`）自动追更 {#schedules}

![VidHarbor 定时任务页面实拍](/screenshots/schedules-en-dark.png)

一个定时任务可以组合 **多个不同平台的榜单选择**（`平台 × 分类 × 周期 × TopN`），支持四种触发模式：

- **每天（`daily`）：** 每天在指定 `HH:MM`（如 `09:00`）运行。
- **每周（`weekly`）：** 在勾选的星期列表（`0 = 周一` … `6 = 周日`）的 `HH:MM` 运行。
- **间隔（`interval`）：** 每隔 `N` 分钟（`1`–`525600`）运行一次。
- **Cron（`cron`）：** 标准 5 段式 Cron 表达式（如 `0 9 * * *`），按 `scheduler.timezone`（默认 `Asia/Shanghai`）解析时区。

### 定时任务去重与防重入机制

- **自动跳过已在库/队列视频：** 每次触发时，`scheduler.py` 会计算候选视频 ID（含 B站 `BVxxx` 与 `BVxxx_p1` 等价识别），同时比对活动队列与 `videos` 表；已存在的条目直接计入 `跳过（skipped）`，绝不重复发起下载。
- **单轮互斥保护：** `claim_run(schedule_id)` 保证同一定时任务同一时刻只运行一轮；若上一轮尚未结束，定时触发或手动点击 **立即运行** 均会安全跳过（手动接口返回 `409 Conflict`）。
- **抖音话题榜校验：** 抖音 `hot` 热搜榜条目为话题而非直接视频（`downloadable: false`），因此定时任务编辑器与后端校验均强制要求抖音定时任务使用「自定义关键词」（`custom:<词>`）。
