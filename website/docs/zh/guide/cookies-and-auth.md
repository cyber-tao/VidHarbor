# 登录管理与 Cookies 配置

VidHarbor 在 `data/cookies/{platform}.txt` 下为每个平台维护独立的 Netscape 格式 cookies 文件（`bilibili.txt`、`youtube.txt`、`tiktok.txt`、`douyin.txt`）。平台专属 cookies 优先于 `config.toml` 中的全局 `download.cookies_file`，且在上传或导入时严格按平台域名白名单（`PLATFORM_DOMAINS`）过滤，确保不会跨站点外发登录态。

![VidHarbor 设置页中文浅色主题实拍](/screenshots/settings-zh-light.png)

## 1. 各平台为什么需要配置 Cookies {#why-cookies}

| 平台 | 允许的 Cookie 域名白名单 | 配置后解锁的能力 |
| --- | --- | --- |
| **哔哩哔哩 (`bilibili`)** | `.bilibili.com`, `.biliapi.net`, `.bilivideo.com`, `.hdslb.com`, `.acgvideo.com` | 1080P+ 高码率与 4K 画质、CC/AI 字幕下载、「每周必看」榜单，以及缓解 `-352` 接口风控 |
| **YouTube (`youtube`)** | `.youtube.com`, `.google.com`, `.googlevideo.com`, `.youtube-nocookie.com` | 年龄限制/会员视频、高清晰度流，以及绕过 `Sign in to confirm you're not a bot` 校验 |
| **TikTok (`tiktok`)** | `.tiktok.com`, `.tiktokcdn.com`, `.tiktokv.com` | 热门与自定义标签榜拉取（需含 `ttwid` / `sessionid` 并配合 Evil0ctal `/tools/sign` 签名） |
| **抖音 (`douyin`)** | `.douyin.com`, `.douyinpic.com`, `.douyinvod.com`, `.zjcdn.com`, `.bytegoofp.com` | 热门榜单页与定时任务中的关键词视频搜索（需含 `ttwid` 并配合 Evil0ctal `/tools/sign` 签名） |

## 2. 方式 A：B站手机扫码登录（B站首选） {#bilibili-qr}

1. 打开 Web 控制台 **设置 → 登录管理（cookies）**。
2. 在 **哔哩哔哩** 卡片点击 **扫码登录**。
3. 使用手机哔哩哔哩 App 扫描弹出的二维码并在手机端确认。
4. 服务端每 2 秒轮询一次扫码状态，成功后自动将包含 `#HttpOnly_` `SESSDATA` 的登录态写入 `data/cookies/bilibili.txt`，并在卡片上展示当前登录昵称（`✓ 已配置 · <昵称>`）。

## 3. 方式 B：上传 `cookies.txt`（通用方式，Docker 部署必选） {#upload-cookies}

1. 在本地浏览器安装 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 扩展（或 Firefox 同类 Netscape 格式导出扩展）。
2. 在浏览器登录对应站点（`bilibili.com`、`youtube.com`、`tiktok.com` 或 `douyin.com`），使用扩展导出 Netscape 格式的 `.txt` 文件。
3. 在 **设置 → 登录管理（cookies）** 对应平台卡片点击 **上传 cookies.txt** 选择文件。
4. 后端会校验 7 列 Netscape 格式（完整保留 `#HttpOnly_` 前缀行），过滤出属于该平台域名的条目并保存至 `data/cookies/{platform}.txt`。

## 4. 方式 C：从本机浏览器一键导入（仅限同机裸机部署） {#import-browser}

当 VidHarbor **裸机运行在你的桌面电脑上**时：

1. 先在本机浏览器（支持 `firefox`、`chrome`、`edge`、`brave`、`chromium`、`opera`、`vivaldi`、`safari`）登录目标网站。
2. 在对应平台卡片下拉框选择浏览器，点击 **从浏览器导入**。

### 浏览器导入的已知系统限制

- **Docker 容器无法直接读取宿主机浏览器：** 容器内没有宿主机浏览器环境，请使用 **方式 A（B站扫码）** 或 **方式 B（上传 `cookies.txt`）**。
- **Windows 文件锁限制（`yt-dlp #7271`）：** Windows 下 Chromium 系浏览器运行期间会锁定 cookies 数据库，需完全退出浏览器（含后台托盘进程）后再点导入。
- **Chrome / Edge 127+ 应用绑定加密（`yt-dlp #10927`）：** 新版 Chrome/Edge 在 Windows 上启用了 App-Bound Encryption（`app_bound_encrypted_key`），外部进程无法解密 v20 cookies。VidHarbor 检测到该加密时会直接提示改用 **Get cookies.txt LOCALLY** 扩展导出上传，或改用 **Firefox** 登录后从 Firefox 导入。
