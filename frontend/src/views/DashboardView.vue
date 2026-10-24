<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { useEvents } from '../stores.js'
import { extractUrls } from '../urls.js'
import { fmtCount, fmtSize, platformColor, platformLabel } from '../format.js'
import { isDark, t } from '../i18n.js'
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
const activeCodec = ref('')

async function load() {
  try {
    stats.value = await api.stats()
  } catch (e) {
    message.error(t('dashboard.statsError') + e.message)
  }
}
onMounted(async () => {
  load()
  try {
    const res = await api.getSettings()
    activeCodec.value = res.settings.library.video_codec === 'h264' ? 'H.264' : 'H.265'
  } catch { /* fallback */ }
})
watch(() => events.statsVersion, load)

const codecText = computed(() =>
  activeCodec.value ? `${t('dashboard.unifiedMp4')} (${activeCodec.value}/AAC)` : t('dashboard.unifiedMp4'),
)

function quickAdd() {
  const urls = extractUrls(urlsText.value)
  if (!urls.length) {
    message.warning(t('dashboard.noValidUrls'))
    return
  }
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
    { label: t('dashboard.cardTotalVideos'), value: fmtCount(v?.total ?? 0), sub: t('dashboard.cardTodayNew', { n: v?.today ?? 0 }), icon: 'M4 5h16v14H4z', tint: 'text-indigo-400' },
    { label: t('dashboard.cardDiskUsage'), value: fmtSize(v?.total_size ?? 0), sub: codecText.value, icon: 'M4 7h16v13H4zM8 7V4h8v3', tint: 'text-emerald-400' },
    { label: t('dashboard.cardActiveTasks'), value: String(events.activeCount), sub: t('dashboard.cardQueued', { n: stats.value?.tasks?.pending ?? 0 }), icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', tint: 'text-amber-400' },
    { label: t('dashboard.cardPlatforms'), value: String(Object.keys(v?.by_platform ?? {}).length || 0), sub: t('dashboard.cardPlatformsSub'), icon: 'M5 12a7 7 0 1014 0 7 7 0 00-14 0zM12 5V3M12 21v-2', tint: 'text-fuchsia-400' },
  ]
})

const donutOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: {
    bottom: 0,
    textStyle: { color: isDark.value ? '#a1a1aa' : '#475569', fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
  },
  series: [{
    type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'],
    itemStyle: {
      borderColor: isDark.value ? '#18181b' : '#ffffff',
      borderWidth: 2,
      borderRadius: 4,
    },
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
    axisLine: { lineStyle: { color: isDark.value ? '#3f3f46' : '#cbd5e1' } },
    axisLabel: { color: isDark.value ? '#71717a' : '#64748b', fontSize: 10 },
  },
  yAxis: {
    type: 'value', minInterval: 1,
    splitLine: { lineStyle: { color: isDark.value ? '#27272a' : '#e2e8f0' } },
    axisLabel: { color: isDark.value ? '#71717a' : '#64748b', fontSize: 10 },
  },
  series: [{
    type: 'bar', barMaxWidth: 18,
    data: (stats.value?.videos?.last14 ?? []).map((d) => d.count),
    itemStyle: { color: isDark.value ? '#818cf8' : '#6366f1', borderRadius: [4, 4, 0, 0] },
  }],
}))

const statusColor = {
  pending: 'text-zinc-400', running: 'text-indigo-300', completed: 'text-emerald-400',
  failed: 'text-red-400', canceled: 'text-zinc-500',
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-5 p-6">
    <h1 class="text-xl font-semibold">{{ t('dashboard.title') }}</h1>

    <!-- Stat Cards -->
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

    <!-- Charts -->
    <div class="grid gap-4 lg:grid-cols-5">
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-2">
        <div class="mb-1 text-sm font-medium text-zinc-300">{{ t('dashboard.chartPlatformDist') }}</div>
        <div class="h-56"><ChartBox :option="donutOption" /></div>
      </div>
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-3">
        <div class="mb-1 text-sm font-medium text-zinc-300">{{ t('dashboard.chartIntake14d') }}</div>
        <div class="h-56"><ChartBox :option="trendOption" /></div>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-5">
      <!-- Quick Download -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-2">
        <div class="mb-2 text-sm font-medium text-zinc-300">{{ t('dashboard.quickDownload') }}</div>
        <textarea v-model="urlsText" rows="4" :placeholder="t('dashboard.quickPlaceholder')"
          class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        <button :disabled="!urlsText.trim()" @click="quickAdd"
          class="mt-2 w-full rounded-lg bg-indigo-500 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          {{ t('dashboard.quickSubmit') }}
        </button>
      </div>
      <!-- Recent Tasks -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-3">
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium text-zinc-300">{{ t('dashboard.recentTasks') }}</span>
          <router-link to="/tasks" class="text-xs text-indigo-400 hover:text-indigo-300">{{ t('dashboard.viewAll') }}</router-link>
        </div>
        <div class="space-y-2">
          <div v-if="!events.taskList.length" class="py-6 text-center text-xs text-zinc-600">{{ t('dashboard.noTasks') }}</div>
          <div v-for="tItem in events.taskList.slice(0, 6)" :key="tItem.id"
            class="flex items-center gap-3 rounded-lg border border-zinc-800/70 bg-zinc-950/50 px-3 py-2 text-xs">
            <PlatformTag :platform="tItem.platform" />
            <span class="min-w-0 flex-1 truncate text-zinc-300">{{ tItem.url }}</span>
            <span v-if="tItem.status === 'running'" class="font-mono text-indigo-300">{{ Math.round((tItem.progress || 0) * 100) }}%</span>
            <span :class="statusColor[tItem.status]">{{ t(`status.${tItem.status}`) }}</span>
          </div>
        </div>
      </div>
    </div>
    <DownloadOptionsDialog v-model:show="showOptions" :urls="pendingUrls" :title="t('dashboard.downloadOptions')" @done="onQuickDone" />
  </div>
</template>
