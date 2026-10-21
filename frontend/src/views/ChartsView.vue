<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { fmtCount, fmtDuration } from '../format.js'
import DownloadOptionsDialog from '../components/DownloadOptionsDialog.vue'

const message = useMessage()
const router = useRouter()

const PLATFORM_TABS = [
  { id: 'bilibili', label: '哔哩哔哩' },
  { id: 'youtube', label: 'YouTube' },
  { id: 'tiktok', label: 'TikTok' },
  { id: 'douyin', label: '抖音' },
]

const platform = ref('bilibili')
const category = ref('')
const period = ref('')
const data = ref(null)
const loading = ref(false)
const selected = ref({})   // url -> item
const customText = ref('')
const showOptions = ref(false)

async function load(p, cat, per = '', refresh = false) {
  loading.value = true
  try {
    data.value = await api.getCharts(p, cat, per, refresh)
    category.value = data.value.category
    period.value = data.value.period
    selected.value = {}
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(() => load(platform.value, ''))
watch(platform, (p) => load(p, ''))

function pickCategory(cat) { load(platform.value, cat.id) }
function pickPeriod(p) { load(platform.value, category.value, p.id) }
function applyCustom() {
  const kw = customText.value.trim()
  if (!kw) return
  load(platform.value, `custom:${kw}`)
  customText.value = ''
}

const items = computed(() => data.value?.items ?? [])
const currentCategory = computed(() =>
  (data.value?.categories ?? []).find((c) => c.id === category.value))
const periods = computed(() => currentCategory.value?.periods ?? [])
const allowCustom = computed(() =>
  (data.value?.categories ?? []).some((c) => c.allow_custom))
const customPlaceholder = computed(() =>
  platform.value === 'youtube' ? '自定义关键词，如「AI」…'
  : platform.value === 'douyin' ? '自定义关键词，如「猫咪」…'
  : '自定义标签，如 cats…')
const selectedUrls = computed(() => Object.values(selected.value).map((i) => i.url))
const downloadableItems = computed(() => items.value.filter((i) => i.downloadable))
const allSelected = computed(() =>
  downloadableItems.value.length > 0 &&
  downloadableItems.value.every((i) => selected.value[i.url]),
)

const LABEL_STYLES = {
  爆: 'bg-red-500/90 text-white',
  热: 'bg-orange-500/90 text-white',
  新: 'bg-sky-500/90 text-white',
  首发: 'bg-violet-500/90 text-white',
}

function toggle(url) {
  const next = { ...selected.value }
  if (next[url]) delete next[url]
  else next[url] = items.value.find((i) => i.url === url)
  selected.value = next
}
function toggleAll() {
  if (allSelected.value) selected.value = {}
  else {
    const next = {}
    for (const i of downloadableItems.value) next[i.url] = i
    selected.value = next
  }
}

function startDownload() {
  if (!selectedUrls.value.length) return
  showOptions.value = true
}
function onDownloadDone() {
  router.push('/tasks')
}

function onCardClick(item) {
  // 抖音热搜词：点击原地钻取该词的视频列表（可勾选下载）
  if (platform.value === 'douyin' && !item.downloadable) {
    load(platform.value, `custom:${item.title}`)
    return
  }
  // 统一交互：点卡片打开源网页；勾选框负责选择下载
  window.open(item.url, '_blank')
}

function backToHot() {
  load(platform.value, 'hot')
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-4 p-6">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-xl font-semibold">热门榜单</h1>
      <div class="flex gap-1 rounded-lg border border-zinc-800 bg-zinc-900/70 p-1">
        <button v-for="p in PLATFORM_TABS" :key="p.id" @click="platform = p.id"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="platform === p.id ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
          {{ p.label }}
        </button>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <button @click="load(platform, category, period, true)" :disabled="loading"
          class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500 disabled:opacity-40">
          {{ loading ? '刷新中…' : '刷新榜单' }}
        </button>
        <button @click="startDownload" :disabled="!selectedUrls.length"
          class="rounded-lg bg-indigo-500 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          下载所选 ({{ selectedUrls.length }})
        </button>
      </div>
    </div>

    <!-- 分类 + 自定义 -->
    <div v-if="data?.categories?.length" class="flex flex-wrap items-center gap-2">
      <button v-for="c in data.categories" :key="c.id" @click="pickCategory(c)"
        class="rounded-full border px-3 py-1 text-xs transition-colors"
        :class="category === c.id
          ? 'border-indigo-500 bg-indigo-500/15 text-indigo-300'
          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'">
        {{ c.name }}
      </button>
      <form v-if="allowCustom" @submit.prevent="applyCustom" class="flex items-center gap-1.5">
        <input v-model="customText" :placeholder="customPlaceholder"
          class="w-40 rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        <button type="submit" :disabled="!customText.trim()"
          class="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300 disabled:opacity-40">
          查询
        </button>
      </form>
      <span class="ml-auto self-center text-[10px] text-zinc-600">点击卡片打开原网页 · 勾选右上角选择下载</span>
      <button v-if="downloadableItems.length" @click="toggleAll"
        class="text-xs text-zinc-500 hover:text-indigo-300">
        {{ allSelected ? '取消全选' : '全选' }}
      </button>
    </div>

    <!-- 时间段（各平台周期不同，按返回数据渲染） -->
    <div v-if="periods.length > 1" class="flex flex-wrap items-center gap-2">
      <span class="text-[11px] text-zinc-500">周期</span>
      <button v-for="p in periods" :key="p.id" @click="pickPeriod(p)"
        class="rounded-full border px-3 py-1 text-xs transition-colors"
        :class="period === p.id
          ? 'border-fuchsia-500 bg-fuchsia-500/15 text-fuchsia-300'
          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'">
        {{ p.name }}
      </button>
    </div>

    <!-- 降级提示 -->
    <div v-if="data?.degraded && data.message"
      class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-300">
      ⚠️ {{ data.message }}
    </div>

    <!-- 抖音说明 / 搜索模式面包屑 -->
    <div v-if="platform === 'douyin' && category.startsWith('custom:')"
      class="flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5 text-xs text-indigo-300">
      <span>🔍 关键词「{{ category.slice(7) }}」的视频结果</span>
      <span class="text-indigo-400/60">· 勾选后即可批量下载</span>
      <button @click="backToHot"
        class="ml-auto rounded-full border border-indigo-500/40 px-2.5 py-1 text-[11px] text-indigo-300 hover:border-indigo-400 hover:text-indigo-200">
        ← 返回热搜榜
      </button>
    </div>
    <div v-else-if="platform === 'douyin'"
      class="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-[11px] leading-5 text-zinc-500">
      抖音热搜为<b class="text-zinc-400">话题榜</b>：点击热搜词查看该话题的视频并勾选下载，
      也可在上方输入关键词直接搜索。需要已在「设置 → 登录管理」导入抖音 cookies，
      并启动 Evil0ctal 签名服务（见 README）。
    </div>

    <!-- 网格 -->
    <div v-if="loading && !items.length" class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i" class="h-48 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/60"></div>
    </div>
    <div v-else-if="!items.length" class="flex flex-col items-center gap-2 py-20 text-zinc-600">
      <span class="text-3xl">📭</span>
      <span class="text-sm">榜单数据为空{{ data?.degraded ? '' : '，点击右上角刷新重试' }}</span>
    </div>
    <div v-else class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
      <div v-for="item in items" :key="item.source_id + item.url"
        class="group cursor-pointer overflow-hidden rounded-xl border transition-all"
        :class="selected[item.url]
          ? 'border-indigo-500 bg-indigo-500/10 shadow-md shadow-indigo-500/10'
          : 'border-zinc-800 bg-zinc-900/60 hover:border-zinc-600'"
        @click="onCardClick(item)">
        <div class="relative aspect-video bg-zinc-800">
          <img v-if="item.cover" :src="item.cover" referrerpolicy="no-referrer" loading="lazy"
            class="h-full w-full object-cover"
            @error="$event.target.style.display = 'none'" />
          <span v-if="item.extra?.rank" class="absolute left-1.5 top-1.5 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] font-bold"
            :class="item.extra.rank <= 3 ? 'text-amber-400' : 'text-zinc-300'">
            #{{ item.extra.rank }}
          </span>
          <!-- 右上角勾选框（可下载项）：负责选择，点击卡片本身打开源网页 -->
          <button v-if="item.downloadable" type="button"
            class="absolute right-1.5 top-1.5 z-10 flex h-5 w-5 items-center justify-center rounded-md border transition-colors"
            :class="selected[item.url]
              ? 'border-indigo-400 bg-indigo-500 text-white'
              : 'border-white/60 bg-black/50 text-transparent hover:border-white hover:bg-black/70'"
            :title="selected[item.url] ? '取消选择' : '选择此视频下载'"
            @click.stop="toggle(item.url)">
            <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"
              stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
          </button>
          <span v-else-if="item.extra?.label"
            class="absolute right-1.5 top-1.5 rounded px-1.5 py-0.5 text-[10px] font-bold"
            :class="LABEL_STYLES[item.extra.label] || 'bg-zinc-600/90 text-white'">
            {{ item.extra.label }}
          </span>
          <span v-if="item.duration" class="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1 py-0.5 font-mono text-[11px] text-zinc-200">
            {{ fmtDuration(item.duration) }}
          </span>
          <span v-if="item.downloadable && selected[item.url]"
            class="pointer-events-none absolute inset-0 bg-indigo-500/20">
          </span>
          <span v-if="!item.downloadable"
            class="absolute bottom-1.5 left-1.5 rounded bg-black/75 px-1 py-0.5 text-[10px] text-zinc-300">
            {{ platform === 'douyin' ? '🔍 搜视频' : '↗ 话题视频' }}
          </span>
        </div>
        <div class="space-y-1 p-2.5">
          <div class="line-clamp-2 text-xs font-medium leading-4 text-zinc-200">{{ item.title }}</div>
          <div class="flex items-center justify-between gap-2 text-[11px] text-zinc-500">
            <span class="truncate">
              {{ item.author || (item.extra?.video_count ? `${item.extra.video_count} 个视频` : '') }}
            </span>
            <span class="flex shrink-0 items-center gap-1.5">
              <span v-if="item.likes" title="点赞">❤ {{ fmtCount(item.likes) }}</span>
              <span v-if="item.views" title="播放/热度">▶ {{ fmtCount(item.views) }}</span>
            </span>
          </div>
          <div v-if="item.published || item.extra?.source === 'api'"
            class="flex items-center gap-1.5 text-[10px] text-zinc-600">
            <span v-if="item.extra?.source === 'api'"
              class="rounded bg-emerald-500/15 px-1 py-0.5 text-[9px] text-emerald-400">官方API</span>
            <span v-if="item.published">🕒 {{ item.published }}</span>
          </div>
        </div>
      </div>
    </div>

    <DownloadOptionsDialog v-model:show="showOptions" :urls="selectedUrls" title="批量下载选项"
      @done="onDownloadDone" />
  </div>
</template>
