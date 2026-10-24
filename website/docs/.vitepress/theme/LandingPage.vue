<script setup>
import { withBase } from 'vitepress'

defineProps({
  locale: {
    type: String,
    default: 'en',
  },
})
</script>

<template>
  <div v-if="locale === 'en'" class="vh-landing">
    <div class="vh-container">
      <!-- Hero Section: Project Title on Top, Three Features Spread Out Below -->
      <section class="vh-hero-section">
        <div class="vh-hero-topline">
          <span class="vh-brand-name">VidHarbor · 影坞</span>
          <span class="vh-version-badge">v0.3.0</span>
        </div>
        <h1 class="vh-hero-headline">Self-Hosted Multi-Platform Video Library</h1>

        <!-- Three Feature Badges Spread Horizontally Below Title -->
        <div class="vh-pill-row">
          <span class="vh-pill"><span class="vh-pill-dot"></span>YouTube · Bilibili · TikTok · Douyin</span>
          <span class="vh-pill"><span class="vh-pill-dot"></span>H.265 / H.264 Lossless Remux &amp; HW Transcode</span>
          <span class="vh-pill"><span class="vh-pill-dot"></span>EN / 简体中文 · Dark &amp; Light Web Console</span>
        </div>

        <p class="vh-hero-lead">
          Built for homelab operators and media archivers. VidHarbor turns messy share links, multi-platform trending charts, and scheduled feeds into a normalized MP4 archive indexed in SQLite.
        </p>

        <!-- Call to Action Buttons -->
        <div class="vh-cta-row">
          <a class="vh-btn vh-btn-primary" :href="withBase('/guide/quickstart.html')">Get Started →</a>
          <a class="vh-btn vh-btn-secondary" :href="withBase('/reference/architecture.html')">Architecture &amp; Pipeline</a>
          <a class="vh-btn vh-btn-secondary" :href="withBase('/reference/configuration.html')">Configuration &amp; API</a>
          <a class="vh-btn vh-btn-secondary" href="https://github.com/cyber-tao/VidHarbor" target="_blank" rel="noopener">GitHub Source ↗</a>
        </div>

        <!-- Three Core Feature Cards Spread Horizontally -->
        <div class="vh-feature-strip">
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">01</span>
              <span class="vh-pillar-title">Multi-Source Intake &amp; Charts</span>
            </div>
            <p class="vh-pillar-desc">
              Paste mobile share text (<code>v.douyin</code>, <code>vm.tiktok</code>, <code>b23.tv</code>), browse 4-platform trending charts (<code>category × period</code>), or schedule automated Top-N jobs with Evil0ctal v5 fallback.
            </p>
          </div>
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">02</span>
              <span class="vh-pillar-title">Hardware-First Unified MP4</span>
            </div>
            <p class="vh-pillar-desc">
              Normalizes every download to <code>+faststart</code> MP4 (<code>H.265 / H.264 + AAC</code>). Streams already in HEVC are losslessly remuxed (<code>-c:v copy -tag:v hvc1</code>, 3.9× faster); others probe NVENC / QSV / AMF / VideoToolbox.
            </p>
          </div>
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">03</span>
              <span class="vh-pillar-title">SQLite Index &amp; Subtitle Tracks</span>
            </div>
            <p class="vh-pillar-desc">
              Indexes metadata, tags, and full SRT subtitles in SQLite (WAL) with pre-download ID deduplication, in-browser WebVTT <code>&lt;track&gt;</code> playback, Bilibili QR login, and live SSE logs.
            </p>
          </div>
        </div>

        <!-- Quick Start Command Box -->
        <div class="vh-quick-cmd">
          <div class="vh-quick-cmd-code">git clone https://github.com/cyber-tao/VidHarbor.git &amp;&amp; cd VidHarbor
./deploy.sh   # Linux / macOS / WSL / Git Bash (or .\deploy.ps1 on Windows PowerShell)</div>
          <div class="vh-quick-cmd-note">
            Requires Docker with Compose v2. Builds the multi-stage image, provisions the optional Evil0ctal v5 fallback stack, and serves the web console at <code>http://127.0.0.1:8666</code>.
          </div>
        </div>

        <!-- Full-Width Console Showcase -->
        <figure class="vh-window">
          <div class="vh-window-bar">
            <span class="vh-dot vh-dot-red"></span>
            <span class="vh-dot vh-dot-amber"></span>
            <span class="vh-dot vh-dot-green"></span>
            <span class="vh-window-url">http://127.0.0.1:8666 — VidHarbor Web Console (v0.3.0 · English / Dark)</span>
          </div>
          <img :src="withBase('/screenshots/dashboard-en-dark.png')" alt="VidHarbor Web Console Dashboard in English Dark mode showing video totals, storage usage, platform breakdown donut chart, 14-day intake bar chart, quick download box, and recent tasks" width="1440" height="900" />
          <figcaption class="vh-figcaption">
            <strong>Question answered:</strong> What does the running console deliver after deployment? <strong>Conclusion:</strong> A single-port FastAPI + Vue 3 console (<code>:8666</code>) with live SSE task progress, platform distribution, 14-day intake telemetry, and instant paste-to-download. (Captured from a running v0.3.0 instance.)
          </figcaption>
        </figure>
      </section>

      <!-- Section 1: Problem to Result -->
      <section class="vh-section" id="problem-to-result">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Workflow Proof</div>
          <h2 class="vh-section-title">From Messy Share Copy to an Indexed Local MP4 Archive</h2>
          <p class="vh-section-desc">
            Mobile apps rarely give you clean URLs or uniform media streams. VidHarbor extracts links from promotional share text, expands short links, deduplicates against your existing library before downloading, and organizes files with sidecar subtitles.
          </p>
        </div>

        <div class="vh-grid-2">
          <div class="vh-code-panel">
            <div class="vh-code-header">1. Input — Raw Share Text or Multi-Platform Links</div>
            <pre class="vh-code-pre">7.43 复制打开抖音，看看【极客工坊的作品】万兆家庭影音库理线实录
https://v.douyin.com/iY8xYz1/

Also grab:
https://youtu.be/dQw4w9WgXcQ
https://www.bilibili.com/video/BV1GJ411x7h7</pre>
          </div>
          <div class="vh-code-panel">
            <div class="vh-code-header">2. Output — Normalized MP4 + Sidecar SRT + SQLite Row</div>
            <pre class="vh-code-pre">library/videos/
├── bilibili/索尼音乐中国/
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].mp4
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].jpg
│   └── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].en-US.srt
└── douyin/GeekWorkshop/
    ├── 20261018 - 10GbE Home Media Library Walkthrough [742700192831].mp4
    └── 20261018 - 10GbE Home Media Library Walkthrough [742700192831].jpg</pre>
          </div>
        </div>
      </section>

      <!-- Section 2: Pipeline & Measured Benchmark -->
      <section class="vh-section" id="pipeline">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Architecture &amp; Measurement</div>
          <h2 class="vh-section-title">Four-Stage Pipeline &amp; Lossless-First Normalization</h2>
          <p class="vh-section-desc">
            Network downloads and FFmpeg transcodes are governed by independent concurrency semaphores. When a downloaded stream already matches the target codec, VidHarbor remuxes it losslessly without consuming a transcode slot.
          </p>
        </div>

        <div class="vh-pipeline">
          <div class="vh-step">
            <div class="vh-step-num">STAGE 01</div>
            <div class="vh-step-title">Ingest &amp; Dedup</div>
            <div class="vh-step-desc">Extract HTTP(S) links, expand <code>v.douyin</code> / <code>vm.tiktok</code> / <code>b23.tv</code> short URLs, resolve canonical IDs (including Bilibili <code>_p1</code> equivalence), and skip active or archived items.</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 02</div>
            <div class="vh-step-title">Dual-Engine Fetch</div>
            <div class="vh-step-desc">Enforce global and per-platform download caps. Run <code>yt-dlp</code> with per-platform cookies/proxy; switch automatically to Evil0ctal v5 when Douyin/TikTok block extraction.</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 03</div>
            <div class="vh-step-title">FFprobe &amp; Normalize</div>
            <div class="vh-step-desc">Inspect streams via <code>ffprobe</code>. Remux matching codecs directly (<code>-c:v copy -tag:v hvc1</code>) or acquire a transcode slot for hardware/CPU encoding into <code>+faststart</code> MP4.</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 04</div>
            <div class="vh-step-title">Archive &amp; Stream</div>
            <div class="vh-step-desc">Sanitize filenames per template, index SRT subtitles and tags in SQLite (WAL), and stream live progress and logs over Server-Sent Events (SSE).</div>
          </div>
        </div>

        <div class="vh-chart-box">
          <div class="vh-chart-title">Measured Post-Processing Time to Target H.265 MP4 (+faststart, hvc1 tag) — Lower is Faster</div>
          <div class="vh-chart-meta">Workload: 5.0s 1920×1080 @ 30fps synthetic video + 48kHz AAC audio · FFmpeg 9.0 · 1 warmup + 5 measured runs · Checked 2026-10-24 (v0.3.0)</div>
          <div class="vh-bar-row">
            <div><strong>HEVC Source → Remux (<code>-c copy</code>)</strong></div>
            <div class="vh-bar-track"><div class="vh-bar-fill" style="width: 25.8%; background: var(--vh-emerald);"></div></div>
            <div><code>525.8 ms</code> (±4.2 ms)</div>
          </div>
          <div class="vh-bar-row">
            <div><strong>H.264 Source → Transcode (<code>libx265</code>)</strong></div>
            <div class="vh-bar-track"><div class="vh-bar-fill" style="width: 100%; background: var(--vp-c-brand-1);"></div></div>
            <div><code>2033.2 ms</code> (±1.3 ms)</div>
          </div>
          <div style="font-size: 0.8rem; color: var(--vh-text-2); margin-top: 0.5rem;">
            <strong>Conclusion:</strong> Stream-copy remuxing completes <strong>3.9× faster</strong> (74.1% time reduction) with zero generation loss and bypasses the transcode concurrency queue. See <a :href="withBase('/reference/evidence.html')">Verification &amp; Evidence</a> and <a :href="withBase('/evidence/postprocess-benchmark.json')" target="_blank">raw JSON data</a> for reproduction commands and scope qualifications.
          </div>
        </div>
      </section>

      <!-- Section 3: Console Walkthrough -->
      <section class="vh-section" id="console-walkthrough">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Web Console Tour</div>
          <h2 class="vh-section-title">Trending Charts, Library Filtering, Schedules &amp; Settings</h2>
          <p class="vh-section-desc">
            Switch between English and Simplified Chinese or Dark and Light themes at any time from the sidebar toolbar or Settings page.
          </p>
        </div>

        <div class="vh-grid-2">
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/charts-en-dark.png')" alt="VidHarbor Trending Charts view in Dark theme showing Bilibili categories and selectable video cards" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>Trending Charts (Dark):</strong> Category × time period filtering across Bilibili, YouTube, TikTok, and Douyin with multi-select batch download.
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/library-en-dark.png')" alt="VidHarbor Video Library view showing tag aggregation filter and video cards with CC subtitle badges" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>Video Library &amp; Tag Filter (Dark):</strong> Full-text search, platform tabs, AND-combined tag filtering, CC subtitle badges, and HTTP Range player.
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/schedules-en-dark.png')" alt="VidHarbor Schedules view showing automated daily and weekly multi-chart download jobs" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>Scheduled Jobs (Dark):</strong> Combine multiple platform charts (<code>platform × category × period × TopN</code>) under daily, weekly, interval, or cron triggers.
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/settings-en-light.png')" alt="VidHarbor Settings view in Light theme showing Appearance & Language, Default Download Options, and Concurrency controls" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>Settings Center (Light):</strong> Runtime overrides for language, theme, resolution, subtitle/audio languages, proxy routing, concurrency caps, and platform cookies.
            </figcaption>
          </figure>
        </div>
      </section>

      <!-- Section 4: Comparison & Limitations -->
      <section class="vh-section" id="fit-and-limitations">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Decision Guide</div>
          <h2 class="vh-section-title">How VidHarbor Compares &amp; Known Limitations</h2>
          <p class="vh-section-desc">
            Evaluate whether VidHarbor fits your workflow compared to raw CLI scripts or single-URL web wrappers.
          </p>
        </div>

        <div class="vh-table-wrap">
          <table class="vh-table">
            <thead>
              <tr>
                <th>Decision Criterion</th>
                <th>Raw <code>yt-dlp</code> + <code>ffmpeg</code> CLI</th>
                <th>Single-URL Web Wrappers (e.g. MeTube)</th>
                <th>VidHarbor (<code>v0.3.0</code>)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Primary workflow</strong></td>
                <td>Ad-hoc terminal commands &amp; shell scripts</td>
                <td>Manual single/playlist URL pasting in browser</td>
                <td>Paste share copy, browse 4-platform charts, or schedule recurring chart intake</td>
              </tr>
              <tr>
                <td><strong>Douyin / TikTok signatures (<code>a_bogus</code> / <code>X-Bogus</code>)</strong></td>
                <td>Manual cookie/extractor workarounds; Douyin frequently blocked</td>
                <td>Depends solely on <code>yt-dlp</code></td>
                <td>Automatic fallback to local Evil0ctal v5 stack + signed Douyin/TikTok chart APIs</td>
              </tr>
              <tr>
                <td><strong>Output consistency</strong></td>
                <td>Manual flags per invocation</td>
                <td>Varies by source stream unless custom post-args configured</td>
                <td>Automatic <code>ffprobe</code> → lossless <code>hvc1</code> remux or hardware-first HEVC/H.264 <code>+faststart</code> MP4</td>
              </tr>
              <tr>
                <td><strong>Local library &amp; subtitles</strong></td>
                <td>Flat files on disk</td>
                <td>Download folder listing</td>
                <td>SQLite (WAL) index with tag aggregation, full-text search, and in-browser VTT <code>&lt;track&gt;</code> player</td>
              </tr>
              <tr>
                <td><strong>Resource footprint</strong></td>
                <td>Minimal (CLI only)</td>
                <td>Lightweight container</td>
                <td>Lightweight core (~Python + FFmpeg); optional Evil0ctal v5 stack uses ~5 GB disk / ~8 GB RAM</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="vh-grid-2">
          <div class="vh-card">
            <h3>When Another Tool Fits Better</h3>
            <p>
              If you only download occasional single videos from a terminal and do not need a persistent web library, trending charts, or scheduled jobs, use <a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noopener"><code>yt-dlp</code></a> directly. Also note that VidHarbor only indexes video streams—photo/carousel posts (<code>图集</code>) on Douyin/TikTok are skipped.
            </p>
          </div>
          <div class="vh-card">
            <h3>Operational Constraints to Know</h3>
            <p>
              Keep the backend to a <strong>single uvicorn worker</strong> (the default) so APScheduler does not fire duplicate jobs. Playing H.265 in a browser requires client OS/GPU HEVC decoding (native in Safari; switch <code>library.video_codec</code> to <code>h264</code> in Settings for universal browser playback).
            </p>
          </div>
        </div>
      </section>

      <!-- Section 5: Documentation Hub -->
      <section class="vh-section" id="explore-manual">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Manuals &amp; Reference</div>
          <h2 class="vh-section-title">Explore the Documentation</h2>
        </div>

        <div class="vh-grid-2">
          <div class="vh-card">
            <h3>🚀 <a :href="withBase('/guide/quickstart.html')">Quickstart Guide →</a></h3>
            <p>Deploy with Docker in one command or run bare-metal on Windows, Linux, and macOS with <code>uv</code>, Node.js, and <code>ffmpeg</code>, then verify your first indexed video.</p>
          </div>
          <div class="vh-card">
            <h3>🐳 <a :href="withBase('/guide/deployment.html')">Docker, GPU &amp; Evil0ctal Deployment →</a></h3>
            <p>Configure NVIDIA NVENC / Intel QSV hardware transcoding, Evil0ctal v5 automatic provisioning, and <code>TOKEN</code> / <code>BIND_IP</code> access control.</p>
          </div>
          <div class="vh-card">
            <h3>🍪 <a :href="withBase('/guide/cookies-and-auth.html')">Cookies &amp; Login Management →</a></h3>
            <p>Sign in via Bilibili QR code, upload Netscape <code>cookies.txt</code>, or import from local browsers (including Chrome/Edge 127+ App-Bound Encryption workarounds).</p>
          </div>
          <div class="vh-card">
            <h3>📖 <a :href="withBase('/reference/configuration.html')">Configuration &amp; API Reference →</a></h3>
            <p>Look up every <code>config.toml</code> key, <code>VIDHARBOR_*</code> environment variable, REST endpoint, SSE event payload, and verification artifact.</p>
          </div>
        </div>
      </section>
    </div>
  </div>

  <!-- Simplified Chinese Landing Page -->
  <div v-else class="vh-landing">
    <div class="vh-container">
      <!-- 首屏区域：项目大标题在上，三大核心特性在下方横向排开 -->
      <section class="vh-hero-section">
        <div class="vh-hero-topline">
          <span class="vh-brand-name">VidHarbor · 影坞</span>
          <span class="vh-version-badge">v0.3.0</span>
        </div>
        <h1 class="vh-hero-headline">自托管多平台本地视频库</h1>

        <!-- 三个特性标签在大标题正下方横向排开 -->
        <div class="vh-pill-row">
          <span class="vh-pill"><span class="vh-pill-dot"></span>YouTube · 哔哩哔哩 · TikTok · 抖音</span>
          <span class="vh-pill"><span class="vh-pill-dot"></span>H.265 / H.264 无损封装与硬件加速转码</span>
          <span class="vh-pill"><span class="vh-pill-dot"></span>中英双语 · 深浅双色 Web 控制台</span>
        </div>

        <p class="vh-hero-lead">
          专为家庭服务器（Homelab）玩家与内容归档者打造，将多平台分享口令、分类×周期热门榜单与定时追更统一转化为规范命名、可全文与标签检索的本地 MP4 视频库。
        </p>

        <!-- 主操作按钮组 -->
        <div class="vh-cta-row">
          <a class="vh-btn vh-btn-primary" :href="withBase('/zh/guide/quickstart.html')">快速开始 →</a>
          <a class="vh-btn vh-btn-secondary" :href="withBase('/zh/reference/architecture.html')">架构与媒体管线</a>
          <a class="vh-btn vh-btn-secondary" :href="withBase('/zh/reference/configuration.html')">配置与 API 参考</a>
          <a class="vh-btn vh-btn-secondary" href="https://github.com/cyber-tao/VidHarbor" target="_blank" rel="noopener">GitHub 源码 ↗</a>
        </div>

        <!-- 三大核心特性横向三列排开 -->
        <div class="vh-feature-strip">
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">01</span>
              <span class="vh-pillar-title">多源采集与定时追更</span>
            </div>
            <p class="vh-pillar-desc">
              支持粘贴 App 分享口令自动提取并展开短链（<code>v.douyin</code> / <code>vm.tiktok</code> / <code>b23.tv</code>）、四平台分类×周期热门榜单多选下载、APScheduler 定时追更与 Evil0ctal v5 无水印兜底。
            </p>
          </div>
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">02</span>
              <span class="vh-pillar-title">硬件优先统一 MP4 管线</span>
            </div>
            <p class="vh-pillar-desc">
              统一入库为 <code>+faststart</code> MP4（<code>H.265 / H.264 + AAC</code>）。源流已是 HEVC 时直接执行无损封装（<code>-c:v copy -tag:v hvc1</code>，实测快 3.9 倍）；非匹配源优先调用 NVENC / QSV / AMF / VideoToolbox 硬编。
            </p>
          </div>
          <div class="vh-feature-pillar">
            <div class="vh-pillar-head">
              <span class="vh-pillar-icon">03</span>
              <span class="vh-pillar-title">SQLite 全量索引与字幕挂载</span>
            </div>
            <p class="vh-pillar-desc">
              下载前按视频 ID 秒级去重；元数据、标签与 SRT 字幕全文统一存入 SQLite (WAL)，内置播放器支持 WebVTT <code>&lt;track&gt;</code> 字幕轨切换、B站扫码登录与 SSE 实时日志流。
            </p>
          </div>
        </div>

        <!-- 一键部署命令栏 -->
        <div class="vh-quick-cmd">
          <div class="vh-quick-cmd-code">git clone https://github.com/cyber-tao/VidHarbor.git &amp;&amp; cd VidHarbor
./deploy.sh   # Linux / macOS / WSL / Git Bash（Windows PowerShell 执行 .\deploy.ps1）</div>
          <div class="vh-quick-cmd-note">
            仅需安装 Docker 与 Compose v2。脚本自动构建多阶段镜像、部署并接线 Evil0ctal v5 兜底服务，启动后访问 <code>http://127.0.0.1:8666</code>。
          </div>
        </div>

        <!-- 全宽浏览器外框控制台实拍图 -->
        <figure class="vh-window">
          <div class="vh-window-bar">
            <span class="vh-dot vh-dot-red"></span>
            <span class="vh-dot vh-dot-amber"></span>
            <span class="vh-dot vh-dot-green"></span>
            <span class="vh-window-url">http://127.0.0.1:8666 — VidHarbor 影坞 Web 控制台 (v0.3.0 · 简体中文 / 深色主题)</span>
          </div>
          <img :src="withBase('/screenshots/dashboard-zh-dark.png')" alt="VidHarbor 影坞 Web 控制台中文深色主题仪表盘截图，展示视频总数、存储占用、平台分布环形图、近14天入库柱状图、快速下载与最近任务" width="1440" height="900" />
          <figcaption class="vh-figcaption">
            <strong>回答的问题：</strong>部署完成后控制台提供哪些核心能力？<strong>结论：</strong>单端口（<code>:8666</code>）FastAPI + Vue 3 控制台，提供 SSE 实时任务进度、平台分布统计、近 14 天入库趋势与一键粘贴下载（实拍自 v0.3.0 运行实例）。
          </figcaption>
        </figure>
      </section>

      <!-- 第一节：输入输出实例对照 -->
      <section class="vh-section" id="problem-to-result">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Workflow Proof</div>
          <h2 class="vh-section-title">从杂乱分享口令到结构化本地 MP4 视频库</h2>
          <p class="vh-section-desc">
            移动端 App 分享文本往往夹杂推广词与短链，各平台直出流也分散在不同容器与编码中。VidHarbor 自动清洗链接、下载前按 ID 查重，并以统一模板归档视频、封面与同名 SRT 字幕。
          </p>
        </div>

        <div class="vh-grid-2">
          <div class="vh-code-panel">
            <div class="vh-code-header">1. 输入 — 直接粘贴 App 分享口令或多平台链接</div>
            <pre class="vh-code-pre">7.43 复制打开抖音，看看【极客工坊的作品】万兆家庭影音库理线实录
https://v.douyin.com/iY8xYz1/

同时批量下载：
https://youtu.be/dQw4w9WgXcQ
https://www.bilibili.com/video/BV1GJ411x7h7</pre>
          </div>
          <div class="vh-code-panel">
            <div class="vh-code-header">2. 输出 — 规范命名 MP4 + 同名 SRT 字幕 + SQLite 索引</div>
            <pre class="vh-code-pre">library/videos/
├── bilibili/索尼音乐中国/
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].mp4
│   ├── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].jpg
│   └── 20191231 - 【官方 MV】Never Gonna Give You Up [BV1GJ411x7h7].en-US.srt
└── douyin/GeekWorkshop/
    ├── 20261018 - 10GbE Home Media Library Walkthrough [742700192831].mp4
    └── 20261018 - 10GbE Home Media Library Walkthrough [742700192831].jpg</pre>
          </div>
        </div>
      </section>

      <!-- 第二节：四阶段管线与实测性能对比 -->
      <section class="vh-section" id="pipeline">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Architecture &amp; Measurement</div>
          <h2 class="vh-section-title">四阶段处理管线与无损优先封装实测</h2>
          <p class="vh-section-desc">
            网络下载并发与 FFmpeg 转码并发相互独立。当源视频流已匹配目标编码时，直接执行无损流拷贝（remux），不占用转码信号量槽位。
          </p>
        </div>

        <div class="vh-pipeline">
          <div class="vh-step">
            <div class="vh-step-num">STAGE 01</div>
            <div class="vh-step-title">文案清洗与去重</div>
            <div class="vh-step-desc">提取 HTTP(S) 链接，展开 <code>v.douyin</code> / <code>vm.tiktok</code> / <code>b23.tv</code> 短链，解析规范 ID（含 B站 <code>_p1</code> 等价识别），秒跳过已在队列或库中的视频。</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 02</div>
            <div class="vh-step-title">限流调度与双引擎</div>
            <div class="vh-step-desc">按全局与单平台并发上限调度；优先使用带平台专属 cookies/代理的 <code>yt-dlp</code>，抖音/TikTok 被拦截时自动切换 Evil0ctal v5。</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 03</div>
            <div class="vh-step-title">FFprobe 探测与封装</div>
            <div class="vh-step-desc">探测音视频流；编码匹配时直接无损封装（<code>-c:v copy -tag:v hvc1</code>），否则申请转码槽位，通过硬件或 CPU 编码输出 <code>+faststart</code> MP4。</div>
          </div>
          <div class="vh-step">
            <div class="vh-step-num">STAGE 04</div>
            <div class="vh-step-title">规范入库与实时推送</div>
            <div class="vh-step-desc">按模板清洗非法字符归档文件，将字幕全文与标签写入 SQLite (WAL)，并通过 SSE 实时推送任务进度与日志。</div>
          </div>
        </div>

        <div class="vh-chart-box">
          <div class="vh-chart-title">目标 H.265 MP4（+faststart, hvc1 标记）后处理耗时实测对比 — 越短越快</div>
          <div class="vh-chart-meta">测试负载：5.0 秒 1920×1080 @ 30fps 测试视频流 + 48kHz AAC 音频 · FFmpeg 9.0 · 1 次预热 + 5 次计时采样 · 实测于 2026-10-24（v0.3.0）</div>
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
          <div style="font-size: 0.8rem; color: var(--vh-text-2); margin-top: 0.5rem;">
            <strong>结论：</strong>源流编码匹配时的无损封装速度是软件重编码的 <strong>3.9 倍</strong>（耗时减少 74.1%），无画质损耗且不占用全局转码并发槽位。复现命令与边界说明见 <a :href="withBase('/zh/reference/evidence.html')">实测验证与证据清单</a> 及 <a :href="withBase('/evidence/postprocess-benchmark.json')" target="_blank">原始 JSON 数据</a>。
          </div>
        </div>
      </section>

      <!-- 第三节：Web 控制台多页面实拍预览 -->
      <section class="vh-section" id="console-walkthrough">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Web Console Tour</div>
          <h2 class="vh-section-title">热门榜单、视频库筛选、定时任务与设置中心</h2>
          <p class="vh-section-desc">
            控制台原生支持中英双语（English / 简体中文）与深浅双色主题（Dark / Light），可在侧边栏底部或设置页随时切换。
          </p>
        </div>

        <div class="vh-grid-2">
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/charts-zh-dark.png')" alt="VidHarbor 热门榜单中文深色主题实拍截图" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>热门榜单（中文 · 深色主题）：</strong>支持 B站、YouTube、TikTok、抖音分类与时间周期筛选及卡片多选批量下载。
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/library-zh-dark.png')" alt="VidHarbor 视频库标签筛选与字幕徽标中文深色实拍截图" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>视频库与标签聚合筛选（中文 · 深色主题）：</strong>支持全文检索、平台过滤、多标签同时满足（AND）筛选、CC 字幕数标记与在线播放。
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/schedules-zh-dark.png')" alt="VidHarbor 定时任务多榜单组合中文深色实拍截图" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>定时任务（中文 · 深色主题）：</strong>一个任务可组合多个平台的分类榜单 TopN，支持每天/每周/间隔/Cron 触发并自动跳过已有视频。
            </figcaption>
          </figure>
          <figure class="vh-figure">
            <img :src="withBase('/screenshots/settings-zh-light.png')" alt="VidHarbor 设置页中文浅色主题实拍截图" width="1440" height="900" />
            <figcaption class="vh-figcaption">
              <strong>设置中心（中文 · 浅色主题）：</strong>支持界面语言与深浅主题切换、下载默认选项、并发上限、编码器探测展示与各平台 Cookies 登录管理。
            </figcaption>
          </figure>
        </div>
      </section>

      <!-- 第四节：方案对比与已知限制 -->
      <section class="vh-section" id="fit-and-limitations">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Decision Guide</div>
          <h2 class="vh-section-title">同类方案对比与已知边界</h2>
          <p class="vh-section-desc">
            对比原生命令行与单链接下载面板，评估 VidHarbor 是否契合你的使用场景。
          </p>
        </div>

        <div class="vh-table-wrap">
          <table class="vh-table">
            <thead>
              <tr>
                <th>评估维度</th>
                <th>原生 <code>yt-dlp</code> + <code>ffmpeg</code> 命令行</th>
                <th>通用单链接下载面板（如 MeTube）</th>
                <th>VidHarbor 影坞（<code>v0.3.0</code>）</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>核心交互方式</strong></td>
                <td>手动拼接终端命令或编写脚本</td>
                <td>网页手动粘贴单条/播放列表链接</td>
                <td>粘贴分享口令、浏览四平台热门榜单多选下载、定时自动追更</td>
              </tr>
              <tr>
                <td><strong>抖音 / TikTok 反爬签名（<code>a_bogus</code> / <code>X-Bogus</code>）</strong></td>
                <td>需自行维护签名或提取器；抖音常被拦截</td>
                <td>仅依赖 <code>yt-dlp</code></td>
                <td>自动回退本地 Evil0ctal v5 兜底栈 + 签名调用官方搜索与标签接口</td>
              </tr>
              <tr>
                <td><strong>入库文件一致性</strong></td>
                <td>每次命令需手动指定参数</td>
                <td>取决于源流封装格式</td>
                <td>自动 <code>ffprobe</code> → 无损 <code>hvc1</code> remux 或硬件优先 HEVC/H.264 <code>+faststart</code> MP4</td>
              </tr>
              <tr>
                <td><strong>本地媒体库与字幕管理</strong></td>
                <td>仅磁盘目录文件</td>
                <td>下载队列文件列表</td>
                <td>SQLite (WAL) 索引、多标签聚合筛选、全文搜索、网页端 WebVTT <code>&lt;track&gt;</code> 字幕切换</td>
              </tr>
              <tr>
                <td><strong>资源占用</strong></td>
                <td>极低（纯命令行）</td>
                <td>轻量容器</td>
                <td>核心容器轻量；可选的 Evil0ctal v5 兜底栈首次部署需约 5 GB 磁盘与 8 GB 内存</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="vh-grid-2">
          <div class="vh-card">
            <h3>何时选择其他方案</h3>
            <p>
              如果你只需要偶尔在终端下载单个视频，不需要本地常驻媒体库、热门榜单浏览或定时自动追更，直接使用命令行 <a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noopener"><code>yt-dlp</code></a> 更为轻量。此外，VidHarbor 仅归档含视频流的作品，抖音/TikTok 图集作品会被自动跳过。
            </p>
          </div>
          <div class="vh-card">
            <h3>运行与播放注意事项</h3>
            <p>
              APScheduler 随应用进程启动，请保持 <strong>单 uvicorn worker</strong> 运行（默认配置），避免定时任务重复触发。浏览器内直接播放 H.265 依赖系统与显卡硬解（Safari 原生支持；若追求全浏览器兼容播放，可在设置页将目标编码切为 <code>h264</code>）。
            </p>
          </div>
        </div>
      </section>

      <!-- 第五节：文档导航 -->
      <section class="vh-section" id="explore-manual">
        <div class="vh-section-header">
          <div class="vh-eyebrow">Manuals &amp; Reference</div>
          <h2 class="vh-section-title">浏览完整用户手册与参考文档</h2>
        </div>

        <div class="vh-grid-2">
          <div class="vh-card">
            <h3>🚀 <a :href="withBase('/zh/guide/quickstart.html')">快速开始指南 →</a></h3>
            <p>使用一键脚本通过 Docker 部署，或在 Windows / Linux / macOS 裸机运行，完成第一条视频下载入库验证。</p>
          </div>
          <div class="vh-card">
            <h3>🐳 <a :href="withBase('/zh/guide/deployment.html')">Docker、GPU 与兜底服务部署 →</a></h3>
            <p>配置 NVIDIA NVENC / Intel QSV 硬件加速转码、Evil0ctal v5 自动接线以及 <code>TOKEN</code> / <code>BIND_IP</code> 访问控制。</p>
          </div>
          <div class="vh-card">
            <h3>🍪 <a :href="withBase('/zh/guide/cookies-and-auth.html')">登录管理与 Cookies 配置 →</a></h3>
            <p>B站手机扫码登录、上传 Netscape <code>cookies.txt</code>、本机浏览器导入（含 Chrome/Edge 127+ 应用绑定加密应对方案）。</p>
          </div>
          <div class="vh-card">
            <h3>📖 <a :href="withBase('/zh/reference/configuration.html')">配置项与 API 接口参考 →</a></h3>
            <p>查阅全部 <code>config.toml</code> 字段、<code>VIDHARBOR_*</code> 环境变量、REST 接口、SSE 实时事件与实测验证证据。</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
