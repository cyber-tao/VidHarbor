<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { useEvents } from '../stores.js'
import { extractUrls } from '../urls.js'
import { fmtCount, fmtSize, platformColor, platformLabel } from '../format.js'
import ChartBox from '../components/ChartBox.vue'
import PlatformTag from '../components/PlatformTag.vue'
import DownloadOptionsDialog from '../components/DownloadOptionsDialog.vue'

const message = useMessage()
const router = useRouter()
const events = useEvents()
const stats = ref(null)
const urlsText = ref('')
const pendingUrls = ref([])
const showOptions = ref(false)
const codecText = ref('统一 MP4')

async function load() {
  try {
    stats.value = await api.stats()
  } catch (e) {
    message.error('统计加载失败: ' + e.message)
  }
}
onMounted(async () => {
  load()
  try {
    const res = await api.getSettings()
    const c = res.settings.library.video_codec === 'h264' ? 'H.264' : 'H.265'
    codecText.value = `统一 MP4 (${c}/AAC)`
  } catch { /* 默认文案 */ }
})
watch(() => events.statsVersion, load)

function quickAdd() {
  const urls = extractUrls(urlsText.value)
  if (!urls.length) return
  pendingUrls.value = urls
  showOptions.value = true
}
function onQuickDone() {
  urlsText.value = ''
  router.push('/tasks')
}

const cards = computed(() => {
  const v = stats.value?.videos
  return [
    { label: '视频总数', value: fmtCount(v?.total ?? 0), sub: `${v?.today ?? 0} 今日新增`, icon: 'M4 5h16v14H4z', tint: 'text-indigo-400' },
    { label: '存储占用', value: fmtSize(v?.total_size ?? 0), sub: codecText.value, icon: 'M4 7h16v13H4zM8 7V4h8v3', tint: 'text-emerald-400' },
    { label: '进行中任务', value: String(events.activeCount), sub: `${stats.value?.tasks?.pending ?? 0} 排队`, icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', tint: 'text-amber-400' },
    { label: '平台覆盖', value: String(Object.keys(v?.by_platform ?? {}).length || 0), sub: 'YouTube·B站·TikTok·抖音', icon: 'M5 12a7 7 0 1014 0 7 7 0 00-14 0zM12 5V3M12 21v-2', tint: 'text-fuchsia-400' },
  ]
})

const donutOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, textStyle: { color: '#a1a1aa', fontSize: 11 }, itemWidth: 10, itemHeight: 10 },
  series: [{
    type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'],
    itemStyle: { borderColor: '#18181b', borderWidth: 2, borderRadius: 4 },
    label: { show: false },
    data: Object.entries(stats.value?.videos?.by_platform ?? {}).map(([name, d]) => ({
      name: platformLabel(name), value: d.count, itemStyle: { color: platformColor(name) },
    })),
  }],
}))

const trendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  grid: { left: 34, right: 12, top: 16, bottom: 24 },
  xAxis: {
    type: 'category',
    data: (stats.value?.videos?.last14 ?? []).map((d) => d.date.slice(5)),
    axisLine: { lineStyle: { color: '#3f3f46' } },
    axisLabel: { color: '#71717a', fontSize: 10 },
  },
  yAxis: {
    type: 'value', minInterval: 1,
    splitLine: { lineStyle: { color: '#27272a' } },
    axisLabel: { color: '#71717a', fontSize: 10 },
  },
  series: [{
    type: 'bar', barMaxWidth: 18,
    data: (stats.value?.videos?.last14 ?? []).map((d) => d.count),
    itemStyle: { color: '#818cf8', borderRadius: [4, 4, 0, 0] },
  }],
}))

const statusText = {
  pending: '排队中', running: '下载中', completed: '完成', failed: '失败', canceled: '已取消',
}
const statusColor = {
  pending: 'text-zinc-400', running: 'text-indigo-300', completed: 'text-emerald-400',
  failed: 'text-red-400', canceled: 'text-zinc-500',
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-5 p-6">
    <h1 class="text-xl font-semibold">仪表盘</h1>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <div v-for="c in cards" :key="c.label"
        class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <div class="flex items-center justify-between">
          <span class="text-xs text-zinc-500">{{ c.label }}</span>
          <svg class="h-4 w-4" :class="c.tint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path :d="c.icon" /></svg>
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums">{{ c.value }}</div>
        <div class="mt-1 text-[11px] text-zinc-600">{{ c.sub }}</div>
      </div>
    </div>

    <!-- 图表 -->
    <div class="grid gap-4 lg:grid-cols-5">
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-2">
        <div class="mb-1 text-sm font-medium text-zinc-300">平台分布</div>
        <div class="h-56"><ChartBox :option="donutOption" /></div>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-3">
        <div class="mb-1 text-sm font-medium text-zinc-300">近 14 天入库</div>
        <div class="h-56"><ChartBox :option="trendOption" /></div>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-5">
      <!-- 快速下载 -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-2">
        <div class="mb-2 text-sm font-medium text-zinc-300">快速下载</div>
        <textarea v-model="urlsText" rows="4" placeholder="粘贴视频链接或 App 分享文案，自动提取链接&#10;支持 YouTube / B站 / TikTok / 抖音"
          class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        <button :disabled="!urlsText.trim()" @click="quickAdd"
          class="mt-2 w-full rounded-lg bg-indigo-500 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          添加到下载队列
        </button>
      </div>
      <!-- 最近任务 -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-3">
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium text-zinc-300">最近任务</span>
          <router-link to="/tasks" class="text-xs text-indigo-400 hover:text-indigo-300">全部 →</router-link>
        </div>
        <div class="space-y-2">
          <div v-if="!events.taskList.length" class="py-6 text-center text-xs text-zinc-600">暂无任务</div>
          <div v-for="t in events.taskList.slice(0, 6)" :key="t.id"
            class="flex items-center gap-3 rounded-lg border border-zinc-800/70 bg-zinc-950/50 px-3 py-2 text-xs">
            <PlatformTag :platform="t.platform" />
            <span class="min-w-0 flex-1 truncate text-zinc-300">{{ t.url }}</span>
            <span v-if="t.status === 'running'" class="font-mono text-indigo-300">{{ Math.round((t.progress || 0) * 100) }}%</span>
            <span :class="statusColor[t.status]">{{ statusText[t.status] }}</span>
          </div>
        </div>
      </div>
    </div>
    <DownloadOptionsDialog v-model:show="showOptions" :urls="pendingUrls" title="下载选项" @done="onQuickDone" />
  </div>
</template>
