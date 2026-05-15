<template>
  <button
    type="button"
    class="group w-full rounded-3xl border bg-white p-5 text-left shadow-sm shadow-slate-200/60 transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-100"
    :class="active ? 'border-blue-300 ring-4 ring-blue-100' : 'border-slate-200'"
    @click="$emit('start', scenario.id)"
  >
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.22em] text-blue-600">{{ scenario.id || '-' }}</p>
        <h3 class="mt-2 text-lg font-black text-slate-900">{{ scenario.title || '未命名关卡' }}</h3>
        <p class="mt-2 text-sm font-semibold text-slate-500">骗局类型：{{ scenario.scam_type || '-' }}</p>
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
