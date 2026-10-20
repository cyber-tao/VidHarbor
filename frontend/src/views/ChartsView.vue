<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { fmtCount, fmtDuration } from '../format.js'

const message = useMessage()
const router = useRouter()

const PLATFORM_TABS = [
  { id: 'bilibili', label: '哔哩哔哩' },
  { id: 'youtube', label: 'YouTube' },
  { id: 'tiktok', label: 'TikTok' },
  { id: 'douyin', label: '抖音热搜' },
]

const platform = ref('bilibili')
const category = ref('')
const data = ref(null)
const loading = ref(false)
const selected = ref({})   // url -> item

async function load(p, cat, refresh = false) {
  loading.value = true
  try {
    data.value = await api.getCharts(p, cat, refresh)
    category.value = data.value.category
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

const items = computed(() => data.value?.items ?? [])
const selectedUrls = computed(() => Object.values(selected.value).map((i) => i.url))
const downloadableItems = computed(() => items.value.filter((i) => i.downloadable))
const allSelected = computed(() =>
  downloadableItems.value.length > 0 &&
  downloadableItems.value.every((i) => selected.value[i.url]),
)

function toggle(url) {
  const next = { ...selected.value }
  if (next[url]) delete next[url]
  else next[url] = url in next ? next : (next[url] = items.value.find((i) => i.url === url))
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

const downloading = ref(false)
async function downloadSelected() {
  if (!selectedUrls.value.length) return
  downloading.value = true
  try {
    const res = await api.createTasks(selectedUrls.value)
    message.success(`已添加 ${res.tasks.length} 个下载任务`)
    router.push('/tasks')
  } catch (e) {
    message.error(e.message)
  } finally {
    downloading.value = false
  }
}

function onCardClick(item) {
  if (!item.downloadable) {
    window.open(item.url, '_blank')
    return
  }
  toggle(item.url)
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
        <button @click="load(platform, category, true)" :disabled="loading"
          class="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500 disabled:opacity-40">
          {{ loading ? '刷新中…' : '刷新榜单' }}
        </button>
        <button @click="downloadSelected" :disabled="downloading || !selectedUrls.length"
          class="rounded-lg bg-indigo-500 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          下载所选 ({{ selectedUrls.length }})
        </button>
      </div>
    </div>

    <!-- 分类 -->
    <div v-if="data?.categories?.length" class="flex flex-wrap items-center gap-2">
      <button v-for="c in data.categories" :key="c.id" @click="pickCategory(c)"
        class="rounded-full border px-3 py-1 text-xs transition-colors"
        :class="category === c.id
          ? 'border-indigo-500 bg-indigo-500/15 text-indigo-300'
          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'">
        {{ c.name }}
      </button>
      <button v-if="platform !== 'douyin'" @click="toggleAll"
        class="ml-auto text-xs text-zinc-500 hover:text-indigo-300">
        {{ allSelected ? '取消全选' : '全选' }}
      </button>
    </div>

    <!-- 降级提示 -->
    <div v-if="data?.degraded && data.message"
      class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-300">
      ⚠️ {{ data.message }}
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
            class="h-full w-full object-cover" :class="item.downloadable ? '' : 'opacity-60'"
            @error="$event.target.style.display = 'none'" />
          <span v-if="item.extra?.rank" class="absolute left-1.5 top-1.5 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] font-bold"
            :class="item.extra.rank <= 3 ? 'text-amber-400' : 'text-zinc-300'">
            #{{ item.extra.rank }}
          </span>
          <span v-if="item.duration" class="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] text-zinc-200">
            {{ fmtDuration(item.duration) }}
          </span>
          <span v-if="item.downloadable && selected[item.url]"
            class="absolute inset-0 flex items-center justify-center bg-indigo-500/25">
            <span class="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-500 text-white">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
            </span>
          </span>
        </div>
        <div class="space-y-1 p-2.5">
          <div class="line-clamp-2 text-xs font-medium leading-4 text-zinc-200">{{ item.title }}</div>
          <div class="flex items-center justify-between text-[11px] text-zinc-500">
            <span class="truncate">{{ item.author || (item.downloadable ? '' : '点击打开抖音搜索') }}</span>
            <span v-if="item.views" class="shrink-0">🔥 {{ fmtCount(item.views) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
