<script setup>
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'
import { useEvents } from '../stores.js'
import { extractUrls } from '../urls.js'
import { t } from '../i18n.js'
import PlatformTag from '../components/PlatformTag.vue'
import DownloadOptionsDialog from '../components/DownloadOptionsDialog.vue'

const message = useMessage()
const events = useEvents()
const urlsText = ref('')
const pendingUrls = ref([])
const showOptions = ref(false)

onMounted(() => events.loadTasks())

function addTasks() {
  const urls = extractUrls(urlsText.value)
  if (!urls.length) {
    message.warning(t('dashboard.noValidUrls'))
    return
  }
  pendingUrls.value = urls
  showOptions.value = true
}
function onAddDone() {
  urlsText.value = ''
}

async function cancelTask(tItem) {
  try {
    const res = await api.cancelTask(tItem.id)
    if (res.canceled) message.info(t('tasks.cancelingMsg'))
    else events.removeLocalTask(tItem.id)
  } catch (e) { message.error(e.message) }
}

async function retryTask(tItem) {
  try {
    await api.retryTask(tItem.id)
    message.success(t('tasks.requeuedMsg'))
  } catch (e) { message.error(e.message) }
}

const STATUS_CLS = {
  pending: 'bg-zinc-700/60 text-zinc-300',
  running: 'bg-indigo-500/20 text-indigo-300 animate-pulse',
  completed: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
  canceled: 'bg-zinc-800 text-zinc-500',
}

function statusText(tItem) {
  const base = t(`status.${tItem.status}`)
  if (tItem.status !== 'running') return base
  const stage = tItem.stage ? t(`stage.${tItem.stage}`) : ''
  return stage && stage !== base && tItem.stage !== 'done' ? `${base} · ${stage}` : base
}

function progressColor(tItem) {
  if (tItem.status === 'completed') return '#34d399'
  if (tItem.status === 'failed') return '#f87171'
  return '#818cf8'
}

function optionBadge(tItem) {
  const o = tItem.options
  if (!o) return ''
  const h = o.max_height ? `${o.max_height}p` : ''
  return [h, o.codec].filter(Boolean).join(' · ')
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-4 p-6">
    <h1 class="text-xl font-semibold">{{ t('tasks.title') }}</h1>

    <!-- Batch Add -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div class="mb-2 text-sm font-medium text-zinc-300">{{ t('tasks.batchAdd') }}</div>
      <div class="flex gap-3">
        <textarea v-model="urlsText" rows="3" :placeholder="t('tasks.placeholder')"
          class="flex-1 resize-none rounded-lg border border-zinc-700 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        <button :disabled="!urlsText.trim()" @click="addTasks"
          class="self-end rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          {{ t('tasks.addBtn') }}
        </button>
      </div>
    </div>

    <!-- Task List -->
    <div v-if="!events.taskList.length" class="flex flex-col items-center gap-2 py-16 text-zinc-600">
      <span class="text-3xl">🛰️</span>
      <span class="text-sm">{{ t('tasks.emptyText') }}</span>
      <router-link to="/charts" class="mt-1 text-xs text-indigo-400 hover:text-indigo-300">{{ t('tasks.browseCharts') }}</router-link>
    </div>

    <div v-for="tItem in events.taskList" :key="tItem.id"
      class="space-y-2.5 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="rounded px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">#{{ tItem.id }}</span>
        <PlatformTag :platform="tItem.platform" />
        <span v-if="tItem.engine" class="rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-400">{{ tItem.engine }}</span>
        <span v-if="optionBadge(tItem)" class="rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 font-mono text-[10px] text-zinc-400">{{ optionBadge(tItem) }}</span>
        <router-link v-if="tItem.schedule_id" :to="`/schedules?focus=${tItem.schedule_id}`"
          class="rounded-full border border-fuchsia-500/40 bg-fuchsia-500/10 px-2 py-0.5 text-[10px] text-fuchsia-300 hover:bg-fuchsia-500/20"
          :title="t('tasks.fromScheduleTitle')">⏱ #{{ tItem.schedule_id }}</router-link>
        <span :class="['rounded px-2 py-0.5 text-[11px] font-medium', STATUS_CLS[tItem.status]]">
          {{ statusText(tItem) }}
        </span>
        <span class="min-w-0 flex-1 truncate font-mono text-[11px] text-zinc-500">{{ tItem.url }}</span>
        <div class="flex items-center gap-1.5">
          <button v-if="tItem.status === 'pending' || tItem.status === 'running'" @click="cancelTask(tItem)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-amber-500/60 hover:text-amber-300">{{ t('tasks.cancelBtn') }}</button>
          <button v-if="tItem.status === 'failed' || tItem.status === 'canceled'" @click="retryTask(tItem)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">{{ t('tasks.retryBtn') }}</button>
          <button v-if="tItem.status === 'completed' && tItem.video_id"
            @click="$router.push(`/video/${tItem.video_id}`)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300">{{ t('tasks.viewBtn') }}</button>
          <button v-if="['completed','failed','canceled'].includes(tItem.status)" @click="cancelTask(tItem)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:border-red-500/60 hover:text-red-300">{{ t('tasks.deleteBtn') }}</button>
        </div>
      </div>

      <!-- Progress Bar -->
      <div v-if="tItem.status === 'running' || tItem.status === 'pending' || tItem.status === 'completed'" class="flex items-center gap-3">
        <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
          <div class="h-full rounded-full transition-all duration-300"
            :style="{ width: `${Math.round((tItem.progress || 0) * 100)}%`, background: progressColor(tItem) }"></div>
        </div>
        <span class="w-10 shrink-0 text-right font-mono text-[11px] text-zinc-400">{{ Math.round((tItem.progress || 0) * 100) }}%</span>
        <span v-if="tItem.status === 'running'" class="w-36 shrink-0 text-right font-mono text-[11px] text-zinc-500">
          {{ tItem.speed }} {{ tItem.eta ? '· ' + tItem.eta : '' }}
        </span>
      </div>

      <div v-if="tItem.error"
        :class="tItem.status === 'completed'
          ? 'text-[11px] text-zinc-500'
          : 'max-h-28 overflow-y-auto rounded-lg border border-red-500/25 bg-red-500/5 p-2.5 font-mono text-[11px] leading-4 break-all text-red-300/90'">
        {{ tItem.error }}
      </div>
    </div>
    <DownloadOptionsDialog v-model:show="showOptions" :urls="pendingUrls" :title="t('dashboard.downloadOptions')" @done="onAddDone" />
  </div>
</template>
