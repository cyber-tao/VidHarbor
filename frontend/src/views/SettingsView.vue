<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'
import { PLATFORM_OPTIONS, platformLabel } from '../format.js'
import { locale, setLocale, setTheme, t, theme } from '../i18n.js'

const message = useMessage()
const meta = ref(null)
const saving = ref(false)
const dirty = ref(false)
const showKeys = reactive({ evil0ctal: false, yt: false })
const keys = reactive({ evil0ctal: { set: false, clear: false }, yt: { set: false, clear: false } })
let saved = null

const form = reactive({
  max_height: 1080, sub_langs: 'zh.*, en.*', audio_langs: '',
  proxy: '', proxyPlatforms: [],
  concurrency: 2, per_platform: 2, transcode: 1,
  video_codec: 'h265', hw_encoder: 'auto',
  evil0ctal_enabled: true, evil0ctal_base_url: '', evil0ctal_api_key: '',
  yt_api_key: '', yt_region: 'US',
  timezone: 'Asia/Shanghai',
})

const heights = computed(() => [
  { v: 0, label: t('optionsDialog.bestUnlimited') },
  { v: 2160, label: '2160p 4K' },
  { v: 1440, label: '1440p 2K' },
  { v: 1080, label: t('settings.heightRecommended') },
  { v: 720, label: '720p' },
  { v: 480, label: '480p' },
  { v: 360, label: '360p' },
])

function splitList(text) {
  return text.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
}

function toPayload() {
  return {
    download: {
      max_height: Number(form.max_height),
      concurrency: Number(form.concurrency),
      per_platform_concurrency: Number(form.per_platform),
      sub_langs: splitList(form.sub_langs),
      audio_langs: splitList(form.audio_langs),
      proxy: form.proxy.trim(),
      proxy_platforms: [...form.proxyPlatforms],
    },
    library: { video_codec: form.video_codec, hw_encoder: form.hw_encoder, transcode_concurrency: Number(form.transcode) },
    evil0ctal: { enabled: form.evil0ctal_enabled, base_url: form.evil0ctal_base_url.trim() },
    youtube: { region_code: (form.yt_region || 'US').trim().toUpperCase() },
    scheduler: { timezone: form.timezone.trim() },
  }
}

function changedFields(current, original) {
  const patch = {}
  for (const [section, fields] of Object.entries(current)) {
    for (const [key, value] of Object.entries(fields)) {
      if (JSON.stringify(value) !== JSON.stringify(original[section][key])) {
        (patch[section] ??= {})[key] = value
      }
    }
  }
  return patch
}

function keyPlaceholder(k, example) {
  if (k.clear) return t('settings.keyClearOnSave')
  return k.set ? t('settings.keyAlreadySet') : example
}

function clearKey(which) {
  keys[which].clear = true
  if (which === 'evil0ctal') form.evil0ctal_api_key = ''
  else form.yt_api_key = ''
  dirty.value = true
}

async function load() {
  try {
    const res = await api.getSettings()
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
    form.evil0ctal_api_key = ''
    form.yt_api_key = ''
    keys.evil0ctal = { set: d.evil0ctal.api_key_set, clear: false }
    keys.yt = { set: d.youtube.api_key_set, clear: false }
    form.yt_region = d.youtube.region_code
    form.timezone = d.scheduler.timezone
    saved = toPayload()
    dirty.value = false
  } catch (e) {
    message.error(e.message)
  }
}
onMounted(() => { load(); loadCookies() })

async function save() {
  const patch = changedFields(toPayload(), saved)
  const evilKey = form.evil0ctal_api_key.trim()
  if (evilKey || keys.evil0ctal.clear) (patch.evil0ctal ??= {}).api_key = evilKey
  const ytKey = form.yt_api_key.trim()
  if (ytKey || keys.yt.clear) (patch.youtube ??= {}).api_key = ytKey
  if (!Object.keys(patch).length) {
    dirty.value = false
    return
  }
  saving.value = true
  try {
    await api.putSettings(patch)
    message.success(t('settings.savedMsg'))
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
    message.success(t('settings.copiedMsg'))
  } catch {
    message.error(t('settings.copyFailed'))
  }
}

// ---- Login Management ----
const cookies = ref({})
const browsers = ref(['chrome', 'edge', 'firefox'])
const importBusy = ref('')
const browserSel = reactive({})
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
  } catch { /* silent */ }
}

function onUpload(platform, ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  api.uploadCookies(platform, file)
    .then((r) => { message.success(t('settings.uploadedCookiesMsg', { n: r.count })); loadCookies() })
    .catch((e) => message.error(e.message))
  ev.target.value = ''
}

async function importBrowser(platform, browser) {
  importBusy.value = platform + browser
  try {
    const r = await api.importCookies(platform, browser)
    message.success(t('settings.importedBrowserMsg', { b: browser, n: r.count }))
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
    message.success(t('settings.clearedMsg'))
    loadCookies()
  } catch (e) { message.error(e.message) }
}

// Bilibili QR
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
        message.success(`${t('settings.biliLoginSuccess')}${r.nickname ? ': ' + r.nickname : ''}`)
        loadCookies()
        setTimeout(() => { qr.show = false }, 1200)
        return
      }
      if (r.status === 'expired') return
    } catch { /* continue polling */ }
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
      <h1 class="text-xl font-semibold">{{ t('settings.title') }}</h1>
      <button :disabled="saving || !dirty" @click="save"
        class="ml-auto rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
        {{ saving ? t('settings.saving') : t('settings.saveBtn') }}
      </button>
    </div>

    <!-- Appearance & Language -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.appearanceTitle') }}</div>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="space-y-1.5">
          <span class="block text-xs text-zinc-400">{{ t('settings.languageLabel') }}</span>
          <div class="inline-flex gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-1 text-xs">
            <button type="button" @click="setLocale('en')"
              class="rounded-md px-3 py-1 font-medium transition-colors"
              :class="locale === 'en' ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
              English
            </button>
            <button type="button" @click="setLocale('zh')"
              class="rounded-md px-3 py-1 font-medium transition-colors"
              :class="locale === 'zh' ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
              简体中文
            </button>
          </div>
        </div>
        <div class="space-y-1.5">
          <span class="block text-xs text-zinc-400">{{ t('settings.themeLabel') }}</span>
          <div class="inline-flex gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-1 text-xs">
            <button type="button" @click="setTheme('dark')"
              class="rounded-md px-3 py-1 font-medium transition-colors"
              :class="theme === 'dark' ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
              {{ t('settings.themeDark') }}
            </button>
            <button type="button" @click="setTheme('light')"
              class="rounded-md px-3 py-1 font-medium transition-colors"
              :class="theme === 'light' ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
              {{ t('settings.themeLight') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Default Download Options -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.downloadTitle') }}</div>
      <div class="grid gap-4 sm:grid-cols-3">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.maxHeight') }}</span>
          <select v-model.number="form.max_height" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="h in heights" :key="h.v" :value="h.v">{{ h.label }}</option>
          </select>
        </label>
        <label class="space-y-1.5 sm:col-span-2">
          <span class="text-xs text-zinc-400">{{ t('settings.subLangs') }}</span>
          <input v-model="form.sub_langs" @input="dirty = true" placeholder="zh.*, en.*"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="space-y-1.5 sm:col-span-2">
          <span class="text-xs text-zinc-400">{{ t('settings.audioLangs') }}</span>
          <input v-model="form.audio_langs" @input="dirty = true" placeholder="zh, ja, en"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="space-y-1.5 sm:col-span-3">
          <span class="text-xs text-zinc-400">{{ t('settings.proxyLabel') }}</span>
          <input v-model="form.proxy" @input="dirty = true" placeholder="http://host.docker.internal:7890"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <div class="space-y-1.5 sm:col-span-3">
          <span class="text-xs text-zinc-400">{{ t('settings.proxyPlatforms') }}</span>
          <div class="flex flex-wrap gap-4">
            <label v-for="pf in PLATFORM_OPTIONS" :key="pf.id" class="flex items-center gap-1.5 text-xs text-zinc-300">
              <input type="checkbox" :value="pf.id" v-model="form.proxyPlatforms" @change="dirty = true"
                class="size-3.5 accent-indigo-500" />
              {{ pf.label }}
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Concurrency & Performance -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.concurrencyTitle') }}</div>
      <div class="grid gap-4 sm:grid-cols-3">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.globalDownloadConcurrency') }}</span>
          <select v-model.number="form.concurrency" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ t('settings.nConcurrentDownloads', { n }) }}</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.perPlatformConcurrency') }}</span>
          <select v-model.number="form.per_platform" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ t('settings.nConcurrentDownloads', { n }) }}</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.globalTranscodeConcurrency') }}</span>
          <select v-model.number="form.transcode" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option v-for="n in 8" :key="n" :value="n">{{ t('settings.nConcurrentTranscodes', { n }) }}</option>
          </select>
        </label>
      </div>
      <div class="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2 text-[11px] leading-4 text-zinc-500">
        {{ t('settings.concurrencyNote') }}
      </div>
    </div>

    <!-- Video Encoding -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.encodingTitle') }}</div>
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.targetCodec') }}</span>
          <select v-model="form.video_codec" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option value="h265">{{ t('settings.codecH265Default') }}</option>
            <option value="h264">{{ t('settings.codecH264Compat') }}</option>
          </select>
        </label>
        <label class="space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.hevcEncoder') }}</span>
          <select v-model="form.hw_encoder" @change="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
            <option value="auto">{{ t('settings.encoderAuto') }}</option>
            <option v-for="e in (meta?.encoders ?? []).filter((x) => x !== 'auto')" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
      </div>
      <div class="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2 text-[11px] text-zinc-500">
        {{ t('settings.detectedEncoderPrefix') }}<span class="font-mono text-zinc-300">{{ meta?.hevc_encoder || '…' }}</span>
        {{ t('settings.detectedEncoderNote') }}
      </div>
    </div>

    <!-- Login Management (Cookies) -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div class="mb-1 text-sm font-medium text-zinc-200">{{ t('settings.cookiesTitle') }}</div>
      <div class="mb-3 text-[11px] text-zinc-500">
        {{ t('settings.cookiesNote') }}
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div v-for="(p, pid) in cookies" :key="pid"
          class="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-zinc-200">{{ platformLabel(pid) }}</span>
            <span v-if="p.exists" class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-400">
              {{ t('settings.configured') }}{{ p.nickname ? ` · ${p.nickname}` : '' }}
            </span>
            <span v-else class="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">{{ t('settings.notConfigured') }}</span>
          </div>
          <div v-if="p.exists" class="mt-1 text-[10px] text-zinc-600">{{ t('settings.updatedAt', { t: p.updated_at }) }}</div>
          <div class="mt-2.5 flex flex-wrap items-center gap-1.5">
            <button v-if="pid === 'bilibili'" @click="startQR"
              class="rounded border border-indigo-500/50 bg-indigo-500/10 px-2.5 py-1 text-[11px] text-indigo-300 hover:bg-indigo-500/20">{{ t('settings.qrLoginBtn') }}</button>
            <a :href="loginUrls[pid]" target="_blank"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-zinc-500">{{ t('settings.openLoginPage') }}</a>
            <label class="cursor-pointer rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-zinc-500">
              {{ t('settings.uploadCookies') }}
              <input type="file" accept=".txt" class="hidden" @change="onUpload(pid, $event)" />
            </label>
            <select v-model="browserSel[pid]"
              class="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 text-[11px] text-zinc-300 outline-none focus:border-indigo-500">
              <option v-for="b in browsers" :key="b" :value="b">{{ b }}</option>
            </select>
            <button @click="importBrowser(pid, browserSel[pid] || 'chrome')"
              :disabled="!!importBusy"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300 disabled:opacity-40">
              {{ importBusy === pid + (browserSel[pid] || 'chrome') ? t('settings.importingBtn') : t('settings.importFromBrowser') }}
            </button>
            <button v-if="p.exists" @click="removeCookies(pid)"
              class="rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-500 hover:border-red-500/60 hover:text-red-300">{{ t('settings.clearBtn') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Evil0ctal Fallback & YouTube API & System -->
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.evil0ctalTitle') }}</div>
        <label class="flex items-center gap-2 text-xs text-zinc-300">
          <input type="checkbox" v-model="form.evil0ctal_enabled" @change="dirty = true" class="accent-indigo-500" />
          {{ t('settings.evil0ctalEnable') }}
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.serviceUrl') }}</span>
          <input v-model="form.evil0ctal_base_url" @input="dirty = true" placeholder="http://127.0.0.1:8000"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.apiKey') }}</span>
          <span class="relative block">
            <input v-model="form.evil0ctal_api_key" @input="dirty = true; keys.evil0ctal.clear = false"
              :placeholder="keyPlaceholder(keys.evil0ctal, 'dtk_...')"
              :type="showKeys.evil0ctal ? 'text' : 'password'" autocomplete="off" spellcheck="false"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-1.5 pl-2.5 pr-12 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
            <button type="button" @click="showKeys.evil0ctal = !showKeys.evil0ctal"
              class="absolute inset-y-0 right-0 rounded-lg px-2 text-[11px] text-zinc-500 hover:text-indigo-300">
              {{ showKeys.evil0ctal ? t('settings.hideKey') : t('settings.showKey') }}
            </button>
          </span>
          <span class="block text-[11px] leading-4 text-zinc-500">
            {{ t('settings.evil0ctalNote') }}
            <button v-if="keys.evil0ctal.set && !keys.evil0ctal.clear" type="button" @click.prevent="clearKey('evil0ctal')"
              class="ml-1 text-zinc-500 underline hover:text-red-300">{{ t('settings.clearSavedKey') }}</button>
          </span>
        </label>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div class="mb-1 text-sm font-medium text-zinc-200">{{ t('settings.ytApiTitle') }}</div>
        <div class="mb-3 text-[11px] leading-4 text-zinc-500">
          {{ t('settings.ytApiNote1') }}
          <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank"
            class="text-indigo-400 hover:underline">Google Cloud Console</a>
          {{ t('settings.ytApiNote2') }}
        </div>
        <label class="block space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.apiKey') }}</span>
          <span class="relative block">
            <input v-model="form.yt_api_key" @input="dirty = true; keys.yt.clear = false"
              :placeholder="keyPlaceholder(keys.yt, 'AIza...')"
              :type="showKeys.yt ? 'text' : 'password'" autocomplete="off" spellcheck="false"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-1.5 pl-2.5 pr-12 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
            <button type="button" @click="showKeys.yt = !showKeys.yt"
              class="absolute inset-y-0 right-0 rounded-lg px-2 text-[11px] text-zinc-500 hover:text-indigo-300">
              {{ showKeys.yt ? t('settings.hideKey') : t('settings.showKey') }}
            </button>
          </span>
          <button v-if="keys.yt.set && !keys.yt.clear" type="button" @click.prevent="clearKey('yt')"
            class="text-[11px] text-zinc-500 underline hover:text-red-300">{{ t('settings.clearSavedKey') }}</button>
        </label>
        <label class="mt-3 block space-y-1.5">
          <span class="text-xs text-zinc-400">{{ t('settings.regionCode') }}</span>
          <input v-model="form.yt_region" @input="dirty = true"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500" />
        </label>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 sm:col-span-2">
        <div class="mb-3 text-sm font-medium text-zinc-200">{{ t('settings.storageTitle') }}</div>
        <div class="space-y-2 text-[11px]">
          <div>
            <div class="mb-1 text-zinc-500">{{ t('settings.libraryRoot') }}</div>
            <div class="flex gap-1.5">
              <input readonly :value="meta?.library_root || ''"
                class="min-w-0 flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-zinc-400 outline-none" />
              <button @click="copyText(meta?.library_root || '')"
                class="shrink-0 rounded-lg border border-zinc-700 px-2.5 py-1.5 text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">{{ t('settings.copyBtn') }}</button>
            </div>
          </div>
          <label class="block space-y-1">
            <span class="text-zinc-500">{{ t('settings.scheduleTimezone') }}</span>
            <input v-model="form.timezone" @input="dirty = true"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500" />
          </label>
        </div>
      </div>
    </div>

    <!-- Bottom Save -->
    <div class="flex items-center justify-end gap-3">
      <span v-if="dirty" class="text-[11px] text-zinc-500">{{ t('settings.unsavedChanges') }}</span>
      <button :disabled="saving || !dirty" @click="save"
        class="rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
        {{ saving ? t('settings.saving') : t('settings.saveBtn') }}
      </button>
    </div>

    <!-- Bilibili QR Modal -->
    <div v-if="qr.show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" @click.self="closeQR">
      <div class="w-full max-w-xs overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 p-5 text-center">
        <div class="mb-1 text-sm font-medium">{{ t('settings.qrModalTitle') }}</div>
        <div class="mb-3 text-[11px] text-zinc-500">{{ t('settings.qrModalSub') }}</div>
        <img v-if="qr.dataUrl" :src="qr.dataUrl" class="mx-auto h-56 w-56 rounded-lg bg-white p-2" :alt="t('settings.qrAlt')" />
        <div class="mt-3 text-xs" :class="{
          'text-zinc-400': qr.status === 'waiting',
          'text-indigo-300': qr.status === 'scanned',
          'text-emerald-400': qr.status === 'success',
          'text-red-400': qr.status === 'expired',
        }">
          {{ {
            waiting: t('settings.qrWaiting'),
            scanned: t('settings.qrScanned'),
            success: `${t('settings.qrSuccess')}${qr.nickname ? ': ' + qr.nickname : ''}`,
            expired: t('settings.qrExpired'),
          }[qr.status] || qr.status }}
        </div>
        <div class="mt-3 flex justify-center gap-2">
          <button v-if="qr.status === 'expired'" @click="startQR" class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">{{ t('settings.qrRegenerate') }}</button>
          <button @click="closeQR" class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">{{ t('settings.qrClose') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
