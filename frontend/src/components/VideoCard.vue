<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { fmtDuration, fmtSize, platformLabel, platformColor } from '../format.js'
import { authUrl } from '../api.js'

const props = defineProps({ video: { type: Object, required: true } })
const router = useRouter()
const thumbUrl = computed(() => authUrl(`/api/videos/${props.video.id}/thumbnail`))
</script>

<template>
  <div class="group cursor-pointer overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/60 transition-all hover:border-zinc-600 hover:shadow-lg hover:shadow-black/40"
    @click="router.push(`/video/${video.id}`)">
    <div class="relative aspect-video overflow-hidden bg-zinc-800">
      <img :src="thumbUrl" :alt="video.title" referrerpolicy="no-referrer" loading="lazy"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" />
      <span class="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] text-zinc-200">
        {{ fmtDuration(video.duration) }}
      </span>
      <span v-if="video.subtitles_count > 0"
        class="absolute left-1.5 top-1.5 rounded bg-black/75 px-1.5 py-0.5 text-[10px] text-indigo-300">
        CC {{ video.subtitles_count }}
      </span>
    </div>
    <div class="space-y-1.5 p-3">
      <div class="line-clamp-2 text-[13px] font-medium leading-5 text-zinc-200">{{ video.title }}</div>
      <div class="flex items-center justify-between text-[11px] text-zinc-500">
        <span class="flex min-w-0 items-center gap-1.5">
          <span class="h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: platformColor(video.platform) }"></span>
          <span class="truncate">{{ video.uploader || platformLabel(video.platform) }}</span>
        </span>
        <span class="shrink-0">{{ fmtSize(video.file_size) }}</span>
      </div>
    </div>
  </div>
</template>
