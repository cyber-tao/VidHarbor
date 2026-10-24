<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { NPagination, useMessage } from 'naive-ui'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import { PLATFORM_OPTIONS, fmtCount, platformLabel } from '../format.js'
import { t } from '../i18n.js'
import VideoCard from '../components/VideoCard.vue'

const route = useRoute()

const message = useMessage()
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 48
const q = ref('')
const platform = ref('')
const loading = ref(false)
const platformFilters = computed(() => [
  { id: '', label: t('platforms.all') },
  ...PLATFORM_OPTIONS,
  { id: 'other', label: platformLabel('other') },
])

function parseTags(raw) {
  return typeof raw === 'string' && raw.trim()
    ? raw.split(',').map((s) => s.trim()).filter(Boolean)
    : []
}

const allTags = ref([])
const activeTags = ref(parseTags(route.query.tag))

let searchTimer = null

async function load() {
  loading.value = true
  try {
    const params = {
      q: q.value, platform: platform.value,
      page: page.value, page_size: pageSize,
    }
    if (activeTags.value.length) params.tag = activeTags.value.join(',')
    const res = await api.videos(params)
    items.value = res.items
    total.value = res.total
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  try {
    const res = await api.tags(platform.value ? { platform: platform.value } : {})
    allTags.value = res.tags
  } catch { /* silent */ }
}

function reload() {
  if (page.value === 1) load()
  else page.value = 1
}

onMounted(() => {
  load(); loadTags()
})

watch(q, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 400)
})
watch(platform, () => {
  reload(); loadTags()
})
watch(page, load)
watch(activeTags, reload, { deep: true })

function toggleTag(name) {
  const i = activeTags.value.indexOf(name)
  if (i >= 0) activeTags.value.splice(i, 1)
  else activeTags.value.push(name)
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-4 p-6">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-xl font-semibold">{{ t('library.title') }}</h1>
      <span class="text-xs text-zinc-500">{{ t('library.videoCount', { n: fmtCount(total) }) }}</span>
      <input v-model="q" :placeholder="t('library.searchPlaceholder')"
        class="ml-auto w-64 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500" />
    </div>

    <div class="flex flex-wrap gap-2">
      <button v-for="p in platformFilters" :key="p.id" @click="platform = p.id"
        class="rounded-full border px-3 py-1 text-xs transition-colors"
        :class="platform === p.id
          ? 'border-indigo-500 bg-indigo-500/15 text-indigo-300'
          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'">
        {{ p.label }}
      </button>
    </div>

    <!-- Tag Aggregation Filter -->
    <div v-if="allTags.length" class="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
      <div class="flex items-center gap-2">
        <span class="text-[11px] text-zinc-500">{{ t('library.tagFilter') }}</span>
        <span class="text-[10px] text-zinc-600">{{ t('library.tagAndHint') }}</span>
        <button v-if="activeTags.length" @click="activeTags = []"
          class="ml-auto text-[11px] text-zinc-500 hover:text-red-300">{{ t('library.clearTags', { n: activeTags.length }) }}</button>
      </div>
      <div class="mt-2 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">
        <button v-for="tagItem in allTags" :key="tagItem.name" @click="toggleTag(tagItem.name)"
          class="rounded-full border px-2.5 py-0.5 text-[11px] transition-colors"
          :class="activeTags.includes(tagItem.name)
            ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300'
            : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'">
          #{{ tagItem.name }}<span class="ml-1 text-[10px] text-zinc-500">{{ tagItem.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="loading && !items.length" class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i" class="h-52 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/60"></div>
    </div>
    <div v-else-if="!items.length" class="flex flex-col items-center gap-2 py-20 text-zinc-600">
      <span class="text-3xl">📚</span>
      <span class="text-sm">{{ activeTags.length ? t('library.emptyFiltered') : t('library.emptyLibrary') }}</span>
      <router-link to="/charts" class="mt-1 text-xs text-indigo-400 hover:text-indigo-300">{{ t('library.goCharts') }}</router-link>
    </div>
    <template v-else>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        <VideoCard v-for="v in items" :key="v.id" :video="v" />
      </div>
      <div class="flex justify-center pt-2">
        <NPagination v-model:page="page" :page-count="Math.max(1, Math.ceil(total / pageSize))"
          :page-size="pageSize" />
      </div>
    </template>
  </div>
</template>
