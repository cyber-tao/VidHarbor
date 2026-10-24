---
title: VidHarbor · 影坞 — 自托管多平台本地视频库
description: 下载 YouTube、哔哩哔哩、TikTok、抖音视频，统一封装为 H.265/H.264 MP4，自带热门榜单、定时任务、字幕入库与中英双语深浅主题 Web 控制台。
---

<script setup>
import { withBase } from 'vitepress'
</script>

<div class="vh-hero">
  <div>
    <div class="vh-badge-row">
      <span class="vh-pill vh-pill-brand">v0.3.0 · 源码实测验证</span>
      <span class="vh-pill">YouTube · 哔哩哔哩 · TikTok · 抖音</span>
      <span class="vh-pill">中英双语 · 深浅双色主题</span>
    </div>
    <h1 class="vh-hero-title">VidHarbor · 影坞<br/>自托管多平台本地视频库</h1>
    <p class="vh-hero-lead">
      VidHarbor（影坞）面向家庭服务器（Homelab）玩家与内容归档者，解决多平台提取器碎片化、App 分享短链混杂乱码、容器与编码格式不统一等痛点。它将 <strong>YouTube、哔哩哔哩、TikTok、抖音</strong> 的链接、热门榜单与定时任务统一转化为规范命名的本地 <strong>MP4（H.265/H.264 + AAC + faststart）</strong> 视频库，并将元数据与字幕完整索引至 SQLite。
    </p>
    <div class="vh-cta-row">
      <a class="vh-btn vh-btn-primary" :href="withBase('/zh/guide/quickstart.html')">快速开始 →</a>
      <a class="vh-btn vh-btn-secondary" :href="withBase('/zh/reference/architecture.html')">架构与媒体管线</a>
      <a class="vh-btn vh-btn-secondary" href="https://github.com/cyber-tao/VidHarbor" target="_blank" rel="noopener">GitHub 源码 ↗</a>
    </div>
    <div class="vh-quick-cmd">
      <div>git clone https://github.com/cyber-tao/VidHarbor.git &amp;&amp; cd VidHarbor</div>
      <div>./deploy.sh &nbsp;# Linux / macOS / WSL（Windows PowerShell 执行 .\deploy.ps1）</div>
      <div class="vh-quick-cmd-note">仅需安装 Docker 与 Compose v2。启动后访问 <code>http://127.0.0.1:8666</code>。</div>
    </div>
  </div>

  <figure class="vh-figure">
    <img :src="withBase('/screenshots/dashboard-zh-dark.png')" alt="VidHarbor 影坞 Web 控制台中文深色主题仪表盘截图，展示视频总数、存储占用、平台分布环形图、近14天入库柱状图、快速下载与最近任务" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>回答的问题：</strong>部署完成后控制台提供哪些核心能力？<strong>结论：</strong>单端口（`:8666`）FastAPI + Vue 3 控制台，提供 SSE 实时任务进度、平台分布统计、近 14 天入库趋势与一键粘贴下载（实拍自 v0.3.0 运行实例）。
    </figcaption>
  </figure>
</div>

## 从杂乱分享文案到结构化本地 MP4 视频库 {#problem-to-result}

移动端 App 的分享口令往往夹杂着推广文案与短链（`v.douyin.com`、`vm.tiktok.com`、`b23.tv`），而各源站直出流又分散在 `webm`、`mkv` 或不同编码（`vp9`、`av01`、`hev1`、`avc1`）中。

### 输入：直接粘贴 App 分享口令或多平台链接

```text
7.43 复制打开抖音，看看【极客工坊的作品】万兆家庭影音库理线实录 https://v.douyin.com/iY8xYz1/
同时下载：https://youtu.be/dQw4w9WgXcQ 与 https://www.bilibili.com/video/BV1GJ411x7h7
```

### 输出：规范命名的本地文件 + SQLite 元数据与字幕索引

```text
library/videos/
├── bilibili/索尼音乐中国/
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up - Rick Astley [BV1GJ411x7h7].mp4
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up - Rick Astley [BV1GJ411x7h7].jpg
│   └── 20191231 - 【官方 MV】Never Gonna Give You Up - Rick Astley [BV1GJ411x7h7].en-US.srt
└── douyin/GeekWorkshop/
    ├── 20261018 - 10GbE Home Media Library Cabling & Silent Cooling Walkthrough [742700192831].mp4
    └── 20261018 - 10GbE Home Media Library Cabling & Silent Cooling Walkthrough [742700192831].jpg
```

每个入库视频均经 `ffprobe` 探测，按需执行无损封装（remux）或硬件加速转码，生成带 `+faststart` 与 `hvc1` 标记的标准 MP4，同时将 SRT 字幕全文存入 SQLite 并支持网页端 `<track>` WebVTT 挂载与本地播放器（VLC、PotPlayer、IINA）同名自动加载。

## 为什么选择 VidHarbor {#why-vidharbor}

<div class="vh-grid-3">
  <div class="vh-card">
    <h3>1. 无损优先的统一 MP4 管线</h3>
    <p>默认目标编码为 H.265 时，源流已是 HEVC+AAC 的视频直接执行无损封装（<code>-c:v copy -tag:v hvc1</code>）免除二次重编码；非 HEVC 源自动探测硬件编码器（<code>hevc_nvenc</code> / <code>hevc_qsv</code> / <code>hevc_amf</code> / <code>hevc_videotoolbox</code>），无硬件时回退 <code>libx265</code>。</p>
  </div>
  <div class="vh-card">
    <h3>2. 下载前 ID 级去重与双引擎兜底</h3>
    <p>在调用 <code>yt-dlp</code> 之前解析规范视频 ID（含 B站多 P 等价 ID <code>_p1</code>），对已在队列或库中的视频直接秒跳过，不浪费带宽。当抖音/TikTok 因 <code>a_bogus</code> 拦截 <code>yt-dlp</code> 时自动切换本地 Evil0ctal v5 无水印兜底引擎。</p>
  </div>
  <div class="vh-card">
    <h3>3. 四平台热门榜单与定时追更</h3>
    <p>内置 B站（全站+8 分区、综合/三日/周榜、每周必看、入站必刷）、YouTube（三级回退）、抖音（热搜+签名视频搜索）、TikTok（签名标签榜），支持多榜单组合定时任务（APScheduler）自动去重入库。</p>
  </div>
</div>

### 实测后处理耗时对比：HEVC 无损封装 vs 软件转码

<div class="vh-chart-box">
  <div class="vh-chart-title">目标 H.265 MP4（+faststart, hvc1 标记）后处理耗时对比 — 越短越快</div>
  <div class="vh-chart-meta">测试负载：5.0 秒 1920×1080 @ 30fps 测试视频流 + 48kHz AAC 音频 · FFmpeg 9.0 · 1 次预热 + 5 次计时采样 · 实测于 2026-10-24（v0.3.0, commit 435b7ca）</div>
  <div class="vh-bar-row">
    <div><strong>HEVC 源流 → 无损 Remux (<code>-c copy</code>)</strong></div>
    <div class="vh-bar-track"><div class="vh-bar-fill" style="width: 25.8%; background: var(--vh-emerald);"></div></div>
    <div><code>525.8 ms</code> (±4.2 ms)</div>
  </div>
  <div class="vh-bar-row">
    <div><strong>H.264 源流 → 软件转码 (<code>libx265</code>)</strong></div>
    <div class="vh-bar-track"><div class="vh-bar-fill" style="width: 100%; background: var(--vp-c-brand-1);"></div></div>
    <div><code>2033.2 ms</code> (±1.3 ms)</div>
  </div>
  <div style="font-size: 0.78rem; color: var(--vh-text-2); margin-top: 0.5rem;">
    <strong>结论：</strong>源流编码匹配时的无损封装速度是软件重编码的 <strong>3.9 倍</strong>（耗时减少 74.1%），无画质损耗且不占用全局转码并发槽位。复现命令与边界说明见 <a :href="withBase('/zh/reference/evidence.html')">实测验证与证据清单</a> 及 <a :href="withBase('/evidence/postprocess-benchmark.json')" target="_blank">原始 JSON 数据</a>。
  </div>
</div>

## 端到端处理管线 {#pipeline}

<div class="vh-pipeline">
  <div class="vh-step">
    <div class="vh-step-num">STAGE 01</div>
    <div class="vh-step-title">文案清洗与去重</div>
    <div class="vh-step-desc">从分享文案提取链接，展开 <code>v.douyin</code> / <code>vm.tiktok</code> / <code>b23.tv</code> 短链，解析视频 ID 并跳过已在队列或库中的条目。</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 02</div>
    <div class="vh-step-title">限流调度与双引擎</div>
    <div class="vh-step-desc">按全局并发与单平台并发上限调度；优先使用带平台专属 cookies/代理的 <code>yt-dlp</code>，失败时自动切换 Evil0ctal v5。</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 03</div>
    <div class="vh-step-title">FFprobe 探测与封装</div>
    <div class="vh-step-desc">探测音视频编码流；目标匹配时直接无损 remux，否则申请转码信号量槽位，通过硬件或 CPU 编码输出 <code>+faststart</code> MP4。</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 04</div>
    <div class="vh-step-title">规范入库与实时推送</div>
    <div class="vh-step-desc">按模板清洗非法字符归档文件，将字幕全文与标签写入 SQLite (WAL)，并通过 SSE 实时推送进度与日志。</div>
  </div>
</div>

## Web 控制台界面实拍：中英双语与深浅双色主题 {#console-walkthrough}

Web 控制台原生内置 **English / 简体中文** 双语与 **深色（Dark）/ 浅色（Light）** 主题切换，可在左侧边栏底部工具栏或「设置」页面随时一键切换。

<div class="vh-grid-2">
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/dashboard-zh-light.png')" alt="VidHarbor 影坞中文浅色主题仪表盘实拍截图" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>仪表盘（中文 · 浅色主题）：</strong>清晰展示视频库总量、存储体积、平台占比与近 14 天入库趋势。
    </figcaption>
  </figure>
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/charts-en-dark.png')" alt="VidHarbor 热门榜单英文深色主题实拍截图" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>热门榜单（英文 · 深色主题）：</strong>支持 B站、YouTube、TikTok、抖音分类与时间周期筛选及卡片多选批量下载。
    </figcaption>
  </figure>
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/library-en-dark.png')" alt="VidHarbor 视频库标签筛选与字幕徽标实拍截图" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>视频库与标签聚合筛选：</strong>支持全文检索、平台过滤、多标签同时满足（AND）筛选、CC 字幕数标记与在线播放。
    </figcaption>
  </figure>
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/schedules-en-dark.png')" alt="VidHarbor 定时任务多榜单组合实拍截图" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>定时任务（APScheduler）：</strong>一个任务可组合多个平台的分类榜单 TopN，支持每天/每周/间隔/Cron 触发并自动跳过已有视频。
    </figcaption>
  </figure>
</div>

## 适用场景、方案对比与已知限制 {#fit-and-limitations}

| 评估维度 | 原生 `yt-dlp` + `ffmpeg` 命令行 | 通用单链接下载面板（如 MeTube） | VidHarbor 影坞（`v0.3.0`） |
| --- | --- | --- | --- |
| **核心交互方式** | 手动拼接终端命令或编写脚本 | 网页手动粘贴单条/播放列表链接 | 粘贴分享口令、浏览四平台热门榜单多选下载、定时自动追更 |
| **抖音 / TikTok 反爬签名（`a_bogus` / `X-Bogus`）** | 需自行维护签名或提取器；抖音常被拦截 | 仅依赖 `yt-dlp` | 自动回退本地 Evil0ctal v5 兜底栈 + 签名调用官方搜索与标签接口 |
| **入库文件一致性** | 每次命令需手动指定参数 | 取决于源流封装格式 | 自动 `ffprobe` → 无损 `hvc1` remux 或硬件优先 HEVC/H.264 `+faststart` MP4 |
| **本地媒体库与字幕管理** | 仅磁盘目录文件 | 下载队列文件列表 | SQLite (WAL) 索引、多标签聚合筛选、全文搜索、网页端 WebVTT `<track>` 字幕切换 |
| **资源占用** | 极低（纯命令行） | 轻量容器 | 核心容器轻量；可选的 Evil0ctal v5 兜底栈首次部署需约 5 GB 磁盘与 8 GB 内存 |

### 何时选择其他方案与已知限制

- **仅需偶尔在终端下载单个视频：** 直接使用命令行 [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) 即可，无需常驻运行 Web 服务。
- **不支持图文/图集作品：** `ensure_mp4` 会校验文件中是否存在视频流，抖音/TikTok 图集作品会被自动跳过或拒绝入库。
- **抖音/TikTok 搜索与兜底依赖：** 抖音关键词搜索、TikTok 标签榜与抖音下载兜底需要启用 Evil0ctal v5 服务（`./deploy.sh` / `.\deploy.ps1` 在 `WITH_EVIL0CTAL=1` 默认模式下会自动部署并接线）以及对应平台的登录 cookies。
- **单 Worker 调度器限制：** APScheduler 随 FastAPI 进程启动，请保持单 worker 运行（`run.py` 与 `Dockerfile` 默认均为单 worker），多 worker 会导致定时任务重复触发。
- **浏览器内播放 H.265 视频：** 网页端直接播放 HEVC 依赖客户端系统与显卡硬解（Safari 原生支持，Chrome/Edge 需硬件解码支持）；若优先追求任意浏览器直接播放，可在「设置」页将入库编码切换为 `h264`。

## 浏览完整文档 {#explore-manual}

<div class="vh-grid-2">
  <div class="vh-card">
    <h3>🚀 <a :href="withBase('/zh/guide/quickstart.html')">快速开始</a></h3>
    <p>使用一键脚本通过 Docker 部署，或在 Windows / Linux / macOS 裸机运行，完成第一条视频下载入库。</p>
  </div>
  <div class="vh-card">
    <h3>🐳 <a :href="withBase('/zh/guide/deployment.html')">Docker、GPU 与兜底服务部署</a></h3>
    <p>配置 NVIDIA NVENC / Intel QSV 硬件加速转码、Evil0ctal v5 自动接线以及 <code>TOKEN</code> 访问控制。</p>
  </div>
  <div class="vh-card">
    <h3>🍪 <a :href="withBase('/zh/guide/cookies-and-auth.html')">登录管理与 Cookies 配置</a></h3>
    <p>B站手机扫码登录、上传 Netscape <code>cookies.txt</code>、本机浏览器导入（含 Chrome/Edge 127+ 应用绑定加密应对方案）。</p>
  </div>
  <div class="vh-card">
    <h3>📖 <a :href="withBase('/zh/reference/configuration.html')">配置项与 API 接口参考</a></h3>
    <p>查阅全部 <code>config.toml</code> 字段、<code>VIDHARBOR_*</code> 环境变量、REST 接口与 SSE 实时事件格式。</p>
  </div>
</div>
