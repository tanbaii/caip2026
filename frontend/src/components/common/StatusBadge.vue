<template>
  <span class="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-black shadow-sm" :class="toneClass">
    <slot />
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tone: {
    type: String,
    default: 'info',
  },
})

const toneClass = computed(() => {
  const tones = {
    info: 'border-blue-100 bg-blue-50 text-blue-700 shadow-blue-100/70',
    success: 'border-emerald-100 bg-emerald-50 text-emerald-700 shadow-emerald-100/70',
    warning: 'border-orange-100 bg-orange-50 text-orange-700 shadow-orange-100/70',
    danger: 'border-red-100 bg-red-50 text-red-700 shadow-red-100/70',
    muted: 'border-slate-200 bg-slate-50 text-slate-500 shadow-slate-100/70',
  }
  return tones[props.tone] || tones.info
})
</script>
