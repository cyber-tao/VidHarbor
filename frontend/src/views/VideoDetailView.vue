<script setup>
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { api, authUrl } from '../api.js'
import { fmtCount, fmtDateTime, fmtDuration, fmtSize, fmtDate } from '../format.js'
import PlatformTag from '../components/PlatformTag.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const video = ref(null)
const subContent = ref(null)   // 当前查看的字幕内容
const subTitle = ref('')
const deleting = ref(false)
const videoEl = ref(null)
const activeSubId = ref(0)     // 当前播放字幕轨（0=关闭）

async function load() {
  try {
    video.value = await api.video(route.params.id)
    activeSubId.value = 0
    await nextTick()
    applySubtitles()
  } catch (e) {
    message.error(e.message)
  }
}
onMounted(load)
watch(() => route.params.id, load)

const subList = computed(() => video.value?.subtitles ?? [])

// 自绘字幕选择：切换 <track> 的显示模式（替代浏览器原生默认第一条）
// track 元素顺序与 subList 一致，按索引对应
function applySubtitles() {
  const el = videoEl.value
  if (!el) return
  el.querySelectorAll('track').forEach((t, i) => {
    const sub = subList.value[i]
    t.track.mode = sub && sub.id === activeSubId.value ? 'showing' : 'disabled'
  })
}
async function selectSub(s) {
  activeSubId.value = activeSubId.value === s.id ? 0 : s.id
  applySubtitles()
}

async function copyPath() {
  const text = video.value?.absolute_path || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    message.success('路径已复制')
  } catch {
    // 非 https / 旧浏览器回退
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
    message.success('路径已复制')
  }
}

function gotoTag(tag) {
  router.push({ path: '/library', query: { tag } })
}

async function viewSubtitle(s) {
  subTitle.value = `${s.lang}${s.auto_generated ? '（自动生成）' : ''}`
  subContent.value = '加载中…'
  try {
    const res = await fetch(authUrl(`/api/videos/${video.value.id}/subtitles/${s.id}`))
    subContent.value = await res.text()
  } catch (e) {
    subContent.value = '加载失败: ' + e.message
  }
}

async function onDelete() {
  if (!window.confirm(`确认删除「${video.value.title.slice(0, 40)}」？视频文件与字幕将一并移除。`)) return
  deleting.value = true
  try {
    await api.deleteVideo(video.value.id)
    message.success('已删除')
    router.push('/library')
  } catch (e) {
    message.error(e.message)
  } finally {
    deleting.value = false
  }
}

function openSource() { window.open(video.value.url, '_blank') }

const codecLabel = computed(() => {
  const v = video.value?.vcodec || ''
  if (v.includes('hevc') || v.includes('h265')) return 'H.265'
  if (v.includes('avc') || v.includes('h264')) return 'H.264'
  return v || '—'
})
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-5 p-6">
    <div class="flex items-center gap-3">
      <button @click="router.back()"
        class="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200">
        <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
        返回
      </button>
      <PlatformTag v-if="video" :platform="video.platform" />
    </div>

    <div v-if="!video" class="py-24 text-center text-sm text-zinc-600">加载中…</div>

    <template v-else>
      <!-- 播放器 -->
      <div class="overflow-hidden rounded-xl border border-zinc-800 bg-black">
        <video v-if="video.file_exists" ref="videoEl" controls :poster="authUrl(`/api/videos/${video.id}/thumbnail`)" class="aspect-video w-full">
          <source :src="authUrl(`/api/videos/${video.id}/file`)" type="video/mp4" />
          <track v-for="s in subList" :key="s.id"
            :src="authUrl(`/api/videos/${video.id}/subtitles/${s.id}/vtt`)"
            :srclang="s.lang" :label="s.lang + (s.auto_generated ? ' (auto)' : '')"
            kind="subtitles" />
          您的浏览器不支持视频播放。
        </video>
        <div v-else class="flex aspect-video items-center justify-center text-sm text-red-400">
          ⚠️ 视频文件缺失（可能已被手动删除）
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-3">
        <!-- 信息 -->
        <div class="space-y-4 lg:col-span-2">
          <div>
            <h1 class="text-lg font-semibold leading-7">{{ video.title }}</h1>
            <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
              <span>{{ video.uploader || '未知作者' }}</span>
              <span v-if="video.upload_date">📅 {{ fmtDate(video.upload_date) }}</span>
              <span>⏱ {{ fmtDuration(video.duration) }}</span>
              <span v-if="video.view_count">▶ {{ fmtCount(video.view_count) }} 播放</span>
              <span v-if="video.like_count">♥ {{ fmtCount(video.like_count) }}</span>
              <span class="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                {{ codecLabel }}{{ video.height ? ` · ${video.height}p` : '' }}
              </span>
            </div>
          </div>

          <div v-if="video.tags?.length" class="flex flex-wrap gap-1.5">
            <button v-for="t in video.tags" :key="t" @click="gotoTag(t)"
              class="rounded-full bg-zinc-800/80 px-2.5 py-0.5 text-[11px] text-zinc-400 transition-colors hover:bg-emerald-500/15 hover:text-emerald-300">
              #{{ t }}</button>
          </div>

          <div v-if="video.description" class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div class="mb-2 text-xs font-medium text-zinc-400">简介</div>
            <div class="max-h-64 overflow-y-auto whitespace-pre-wrap text-[13px] leading-6 text-zinc-300">{{ video.description }}</div>
          </div>
        </div>

        <!-- 元数据 & 字幕 -->
        <div class="space-y-4">
          <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div class="mb-2 text-xs font-medium text-zinc-400">技术信息</div>
            <dl class="space-y-1.5 text-xs">
              <div class="flex justify-between gap-2"><dt class="text-zinc-500">分辨率</dt><dd class="font-mono text-zinc-300">{{ video.width }}×{{ video.height }}{{ video.fps ? ` @ ${video.fps}fps` : '' }}</dd></div>
              <div class="flex justify-between gap-2"><dt class="text-zinc-500">编码</dt><dd class="font-mono text-zinc-300">{{ video.vcodec || '—' }} / {{ video.acodec || '—' }}</dd></div>
              <div class="flex justify-between gap-2"><dt class="text-zinc-500">大小</dt><dd class="font-mono text-zinc-300">{{ fmtSize(video.file_size) }}</dd></div>
              <div class="flex justify-between gap-2"><dt class="text-zinc-500">入库时间</dt><dd class="text-zinc-300">{{ fmtDateTime(video.created_at) }}</dd></div>
            </dl>
            <div class="mt-2.5">
              <div class="mb-1 text-[11px] text-zinc-500">存储路径（绝对路径）</div>
              <div class="flex gap-1.5">
                <input readonly :value="video.absolute_path || video.video_path"
                  class="min-w-0 flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-[11px] text-zinc-400 outline-none" />
                <button @click="copyPath" title="一键复制"
                  class="shrink-0 rounded-lg border border-zinc-700 px-2.5 py-1.5 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">
                  复制
                </button>
              </div>
            </div>
            <div class="mt-3 flex gap-2">
              <button @click="openSource" class="flex-1 rounded-lg border border-zinc-700 px-2 py-1.5 text-[11px] text-zinc-300 hover:border-indigo-500/60 hover:text-indigo-300">打开来源页</button>
              <button :disabled="deleting" @click="onDelete" class="flex-1 rounded-lg border border-red-500/40 px-2 py-1.5 text-[11px] text-red-400 hover:bg-red-500/10 disabled:opacity-40">
                {{ deleting ? '删除中…' : '删除视频' }}
              </button>
            </div>
          </div>

          <div class="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div class="mb-2 text-xs font-medium text-zinc-400">字幕（{{ subList.length }}）</div>
            <div v-if="!subList.length" class="text-[11px] text-zinc-600">无字幕（B站/YouTube 需在「设置 → 登录管理」配置 cookies 才能拿到字幕）</div>
            <div v-else class="space-y-1.5">
              <button @click="selectSub({ id: 0 })"
                class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-xs transition-colors"
                :class="activeSubId === 0
                  ? 'border-emerald-500/60 bg-emerald-500/10 text-emerald-300'
                  : 'border-zinc-800 text-zinc-300 hover:border-zinc-600'">
                <span>关闭字幕</span>
                <span class="text-[10px] text-zinc-500">{{ activeSubId === 0 ? '当前' : '' }}</span>
              </button>
              <button v-for="s in subList" :key="s.id" @click="selectSub(s)"
                class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-xs transition-colors"
                :class="activeSubId === s.id
                  ? 'border-emerald-500/60 bg-emerald-500/10 text-emerald-300'
                  : 'border-zinc-800 text-zinc-300 hover:border-zinc-600'">
                <span>{{ s.lang }}{{ s.auto_generated ? ' · 自动' : '' }}</span>
                <span class="flex items-center gap-2">
                  <span class="text-[10px] text-zinc-500">{{ activeSubId === s.id ? '播放中' : '选为播放字幕' }}</span>
                  <span @click.stop="viewSubtitle(s)" class="text-[10px] text-indigo-400 hover:text-indigo-300">查看 →</span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 字幕内容弹窗 -->
      <div v-if="subContent" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-8" @click.self="subContent = null">
        <div class="flex max-h-[75vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
          <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
            <span class="text-sm font-medium">字幕 · {{ subTitle }}</span>
            <button class="text-zinc-500 hover:text-zinc-200" @click="subContent = null">✕</button>
          </div>
          <pre class="overflow-y-auto p-4 font-mono text-xs leading-5 text-zinc-300">{{ subContent }}</pre>
        </div>
      </div>
    </template>
  </div>
</template>
