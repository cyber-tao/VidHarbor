<script setup>
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'
import { useEvents } from '../stores.js'
import PlatformTag from '../components/PlatformTag.vue'

const message = useMessage()
const events = useEvents()
const urlsText = ref('')
const adding = ref(false)

onMounted(() => events.loadTasks())

async function addTasks() {
  const urls = urlsText.value.split('\n').map((s) => s.trim()).filter(Boolean)
  if (!urls.length) return
  adding.value = true
  try {
    const res = await api.createTasks(urls)
    message.success(`已创建 ${res.tasks.length} 个下载任务`)
    urlsText.value = ''
  } catch (e) {
    message.error(e.message)
  } finally {
    adding.value = false
  }
}

async function cancelTask(t) {
  try {
    const res = await api.cancelTask(t.id)
    if (res.canceled) message.info('任务取消中')
    else events.removeLocalTask(t.id)
  } catch (e) { message.error(e.message) }
}

async function retryTask(t) {
  try {
    await api.retryTask(t.id)
    message.success('已重新排队')
  } catch (e) { message.error(e.message) }
}

const STATUS = {
  pending: { text: '排队中', cls: 'bg-zinc-700/60 text-zinc-300' },
  running: { text: '下载中', cls: 'bg-indigo-500/20 text-indigo-300 animate-pulse' },
  completed: { text: '完成', cls: 'bg-emerald-500/15 text-emerald-400' },
  failed: { text: '失败', cls: 'bg-red-500/15 text-red-400' },
  canceled: { text: '已取消', cls: 'bg-zinc-800 text-zinc-500' },
}
const STAGE_TEXT = {
  downloading: '下载中', merging: '合并流', processing: '转码/入库', done: '完成',
}

function progressColor(t) {
  if (t.status === 'completed') return '#34d399'
  if (t.status === 'failed') return '#f87171'
  return '#818cf8'
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-4 p-6">
    <h1 class="text-xl font-semibold">下载任务</h1>

    <!-- 批量添加 -->
    <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div class="mb-2 text-sm font-medium text-zinc-300">批量添加</div>
      <div class="flex gap-3">
        <textarea v-model="urlsText" rows="3" placeholder="粘贴视频链接，每行一个（支持批量粘贴）"
          class="flex-1 resize-none rounded-lg border border-zinc-700 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
        <button :disabled="adding || !urlsText.trim()" @click="addTasks"
          class="self-end rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
          {{ adding ? '提交中…' : '添加任务' }}
        </button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div v-if="!events.taskList.length" class="flex flex-col items-center gap-2 py-16 text-zinc-600">
      <span class="text-3xl">🛰️</span>
      <span class="text-sm">暂无任务 —— 去热门榜单批量下载，或在上方粘贴链接</span>
      <router-link to="/charts" class="mt-1 text-xs text-indigo-400 hover:text-indigo-300">浏览热门榜单 →</router-link>
    </div>

    <div v-for="t in events.taskList" :key="t.id"
      class="space-y-2.5 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="rounded px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">#{{ t.id }}</span>
        <PlatformTag :platform="t.platform" />
        <span v-if="t.engine" class="rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-400">{{ t.engine }}</span>
        <span :class="['rounded px-2 py-0.5 text-[11px] font-medium', STATUS[t.status]?.cls]">
          {{ STATUS[t.status]?.text ?? t.status }}
          <template v-if="t.status === 'running' && t.stage && STAGE_TEXT[t.stage]"> · {{ STAGE_TEXT[t.stage] }}</template>
        </span>
        <span class="min-w-0 flex-1 truncate font-mono text-[11px] text-zinc-500">{{ t.url }}</span>
        <div class="flex items-center gap-1.5">
          <button v-if="t.status === 'pending' || t.status === 'running'" @click="cancelTask(t)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-amber-500/60 hover:text-amber-300">取消</button>
          <button v-if="t.status === 'failed' || t.status === 'canceled'" @click="retryTask(t)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">重试</button>
          <button v-if="t.status === 'completed' && t.video_id"
            @click="$router.push(`/video/${t.video_id}`)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300">查看</button>
          <button v-if="['completed','failed','canceled'].includes(t.status)" @click="cancelTask(t)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:border-red-500/60 hover:text-red-300">删除</button>
        </div>
      </div>

      <!-- 进度条 -->
      <div v-if="t.status === 'running' || t.status === 'pending' || t.status === 'completed'" class="flex items-center gap-3">
        <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
          <div class="h-full rounded-full transition-all duration-300"
            :style="{ width: `${Math.round((t.progress || 0) * 100)}%`, background: progressColor(t) }"></div>
        </div>
        <span class="w-10 shrink-0 text-right font-mono text-[11px] text-zinc-400">{{ Math.round((t.progress || 0) * 100) }}%</span>
        <span v-if="t.status === 'running'" class="w-36 shrink-0 text-right font-mono text-[11px] text-zinc-500">
          {{ t.speed }} {{ t.eta ? '· ' + t.eta : '' }}
        </span>
      </div>

      <div v-if="t.error"
        :class="t.status === 'completed'
          ? 'text-[11px] text-zinc-500'
          : 'max-h-28 overflow-y-auto rounded-lg border border-red-500/25 bg-red-500/5 p-2.5 font-mono text-[11px] leading-4 break-all text-red-300/90'">
        {{ t.error }}
      </div>
    </div>
  </div>
</template>
