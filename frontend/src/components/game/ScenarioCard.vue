<template>
  <button
    type="button"
    class="group interactive-card w-full rounded-3xl border bg-white p-5 text-left shadow-sm shadow-slate-200/60"
    :class="active ? 'border-blue-300 bg-blue-50/40 ring-4 ring-blue-100' : 'border-slate-200'"
    @click="$emit('start', scenario.id)"
  >
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.22em] text-blue-600">{{ scenario.id || '-' }}</p>
        <h3 class="mt-2 text-lg font-black text-slate-900">{{ scenario.title || '未命名关卡' }}</h3>
        <p class="mt-2 flex flex-wrap gap-1.5">
          <span class="inline-flex max-w-full rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{{ scenario.scam_type || '-' }}</span>
          <span v-if="scenario.mode === 'case_mystery'" class="inline-flex rounded-full bg-purple-50 px-3 py-1 text-xs font-black text-purple-700 ring-1 ring-purple-100">剧本推理</span>
        </p>
        <p v-if="scenario.story" class="mt-2 line-clamp-2 text-xs font-medium leading-5 text-slate-400">{{ scenario.story }}</p>
      </div>
      <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white">
        <Gamepad2 class="h-5 w-5" />
      </div>
    </div>
  </button>
</template>

<script setup>
import { Gamepad2 } from 'lucide-vue-next'

defineProps({
  scenario: {
    type: Object,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['start'])
</script>
