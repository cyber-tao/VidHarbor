<script setup>
// 定时任务：一个任务可组合多个榜单选择（平台×分类×周期×TopN），到点自动抓取入库（库中已有的自动跳过）
import { onMounted, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import { fmtDateTime, platformLabel } from '../format.js'
import { useEvents } from '../stores.js'

const message = useMessage()
const route = useRoute()
const events = useEvents()
const list = ref([])
const loading = ref(false)
const focusId = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await api.listSchedules()
    list.value = res.schedules
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  if (route.query.focus) focusId.value = Number(route.query.focus)
  load()
  PLATFORM_TABS.forEach((p) => ensureMeta(p.id))
})
// 定时任务产生下载 → 完成时刷新（stats_dirty 已 bump）
watch(() => events.statsVersion, () => load())

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const PLATFORM_TABS = [
  { id: 'bilibili', label: '哔哩哔哩' },
  { id: 'youtube', label: 'YouTube' },
  { id: 'tiktok', label: 'TikTok' },
  { id: 'douyin', label: '抖音' },
]

// ---- 编辑器 ----
const editor = reactive({
  show: false, id: 0, name: '', mode: 'daily',
  at_time: '09:00', weekdays: [0], interval_minutes: 120, cron: '0 9 * * *',
  selections: [], useDefault: true,
  max_height: 1080, codec: 'h265', sub_langs: '', audio_langs: '',
})
const metaCache = reactive({})   // platform -> categories

async function ensureMeta(platform) {
  if (metaCache[platform]) return
  try {
    const res = await api.chartsMeta(platform)
    metaCache[platform] = res.categories
  } catch {
    metaCache[platform] = []
  }
}

// 定时任务只能选可直接下载的分类（抖音热搜是话题榜，只能用自定义关键词）
function catsOf(platform) { return (metaCache[platform] ?? []).filter((c) => c.downloadable !== false) }
function allowCustom(platform) { return (metaCache[platform] ?? []).some((c) => c.allow_custom) }
function periodsOf(sel) {
  if (sel.category === '__custom__' || sel.category.startsWith('custom:')) {
    const withCustom = (metaCache[sel.platform] ?? []).find((c) => c.allow_custom)
    return withCustom?.periods ?? [{ id: 'default', name: '默认' }]
  }
  return catsOf(sel.platform).find((c) => c.id === sel.category)?.periods ?? []
}

function addSelection() {
  editor.selections.push({ platform: 'bilibili', category: 'all', period: 'default', limit: 10, custom: '' })
  ensureMeta('bilibili')
}
function removeSelection(i) { editor.selections.splice(i, 1) }

async function onSelPlatform(sel) {
  await ensureMeta(sel.platform)
  const cats = catsOf(sel.platform)
  sel.category = cats[0]?.id ?? (allowCustom(sel.platform) ? '__custom__' : '')
  sel.period = periodsOf(sel)[0]?.id ?? ''
  sel.custom = ''
}
function onSelCategory(sel) {
  if (sel.category === '__custom__') return
  sel.period = periodsOf(sel)[0]?.id ?? ''
}
function selectionPayload(sel) {
  let category = sel.category
  if (category === '__custom__') category = `custom:${sel.custom.trim()}`
  return { platform: sel.platform, category, period: sel.period, limit: Number(sel.limit) || 10 }
}
// 列表卡片上的榜单摘要（中文分类名 + 周期）
function selectionText(s) {
  const cats = metaCache[s.platform] ?? []
  const isCustom = String(s.category).startsWith('custom:')
  const cat = cats.find((c) => c.id === s.category)
  const catName = isCustom ? `“${String(s.category).slice(7)}”` : (cat?.name ?? s.category)
  const per = cat?.periods?.find((p) => p.id === s.period)?.name ?? ''
  const perText = per && per !== '综合' && per !== '默认' ? ` · ${per}` : ''
  return `${platformLabel(s.platform)} · ${catName}${perText} · Top${s.limit}`
}

function openCreate() {
  Object.assign(editor, {
    show: true, id: 0, name: '', mode: 'daily',
    at_time: '09:00', weekdays: [0], interval_minutes: 120, cron: '0 9 * * *',
    selections: [], useDefault: true,
    max_height: 1080, codec: 'h265', sub_langs: '', audio_langs: '',
  })
  addSelection()
}

async function openEdit(row) {
  Object.assign(editor, {
    show: true, id: row.id, name: row.name, mode: row.mode,
    at_time: row.at_time || '09:00',
    weekdays: Array.isArray(row.weekdays) ? row.weekdays : [0],
    interval_minutes: row.interval_minutes || 120,
    cron: row.cron || '0 9 * * *',
    selections: [], useDefault: !row.options || !Object.keys(row.options).length,
    max_height: row.options?.max_height ?? 1080,
    codec: row.options?.codec ?? 'h265',
    sub_langs: (row.options?.sub_langs ?? []).join(', '),
    audio_langs: (row.options?.audio_langs ?? []).join(', '),
  })
  for (const s of row.selections) {
    await ensureMeta(s.platform)
    const isCustom = String(s.category).startsWith('custom:')
    editor.selections.push({
      platform: s.platform,
      category: isCustom ? '__custom__' : s.category,
      custom: isCustom ? String(s.category).slice(7) : '',
      period: s.period || 'default', limit: s.limit ?? 10,
    })
  }
}

const saving = ref(false)
async function save() {
  if (!editor.name.trim()) { message.error('请填写任务名'); return }
  if (!editor.selections.length) { message.error('至少添加一个榜单选择'); return }
  if (editor.selections.some((s) => s.category === '__custom__' && !s.custom.trim())) {
    message.error('自定义关键词不能为空'); return
  }
  const options = editor.useDefault ? {} : buildOptions()
  const payload = {
    name: editor.name.trim(), mode: editor.mode,
    at_time: editor.at_time, weekdays: editor.weekdays,
    interval_minutes: Number(editor.interval_minutes) || 60,
    cron: editor.cron,
    selections: editor.selections.map(selectionPayload),
    options,
  }
  saving.value = true
  try {
    if (editor.id) await api.updateSchedule(editor.id, payload)
    else await api.createSchedule(payload)
    message.success(editor.id ? '已更新' : '已创建')
    editor.show = false
    load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

function buildOptions() {
  const opts = { max_height: Number(editor.max_height), codec: editor.codec }
  const subs = editor.sub_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  if (subs.length) opts.sub_langs = subs
  const auds = editor.audio_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  if (auds.length) opts.audio_langs = auds
  return opts
}

async function toggle(row) {
  try {
    const res = await api.toggleSchedule(row.id)
    Object.assign(row, res.schedule)
    load()
  } catch (e) { message.error(e.message) }
}
const running = ref(0)
async function runNow(row) {
  running.value = row.id
  try {
    const res = await api.runSchedule(row.id)
    message.success(res.message)
    setTimeout(load, 4000)
  } catch (e) { message.error(e.message) } finally { running.value = 0 }
}
async function remove(row) {
  if (!window.confirm(`确认删除定时任务「${row.name}」？`)) return
  try {
    await api.deleteSchedule(row.id)
    load()
  } catch (e) { message.error(e.message) }
}

const HEIGHTS = [
  { v: 0, label: '最佳（不限）' }, { v: 2160, label: '2160p' }, { v: 1440, label: '1440p' },
  { v: 1080, label: '1080p' }, { v: 720, label: '720p' }, { v: 480, label: '480p' },
]
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-4 p-6">
    <div class="flex items-center gap-3">
      <h1 class="text-xl font-semibold">定时任务</h1>
      <span class="text-xs text-zinc-500">按时间自动下载榜单内容，库中已有的视频自动跳过</span>
      <button @click="openCreate"
        class="ml-auto rounded-lg bg-indigo-500 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-400">
        + 新建定时任务
      </button>
    </div>

    <div v-if="loading && !list.length" class="py-16 text-center text-sm text-zinc-600">加载中…</div>
    <div v-else-if="!list.length" class="flex flex-col items-center gap-2 py-16 text-zinc-600">
      <span class="text-3xl">⏱️</span>
      <span class="text-sm">还没有定时任务</span>
      <span class="text-xs">例如：每天 9 点自动下载 B站游戏区周榜 Top10 + YouTube 音乐月榜 Top5</span>
    </div>

    <div v-for="row in list" :key="row.id"
      class="space-y-3 rounded-xl border p-4 transition-colors"
      :class="focusId === row.id ? 'border-indigo-500/70 bg-indigo-500/5' : 'border-zinc-800 bg-zinc-900/60'">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm font-medium text-zinc-100">{{ row.name }}</span>
        <span class="rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-400">{{ row.trigger_desc }}</span>
        <span :class="['rounded-full px-2 py-0.5 text-[10px]',
          row.enabled ? 'bg-emerald-500/15 text-emerald-400' : 'bg-zinc-800 text-zinc-500']">
          {{ row.enabled ? '启用' : '停用' }}
        </span>
        <div class="ml-auto flex items-center gap-1.5">
          <button @click="runNow(row)" :disabled="running === row.id"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300 disabled:opacity-40">
            {{ running === row.id ? '启动中…' : '立即运行' }}
          </button>
          <button @click="openEdit(row)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-zinc-500">编辑</button>
          <button @click="toggle(row)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-amber-500/60 hover:text-amber-300">
            {{ row.enabled ? '停用' : '启用' }}
          </button>
          <button @click="remove(row)"
            class="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-500 hover:border-red-500/60 hover:text-red-300">删除</button>
        </div>
      </div>

      <div class="flex flex-wrap gap-1.5">
        <span v-for="(s, i) in row.selections" :key="i"
          class="rounded-full bg-zinc-800/70 px-2.5 py-0.5 text-[11px] text-zinc-300">
          {{ selectionText(s) }}
        </span>
      </div>

      <div class="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        <span>下次运行：<span class="text-zinc-300">{{ row.next_run_at ? fmtDateTime(row.next_run_at) : '—' }}</span></span>
        <span>上次运行：<span class="text-zinc-300">{{ row.last_run_at ? fmtDateTime(row.last_run_at) : '—' }}</span></span>
        <template v-if="row.last_result">
          <span class="text-emerald-400/80">新建 {{ row.last_result.created }}</span>
          <span>跳过 {{ row.last_result.skipped }}</span>
          <span v-if="row.last_result.failed" class="text-red-400/80">失败 {{ row.last_result.failed }}</span>
        </template>
      </div>
      <div v-if="row.last_result?.errors?.length"
        class="max-h-20 overflow-y-auto rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 font-mono text-[10px] leading-4 text-amber-300/80">
        <div v-for="(e, i) in row.last_result.errors" :key="i">{{ e }}</div>
      </div>
    </div>

    <!-- 编辑器弹窗 -->
    <div v-if="editor.show" class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-6" @click.self="editor.show = false">
      <div class="w-full max-w-2xl overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
        <div class="border-b border-zinc-800 px-4 py-3 text-sm font-medium">
          {{ editor.id ? '编辑定时任务' : '新建定时任务' }}
        </div>
        <div class="max-h-[70vh] space-y-4 overflow-y-auto p-4">
          <label class="block">
            <span class="mb-1 block text-xs text-zinc-400">任务名称</span>
            <input v-model="editor.name" placeholder="如：每日热榜自动追更"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
          </label>

          <!-- 触发时间 -->
          <div>
            <div class="mb-1.5 text-xs text-zinc-400">运行时间</div>
            <div class="flex gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-1 text-xs">
              <button v-for="m in [
                { v: 'daily', label: '每天' }, { v: 'weekly', label: '每周' },
                { v: 'interval', label: '间隔' }, { v: 'cron', label: 'Cron' }]"
                :key="m.v" @click="editor.mode = m.v"
                class="rounded px-3 py-1"
                :class="editor.mode === m.v ? 'bg-indigo-500 text-white' : 'text-zinc-400 hover:text-zinc-200'">
                {{ m.label }}
              </button>
            </div>
            <div class="mt-2.5 space-y-2.5">
              <div v-if="editor.mode === 'daily' || editor.mode === 'weekly'" class="flex items-center gap-2 text-xs text-zinc-300">
                <span class="text-zinc-500">时间</span>
                <input v-model="editor.at_time" type="time"
                  class="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500" />
              </div>
              <div v-if="editor.mode === 'weekly'" class="flex flex-wrap gap-1.5">
                <button v-for="(d, i) in WEEKDAYS" :key="i" @click="editor.weekdays.includes(i)
                  ? editor.weekdays = editor.weekdays.filter((x) => x !== i)
                  : editor.weekdays.push(i)"
                  class="rounded-full border px-2.5 py-1 text-[11px]"
                  :class="editor.weekdays.includes(i)
                    ? 'border-fuchsia-500 bg-fuchsia-500/15 text-fuchsia-300'
                    : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'">
                  {{ d }}
                </button>
              </div>
              <div v-if="editor.mode === 'interval'" class="flex items-center gap-2 text-xs text-zinc-300">
                <span class="text-zinc-500">每</span>
                <input v-model.number="editor.interval_minutes" type="number" min="1"
                  class="w-24 rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500" />
                <span class="text-zinc-500">分钟运行一次</span>
              </div>
              <div v-if="editor.mode === 'cron'" class="flex items-center gap-2 text-xs text-zinc-300">
                <span class="text-zinc-500">Cron 表达式</span>
                <input v-model="editor.cron" placeholder="0 9 * * *"
                  class="flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500" />
              </div>
            </div>
          </div>

          <!-- 榜单组合 -->
          <div>
            <div class="mb-1.5 flex items-center gap-2">
              <span class="text-xs text-zinc-400">榜单组合</span>
              <button @click="addSelection"
                class="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">+ 添加榜单</button>
            </div>
            <div class="space-y-2">
              <div v-for="(sel, i) in editor.selections" :key="i"
                class="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
                <div class="flex flex-wrap items-center gap-2 text-xs">
                  <select v-model="sel.platform" @change="onSelPlatform(sel)"
                    class="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-indigo-500">
                    <option v-for="p in PLATFORM_TABS" :key="p.id" :value="p.id">{{ p.label }}</option>
                  </select>
                  <select v-model="sel.category" @change="onSelCategory(sel)"
                    class="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-indigo-500">
                    <option v-for="c in catsOf(sel.platform)" :key="c.id" :value="c.id">{{ c.name }}</option>
                    <option v-if="allowCustom(sel.platform)" value="__custom__">自定义…</option>
                  </select>
                  <input v-if="sel.category === '__custom__'" v-model="sel.custom" placeholder="关键词 / 标签"
                    class="w-32 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
                  <select v-if="periodsOf(sel).length > 1" v-model="sel.period"
                    class="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-indigo-500">
                    <option v-for="p in periodsOf(sel)" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                  <span class="text-zinc-500">Top</span>
                  <input v-model.number="sel.limit" type="number" min="1" max="100"
                    class="w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-indigo-500" />
                  <button @click="removeSelection(i)" :disabled="editor.selections.length <= 1"
                    class="ml-auto rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-500 hover:border-red-500/60 hover:text-red-300 disabled:opacity-30">移除</button>
                </div>
              </div>
            </div>
          </div>

          <!-- 下载选项 -->
          <div>
            <label class="flex items-center gap-2 text-xs text-zinc-300">
              <input type="checkbox" v-model="editor.useDefault" class="accent-indigo-500" />
              使用全局默认下载选项
            </label>
            <div v-if="!editor.useDefault" class="mt-2 grid grid-cols-2 gap-3">
              <label class="space-y-1">
                <span class="text-[11px] text-zinc-500">最高清晰度</span>
                <select v-model.number="editor.max_height"
                  class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
                  <option v-for="h in HEIGHTS" :key="h.v" :value="h.v">{{ h.label }}</option>
                </select>
              </label>
              <label class="space-y-1">
                <span class="text-[11px] text-zinc-500">目标编码</span>
                <select v-model="editor.codec"
                  class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
                  <option value="h265">H.265</option>
                  <option value="h264">H.264</option>
                </select>
              </label>
              <label class="col-span-2 space-y-1">
                <span class="text-[11px] text-zinc-500">字幕语言（留空=全局默认）</span>
                <input v-model="editor.sub_langs" placeholder="zh.*, en.*"
                  class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
              </label>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 border-t border-zinc-800 px-4 py-3">
          <button @click="editor.show = false"
            class="rounded-lg border border-zinc-700 px-3.5 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">取消</button>
          <button :disabled="saving" @click="save"
            class="rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
