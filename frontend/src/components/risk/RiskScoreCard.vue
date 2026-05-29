<template>
  <div class="rounded-3xl border p-5 shadow-sm" :class="[risk.meta.bg, risk.meta.border]">
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.22em]" :class="risk.meta.text">Risk Score</p>
        <div class="mt-2 flex items-end gap-2">
          <span class="text-5xl font-black tracking-tighter" :class="risk.meta.text">{{ risk.score }}</span>
          <span class="pb-2 text-sm font-black text-slate-400">/ 100</span>
        </div>
      </div>
      <StatusBadge :tone="risk.tone">{{ risk.label }}</StatusBadge>
    </div>
    <div class="mt-5 h-3 overflow-hidden rounded-full bg-white/80">
      <div class="h-full rounded-full transition-all" :class="risk.meta.bar" :style="{ width: `${Math.min(risk.score, 100)}%` }" />
    </div>
    <div class="mt-4 rounded-2xl bg-white/80 p-3 text-sm font-semibold leading-6 text-slate-600 ring-1 ring-white/80">
      <span class="font-black text-slate-800">识别意图：</span>{{ risk.intent }}
    </div>
  </div>
</template>

<script setup>
import StatusBadge from '../common/StatusBadge.vue'

defineProps({
  risk: {
    type: Object,
    required: true,
  },
})
</script>
