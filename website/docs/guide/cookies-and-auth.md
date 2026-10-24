# Platform Cookies & Login Management

VidHarbor maintains isolated per-platform cookie files under `data/cookies/{platform}.txt` (`bilibili.txt`, `youtube.txt`, `tiktok.txt`, `douyin.txt`). Per-platform cookies take priority over the global fallback `download.cookies_file` in `config.toml`, and every uploaded or imported cookie jar is filtered by domain (`PLATFORM_DOMAINS`) so credentials from one platform are never sent to another.

![VidHarbor Settings page in Light theme](/screenshots/settings-en-light.png)

## 1. Why Each Platform Needs Cookies {#why-cookies}

| Platform | Allowed Cookie Domains | What Cookies Unlock |
| --- | --- | --- |
| **Bilibili** | `.bilibili.com`, `.biliapi.net`, `.bilivideo.com`, `.hdslb.com`, `.acgvideo.com` | 1080P+ / 4K streams, subtitle downloads (`zh-CN` / AI subtitles), *Weekly Must-Watch* (`每周必看`) chart, and avoiding `-352` risk-control errors |
| **YouTube** | `.youtube.com`, `.google.com`, `.googlevideo.com`, `.youtube-nocookie.com` | Age-restricted or member videos, high-bitrate streams, and bypassing `Sign in to confirm you're not a bot` checks |
| **TikTok** | `.tiktok.com`, `.tiktokcdn.com`, `.tiktokv.com` | Hashtag trending charts (`ttwid` + `sessionid` required alongside Evil0ctal `/tools/sign`) |
| **Douyin** | `.douyin.com`, `.douyinpic.com`, `.douyinvod.com`, `.zjcdn.com`, `.bytegoofp.com` | Keyword video search in Trending Charts & Schedules (`ttwid` required alongside Evil0ctal `/tools/sign`) |

## 2. Method A: Bilibili QR Code Login (Recommended for Bilibili) {#bilibili-qr}

1. Open **Settings → Login Management (Cookies)** in the VidHarbor web console.
2. On the **Bilibili** card, click **QR Login**.
3. Scan the displayed QR code using the Bilibili mobile app and confirm on your phone.
4. VidHarbor polls the login status every 2 seconds, writes the resulting cookies (including `#HttpOnly_` `SESSDATA`) to `data/cookies/bilibili.txt`, and displays your Bilibili nickname on the card (`✓ Configured · <nickname>`).

## 3. Method B: Upload `cookies.txt` (Works Everywhere, Including Docker) {#upload-cookies}

1. Install the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension in Chrome, Edge, or Brave (or an equivalent Netscape cookie exporter in Firefox).
2. Log in to the target site (`bilibili.com`, `youtube.com`, `tiktok.com`, or `douyin.com`) and export the cookies in **Netscape HTTP Cookie File** format.
3. In **Settings → Login Management (Cookies)**, click **Upload cookies.txt** on the corresponding platform card and select the exported `.txt` file.
4. VidHarbor validates the 7-column Netscape format (preserving `#HttpOnly_` entries), keeps only domains matching that platform, and saves `data/cookies/{platform}.txt`.

## 4. Method C: Import from Local Browser (Bare-Metal Only) {#import-browser}

If VidHarbor is running **bare-metal on the same machine** as your desktop browser:

1. Log in to the target platform in your browser (`firefox`, `chrome`, `edge`, `brave`, `chromium`, `opera`, `vivaldi`, or `safari`).
2. Select the browser in the platform card dropdown and click **Import from Browser**.

### Known Browser Import Constraints

- **Docker containers cannot read host browsers:** Inside Docker, use **Method A (Bilibili QR)** or **Method B (Upload `cookies.txt`)**.
- **Windows file locking (`yt-dlp #7271`):** Chromium browsers lock their SQLite cookie database while running on Windows. Fully close the browser (including system tray processes) before clicking **Import from Browser**.
- **Chrome / Edge 127+ App-Bound Encryption (`yt-dlp #10927`):** Recent Chrome, Edge, and Brave builds on Windows encrypt cookies using `app_bound_encrypted_key` (v20 DPAPI). VidHarbor detects this in `Local State` and returns an actionable message: export via the **Get cookies.txt LOCALLY** extension and upload, or log in with **Firefox** and import from Firefox.
