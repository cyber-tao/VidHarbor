<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { darkTheme, dateEnUS, dateZhCN, enUS, NConfigProvider, NMessageProvider, zhCN } from 'naive-ui'
import { access, api } from './api.js'
import { isDark, isZh, locale, setLocale, t, toggleTheme } from './i18n.js'
import { useEvents } from './stores.js'
import LogDrawer from './components/LogDrawer.vue'

const events = useEvents()
const route = useRoute()

onMounted(async () => {
  try {
    const s = await api.sessionStatus()
    if (s.required && !s.authenticated) {
      access.denied = true
      return
    }
  } catch { /* 状态接口不可用时照常连接，SSE 自带重连 */ }
  events.connect()
})

const tokenInput = ref('')
const tokenError = ref('')
async function submitToken() {
  tokenError.value = ''
  try {
    await api.createSession(tokenInput.value.trim())
    location.reload()
  } catch (e) {
    tokenError.value = e.message
  }
}

const langOpen = ref(false)
const langWrapRef = ref(null)
const langBtnRef = ref(null)
let hoverTimer = null
let hoverOpenedAt = 0

function openLangHover(e) {
  if (e && e.pointerType && e.pointerType !== 'mouse') return
  clearTimeout(hoverTimer)
  if (!langOpen.value) {
    langOpen.value = true
    hoverOpenedAt = Date.now()
  }
}
function closeLangHover(e) {
  if (e && e.pointerType && e.pointerType !== 'mouse') return
  clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => { langOpen.value = false }, 150)
}
function toggleLangMenu() {
  if (langOpen.value && Date.now() - hoverOpenedAt < 350) {
    return
  }
  langOpen.value = !langOpen.value
}
function chooseLang(next) {
  setLocale(next)
  langOpen.value = false
}
function onKeydown(e) {
  if (e.key === 'Escape' && langOpen.value) {
    langOpen.value = false
    langBtnRef.value?.focus()
  }
}
function onDocClick(e) {
  if (langOpen.value && langWrapRef.value && !langWrapRef.value.contains(e.target)) {
    langOpen.value = false
  }
}
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('pointerdown', onDocClick)
})
onBeforeUnmount(() => {
  clearTimeout(hoverTimer)
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('pointerdown', onDocClick)
})

const nav = computed(() => [
  { path: '/', label: t('app.nav.dashboard'), icon: 'M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10' },
  { path: '/charts', label: t('app.nav.charts'), icon: 'M5 20V9m7 11V4m7 16v-7' },
  { path: '/tasks', label: t('app.nav.tasks'), icon: 'M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2' },
  { path: '/library', label: t('app.nav.library'), icon: 'M4 5h16v14H4zM4 9h16M9 9v10' },
  { path: '/schedules', label: t('app.nav.schedules'), icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM12 2v2' },
  { path: '/settings', label: t('app.nav.settings'), icon: 'M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h0a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h0a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v0a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z' },
])
</script>

<template>
  <NConfigProvider
    :theme="isDark ? darkTheme : null"
    :locale="isZh ? zhCN : enUS"
    :date-locale="isZh ? dateZhCN : dateEnUS"
    class="h-full"
  >
    <NMessageProvider placement="top-right">
      <div class="flex h-full min-h-0">
        <!-- Sidebar -->
        <aside class="fixed inset-y-0 left-0 z-30 flex w-52 flex-col border-r border-zinc-800 bg-zinc-900/80 backdrop-blur">
          <div class="flex items-center gap-2.5 px-5 py-5">
            <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-lg text-white shadow-lg shadow-indigo-500/20">⚓</div>
            <div>
              <div class="text-[15px] font-semibold tracking-wide text-zinc-100">VidHarbor</div>
              <div class="text-[11px] text-zinc-500">{{ t('app.subtitle') }}</div>
            </div>
          </div>

          <nav class="mt-2 flex-1 space-y-1 px-3">
            <router-link v-for="item in nav" :key="item.path" :to="item.path"
              class="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors"
              :class="route.path === item.path
                ? 'bg-indigo-500/15 text-indigo-300 font-medium'
                : 'text-zinc-400 hover:bg-zinc-800/70 hover:text-zinc-200'">
              <svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg>
              <span>{{ item.label }}</span>
              <span v-if="item.path === '/tasks' && events.activeCount > 0"
                class="ml-auto rounded-full bg-indigo-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                {{ events.activeCount }}
              </span>
            </router-link>
          </nav>

          <!-- Language / Theme / GitHub Controls -->
          <div class="border-t border-zinc-800 px-4 py-3">
            <div class="flex items-center justify-between">
              <!-- Language Control -->
              <div
                ref="langWrapRef"
                class="relative flex items-center"
                @pointerenter="openLangHover"
                @pointerleave="closeLangHover"
              >
                <button
                  ref="langBtnRef"
                  type="button"
                  data-testid="lang-trigger"
                  :aria-label="t('app.langLabel')"
                  :aria-expanded="langOpen ? 'true' : 'false'"
                  aria-haspopup="true"
                  class="flex h-9 items-center gap-1 rounded-lg px-2 text-zinc-300 transition-colors duration-200 hover:text-zinc-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
                  @click="toggleLangMenu"
                >
                  <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m5 8 6 6" /><path d="m4 14 6-6 2-3" /><path d="M2 5h12" /><path d="M7 2h1" /><path d="m22 22-5-10-5 10" /><path d="M14 18h6" />
                  </svg>
                  <svg class="h-3.5 w-3.5 transition-transform duration-200" :class="langOpen ? 'rotate-180' : ''" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </button>

                <div
                  v-show="langOpen"
                  data-testid="lang-menu"
                  class="absolute bottom-full left-0 z-50 mb-1.5 min-w-[128px] rounded-xl border border-zinc-700 bg-zinc-900 p-1.5 shadow-xl"
                >
                  <button
                    type="button"
                    data-testid="lang-option-en"
                    class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-zinc-800 hover:text-indigo-300"
                    :class="locale === 'en' ? 'font-semibold text-indigo-300' : 'text-zinc-300'"
                    @click="chooseLang('en')"
                  >
                    <span>English</span>
                    <span v-if="locale === 'en'" class="text-[10px]">✓</span>
                  </button>
                  <button
                    type="button"
                    data-testid="lang-option-zh"
                    class="mt-0.5 flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-zinc-800 hover:text-indigo-300"
                    :class="locale === 'zh' ? 'font-semibold text-indigo-300' : 'text-zinc-300'"
                    @click="chooseLang('zh')"
                  >
                    <span>简体中文</span>
                    <span v-if="locale === 'zh'" class="text-[10px]">✓</span>
                  </button>
                </div>
              </div>

              <span class="h-6 w-px bg-zinc-800" aria-hidden="true"></span>

              <!-- Theme Switch Control (40x22 pill, 18px thumb, 12px sun/moon) -->
              <button
                type="button"
                role="switch"
                data-testid="theme-switch"
                :aria-checked="isDark ? 'true' : 'false'"
                :aria-label="isDark ? t('app.switchToLight') : t('app.switchToDark')"
                :title="isDark ? t('app.switchToLight') : t('app.switchToDark')"
                class="relative inline-flex h-[22px] w-[40px] shrink-0 cursor-pointer items-center rounded-full border border-zinc-700 bg-zinc-950 p-[1px] transition-colors duration-200 hover:border-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
                @click="toggleTheme"
              >
                <span
                  class="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-zinc-800 text-zinc-200 shadow-sm transition-transform duration-200"
                  :style="{ transform: isDark ? 'translateX(18px)' : 'translateX(0px)' }"
                >
                  <!-- Moon (Dark) -->
                  <svg v-if="isDark" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
                  </svg>
                  <!-- Sun (Light) -->
                  <svg v-else class="h-3 w-3 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                  </svg>
                </span>
              </button>

              <span class="h-6 w-px bg-zinc-800" aria-hidden="true"></span>

              <!-- GitHub Control (36px target, 20px icon) -->
              <a
                href="https://github.com/cyber-tao/VidHarbor"
                target="_blank"
                rel="noopener"
                data-testid="github-link"
                :aria-label="t('app.githubLabel')"
                :title="t('app.githubLabel')"
                class="flex h-9 w-9 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
              </a>
            </div>
          </div>

          <div class="px-5 pb-4 pt-1 text-[11px] text-zinc-600">
            <div class="flex items-center gap-1.5">
              <span class="inline-block h-1.5 w-1.5 rounded-full" :class="events.connected ? 'bg-emerald-400' : 'bg-zinc-600'"></span>
              {{ events.connected ? t('app.sseConnected') : t('app.sseDisconnected') }}
            </div>
            <div class="mt-1">VidHarbor v0.3.0</div>
          </div>
        </aside>

        <!-- Main Content Area -->
        <main class="ml-52 flex min-h-0 flex-1 flex-col pb-9">
          <router-view v-slot="{ Component }">
            <component :is="Component" class="flex-1 overflow-y-auto" />
          </router-view>
        </main>
      </div>

      <LogDrawer />

      <!-- Access Token Modal -->
      <div v-if="access.denied" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-6">
        <form class="w-full max-w-sm space-y-3 rounded-xl border border-zinc-700 bg-zinc-900 p-5" @submit.prevent="submitToken">
          <div class="text-sm font-medium text-zinc-100">{{ t('app.tokenRequired') }}</div>
          <div class="text-[11px] leading-4 text-zinc-500">
            {{ t('app.tokenDesc') }}
          </div>
          <input v-model="tokenInput" type="password" autocomplete="current-password" :placeholder="t('app.tokenPlaceholder')"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
          <div v-if="tokenError" class="text-[11px] text-red-400">{{ tokenError }}</div>
          <button type="submit" :disabled="!tokenInput.trim()"
            class="w-full rounded-lg bg-indigo-500 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-40">
            {{ t('app.tokenSubmit') }}
          </button>
        </form>
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>
