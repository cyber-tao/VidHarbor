<script setup>
import { nextTick, ref, watch } from 'vue'
import { useEvents } from '../stores.js'
import { fmtTime } from '../format.js'

const events = useEvents()
const bodyRef = ref(null)

const levelClass = {
  ERROR: 'text-red-400',
  WARNING: 'text-amber-400',
  CRITICAL: 'text-red-400',
}

function onToggle() {
  events.logExpanded = !events.logExpanded
  if (events.logExpanded) scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  const el = bodyRef.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => events.logs.length,
  () => {
    if (events.logExpanded && !events.logPaused) scrollToBottom()
  },
)
</script>

<template>
  <div class="fixed bottom-0 left-52 right-0 z-40 border-t border-zinc-800 bg-zinc-950/95 backdrop-blur">
    <!-- 折叠条 -->
    <div class="flex h-9 items-center gap-2 px-4 text-xs">
      <button class="flex items-center gap-1.5 rounded px-1.5 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        @click="onToggle">
        <svg class="h-3.5 w-3.5 transition-transform" :class="events.logExpanded ? 'rotate-180' : ''"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        日志
      </button>
      <span class="text-zinc-700">|</span>
      <div class="min-w-0 flex-1 truncate font-mono text-[11px]"
        :class="levelClass[events.lastLog?.level] || 'text-zinc-500'">
        <span v-if="events.lastLog" class="text-zinc-600">{{ fmtTime(events.lastLog.ts) }} </span>{{ events.lastLog?.message ?? '暂无日志' }}
      </div>
      <template v-if="events.logExpanded">
        <button class="rounded px-2 py-1 hover:bg-zinc-800 hover:text-zinc-200"
          :class="events.logPaused ? 'text-amber-400' : 'text-zinc-400'"
          @click="events.logPaused = !events.logPaused">
          {{ events.logPaused ? '继续滚动' : '暂停滚动' }}
        </button>
        <button class="rounded px-2 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          @click="events.logs = []">清空</button>
      </template>
      <span class="font-mono text-[10px] text-zinc-600">{{ events.logs.length }}</span>
    </div>
    <!-- 展开面板 -->
    <div v-if="events.logExpanded" ref="bodyRef"
      class="h-72 overflow-y-auto border-t border-zinc-800/70 bg-black/40 px-4 py-2 font-mono text-[11px] leading-5">
      <div v-if="!events.logs.length" class="text-zinc-600">暂无日志</div>
      <div v-for="(l, i) in events.logs" :key="i" class="whitespace-pre-wrap break-all">
        <span class="text-zinc-600">{{ fmtTime(l.ts) }}</span>
        <span :class="levelClass[l.level] || 'text-zinc-400'"> {{ l.level.padEnd(7) }}</span>
        <span class="text-zinc-500"> {{ l.name.replace('vidharbor.', '') }} </span>
        <span :class="l.level === 'ERROR' || l.level === 'WARNING' ? '' : 'text-zinc-300'">{{ l.message }}</span>
      </div>
    </div>
  </div>
</template>
