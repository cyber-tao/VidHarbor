<script setup>
// 设置页：下载默认/编码/登录管理(扫码·导入·上传)/兜底引擎/存储路径
import { onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'

const message = useMessage()
const settings = ref(null)
const meta = ref(null)
const saving = ref(false)
const dirty = ref(false)
// API Key 掩码显示开关（默认隐藏，防止旁人窥屏）
const showKeys = reactive({ evil0ctal: false, yt: false })

const PLATFORMS = [
  { id: 'bilibili', label: '哔哩哔哩' }, { id: 'youtube', label: 'YouTube' },
  { id: 'tiktok', label: 'TikTok' }, { id: 'douyin', label: '抖音' },
]

const form = reactive({
  max_height: 1080, sub_langs: 'zh.*, en.*', audio_langs: '',
  proxy: '', proxyPlatforms: [],
  concurrency: 2, per_platform: 2, transcode: 1,
  video_codec: 'h265', hw_encoder: 'auto',
  evil0ctal_enabled: true, evil0ctal_base_url: '', evil0ctal_api_key: '',
  yt_api_key: '', yt_region: 'US',
  timezone: 'Asia/Shanghai',
})

const HEIGHTS = [
  { v: 0, label: '最佳（不限）' }, { v: 2160, label: '2160p 4K' }, { v: 1440, label: '1440p 2K' },
  { v: 1080, label: '1080p（推荐）' }, { v: 720, label: '720p' }, { v: 480, label: '480p' }, { v: 360, label: '360p' },
]

async function load() {
  try {
    const res = await api.getSettings()
    settings.value = res.settings
    meta.value = res.meta
    const d = res.settings
    form.max_height = d.download.max_height
    form.sub_langs = d.download.sub_langs.join(', ')
    form.audio_langs = d.download.audio_langs.join(', ')
    form.concurrency = d.download.concurrency ?? 2
    form.per_platform = d.download.per_platform_concurrency ?? 2
    form.proxy = d.download.proxy || ''
    form.proxyPlatforms = d.download.proxy_platforms || []
    form.transcode = d.library.transcode_concurrency ?? 1
    form.video_codec = d.library.video_codec
    form.hw_encoder = d.library.hw_encoder
    form.evil0ctal_enabled = d.evil0ctal.enabled
    form.evil0ctal_base_url = d.evil0ctal.base_url
    form.evil0ctal_api_key = d.evil0ctal.api_key
    form.yt_api_key = d.youtube.api_key
    form.yt_region = d.youtube.region_code
    form.timezone = d.scheduler.timezone
    dirty.value = false
  } catch (e) {
    message.error(e.message)
  }
}
onMounted(() => { load(); loadCookies() })

async function save() {
  saving.value = true
  try {
    await api.putSettings({
      download: {
        max_height: Number(form.max_height),
        concurrency: Number(form.concurrency),
        per_platform_concurrency: Number(form.per_platform),
        sub_langs: form.sub_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
        audio_langs: form.audio_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
        proxy: form.proxy.trim(),
        proxy_platforms: [...form.proxyPlatforms],
      },
      library: { video_codec: form.video_codec, hw_encoder: form.hw_encoder, transcode_concurrency: Number(form.transcode) },
      evil0ctal: { enabled: form.evil0ctal_enabled, base_url: form.evil0ctal_base_url, api_key: form.evil0ctal_api_key.trim() },
      youtube: { api_key: form.yt_api_key.trim(), region_code: (form.yt_region || 'US').trim().toUpperCase() },
      scheduler: { timezone: form.timezone },
    })
    message.success('设置已保存')
    dirty.value = false
    load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch {
    message.error('复制失败')
  }
}

// ---- 登录管理 ----
const cookies = ref({})
const browsers = ref(['chrome', 'edge', 'firefox'])
const importBusy = ref('')
const browserSel = reactive({})   // platform -> 浏览器名（模板表达式访问不到 document，必须用状态）
const loginUrls = {
  bilibili: 'https://passport.bilibili.com/login',
  youtube: 'https://accounts.google.com/',
  tiktok: 'https://www.tiktok.com/login',
  douyin: 'https://www.douyin.com/',
}

async function loadCookies() {
  try {
    const res = await api.cookiesStatus()
    cookies.value = res.platforms
    browsers.value = res.browsers
    for (const pid of Object.keys(res.platforms)) {
      if (!browserSel[pid]) browserSel[pid] = 'chrome'
    }
  } catch { /* 静默 */ }
}

function onUpload(platform, ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  api.uploadCookies(platform, file)
    .then((r) => { message.success(`已导入 ${r.count} 条 cookies`); loadCookies() })
    .catch((e) => message.error(e.message))
  ev.target.value = ''
}

async function importBrowser(platform, browser) {
  importBusy.value = platform + browser
  try {
    const r = await api.importCookies(platform, browser)
    message.success(`从 ${browser} 导入 ${r.count} 条 cookies`)
    loadCookies()
  } catch (e) {
    message.error(e.message)
  } finally {
    importBusy.value = ''
  }
}

async function removeCookies(platform) {
  try {
    await api.deleteCookies(platform)
    message.success('已清除')
    loadCookies()
  } catch (e) { message.error(e.message) }
}

// B站扫码
const qr = reactive({ show: false, dataUrl: '', key: '', status: '', nickname: '' })
let pollTimer = null

async function startQR() {
  try {
    const r = await api.createBiliQR()
    qr.show = true
    qr.dataUrl = r.qr_data_url
    qr.key = r.qrcode_key
    qr.status = 'waiting'
    poll()
  } catch (e) {
    message.error(e.message)
  }
}

function poll() {
  clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    if (!qr.show || !qr.key) return
    try {
      const r = await api.pollBiliQR(qr.key)
      qr.status = r.status
      if (r.status === 'success') {
        qr.nickname = r.nickname || ''
        message.success(`B站登录成功${r.nickname ? '：' + r.nickname : ''}`)
        loadCookies()
        setTimeout(() => { qr.show = false }, 1200)
        return
      }
      if (r.status === 'expired') return
    } catch { /* 继续轮询 */ }
    poll()
  }, 2000)
}

function closeQR() {
  qr.show = false
  qr.key = ''
  clearTimeout(pollTimer)
}
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-5 p-6">
    <div class="flex items-center gap-3">
      <h1 class="text-xl font-semibold">设置</h1>
      <button :disabled="saving || !dirty" @click="save"
        class="ml-auto rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
        {{ saving ? '保存中…' : '保存设置' }}
      </button>
    </div>

    <!-- 下载默认 -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">下载默认选项</div>
      <div class="grid gap-4 sm:grid-cols-3">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">最高清晰度</span>
          <select v-model.number="form.max_height" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="h in HEIGHTS" :key="h.v" :value="h.v">{{ h.label }}</option>
          </select>
        </label>
        <label class="space-y-1.5 sm:col-span-2">
          <span class="text-xs text-zinc-400">字幕语言（逗号分隔，支持正则）</span>
          <input v-model="form.sub_langs" @input="dirty = true" placeholder="zh.*, en.*"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="space-y-1.5 sm:col-span-2">
          <span class="text-xs text-zinc-400">音轨语言偏好（逗号分隔按顺序，留空=原声；多音轨视频只下载首选一条）</span>
          <input v-model="form.audio_langs" @input="dirty = true" placeholder="zh, ja, en"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="space-y-1.5 sm:col-span-3">
          <span class="text-xs text-zinc-400">出口代理（http://host:port 或 socks5://host:port，留空=不用；勾选平台的下载与榜单请求走代理）</span>
          <input v-model="form.proxy" @input="dirty = true" placeholder="http://host.docker.internal:7890"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <div class="space-y-1.5 sm:col-span-3">
          <span class="text-xs text-zinc-400">走代理的平台</span>
          <div class="flex flex-wrap gap-4">
            <label v-for="pf in PLATFORMS" :key="pf.id" class="flex items-center gap-1.5 text-xs text-zinc-300">
              <input type="checkbox" :value="pf.id" v-model="form.proxyPlatforms" @change="dirty = true"
                class="size-3.5 accent-indigo-500" />
              {{ pf.label }}
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- 并发与性能 -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">并发与性能</div>
      <div class="grid gap-4 sm:grid-cols-3">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">全局并发下载（各平台合计）</span>
          <select v-model.number="form.concurrency" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ n }} 个同时下载</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">每平台并发下载</span>
          <select v-model.number="form.per_platform" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ n }} 个同时下载</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">全局并发转码</span>
          <select v-model.number="form.transcode" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ n }} 个同时转码</option>
          </select>
        </label>
      </div>
      <div class="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2 text-[11px] leading-4 text-zinc-500">
        「每平台并发」限制同一平台同时下载的任务数（建议 1–2，防止触发风控/限速）；某平台满员时其他平台的任务照常调度。
        「全局并发转码」限制整个系统同时进行的转码数——转码非常吃 CPU/GPU，即使多个任务同时下载完，超出上限的也会排队等待（无损 remux 不占额度）。修改保存后即时生效。
      </div>
    </div>

    <!-- 编码 -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">视频编码</div>
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">入库目标编码</span>
          <select v-model="form.video_codec" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option value="h265">H.265/HEVC（默认，更省空间）</option>
            <option value="h264">H.264（浏览器兼容最好）</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">H.265 转码编码器</span>
          <select v-model="form.hw_encoder" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option value="auto">auto（硬件优先，回退 libx265）</option>
            <option v-for="e in (meta?.encoders ?? []).filter((x) => x !== 'auto')" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
      </div>
      <div class="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2 text-[11px] text-zinc-500">
        当前检测到可用 HEVC 编码器：<span class="font-mono text-zinc-300">{{ meta?.hevc_encoder || '…' }}</span>
        （源已是 HEVC 的视频直接封装不转码；HEVC 统一打 hvc1 标记保证 Apple 兼容；网页播放 HEVC 依赖浏览器/硬件支持，Safari 原生支持）
      </div>
    </div>

    <!-- 登录管理 -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-1 text-sm font-medium text-zinc-200">登录管理（cookies）</div>
      <div class="mb-3 text-[11px] text-zinc-500">
        B站支持扫码登录。其他平台推荐用扩展（Get cookies.txt LOCALLY）导出后上传；
        注意：Chrome/Edge 127+ 启用了应用绑定加密，Windows 下无法直接「从浏览器导入」——需要完全退出浏览器才可读取数据库，且新版加密无法解密，此时请改用扩展上传或从 Firefox 导入。
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div v-for="(p, pid) in cookies" :key="pid"
          class="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-zinc-200">{{ p.name }}</span>
            <span v-if="p.exists" class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-400">
              ✓ 已配置{{ p.nickname ? ` · ${p.nickname}` : '' }}
            </span>
            <span v-else class="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">未配置</span>
          </div>
          <div v-if="p.exists" class="mt-1 text-[10px] text-zinc-600">更新于 {{ p.updated_at }}</div>
          <div class="mt-2.5 flex flex-wrap items-center gap-1.5">
            <button v-if="pid === 'bilibili'" @click="startQR"
              class="rounded border border-indigo-500/50 bg-indigo-500/10 px-2.5 py-1 text-[11px] text-indigo-300 hover:bg-indigo-500/20">扫码登录</button>
            <a :href="loginUrls[pid]" target="_blank"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-zinc-500">打开登录页 ↗</a>
            <label class="cursor-pointer rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-zinc-500">
              上传 cookies.txt
              <input type="file" accept=".txt" class="hidden" @change="onUpload(pid, $event)" />
            </label>
            <select v-model="browserSel[pid]"
              class="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 text-[11px] text-zinc-300 outline-none focus:border-indigo-500">
              <option v-for="b in browsers" :key="b" :value="b">{{ b }}</option>
            </select>
            <button @click="importBrowser(pid, browserSel[pid] || 'chrome')"
              :disabled="!!importBusy"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300 disabled:opacity-40">
              {{ importBusy === pid + (browserSel[pid] || 'chrome') ? '导入中…' : '从浏览器导入' }}
            </button>
            <button v-if="p.exists" @click="removeCookies(pid)"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-500 hover:border-red-500/60 hover:text-red-300">清除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 抖音兜底 & YouTube API & 系统 -->
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div class="mb-3 text-sm font-medium text-zinc-200">抖音 / TikTok 兜底引擎（Evil0ctal v5）</div>
        <label class="flex items-center gap-2 text-xs text-zinc-300">
          <input type="checkbox" v-model="form.evil0ctal_enabled" @change="dirty = true" class="accent-indigo-500" />
          启用（yt-dlp 失败时自动切换）
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">服务地址</span>
          <input v-model="form.evil0ctal_base_url" @input="dirty = true" placeholder="http://127.0.0.1:8000"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">API Key</span>
          <span class="relative block">
            <input v-model="form.evil0ctal_api_key" @input="dirty = true" placeholder="dtk_..."
              :type="showKeys.evil0ctal ? 'text' : 'password'" autocomplete="off" spellcheck="false"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-1.5 pl-2.5 pr-12 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
            <button type="button" @click="showKeys.evil0ctal = !showKeys.evil0ctal"
              class="absolute inset-y-0 right-0 rounded-lg px-2 text-[11px] text-zinc-500 hover:text-indigo-300">
              {{ showKeys.evil0ctal ? '隐藏' : '显示' }}
            </button>
          </span>
          <span class="block text-[11px] leading-4 text-zinc-500">
            在服务控制台 /api-keys 创建，勾选 douyin:read 与 tiktok:read；部署方法见 README。
          </span>
        </label>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div class="mb-1 text-sm font-medium text-zinc-200">YouTube Data API（推荐）</div>
        <div class="mb-3 text-[11px] leading-4 text-zinc-500">
          配置后榜单优先走官方 API：真实热门榜（含点赞数/发布时间），每日免费配额个人使用足够。
          在 <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank"
            class="text-indigo-400 hover:underline">Google Cloud Console</a> 启用 YouTube Data API v3 并创建 API 密钥；
          未配置时自动使用免登录通道（InnerTube）。
        </div>
        <label class="block space-y-1.5">
          <span class="text-xs text-zinc-400">API Key</span>
          <span class="relative block">
            <input v-model="form.yt_api_key" @input="dirty = true" placeholder="AIza..."
              :type="showKeys.yt ? 'text' : 'password'" autocomplete="off" spellcheck="false"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-1.5 pl-2.5 pr-12 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
            <button type="button" @click="showKeys.yt = !showKeys.yt"
              class="absolute inset-y-0 right-0 rounded-lg px-2 text-[11px] text-zinc-500 hover:text-indigo-300">
              {{ showKeys.yt ? '隐藏' : '显示' }}
            </button>
          </span>
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">地区代码（影响热门榜内容，如 US / JP / TW / HK）</span>
          <input v-model="form.yt_region" @input="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500" />
        </label>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 sm:col-span-2">
        <div class="mb-3 text-sm font-medium text-zinc-200">存储与系统</div>
        <div class="space-y-2 text-[11px]">
          <div>
            <div class="mb-1 text-zinc-500">视频库根目录（绝对路径）</div>
            <div class="flex gap-1.5">
              <input readonly :value="meta?.library_root || ''"
                class="min-w-0 flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-zinc-400 outline-none" />
              <button @click="copyText(meta?.library_root || '')"
                class="shrink-0 rounded-lg border border-zinc-700 px-2.5 py-1.5 text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">复制</button>
            </div>
          </div>
          <label class="block space-y-1">
            <span class="text-zinc-500">定时任务时区</span>
            <input v-model="form.timezone" @input="dirty = true"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500" />
          </label>
        </div>
      </div>
    </div>

    <!-- 底部保存 -->
    <div class="flex items-center justify-end gap-3">
      <span v-if="dirty" class="text-[11px] text-zinc-500">有未保存的修改</span>
      <button :disabled="saving || !dirty" @click="save"
        class="rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
        {{ saving ? '保存中…' : '保存设置' }}
      </button>
    </div>

    <!-- B站扫码弹窗 -->
    <div v-if="qr.show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" @click.self="closeQR">
      <div class="w-full max-w-xs overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 p-5 text-center">
        <div class="mb-1 text-sm font-medium">B站扫码登录</div>
        <div class="mb-3 text-[11px] text-zinc-500">用 B站 App 扫码确认登录</div>
        <img v-if="qr.dataUrl" :src="qr.dataUrl" class="mx-auto h-56 w-56 rounded-lg bg-white p-2" alt="登录二维码" />
        <div class="mt-3 text-xs" :class="{
          'text-zinc-400': qr.status === 'waiting',
          'text-indigo-300': qr.status === 'scanned',
          'text-emerald-400': qr.status === 'success',
          'text-red-400': qr.status === 'expired',
        }">
          {{ { waiting: '等待扫码…', scanned: '已扫描，请在手机上确认', success: `登录成功${qr.nickname ? '：' + qr.nickname : ''}`, expired: '二维码已过期' }[qr.status] || qr.status }}
        </div>
        <div class="mt-3 flex justify-center gap-2">
          <button v-if="qr.status === 'expired'" @click="startQR" class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">重新生成</button>
          <button @click="closeQR" class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
