<template>
  <span class="inline-flex items-center rounded-full border px-3 py-1 text-xs font-black" :class="toneClass">
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
    info: 'border-blue-100 bg-blue-50 text-blue-700',
    success: 'border-emerald-100 bg-emerald-50 text-emerald-700',
    warning: 'border-orange-100 bg-orange-50 text-orange-700',
    danger: 'border-red-100 bg-red-50 text-red-700',
    muted: 'border-slate-200 bg-slate-50 text-slate-500',
  }
  return tones[props.tone] || tones.info
})
</script>
