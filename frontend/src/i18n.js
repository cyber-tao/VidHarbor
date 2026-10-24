import { computed, ref, watch } from 'vue'

const THEME_KEY = 'vidharbor-theme'
const LOCALE_KEY = 'vidharbor-locale'

function readInitialTheme() {
  try {
    const url = new URL(location.href)
    const q = url.searchParams.get('theme')
    if (q === 'light' || q === 'dark') return q
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* storage blocked */ }
  return 'dark'
}

function readInitialLocale() {
  try {
    const url = new URL(location.href)
    const q = url.searchParams.get('lang')
    if (q === 'zh' || q === 'zh-CN') return 'zh'
    if (q === 'en') return 'en'
    const saved = localStorage.getItem(LOCALE_KEY)
    if (saved === 'zh' || saved === 'en') return saved
  } catch { /* storage blocked */ }
  return 'en'
}

export const theme = ref(readInitialTheme())
export const locale = ref(readInitialLocale())

export const isDark = computed(() => theme.value === 'dark')
export const isZh = computed(() => locale.value === 'zh')

function applyThemeDom(val) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.remove('dark', 'light')
  root.classList.add(val)
  root.style.colorScheme = val
}

function applyLocaleDom(val) {
  if (typeof document === 'undefined') return
  document.documentElement.lang = val === 'zh' ? 'zh-CN' : 'en'
  document.title = val === 'zh'
    ? 'VidHarbor「影坞」· 本地视频库'
    : 'VidHarbor · Self-Hosted Video Library'
}

applyThemeDom(theme.value)
applyLocaleDom(locale.value)

watch(theme, (val) => {
  applyThemeDom(val)
  try { localStorage.setItem(THEME_KEY, val) } catch { /* ignore */ }
})

watch(locale, (val) => {
  applyLocaleDom(val)
  try { localStorage.setItem(LOCALE_KEY, val) } catch { /* ignore */ }
})

export function setTheme(next) {
  if (next === 'dark' || next === 'light') theme.value = next
}

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

export function setLocale(next) {
  if (next === 'zh' || next === 'en') locale.value = next
}

const MESSAGES = {
  zh: {
    app: {
      subtitle: '影坞 · 本地视频库',
      nav: {
        dashboard: '仪表盘',
        charts: '热门榜单',
        tasks: '下载任务',
        library: '视频库',
        schedules: '定时任务',
        settings: '设置',
      },
      sseConnected: '实时连接正常',
      sseDisconnected: '连接已断开',
      tokenRequired: '需要访问令牌',
      tokenDesc: '服务端设置了访问令牌（.env 中的 TOKEN）。输入后本浏览器会记住登录状态。',
      tokenPlaceholder: '访问令牌',
      tokenSubmit: '进入',
      langLabel: '选择语言',
      switchToLight: '切换到浅色主题',
      switchToDark: '切换到深色主题',
      githubLabel: 'GitHub 仓库',
    },
    platforms: {
      youtube: 'YouTube',
      bilibili: '哔哩哔哩',
      tiktok: 'TikTok',
      douyin: '抖音',
      other: '其他',
      all: '全部',
    },
    dashboard: {
      title: '仪表盘',
      statsError: '统计加载失败: ',
      unifiedMp4: '统一 MP4',
      cardTotalVideos: '视频总数',
      cardTodayNew: '{n} 今日新增',
      cardDiskUsage: '存储占用',
      cardActiveTasks: '进行中任务',
      cardQueued: '{n} 排队',
      cardPlatforms: '平台覆盖',
      cardPlatformsSub: 'YouTube·B站·TikTok·抖音',
      chartPlatformDist: '平台分布',
      chartIntake14d: '近 14 天入库',
      quickDownload: '快速下载',
      quickPlaceholder: '粘贴视频链接或 App 分享文案，自动提取链接\n支持 YouTube / B站 / TikTok / 抖音',
      quickSubmit: '添加到下载队列',
      noValidUrls: '未在输入中识别到有效链接',
      recentTasks: '最近任务',
      viewAll: '全部 →',
      noTasks: '暂无任务',
      downloadOptions: '下载选项',
    },
    status: {
      pending: '排队中',
      running: '下载中',
      completed: '完成',
      failed: '失败',
      canceled: '已取消',
    },
    stage: {
      downloading: '下载中',
      merging: '合并流',
      processing: '转码/入库',
      done: '完成',
    },
    optionsDialog: {
      defaultTitle: '下载选项',
      videoCount: '{n} 个视频',
      useDefault: '使用默认设置（在「设置」页可改默认值）',
      maxHeight: '最高清晰度',
      bestUnlimited: '最佳（不限）',
      targetCodec: '目标编码',
      codecH265: 'H.265 (HEVC，省空间)',
      codecH264: 'H.264 (兼容最好)',
      subLangs: '字幕语言（逗号分隔，支持正则）',
      audioLangs: '音轨语言偏好（逗号分隔，按顺序；留空=原声）',
      cancel: '取消',
      submitting: '提交中…',
      startDownload: '开始下载',
      addedMsg: '已添加 {n} 个下载任务',
      skippedMsg: '（跳过 {n} 个已在队列）',
    },
    logDrawer: {
      title: '日志',
      empty: '暂无日志',
      resumeScroll: '继续滚动',
      pauseScroll: '暂停滚动',
      clear: '清空',
    },
    charts: {
      title: '热门榜单',
      refreshing: '刷新中…',
      refresh: '刷新榜单',
      downloadSelected: '下载所选 ({n})',
      customYoutube: '自定义关键词，如「AI」…',
      customDouyin: '自定义关键词，如「猫咪」…',
      customTiktok: '自定义标签，如 cats…',
      searchBtn: '查询',
      hint: '点击卡片打开原网页 · 勾选右上角选择下载',
      deselectAll: '取消全选',
      selectAll: '全选',
      periodLabel: '周期',
      douyinKeywordResult: '🔍 关键词「{kw}」的视频结果',
      douyinKeywordHint: '· 勾选后即可批量下载',
      backToHot: '← 返回热搜榜',
      douyinTopicNotice1: '抖音热搜为',
      douyinTopicNoticeBold: '话题榜',
      douyinTopicNotice2: '：点击热搜词查看该话题的视频并勾选下载，也可在上方输入关键词直接搜索。需要已在「设置 → 登录管理」导入抖音 cookies，并启动 Evil0ctal 签名服务（见 README）。',
      emptyChart: '榜单数据为空',
      emptyRetry: '，点击右上角刷新重试',
      unselectVideo: '取消选择',
      selectVideo: '选择此视频下载',
      searchVideosBadge: '🔍 搜视频',
      topicVideosBadge: '↗ 话题视频',
      videoCount: '{n} 个视频',
      likesTitle: '点赞',
      viewsTitle: '播放/热度',
      officialApi: '官方API',
      batchOptionsTitle: '批量下载选项',
    },
    tasks: {
      title: '下载任务',
      batchAdd: '批量添加',
      placeholder: '粘贴视频链接或 App 分享文案（自动提取链接，支持批量）',
      addBtn: '添加任务',
      emptyText: '暂无任务 —— 去热门榜单批量下载，或在上方粘贴链接',
      browseCharts: '浏览热门榜单 →',
      fromScheduleTitle: '来自定时任务',
      cancelBtn: '取消',
      retryBtn: '重试',
      viewBtn: '查看',
      deleteBtn: '删除',
      cancelingMsg: '任务取消中',
      requeuedMsg: '已重新排队',
    },
    library: {
      title: '视频库',
      videoCount: '{n} 个视频',
      searchPlaceholder: '搜索标题 / 作者 / 简介…',
      tagFilter: '标签筛选',
      tagAndHint: '（多选为同时满足）',
      clearTags: '清除 × {n}',
      emptyFiltered: '当前筛选没有匹配视频',
      emptyLibrary: '库还是空的',
      goCharts: '去热门榜单挑几个视频 →',
    },
    videoDetail: {
      back: '返回',
      loading: '加载中…',
      browserNoVideo: '您的浏览器不支持视频播放。',
      fileMissing: '⚠️ 视频文件缺失（可能已被手动删除）',
      unknownAuthor: '未知作者',
      viewsSuffix: '{n} 播放',
      description: '简介',
      techInfo: '技术信息',
      resolution: '分辨率',
      codec: '编码',
      fileSize: '大小',
      createdAt: '入库时间',
      storagePath: '存储路径（绝对路径）',
      copyTitle: '一键复制',
      copyBtn: '复制',
      pathCopied: '路径已复制',
      openSource: '打开来源页',
      deleting: '删除中…',
      deleteVideo: '删除视频',
      confirmDelete: '确认删除「{title}」？视频文件与字幕将一并移除。',
      deletedMsg: '已删除',
      subtitlesTitle: '字幕（{n}）',
      noSubtitles: '无字幕（B站/YouTube 需在「设置 → 登录管理」配置 cookies 才能拿到字幕）',
      disableSub: '关闭字幕',
      currentSub: '当前',
      autoTag: ' · 自动',
      autoParen: '（自动生成）',
      playingSub: '播放中',
      selectSub: '选为播放字幕',
      viewSub: '查看 →',
      subModalPrefix: '字幕 · ',
      loadFailed: '加载失败: ',
    },
    schedules: {
      title: '定时任务',
      subtitle: '按时间自动下载榜单内容，库中已有的视频自动跳过',
      createBtn: '+ 新建定时任务',
      loading: '加载中…',
      emptyTitle: '还没有定时任务',
      emptyExample: '例如：每天 9 点自动下载 B站游戏区周榜 Top10 + YouTube 音乐月榜 Top5',
      enabled: '启用',
      disabled: '停用',
      enableBtn: '启用',
      disableBtn: '停用',
      runningBtn: '启动中…',
      runNowBtn: '立即运行',
      editBtn: '编辑',
      deleteBtn: '删除',
      nextRun: '下次运行：',
      lastRun: '上次运行：',
      resCreated: '新建 {n}',
      resSkipped: '跳过 {n}',
      resFailed: '失败 {n}',
      editTitle: '编辑定时任务',
      newTitle: '新建定时任务',
      nameLabel: '任务名称',
      namePlaceholder: '如：每日热榜自动追更',
      runTimeLabel: '运行时间',
      modeDaily: '每天',
      modeWeekly: '每周',
      modeInterval: '间隔',
      modeCron: 'Cron',
      timeLabel: '时间',
      everyPrefix: '每',
      everyMinutesSuffix: '分钟运行一次',
      cronLabel: 'Cron 表达式',
      chartCombo: '榜单组合',
      addChart: '+ 添加榜单',
      customOption: '自定义…',
      customPlaceholder: '关键词 / 标签',
      removeBtn: '移除',
      useGlobalDefault: '使用全局默认下载选项',
      maxHeight: '最高清晰度',
      targetCodec: '目标编码',
      subLangsHint: '字幕语言（留空=全局默认）',
      cancelBtn: '取消',
      savingBtn: '保存中…',
      saveBtn: '保存',
      errNameRequired: '请填写任务名',
      errSelectionRequired: '至少添加一个榜单选择',
      errCustomRequired: '自定义关键词不能为空',
      updatedMsg: '已更新',
      createdMsg: '已创建',
      confirmDelete: '确认删除定时任务「{name}」？',
      weekdays: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    },
    settings: {
      title: '设置',
      saving: '保存中…',
      saveBtn: '保存设置',
      savedMsg: '设置已保存',
      unsavedChanges: '有未保存的修改',
      copiedMsg: '已复制',
      copyFailed: '复制失败',
      appearanceTitle: '界面语言与主题',
      languageLabel: '界面语言 (Language)',
      themeLabel: '界面主题 (Theme)',
      themeDark: '深色 (Dark)',
      themeLight: '浅色 (Light)',
      downloadTitle: '下载默认选项',
      maxHeight: '最高清晰度',
      heightRecommended: '1080p（推荐）',
      subLangs: '字幕语言（逗号分隔，支持正则）',
      audioLangs: '音轨语言偏好（逗号分隔按顺序，留空=原声；多音轨视频只下载首选一条）',
      proxyLabel: '出口代理（http://host:port 或 socks5://host:port，留空=不用；勾选平台的下载与榜单请求走代理）',
      proxyPlatforms: '走代理的平台',
      concurrencyTitle: '并发与性能',
      globalDownloadConcurrency: '全局并发下载（各平台合计）',
      perPlatformConcurrency: '每平台并发下载',
      nConcurrentDownloads: '{n} 个同时下载',
      globalTranscodeConcurrency: '全局并发转码',
      nConcurrentTranscodes: '{n} 个同时转码',
      concurrencyNote: '「每平台并发」限制同一平台同时下载的任务数（建议 1–2，防止触发风控/限速）；某平台满员时其他平台的任务照常调度。「全局并发转码」限制整个系统同时进行的转码数——转码非常吃 CPU/GPU，即使多个任务同时下载完，超出上限的也会排队等待（无损 remux 不占额度）。修改保存后即时生效。',
      encodingTitle: '视频编码',
      targetCodec: '入库目标编码',
      codecH265Default: 'H.265/HEVC（默认，更省空间）',
      codecH264Compat: 'H.264（浏览器兼容最好）',
      hevcEncoder: 'H.265 转码编码器',
      encoderAuto: 'auto（硬件优先，回退 libx265）',
      detectedEncoderPrefix: '当前检测到可用 HEVC 编码器：',
      detectedEncoderNote: '（源已是 HEVC 的视频直接封装不转码；HEVC 统一打 hvc1 标记保证 Apple 兼容；网页播放 HEVC 依赖浏览器/硬件支持，Safari 原生支持）',
      cookiesTitle: '登录管理（cookies）',
      cookiesNote: 'B站支持扫码登录。其他平台推荐用扩展（Get cookies.txt LOCALLY）导出后上传；注意：Chrome/Edge 127+ 启用了应用绑定加密，Windows 下无法直接「从浏览器导入」——需要完全退出浏览器才可读取数据库，且新版加密无法解密，此时请改用扩展上传或从 Firefox 导入。',
      configured: '✓ 已配置',
      notConfigured: '未配置',
      updatedAt: '更新于 {t}',
      qrLoginBtn: '扫码登录',
      openLoginPage: '打开登录页 ↗',
      uploadCookies: '上传 cookies.txt',
      importingBtn: '导入中…',
      importFromBrowser: '从浏览器导入',
      clearBtn: '清除',
      uploadedCookiesMsg: '已导入 {n} 条 cookies',
      importedBrowserMsg: '从 {b} 导入 {n} 条 cookies',
      clearedMsg: '已清除',
      evil0ctalTitle: '抖音 / TikTok 兜底引擎（Evil0ctal v5）',
      evil0ctalEnable: '启用（yt-dlp 失败时自动切换）',
      serviceUrl: '服务地址',
      apiKey: 'API Key',
      hideKey: '隐藏',
      showKey: '显示',
      evil0ctalNote: '在服务控制台 /api-keys 创建，勾选 douyin:read 与 tiktok:read；部署方法见 README。',
      clearSavedKey: '清除已保存的 Key',
      keyClearOnSave: '保存后清除',
      keyAlreadySet: '已设置（留空则保持不变）',
      ytApiTitle: 'YouTube Data API（推荐）',
      ytApiNote1: '配置后榜单优先走官方 API：真实热门榜（含点赞数/发布时间），每日免费配额个人使用足够。在',
      ytApiNote2: '启用 YouTube Data API v3 并创建 API 密钥；未配置时自动使用免登录通道（InnerTube）。',
      regionCode: '地区代码（影响热门榜内容，如 US / JP / TW / HK）',
      storageTitle: '存储与系统',
      libraryRoot: '视频库根目录（绝对路径）',
      copyBtn: '复制',
      scheduleTimezone: '定时任务时区',
      qrModalTitle: 'B站扫码登录',
      qrModalSub: '用 B站 App 扫码确认登录',
      qrAlt: '登录二维码',
      qrWaiting: '等待扫码…',
      qrScanned: '已扫描，请在手机上确认',
      qrSuccess: '登录成功',
      qrExpired: '二维码已过期',
      qrRegenerate: '重新生成',
      qrClose: '关闭',
      biliLoginSuccess: 'B站登录成功',
    },
  },
  en: {
    app: {
      subtitle: 'Self-Hosted Video Library',
      nav: {
        dashboard: 'Dashboard',
        charts: 'Trending Charts',
        tasks: 'Download Tasks',
        library: 'Video Library',
        schedules: 'Schedules',
        settings: 'Settings',
      },
      sseConnected: 'Live Stream Connected',
      sseDisconnected: 'Stream Disconnected',
      tokenRequired: 'Access Token Required',
      tokenDesc: 'An access token (TOKEN in .env) is configured on the server. Enter it once to save a session in this browser.',
      tokenPlaceholder: 'Access token',
      tokenSubmit: 'Sign In',
      langLabel: 'Select language',
      switchToLight: 'Switch to light theme',
      switchToDark: 'Switch to dark theme',
      githubLabel: 'GitHub repository',
    },
    platforms: {
      youtube: 'YouTube',
      bilibili: 'Bilibili',
      tiktok: 'TikTok',
      douyin: 'Douyin',
      other: 'Other',
      all: 'All',
    },
    dashboard: {
      title: 'Dashboard',
      statsError: 'Failed to load stats: ',
      unifiedMp4: 'Unified MP4',
      cardTotalVideos: 'Total Videos',
      cardTodayNew: '{n} added today',
      cardDiskUsage: 'Storage Used',
      cardActiveTasks: 'Active Tasks',
      cardQueued: '{n} queued',
      cardPlatforms: 'Platforms',
      cardPlatformsSub: 'YouTube · Bilibili · TikTok · Douyin',
      chartPlatformDist: 'Platform Breakdown',
      chartIntake14d: '14-Day Intake Trend',
      quickDownload: 'Quick Download',
      quickPlaceholder: 'Paste video URLs or mobile share text (links extracted automatically)\nSupports YouTube / Bilibili / TikTok / Douyin',
      quickSubmit: 'Add to Download Queue',
      noValidUrls: 'No valid video links found in the input',
      recentTasks: 'Recent Tasks',
      viewAll: 'View all →',
      noTasks: 'No tasks yet',
      downloadOptions: 'Download Options',
    },
    status: {
      pending: 'Queued',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      canceled: 'Canceled',
    },
    stage: {
      downloading: 'Downloading',
      merging: 'Merging',
      processing: 'Transcoding',
      done: 'Done',
    },
    optionsDialog: {
      defaultTitle: 'Download Options',
      videoCount: '{n} video(s)',
      useDefault: 'Use default settings (configurable in Settings)',
      maxHeight: 'Max Resolution',
      bestUnlimited: 'Best (Unlimited)',
      targetCodec: 'Target Codec',
      codecH265: 'H.265 (HEVC, smaller size)',
      codecH264: 'H.264 (Best compatibility)',
      subLangs: 'Subtitle Languages (comma-separated regex)',
      audioLangs: 'Preferred Audio Languages (ordered, blank = original)',
      cancel: 'Cancel',
      submitting: 'Submitting…',
      startDownload: 'Start Download',
      addedMsg: 'Added {n} download task(s)',
      skippedMsg: ' ({n} already queued skipped)',
    },
    logDrawer: {
      title: 'Logs',
      empty: 'No logs yet',
      resumeScroll: 'Resume Scroll',
      pauseScroll: 'Pause Scroll',
      clear: 'Clear',
    },
    charts: {
      title: 'Trending Charts',
      refreshing: 'Refreshing…',
      refresh: 'Refresh Chart',
      downloadSelected: 'Download Selected ({n})',
      customYoutube: 'Custom keyword, e.g. "AI"…',
      customDouyin: 'Custom keyword, e.g. "cats"…',
      customTiktok: 'Custom hashtag, e.g. cats…',
      searchBtn: 'Search',
      hint: 'Click card to open source page · Check top-right box to select for download',
      deselectAll: 'Deselect All',
      selectAll: 'Select All',
      periodLabel: 'Period',
      douyinKeywordResult: '🔍 Video results for "{kw}"',
      douyinKeywordHint: '· Select items to batch download',
      backToHot: '← Back to Hot Search',
      douyinTopicNotice1: 'Douyin Hot Search is a ',
      douyinTopicNoticeBold: 'topic list',
      douyinTopicNotice2: ': click any trending topic to drill into its videos for batch download, or search a keyword above. Requires Douyin cookies in Settings → Login Management and the Evil0ctal signing service.',
      emptyChart: 'No chart items returned',
      emptyRetry: ' — click Refresh in the top-right to retry',
      unselectVideo: 'Deselect video',
      selectVideo: 'Select video for download',
      searchVideosBadge: '🔍 Search videos',
      topicVideosBadge: '↗ Topic videos',
      videoCount: '{n} videos',
      likesTitle: 'Likes',
      viewsTitle: 'Views / Heat',
      officialApi: 'Official API',
      batchOptionsTitle: 'Batch Download Options',
    },
    tasks: {
      title: 'Download Tasks',
      batchAdd: 'Batch Add URLs',
      placeholder: 'Paste video URLs or mobile share text (links extracted automatically, supports batch)',
      addBtn: 'Add Tasks',
      emptyText: 'No tasks yet — batch download from Trending Charts or paste URLs above',
      browseCharts: 'Browse Trending Charts →',
      fromScheduleTitle: 'Triggered by scheduled job',
      cancelBtn: 'Cancel',
      retryBtn: 'Retry',
      viewBtn: 'View',
      deleteBtn: 'Delete',
      cancelingMsg: 'Canceling task…',
      requeuedMsg: 'Re-queued task',
    },
    library: {
      title: 'Video Library',
      videoCount: '{n} video(s)',
      searchPlaceholder: 'Search title / uploader / description…',
      tagFilter: 'Filter by Tags',
      tagAndHint: '(multi-select matches all)',
      clearTags: 'Clear × {n}',
      emptyFiltered: 'No videos match the active filters',
      emptyLibrary: 'Your video library is empty',
      goCharts: 'Pick videos from Trending Charts →',
    },
    videoDetail: {
      back: 'Back',
      loading: 'Loading…',
      browserNoVideo: 'Your browser does not support HTML5 video.',
      fileMissing: '⚠️ Video file is missing on disk (may have been removed manually)',
      unknownAuthor: 'Unknown Uploader',
      viewsSuffix: '{n} views',
      description: 'Description',
      techInfo: 'Technical Metadata',
      resolution: 'Resolution',
      codec: 'Codec',
      fileSize: 'File Size',
      createdAt: 'Indexed At',
      storagePath: 'Storage Path (Absolute)',
      copyTitle: 'Copy path',
      copyBtn: 'Copy',
      pathCopied: 'Path copied to clipboard',
      openSource: 'Open Source URL',
      deleting: 'Deleting…',
      deleteVideo: 'Delete Video',
      confirmDelete: 'Delete "{title}"? The video file and subtitle tracks will be removed from disk.',
      deletedMsg: 'Video deleted',
      subtitlesTitle: 'Subtitles ({n})',
      noSubtitles: 'No subtitles indexed (configure Bilibili/YouTube cookies in Settings → Login Management to fetch subtitles)',
      disableSub: 'Subtitles Off',
      currentSub: 'Active',
      autoTag: ' · Auto',
      autoParen: ' (Auto)',
      playingSub: 'Showing',
      selectSub: 'Use track',
      viewSub: 'Inspect →',
      subModalPrefix: 'Subtitle · ',
      loadFailed: 'Failed to load: ',
    },
    schedules: {
      title: 'Schedules',
      subtitle: 'Automatically fetch trending charts on a schedule; videos already in the library are skipped',
      createBtn: '+ New Schedule',
      loading: 'Loading…',
      emptyTitle: 'No scheduled jobs yet',
      emptyExample: 'Example: Every day at 09:00, download Bilibili Gaming Weekly Top 10 + YouTube Music Monthly Top 5',
      enabled: 'Enabled',
      disabled: 'Disabled',
      enableBtn: 'Enable',
      disableBtn: 'Disable',
      runningBtn: 'Starting…',
      runNowBtn: 'Run Now',
      editBtn: 'Edit',
      deleteBtn: 'Delete',
      nextRun: 'Next run: ',
      lastRun: 'Last run: ',
      resCreated: 'Created {n}',
      resSkipped: 'Skipped {n}',
      resFailed: 'Failed {n}',
      editTitle: 'Edit Schedule',
      newTitle: 'New Schedule',
      nameLabel: 'Job Name',
      namePlaceholder: 'e.g. Daily Trending Digest',
      runTimeLabel: 'Trigger Schedule',
      modeDaily: 'Daily',
      modeWeekly: 'Weekly',
      modeInterval: 'Interval',
      modeCron: 'Cron',
      timeLabel: 'Time',
      everyPrefix: 'Run every',
      everyMinutesSuffix: 'minutes',
      cronLabel: 'Cron Expression',
      chartCombo: 'Chart Selections',
      addChart: '+ Add Chart',
      customOption: 'Custom…',
      customPlaceholder: 'Keyword / Hashtag',
      removeBtn: 'Remove',
      useGlobalDefault: 'Use global default download options',
      maxHeight: 'Max Resolution',
      targetCodec: 'Target Codec',
      subLangsHint: 'Subtitle Languages (blank = global default)',
      cancelBtn: 'Cancel',
      savingBtn: 'Saving…',
      saveBtn: 'Save',
      errNameRequired: 'Please enter a job name',
      errSelectionRequired: 'Add at least one chart selection',
      errCustomRequired: 'Custom keyword cannot be empty',
      updatedMsg: 'Schedule updated',
      createdMsg: 'Schedule created',
      confirmDelete: 'Delete schedule "{name}"?',
      weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    },
    settings: {
      title: 'Settings',
      saving: 'Saving…',
      saveBtn: 'Save Settings',
      savedMsg: 'Settings saved',
      unsavedChanges: 'Unsaved changes',
      copiedMsg: 'Copied to clipboard',
      copyFailed: 'Copy failed',
      appearanceTitle: 'Appearance & Language',
      languageLabel: 'Interface Language',
      themeLabel: 'Color Theme',
      themeDark: 'Dark',
      themeLight: 'Light',
      downloadTitle: 'Default Download Options',
      maxHeight: 'Max Resolution',
      heightRecommended: '1080p (Recommended)',
      subLangs: 'Subtitle Languages (comma-separated regex)',
      audioLangs: 'Preferred Audio Languages (ordered, blank = original; downloads single best track)',
      proxyLabel: 'Egress Proxy (http://host:port or socks5://host:port, blank = direct; applies to selected platforms)',
      proxyPlatforms: 'Platforms Using Proxy',
      concurrencyTitle: 'Concurrency & Performance',
      globalDownloadConcurrency: 'Global Concurrent Downloads',
      perPlatformConcurrency: 'Per-Platform Concurrency',
      nConcurrentDownloads: '{n} concurrent',
      globalTranscodeConcurrency: 'Concurrent Transcodes',
      nConcurrentTranscodes: '{n} concurrent',
      concurrencyNote: '"Per-Platform Concurrency" caps simultaneous downloads per site (1–2 recommended to avoid rate-limiting); other platforms continue unaffected. "Concurrent Transcodes" caps simultaneous FFmpeg encodes — lossless remuxing does not consume a transcode slot. Changes apply immediately upon saving.',
      encodingTitle: 'Video Encoding',
      targetCodec: 'Target Library Codec',
      codecH265Default: 'H.265 / HEVC (Default, saves space)',
      codecH264Compat: 'H.264 / AVC (Maximum browser compatibility)',
      hevcEncoder: 'H.265 Hardware / Software Encoder',
      encoderAuto: 'auto (Hardware first, fallback libx265)',
      detectedEncoderPrefix: 'Detected active HEVC encoder: ',
      detectedEncoderNote: '(Sources already encoded in HEVC are remuxed losslessly without re-encoding; hvc1 tag is applied for Apple/QuickTime compatibility.)',
      cookiesTitle: 'Login Management (Cookies)',
      cookiesNote: 'Bilibili supports QR login. For other platforms, exporting via the "Get cookies.txt LOCALLY" browser extension and uploading is recommended. Note: Chrome/Edge 127+ use App-Bound Encryption on Windows, which blocks direct browser import unless you upload cookies.txt or import from Firefox.',
      configured: '✓ Configured',
      notConfigured: 'Not set',
      updatedAt: 'Updated {t}',
      qrLoginBtn: 'QR Login',
      openLoginPage: 'Open Login Page ↗',
      uploadCookies: 'Upload cookies.txt',
      importingBtn: 'Importing…',
      importFromBrowser: 'Import from Browser',
      clearBtn: 'Clear',
      uploadedCookiesMsg: 'Imported {n} cookies',
      importedBrowserMsg: 'Imported {n} cookies from {b}',
      clearedMsg: 'Cookies cleared',
      evil0ctalTitle: 'Douyin / TikTok Fallback Engine (Evil0ctal v5)',
      evil0ctalEnable: 'Enable automatic fallback when yt-dlp fails',
      serviceUrl: 'Service Base URL',
      apiKey: 'API Key',
      hideKey: 'Hide',
      showKey: 'Show',
      evil0ctalNote: 'Create a key under /api-keys in the Evil0ctal console with douyin:read and tiktok:read scopes. See README for deployment.',
      clearSavedKey: 'Clear saved key',
      keyClearOnSave: 'Will clear on save',
      keyAlreadySet: 'Configured (leave blank to keep)',
      ytApiTitle: 'YouTube Data API v3 (Recommended)',
      ytApiNote1: 'When configured, YouTube charts use the official Data API v3 (mostPopular + view counts/likes). Enable YouTube Data API v3 in ',
      ytApiNote2: ' and create an API key; when blank, VidHarbor falls back to InnerTube search.',
      regionCode: 'Region Code (ISO 3166-1 alpha-2, e.g. US / JP / TW / HK)',
      storageTitle: 'Storage & System',
      libraryRoot: 'Library Root Directory (Absolute Path)',
      copyBtn: 'Copy',
      scheduleTimezone: 'Scheduler Timezone (IANA)',
      qrModalTitle: 'Bilibili QR Login',
      qrModalSub: 'Scan with the Bilibili mobile app to sign in',
      qrAlt: 'Bilibili login QR code',
      qrWaiting: 'Waiting for scan…',
      qrScanned: 'Scanned — please confirm on your phone',
      qrSuccess: 'Signed in',
      qrExpired: 'QR code expired',
      qrRegenerate: 'Regenerate',
      qrClose: 'Close',
      biliLoginSuccess: 'Bilibili login succeeded',
    },
  },
}

export function t(path, params = {}) {
  const dict = MESSAGES[locale.value] || MESSAGES.en
  const parts = path.split('.')
  let cur = dict
  for (const p of parts) {
    cur = cur?.[p]
  }
  if (typeof cur !== 'string') return path
  return cur.replace(/\{(\w+)\}/g, (_, k) => (params[k] !== undefined ? String(params[k]) : `{${k}}`))
}

const CATEGORY_EN = {
  bilibili: {
    all: 'All',
    '1': 'Anime',
    '3': 'Music',
    '4': 'Gaming',
    '5': 'Entertainment',
    '36': 'Knowledge',
    '188': 'Tech',
    '23': 'Movies',
    '119': 'Kichiku',
    weekly: 'Weekly Must-Watch',
    precious: 'All-Time Classics',
  },
  youtube: {
    trending: 'Trending',
    music: 'Music',
    gaming: 'Gaming',
    tech: 'Tech',
    movie: 'Movies & TV',
    podcast: 'Podcasts',
  },
  douyin: {
    hot: 'Hot Search',
  },
}

export function tCategory(platform, id, fallbackName = '') {
  if (locale.value === 'zh') return fallbackName || id
  return CATEGORY_EN[platform]?.[id] || fallbackName || id
}

const PERIOD_EN = {
  default: 'Overall',
  '3d': '3-Day',
  week: 'Weekly',
  day: 'Today',
  month: 'This Month',
}

export function tPeriod(id, fallbackName = '', platform = '') {
  if (locale.value === 'zh') return fallbackName || id
  if (id === 'default') {
    if (platform === 'douyin') return 'Live'
    if (platform === 'tiktok') return 'All Time'
    return 'Overall'
  }
  if (id === 'week' && platform === 'youtube') return 'This Week'
  return PERIOD_EN[id] || fallbackName || id
}

const BADGE_LABEL_EN = {
  爆: 'Viral',
  热: 'Hot',
  新: 'New',
  首发: 'Debut',
}

export function tBadgeLabel(label) {
  if (locale.value === 'zh') return label
  return BADGE_LABEL_EN[label] || label
}

export function tPublished(raw) {
  if (!raw || locale.value === 'zh') return raw
  return String(raw)
    .replace(/(\d+)\s*分钟前/, '$1m ago')
    .replace(/(\d+)\s*小时前/, '$1h ago')
    .replace(/(\d+)\s*天前/, '$1d ago')
    .replace(/(\d+)\s*周前/, '$1w ago')
    .replace(/(\d+)\s*个月前/, '$1mo ago')
    .replace(/(\d+)\s*年前/, '$1y ago')
}

export function tTriggerDesc(row) {
  if (!row) return ''
  if (locale.value === 'zh') return row.trigger_desc || ''
  if (row.mode === 'interval') {
    const m = Math.max(1, Number(row.interval_minutes) || 60)
    return m >= 60 && m % 60 === 0 ? `Every ${m / 60}h` : `Every ${m}m`
  }
  if (row.mode === 'cron') {
    return `cron: ${row.cron}`
  }
  const names = MESSAGES.en.schedules.weekdays
  if (row.mode === 'weekly') {
    const days = Array.isArray(row.weekdays) && row.weekdays.length
      ? row.weekdays.map((d) => names[d] || d).join('/')
      : 'Daily'
    return `${days} ${row.at_time}`
  }
  return `Daily ${row.at_time}`
}

export function tLogMessage(msg) {
  if (!msg || locale.value === 'zh') return msg
  return String(msg)
    .replace(/HEVC 编码器\s*\[([^\]]+)\]:\s*(\S+?)\s*[（(]硬件加速[）)]/g, 'HEVC encoder [$1]: $2 (hardware acceleration)')
    .replace(/HEVC 编码器\s*\[([^\]]+)\]:\s*(\S+?)\s*[（(]软件(?:回退)?[）)]/g, 'HEVC encoder [$1]: $2 (software)')
    .replace(/ffmpeg\/ffprobe 就绪/g, 'ffmpeg/ffprobe ready')
    .replace(/已配置平台 cookies:\s*([^（]+)（设置页可管理）/g, 'Platform cookies configured: $1 (manage in Settings)')
    .replace(/Evil0ctal 兜底服务在线:/g, 'Evil0ctal fallback service online:')
    .replace(/Evil0ctal 兜底服务不可达:/g, 'Evil0ctal fallback service unreachable:')
    .replace(/下载队列就绪（全局并发=(\d+)，每平台并发=(\d+)）/g, 'Download queue ready (global=$1, per_platform=$2)')
    .replace(/定时任务已注册:\s*(\d+)\s*个（启用\s*(\d+)）/g, 'Scheduled jobs registered: $1 ($2 enabled)')
    .replace(/VidHarbor 就绪:\s*视频库=\S+\s*数据库=\S+/g, 'VidHarbor ready: library & SQLite database initialized')
    .replace(/榜单刷新:/g, 'Chart refreshed:')
}

