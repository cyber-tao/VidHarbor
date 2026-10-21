<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { darkTheme, NConfigProvider, NMessageProvider, NDialogProvider } from 'naive-ui'
import { useEvents } from './stores.js'
import LogDrawer from './components/LogDrawer.vue'

const events = useEvents()
const route = useRoute()
const router = useRouter()
onMounted(() => events.connect())

const nav = [
  { path: '/', label: '仪表盘', icon: 'M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10' },
  { path: '/charts', label: '热门榜单', icon: 'M5 20V9m7 11V4m7 16v-7' },
  { path: '/tasks', label: '下载任务', icon: 'M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2' },
  { path: '/library', label: '视频库', icon: 'M4 5h16v14H4zM4 9h16M9 9v10' },
  { path: '/schedules', label: '定时任务', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM12 2v2' },
  { path: '/settings', label: '设置', icon: 'M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h0a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h0a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v0a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z' },
]
const active = computed(() => nav.find((n) => n.path === route.path) || nav[0])
</script>

<template>
  <NConfigProvider :theme="darkTheme" class="h-full">
    <NMessageProvider placement="top-right">
      <NDialogProvider>
        <div class="flex h-full min-h-0">
          <!-- 侧边栏 -->
          <aside class="fixed inset-y-0 left-0 z-30 flex w-52 flex-col border-r border-zinc-800 bg-zinc-900/80 backdrop-blur">
            <div class="flex items-center gap-2.5 px-5 py-5">
              <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-lg shadow-lg shadow-indigo-500/20">⚓</div>
              <div>
                <div class="text-[15px] font-semibold tracking-wide">VidHarbor</div>
                <div class="text-[11px] text-zinc-500">影坞 · 本地视频库</div>
              </div>
            </div>
            <nav class="mt-2 flex-1 space-y-1 px-3">
              <router-link v-for="item in nav" :key="item.path" :to="item.path"
                class="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors"
                :class="route.path === item.path
                  ? 'bg-indigo-500/15 text-indigo-300'
                  : 'text-zinc-400 hover:bg-zinc-800/70 hover:text-zinc-200'">
                <svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg>
                <span>{{ item.label }}</span>
                <span v-if="item.path === '/tasks' && events.activeCount > 0"
                  class="ml-auto rounded-full bg-indigo-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  {{ events.activeCount }}
                </span>
              </router-link>
            </nav>
            <div class="px-5 py-4 text-[11px] text-zinc-600">
              <div class="flex items-center gap-1.5">
                <span class="inline-block h-1.5 w-1.5 rounded-full" :class="events.connected ? 'bg-emerald-400' : 'bg-zinc-600'"></span>
                {{ events.connected ? '实时连接正常' : '连接已断开' }}
              </div>
              <div class="mt-1">VidHarbor v0.2.0</div>
            </div>
          </aside>

          <!-- 主区域 -->
          <main class="ml-52 flex min-h-0 flex-1 flex-col pb-9">
            <router-view v-slot="{ Component }">
              <component :is="Component" class="flex-1 overflow-y-auto" />
            </router-view>
          </main>
        </div>
        <LogDrawer />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
