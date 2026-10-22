<script setup>
// 下载选项确认弹窗：批量下载/粘贴下载前可选清晰度、字幕语言、音轨语言、编码。
// 勾选「使用默认设置」时提交 options=null（服务端按全局设置处理）。
import { computed, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  urls: { type: Array, default: () => [] },
  title: { type: String, default: '下载选项' },
})
const emit = defineEmits(['update:show', 'done'])

const message = useMessage()
const useDefault = ref(true)
const submitting = ref(false)
const form = reactive({ max_height: 1080, sub_langs: 'zh.*, en.*', audio_langs: '', codec: '' })
const defaults = ref(null)

watch(() => props.show, async (v) => {
  if (!v || defaults.value) return
  try {
    const res = await api.getSettings()
    const d = res.settings.download
    defaults.value = d
    form.max_height = d.max_height
    form.sub_langs = d.sub_langs.join(', ')
    form.audio_langs = d.audio_langs.join(', ')
    form.codec = res.settings.library.video_codec
  } catch { /* 用初始值兜底 */ }
})

const HEIGHTS = [
  { v: 0, label: '最佳（不限）' }, { v: 2160, label: '2160p 4K' }, { v: 1440, label: '1440p 2K' },
  { v: 1080, label: '1080p' }, { v: 720, label: '720p' }, { v: 480, label: '480p' }, { v: 360, label: '360p' },
]

const optionsPayload = computed(() => {
  if (useDefault.value) return null
  const opts = { max_height: Number(form.max_height) }
  const subs = form.sub_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  if (subs.length) opts.sub_langs = subs
  const auds = form.audio_langs.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  if (auds.length) opts.audio_langs = auds
  if (form.codec) opts.codec = form.codec
  return opts
})

async function submit() {
  submitting.value = true
  try {
    const res = await api.createTasks(props.urls, optionsPayload.value)
    const extra = res.skipped ? `（跳过 ${res.skipped} 个已在队列）` : ''
    message.success(`已添加 ${res.tasks.length} 个下载任务${extra}`)
    emit('update:show', false)
    emit('done', res)
  } catch (e) {
    message.error(e.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" @click.self="emit('update:show', false)">
    <div class="w-full max-w-md overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
      <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <span class="text-sm font-medium">{{ title }}</span>
        <span class="text-xs text-zinc-500">{{ urls.length }} 个视频</span>
      </div>
      <div class="space-y-3.5 p-4">
        <label class="flex items-center gap-2 text-xs text-zinc-300">
          <input type="checkbox" v-model="useDefault" class="accent-indigo-500" />
          使用默认设置（在「设置」页可改默认值）
        </label>
        <template v-if="!useDefault">
          <div class="flex items-center justify-between gap-3">
            <span class="text-xs text-zinc-400">最高清晰度</span>
            <select v-model.number="form.max_height"
              class="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
              <option v-for="h in HEIGHTS" :key="h.v" :value="h.v">{{ h.label }}</option>
            </select>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-xs text-zinc-400">目标编码</span>
            <select v-model="form.codec"
              class="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500">
              <option value="h265">H.265 (HEVC，省空间)</option>
              <option value="h264">H.264 (兼容最好)</option>
            </select>
          </div>
          <div>
            <div class="mb-1 text-xs text-zinc-400">字幕语言（逗号分隔，支持正则）</div>
            <input v-model="form.sub_langs" placeholder="zh.*, en.*"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
          </div>
          <div>
            <div class="mb-1 text-xs text-zinc-400">音轨语言偏好（逗号分隔，按顺序；留空=原声）</div>
            <input v-model="form.audio_langs" placeholder="zh, ja, en"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
          </div>
        </template>
      </div>
      <div class="flex justify-end gap-2 border-t border-zinc-800 px-4 py-3">
        <button @click="emit('update:show', false)"
          class="rounded-lg border border-zinc-700 px-3.5 py-1.5 text-xs text-zinc-300 hover:border-zinc-500">取消</button>
        <button :disabled="submitting || !urls.length" @click="submit"
          class="rounded-lg bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
          {{ submitting ? '提交中…' : '开始下载' }}
        </button>
      </div>
    </div>
  </div>
</template>
