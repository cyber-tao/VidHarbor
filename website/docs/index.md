---
title: VidHarbor · Self-Hosted Multi-Platform Video Library
description: Download videos from YouTube, Bilibili, TikTok, and Douyin into a normalized H.265/H.264 MP4 library with trending charts, scheduled jobs, and SQLite indexing.
---

<script setup>
import { withBase } from 'vitepress'
</script>

<div class="vh-hero">
  <div>
    <div class="vh-badge-row">
      <span class="vh-pill vh-pill-brand">v0.3.0 · Source-Verified</span>
      <span class="vh-pill">YouTube · Bilibili · TikTok · Douyin</span>
      <span class="vh-pill">EN / 简体中文 · Dark / Light</span>
    </div>
    <h1 class="vh-hero-title">Self-Hosted Multi-Platform Video Library</h1>
    <p class="vh-hero-lead">
      VidHarbor (影坞) is a self-hosted web application for homelab operators and media archivers. It removes the friction of fragmented platform extractors, expiring short links, and inconsistent codecs by turning links, trending charts, and scheduled feeds from <strong>YouTube, Bilibili, TikTok, and Douyin</strong> into a normalized local <strong>MP4 (H.265/H.264 + AAC + faststart)</strong> library indexed in SQLite.
    </p>
    <div class="vh-cta-row">
      <a class="vh-btn vh-btn-primary" :href="withBase('/guide/quickstart.html')">Get Started →</a>
      <a class="vh-btn vh-btn-secondary" :href="withBase('/reference/architecture.html')">Architecture & Pipeline</a>
      <a class="vh-btn vh-btn-secondary" href="https://github.com/cyber-tao/VidHarbor" target="_blank" rel="noopener">GitHub Source ↗</a>
    </div>
    <div class="vh-quick-cmd">
      <div>git clone https://github.com/cyber-tao/VidHarbor.git &amp;&amp; cd VidHarbor</div>
      <div>./deploy.sh &nbsp;# Linux / macOS / WSL (or .\deploy.ps1 on Windows PowerShell)</div>
      <div class="vh-quick-cmd-note">Requires Docker with Compose v2. Opens the web console at <code>http://127.0.0.1:8666</code>.</div>
    </div>
  </div>

  <figure class="vh-figure">
    <img :src="withBase('/screenshots/dashboard-en-dark.png')" alt="VidHarbor Web Console Dashboard in English Dark mode showing video totals, storage usage, platform breakdown donut chart, 14-day intake bar chart, quick download box, and recent tasks" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>Question answered:</strong> What does the running console deliver after deployment? <strong>Conclusion:</strong> A single-port FastAPI + Vue 3 console (`:8666`) with live SSE task progress, platform distribution, 14-day intake telemetry, and instant paste-to-download. (Captured from running v0.3.0 instance with seeded demo library.)
    </figcaption>
  </figure>
</div>

## From Messy Share Text to an Indexed Local MP4 Archive {#problem-to-result}

Mobile apps rarely give you clean URLs or uniform media streams: sharing from Douyin, TikTok, or Bilibili produces promotional text mixed with short links (`v.douyin.com`, `vm.tiktok.com`, `b23.tv`), and downloaded streams arrive in mismatched containers (`webm`, `mkv`, fragmented `mp4`) with varying codecs (`vp9`, `av01`, `hev1`, `avc1`).

### Input: Raw Share Copy or Multi-Chart Selection

```text
7.43 复制打开抖音，看看【极客工坊的作品】万兆家庭影音库理线实录 https://v.douyin.com/iY8xYz1/
Also grab: https://youtu.be/dQw4w9WgXcQ and https://www.bilibili.com/video/BV1GJ411x7h7
```

### Output: Normalized Files on Disk + Indexed SQLite Record

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

Every archived video is probed with `ffprobe`, remuxed or transcoded to `+faststart` MP4 (`hvc1` tag for Apple/QuickTime HEVC playback), and indexed in SQLite (`videos`, `subtitles`, `tags`) so subtitles can be streamed to the browser as `<track>` WebVTT or loaded automatically by local players (VLC, IINA, PotPlayer).

## Why Choose VidHarbor {#why-vidharbor}

<div class="vh-grid-3">
  <div class="vh-card">
    <h3>1. Lossless-First Unified MP4 Pipeline</h3>
    <p>When targeting H.265 (default), streams already encoded in HEVC+AAC are losslessly remuxed (<code>-c:v copy -tag:v hvc1</code>) instead of re-encoded. Non-HEVC sources automatically probe hardware encoders (<code>hevc_nvenc</code>, <code>hevc_qsv</code>, <code>hevc_amf</code>, <code>hevc_videotoolbox</code>) before falling back to <code>libx265</code>.</p>
  </div>
  <div class="vh-card">
    <h3>2. Pre-Download ID Deduplication &amp; Fallback</h3>
    <p>Canonical video IDs (<code>BV...</code>, 11-char YouTube IDs, numeric aweme IDs, plus multi-part <code>_p1</code> equivalence) are checked against active queue tasks and SQLite <em>before</em> invoking <code>yt-dlp</code>. When Douyin/TikTok block <code>yt-dlp</code> via <code>a_bogus</code>, VidHarbor falls back to a local Evil0ctal v5 stack.</p>
  </div>
  <div class="vh-card">
    <h3>3. Trending Charts &amp; APScheduler Automation</h3>
    <p>Browse Bilibili (site-wide, 8 regions, Weekly Must-Watch, Classics), YouTube (Data API v3 → InnerTube → yt-dlp), Douyin Hot Search + signed keyword video search, and TikTok hashtags. Combine multiple charts into scheduled jobs that skip existing videos automatically.</p>
  </div>
</div>

### Measured Post-Processing Behavior: Lossless Remux vs Software Transcode

<div class="vh-chart-box">
  <div class="vh-chart-title">Post-Processing Time to Target H.265 MP4 (+faststart, hvc1 tag) — Lower is Faster</div>
  <div class="vh-chart-meta">Workload: 5.0s 1920×1080 @ 30fps synthetic video + 48kHz AAC audio · FFmpeg 9.0 · 1 warmup + 5 measured runs · Checked 2026-10-24 (v0.3.0, commit 435b7ca)</div>
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
  <div style="font-size: 0.78rem; color: var(--vh-text-2); margin-top: 0.5rem;">
    <strong>Conclusion:</strong> Stream-copy remuxing completes <strong>3.9× faster</strong> (74.1% time reduction) with zero generation loss and does not consume the global transcode concurrency semaphore. See <a :href="withBase('/reference/evidence.html')">Verification &amp; Evidence</a> and <a :href="withBase('/evidence/postprocess-benchmark.json')" target="_blank">raw JSON data</a> for reproduction commands and limitations.
  </div>
</div>

## End-to-End Execution Pipeline {#pipeline}

<div class="vh-pipeline">
  <div class="vh-step">
    <div class="vh-step-num">STAGE 01</div>
    <div class="vh-step-title">Ingest &amp; Dedup</div>
    <div class="vh-step-desc">Extract URLs from share copy, expand <code>v.douyin</code> / <code>vm.tiktok</code> / <code>b23.tv</code> short links, resolve canonical IDs, and skip items already queued or in SQLite.</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 02</div>
    <div class="vh-step-title">Dual-Engine Fetch</div>
    <div class="vh-step-desc">Enforce global and per-platform concurrency caps. Run <code>yt-dlp</code> with per-platform cookies/proxy; switch to Evil0ctal v5 on Douyin/TikTok extractor failure.</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 03</div>
    <div class="vh-step-title">FFprobe &amp; Normalize</div>
    <div class="vh-step-desc">Inspect streams via <code>ffprobe</code>. Remux matching codecs directly or acquire a transcode slot for hardware/CPU encoding into <code>+faststart</code> MP4.</div>
  </div>
  <div class="vh-step">
    <div class="vh-step-num">STAGE 04</div>
    <div class="vh-step-title">Archive &amp; Stream</div>
    <div class="vh-step-desc">Sanitize filenames per template, persist SRT subtitles + tags in SQLite (WAL), and broadcast task/stats updates to the browser via Server-Sent Events (SSE).</div>
  </div>
</div>

## Web Console Walkthrough: Bilingual & Dual-Theme {#console-walkthrough}

The built-in web console supports **English** and **Simplified Chinese (`简体中文`)** alongside **Dark** and **Light** themes, accessible directly from the sidebar toolbar or Settings page.

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
      <strong>Video Library &amp; Tag Filter (Dark):</strong> Full-text search, platform tabs, AND-combined tag filtering, duration/subtitle badges, and HTML5 Range streaming player.
    </figcaption>
  </figure>
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/schedules-en-dark.png')" alt="VidHarbor Schedules view showing automated daily and weekly multi-chart download jobs" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>Scheduled Jobs (Dark):</strong> Combine multiple platform charts (`platform × category × period × TopN`) under daily, weekly, interval, or cron triggers.
    </figcaption>
  </figure>
  <figure class="vh-figure">
    <img :src="withBase('/screenshots/settings-en-light.png')" alt="VidHarbor Settings view in Light theme showing Appearance & Language, Default Download Options, and Concurrency controls" width="1440" height="900" />
    <figcaption class="vh-figcaption">
      <strong>Settings Center (Light):</strong> Runtime overrides for resolution, subtitle/audio languages, proxy routing, concurrency caps, encoder selection, and platform cookies.
    </figcaption>
  </figure>
</div>

## Who It Fits, Alternatives & Limitations {#fit-and-limitations}

| Decision Criterion | Raw `yt-dlp` + `ffmpeg` CLI | Generic Single-URL Web Wrappers (e.g. MeTube) | VidHarbor (`v0.3.0`) |
| --- | --- | --- | --- |
| **Primary workflow** | Ad-hoc terminal commands & shell scripts | Manual single/playlist URL pasting in browser | Paste share text, browse 4-platform charts, or schedule recurring chart intake |
| **Douyin / TikTok anti-bot (`a_bogus` / `X-Bogus`)** | Manual cookie/extractor workarounds; Douyin extractor frequently blocked | Depends solely on `yt-dlp` | Automatic fallback to local Evil0ctal v5 stack + signed Douyin/TikTok chart APIs |
| **Output consistency** | Manual flags per invocation | Varies by source stream unless custom post-args configured | Automatic `ffprobe` → lossless `hvc1` remux or hardware-first HEVC/H.264 `+faststart` MP4 |
| **Local library & subtitles** | Flat files on disk | Download folder listing | SQLite (WAL) index with tag aggregation, full-text search, and in-browser VTT `<track>` player |
| **Resource footprint** | Minimal (CLI only) | Lightweight container | Lightweight core (~Python + FFmpeg); optional Evil0ctal v5 stack requires ~5 GB disk / ~8 GB RAM |

### When Another Approach Fits Better & Known Limitations

- **You only need occasional one-off CLI downloads:** Use [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) directly in your terminal without running a persistent web service.
- **Image/photo-carousel posts (`图集`):** VidHarbor only indexes video streams (`ensure_mp4` rejects files without a video stream); Douyin/TikTok photo posts are skipped.
- **Douyin/TikTok signing & fallback requirements:** Douyin keyword search, TikTok hashtag charts, and Douyin/TikTok fallback downloads require running the companion Evil0ctal v5 stack (deployed automatically by `./deploy.sh` / `.\deploy.ps1` when `WITH_EVIL0CTAL=1`) plus valid platform cookies.
- **Single-worker scheduler constraint:** APScheduler runs inside the FastAPI process; always run a single `uvicorn` worker (the default in `run.py` and `Dockerfile`) to prevent duplicate schedule execution.
- **Browser HEVC playback:** Playing H.265 videos directly inside the web browser depends on client OS/GPU hardware decoding support (native in Safari; requires hardware HEVC extensions in Chrome/Edge). Switch `library.video_codec` to `h264` in Settings if universal in-browser playback is preferred over disk savings.

## Explore the Manual {#explore-manual}

<div class="vh-grid-2">
  <div class="vh-card">
    <h3>🚀 <a :href="withBase('/guide/quickstart.html')">Quickstart Guide</a></h3>
    <p>Deploy with Docker in one command or run bare-metal on Windows, Linux, and macOS with <code>uv</code>, Node.js, and <code>ffmpeg</code>, then complete your first video download.</p>
  </div>
  <div class="vh-card">
    <h3>🐳 <a :href="withBase('/guide/deployment.html')">Docker, GPU &amp; Evil0ctal Deployment</a></h3>
    <p>Configure NVIDIA NVENC / Intel QSV hardware transcoding, Evil0ctal v5 automatic provisioning, and <code>TOKEN</code> / <code>BIND_IP</code> access control.</p>
  </div>
  <div class="vh-card">
    <h3>🍪 <a :href="withBase('/guide/cookies-and-auth.html')">Cookies &amp; Login Management</a></h3>
    <p>Sign in via Bilibili QR code, upload Netscape <code>cookies.txt</code>, or import from local browsers (including Chrome/Edge 127+ App-Bound Encryption workarounds).</p>
  </div>
  <div class="vh-card">
    <h3>📖 <a :href="withBase('/reference/configuration.html')">Configuration &amp; API Reference</a></h3>
    <p>Inspect every <code>config.toml</code> field, <code>VIDHARBOR_*</code> environment variable, REST endpoint, and SSE event payload.</p>
  </div>
</div>
