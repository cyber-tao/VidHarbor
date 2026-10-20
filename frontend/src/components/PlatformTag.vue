<script setup>
import { computed } from 'vue'
import { platformLabel, platformColor } from '../format.js'

const props = defineProps({ platform: { type: String, required: true } })
const label = computed(() => platformLabel(props.platform))
const color = computed(() => platformColor(props.platform))
</script>

<template>
  <span class="inline-flex items-center gap-1 rounded-full border border-zinc-700/80 bg-zinc-900/80 px-2 py-0.5 text-[11px] text-zinc-300">
    <span class="h-1.5 w-1.5 rounded-full" :style="{ background: color }"></span>
    {{ label }}
  </span>
</template>
