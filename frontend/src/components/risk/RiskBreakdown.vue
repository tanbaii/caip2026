<template>
  <section v-if="hasScores" class="space-y-3">
    <h3 class="text-sm font-black text-slate-900">风险分构成</h3>
    <div class="max-h-56 space-y-2 overflow-y-auto pr-1">
      <div v-for="dim in dimensions" :key="dim.key" class="flex items-center gap-3 text-sm">
        <span class="w-20 shrink-0 text-xs font-bold text-slate-500">{{ dim.label }}</span>
        <div class="flex-1 min-w-0 h-2 overflow-hidden rounded-full bg-slate-100">
          <div class="h-full rounded-full transition-all" :class="dim.bar" :style="{ width: dim.pct + '%' }" />
        </div>
        <span class="w-8 shrink-0 text-right text-xs font-black text-slate-600">{{ dim.value }}</span>
      </div>
    </div>
    <div v-if="total > 0" class="flex items-center justify-end gap-2 border-t border-slate-100 pt-2">
      <span class="text-xs font-bold text-slate-500">合计</span>
      <span class="text-sm font-black text-slate-900">{{ total }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  breakdown: {
    type: Object,
    default: () => ({}),
  },
})

const dimensionDefs = [
  { key: 'text_score',     label: '文本规则', bar: 'bg-blue-500' },
  { key: 'url_score',      label: 'URL 风险', bar: 'bg-purple-500' },
  { key: 'content_score',  label: '文本风险', bar: 'bg-blue-500' },
  { key: 'knowledge_score',label: '知识库',   bar: 'bg-emerald-500' },
  { key: 'profile_score',  label: '用户画像', bar: 'bg-indigo-500' },
  { key: 'emotion_score',  label: '情绪信号', bar: 'bg-pink-500' },
]

const hasScores = computed(() => Object.keys(props.breakdown).length > 0)

const total = computed(() => Number(props.breakdown.total) || 0)

const dimensions = computed(() => {
  const maxVal = Math.max(
    total.value,
    ...dimensionDefs.map(d => Number(props.breakdown[d.key]) || 0),
  ) || 1

  return dimensionDefs
    .filter(d => (props.breakdown[d.key] || 0) > 0)
    .map(d => ({
      ...d,
      value: Number(props.breakdown[d.key]) || 0,
      pct: Math.round(((Number(props.breakdown[d.key]) || 0) / maxVal) * 100),
    }))
})
</script>
