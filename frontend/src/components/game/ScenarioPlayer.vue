<template>
  <BaseCard padding-class="p-6 md:p-8" class="min-h-[520px] space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="section-kicker">Scenario Player</p>
        <h2 class="mt-1 text-2xl font-black text-slate-950">{{ scenario?.title || '选择一个关卡开始' }}</h2>
        <span v-if="scenario?.mode === 'case_mystery'" class="mt-1 inline-block rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-black text-purple-700 ring-1 ring-purple-100">剧本推理</span>
        <p v-if="scenario && !scenario.finished" class="mt-2 text-sm font-bold text-slate-500">
          本局 {{ safeNumber(scenario.run_score) }}/{{ safeNumber(scenario.max_score) }} 分
          <span v-if="safeNumber(scenario.previous_best) > 0"> · 历史最佳 {{ safeNumber(scenario.previous_best) }}</span>
        </p>
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
      <!-- Case Mystery: Story & Role intro -->
      <div v-if="scenario.story && showIntro" class="space-y-4">
        <div class="rounded-3xl bg-gradient-to-br from-purple-50 to-white p-5 ring-1 ring-purple-100/70">
          <p class="text-xs font-black uppercase tracking-widest text-purple-600">案件背景</p>
          <p class="mt-3 break-words text-sm font-semibold leading-7 text-slate-700">{{ scenario.story }}</p>
          <div v-if="scenario.role" class="mt-3 flex items-center gap-2">
            <span class="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-black text-purple-700">你的角色</span>
            <span class="text-sm font-bold text-purple-800">{{ scenario.role }}</span>
          </div>
        </div>

        <div v-if="list(scenario.objectives).length" class="rounded-3xl bg-amber-50 p-5 ring-1 ring-amber-100">
          <p class="text-xs font-black uppercase tracking-widest text-amber-700">案件目标</p>
          <ul class="mt-2 space-y-1.5">
            <li v-for="(obj, i) in list(scenario.objectives)" :key="i" class="flex gap-2 text-sm font-semibold text-slate-700">
              <span class="text-amber-600">{{ i + 1 }}.</span>
              <span>{{ obj }}</span>
            </li>
          </ul>
        </div>

        <div v-if="list(scenario.characters).length" class="space-y-2">
          <p class="text-xs font-black uppercase tracking-widest text-slate-500">涉案人物</p>
          <div class="grid gap-2 sm:grid-cols-2">
            <div v-for="ch in list(scenario.characters)" :key="ch.name" class="rounded-2xl border border-slate-100 bg-white p-3">
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-black text-slate-800">{{ ch.name }}</span>
                <span
                  class="rounded-full px-2 py-0.5 text-xs font-bold"
                  :class="ch.suspicion_level === 'high' ? 'bg-red-50 text-red-700 ring-1 ring-red-100' : ch.suspicion_level === 'medium' ? 'bg-orange-50 text-orange-700 ring-1 ring-orange-100' : 'bg-slate-50 text-slate-600 ring-1 ring-slate-100'"
                >{{ ch.suspicion_level === 'high' ? '高疑' : ch.suspicion_level === 'medium' ? '中疑' : '待查' }}</span>
              </div>
              <p class="mt-1 text-xs font-semibold text-slate-500">{{ ch.role }}</p>
              <p class="mt-1 text-xs leading-5 text-slate-600">{{ ch.description }}</p>
            </div>
          </div>
        </div>

        <BaseButton variant="primary" class="w-full" @click="showIntro = false">开始推理</BaseButton>
      </div>

      <template v-if="!showIntro || !scenario.story">
        <!-- Clues panel (case mystery mode) -->
        <details v-if="list(scenario.clues).length" class="rounded-3xl border border-slate-100 bg-white">
          <summary class="cursor-pointer p-4 text-sm font-black text-slate-800">
            线索卡片（{{ list(scenario.clues).length }} 条）
          </summary>
          <div class="space-y-2 px-4 pb-4">
            <div v-for="clue in list(scenario.clues)" :key="clue.id" class="rounded-2xl border border-blue-50 bg-blue-50/40 p-3">
              <div class="flex items-center gap-2">
                <span class="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-black text-blue-700">{{ clue.id }}</span>
                <span class="text-sm font-black text-slate-800">{{ clue.title }}</span>
              </div>
              <p class="mt-1.5 text-xs font-semibold leading-5 text-slate-600">{{ clue.content }}</p>
              <p v-if="clue.risk_signal" class="mt-1 text-xs font-bold text-red-600">风险信号：{{ clue.risk_signal }}</p>
            </div>
          </div>
        </details>

        <!-- Step prompt -->
        <div class="rounded-3xl bg-gradient-to-br from-blue-50 to-white p-6 ring-1 ring-blue-100/70">
          <div class="flex items-center justify-between gap-4">
            <p class="text-xs font-black uppercase tracking-widest text-blue-600">Step {{ safeNumber(scenario.step_index) + 1 }}</p>
            <div class="h-2 w-28 overflow-hidden rounded-full bg-blue-100">
              <div class="h-full rounded-full bg-blue-600" :style="{ width: `${stepProgress}%` }" />
            </div>
          </div>
          <p class="mt-4 break-words text-xl font-black leading-9 text-slate-800">{{ scenario.prompt || '暂无剧情内容' }}</p>
        </div>

        <!-- Feedback -->
        <div v-if="scenario.feedback" class="rounded-3xl border border-blue-100 bg-blue-50 p-5 text-blue-800 shadow-sm shadow-blue-100/70">
          <p class="text-xs font-black uppercase tracking-widest">反馈</p>
          <p class="mt-2 text-sm font-bold leading-7">{{ scenario.feedback }}</p>
        </div>

        <!-- Completion -->
        <div v-if="scenario.finished" class="space-y-4">
          <div class="rounded-3xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-6 text-emerald-800 shadow-lg shadow-emerald-100/60">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-2xl font-black">闯关完成</p>
              <StatusBadge :tone="scenario.first_clear ? 'success' : 'info'">{{ scenario.first_clear ? '首次通关' : `第 ${safeNumber(scenario.attempts)} 次挑战` }}</StatusBadge>
            </div>
            <div class="mt-4 grid gap-3 sm:grid-cols-3">
              <div class="rounded-2xl bg-white/80 p-3">
                <p class="text-xs font-black text-emerald-600">本局成绩</p>
                <p class="mt-1 text-2xl font-black">{{ safeNumber(scenario.run_score) }}/{{ safeNumber(scenario.max_score) }}</p>
              </div>
              <div class="rounded-2xl bg-white/80 p-3">
                <p class="text-xs font-black text-emerald-600">历史最佳</p>
                <p class="mt-1 text-2xl font-black">{{ safeNumber(scenario.best_score) }}</p>
              </div>
              <div class="rounded-2xl bg-white/80 p-3">
                <p class="text-xs font-black text-emerald-600">本次奖励</p>
                <p class="mt-1 text-2xl font-black">+{{ safeNumber(scenario.points_gained) }}</p>
              </div>
            </div>
            <p v-if="safeNumber(scenario.points_gained) > 0" class="mt-3 text-sm font-bold">
              {{ scenario.first_clear ? '包含首次通关奖励与本局成绩分。' : `刷新最佳成绩 ${safeNumber(scenario.score_improvement)} 分，奖励对应增量。` }}当前总分 {{ safeNumber(scenario.total_points) }}。
            </p>
            <p v-else class="mt-3 text-sm font-bold">本次未超过历史最佳，不重复发放积分。当前总分 {{ safeNumber(scenario.total_points) }}。</p>
            <div class="mt-4 flex flex-wrap gap-2">
              <StatusBadge v-for="badge in list(scenario.new_badges)" :key="badge" tone="success">新徽章：{{ badge }}</StatusBadge>
              <StatusBadge v-if="!list(scenario.new_badges).length" tone="muted">本次暂无新徽章</StatusBadge>
            </div>
          </div>

          <!-- Case Summary -->
          <div v-if="scenario.case_summary" class="rounded-3xl bg-gradient-to-br from-purple-50 to-white p-5 ring-1 ring-purple-100">
            <p class="text-xs font-black uppercase tracking-widest text-purple-600">案件复盘</p>
            <p class="mt-3 break-words text-sm font-semibold leading-7 text-slate-700">{{ scenario.case_summary }}</p>
          </div>

          <!-- Debrief -->
          <div v-if="list(scenario.debrief).length" class="rounded-3xl bg-amber-50 p-5 ring-1 ring-amber-100">
            <p class="text-xs font-black uppercase tracking-widest text-amber-700">反诈知识点</p>
            <ul class="mt-3 space-y-2">
              <li v-for="(point, i) in list(scenario.debrief)" :key="i" class="flex gap-2 text-sm font-semibold leading-6 text-slate-700">
                <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-200 text-xs font-black text-amber-800">{{ i + 1 }}</span>
                <span class="min-w-0 break-words">{{ point }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Options -->
        <div v-else class="space-y-3">
          <button
            v-for="(option, index) in list(scenario.options)"
            :key="`${index}-${option}`"
            type="button"
            :disabled="loading"
            class="interactive-card w-full rounded-2xl border border-slate-200 bg-white p-4 text-left text-sm font-black leading-6 text-slate-700 shadow-sm shadow-slate-200/60 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            @click="$emit('answer', index)"
          >
            {{ index + 1 }}. {{ option }}
          </button>
          <p v-if="!list(scenario.options).length" class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无可选答案。</p>
        </div>
      </template>
    </template>
  </BaseCard>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import BaseButton from '../common/BaseButton.vue'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'

const props = defineProps({
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

const showIntro = ref(false)
const lastScenarioId = ref(null)

const stepProgress = computed(() => {
  const total = Math.max(1, safeNumber(props.scenario?.total_steps))
  const current = Math.min(total, safeNumber(props.scenario?.step_index) + 1)
  return Math.round((current / total) * 100)
})

watch(() => props.scenario, (val) => {
  if (!val) {
    showIntro.value = false
    lastScenarioId.value = null
    return
  }
  if (val.scenario_id !== lastScenarioId.value) {
    lastScenarioId.value = val.scenario_id
    showIntro.value = Boolean(val.story)
  }
}, { immediate: true })

function list(value) {
  return Array.isArray(value) ? value : []
}

function safeNumber(value) {
  return Number(value) || 0
}
</script>
