<template>
  <BaseCard padding-class="p-6 md:p-8" class="min-h-[520px] space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.24em] text-indigo-600">Scenario Player</p>
        <h2 class="mt-1 text-2xl font-black text-slate-900">{{ scenario?.title || '选择一个关卡开始' }}</h2>
      </div>
      <BaseButton v-if="scenario" variant="secondary" @click="$emit('reset')">重新选择</BaseButton>
    </div>

    <div v-if="!scenario" class="flex min-h-[360px] items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
      <div>
        <p class="text-lg font-black text-slate-900">还没有开始闯关</p>
        <p class="mt-2 text-sm font-medium text-slate-500">从左侧关卡列表选择一个真实后端关卡。</p>
      </div>
    </div>

    <template v-else>
      <div class="rounded-3xl bg-slate-50 p-6 ring-1 ring-slate-100">
        <p class="text-xs font-black uppercase tracking-widest text-slate-400">Step {{ safeNumber(scenario.step_index) + 1 }}</p>
        <p class="mt-3 text-lg font-black leading-8 text-slate-800">{{ scenario.prompt || '暂无剧情内容' }}</p>
      </div>

      <div v-if="scenario.feedback" class="rounded-3xl bg-blue-50 p-5 text-blue-800 ring-1 ring-blue-100">
        <p class="text-xs font-black uppercase tracking-widest">反馈</p>
        <p class="mt-2 text-sm font-bold leading-7">{{ scenario.feedback }}</p>
      </div>

      <div v-if="scenario.finished" class="rounded-3xl bg-emerald-50 p-6 text-emerald-800 ring-1 ring-emerald-100">
        <p class="text-xl font-black">闯关完成</p>
        <p class="mt-2 text-sm font-bold">本次积分 +{{ safeNumber(scenario.points_gained) }}，当前总分 {{ safeNumber(scenario.total_points) }}</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <StatusBadge v-for="badge in list(scenario.badges)" :key="badge" tone="success">{{ badge }}</StatusBadge>
          <StatusBadge v-if="!list(scenario.badges).length" tone="muted">暂无新徽章</StatusBadge>
        </div>
      </div>

      <div v-else class="space-y-3">
        <button
          v-for="(option, index) in list(scenario.options)"
          :key="`${index}-${option}`"
          type="button"
          :disabled="loading"
          class="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left text-sm font-black leading-6 text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          @click="$emit('answer', index)"
        >
          {{ index + 1 }}. {{ option }}
        </button>
        <p v-if="!list(scenario.options).length" class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无可选答案。</p>
      </div>
    </template>
  </BaseCard>
</template>

<script setup>
import BaseButton from '../common/BaseButton.vue'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'

defineProps({
  scenario: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['answer', 'reset'])

function list(value) {
  return Array.isArray(value) ? value : []
}

function safeNumber(value) {
  return Number(value) || 0
}
</script>
