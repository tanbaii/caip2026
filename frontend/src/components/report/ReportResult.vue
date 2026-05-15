<template>
  <BaseCard padding-class="p-6" class="space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.24em] text-blue-600">Analysis Result</p>
        <h2 class="mt-1 text-2xl font-black text-slate-900">举报分析结果</h2>
      </div>
      <StatusBadge v-if="result" :tone="tone">{{ verdictLabel }}</StatusBadge>
    </div>

    <div v-if="!result" class="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
      <p class="text-sm font-bold leading-6 text-slate-500">提交举报后，这里会显示风险分、命中关键词、判定原因和处理建议。</p>
    </div>

    <template v-else>
      <div class="rounded-3xl p-5 ring-1" :class="scoreClass">
        <p class="text-xs font-black uppercase tracking-widest">风险分</p>
        <p class="mt-2 text-5xl font-black tracking-tighter">{{ safeNumber(result.risk_score) }}</p>
        <p class="mt-3 text-sm font-semibold">举报单号：{{ result.report_id || '-' }}</p>
      </div>

      <section class="space-y-3">
        <h3 class="text-sm font-black text-slate-900">命中关键词</h3>
        <div v-if="list(result.matched_keywords).length" class="flex flex-wrap gap-2">
          <span v-for="keyword in list(result.matched_keywords)" :key="keyword" class="rounded-full bg-red-50 px-3 py-1.5 text-xs font-black text-red-700 ring-1 ring-red-100">{{ keyword }}</span>
        </div>
        <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无关键词命中。</p>
      </section>

      <ResultList title="判定原因" :items="list(result.reasons)" />
      <ResultList title="URL 特征" :items="list(result.url_flags)" />
      <ResultList title="处理建议" :items="list(result.recommendations)" />
    </template>
  </BaseCard>
</template>

<script setup>
import { computed } from 'vue'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'

const props = defineProps({
  result: {
    type: Object,
    default: null,
  },
})

const ResultList = {
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
  },
  template: `
    <section class="space-y-3">
      <h3 class="text-sm font-black text-slate-900">{{ title }}</h3>
      <ol v-if="items.length" class="space-y-2">
        <li v-for="(item, index) in items" :key="index" class="rounded-2xl bg-slate-50 p-3 text-sm font-semibold leading-6 text-slate-600">
          {{ index + 1 }}. {{ item }}
        </li>
      </ol>
      <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无内容。</p>
    </section>
  `,
}

function list(value) {
  return Array.isArray(value) ? value : []
}

function safeNumber(value) {
  return Number(value) || 0
}

const verdictLabel = computed(() => {
  const labels = {
    safe: '相对安全',
    suspicious: '可疑',
    high_risk: '高风险',
  }
  return labels[props.result?.verdict] || '未知'
})

const tone = computed(() => {
  if (props.result?.verdict === 'high_risk') return 'danger'
  if (props.result?.verdict === 'suspicious') return 'warning'
  return 'success'
})

const scoreClass = computed(() => {
  if (props.result?.verdict === 'high_risk') return 'bg-red-50 text-red-700 ring-red-100'
  if (props.result?.verdict === 'suspicious') return 'bg-orange-50 text-orange-700 ring-orange-100'
  return 'bg-emerald-50 text-emerald-700 ring-emerald-100'
})
</script>
