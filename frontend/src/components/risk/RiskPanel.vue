<template>
  <aside class="w-full xl:w-[390px]">
    <BaseCard padding-class="p-5" class="sticky top-6 space-y-6">
      <div class="flex items-center justify-between gap-4">
        <div>
          <p class="text-xs font-black uppercase tracking-[0.24em] text-blue-600">Risk Console</p>
          <h2 class="mt-1 text-2xl font-black text-slate-900">风险分析面板</h2>
        </div>
        <ShieldAlert class="h-7 w-7 text-blue-600" />
      </div>

      <div v-if="!hasRisk" class="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-slate-400 shadow-sm">
          <Radar class="h-7 w-7" />
        </div>
        <h3 class="mt-5 text-lg font-black text-slate-900">等待首次研判</h3>
        <p class="mt-2 text-sm font-medium leading-6 text-slate-500">发送可疑对话后，这里会展示风险等级、骗局类型、劝阻建议和积分变化。</p>
      </div>

      <template v-else>
        <RiskScoreCard :risk="risk" />
        <ScamMatchList :items="risk.matchedScams" />
        <RecommendationList title="劝阻话术" :items="risk.interventionScript" />
        <RecommendationList title="防护建议" :items="risk.recommendations" />

        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-2xl bg-blue-50 p-4 text-blue-700 ring-1 ring-blue-100">
            <p class="text-xs font-black uppercase tracking-widest">本次积分</p>
            <p class="mt-1 text-2xl font-black">+{{ risk.pointsGained }}</p>
          </div>
          <div class="rounded-2xl bg-slate-50 p-4 text-slate-700 ring-1 ring-slate-100">
            <p class="text-xs font-black uppercase tracking-widest">总积分</p>
            <p class="mt-1 text-2xl font-black">{{ risk.totalPoints }}</p>
          </div>
        </div>

        <div class="space-y-3">
          <h3 class="text-sm font-black text-slate-900">勋章与性能</h3>
          <div class="flex flex-wrap gap-2">
            <StatusBadge v-for="badge in risk.badges" :key="badge" tone="info">{{ badge }}</StatusBadge>
            <StatusBadge v-if="!risk.badges.length" tone="muted">暂无新勋章</StatusBadge>
            <StatusBadge tone="muted">{{ risk.latencyMs.toFixed(1) }} ms</StatusBadge>
          </div>
        </div>
      </template>
    </BaseCard>
  </aside>
</template>

<script setup>
import { Radar, ShieldAlert } from 'lucide-vue-next'
import { useRiskPanel } from '../../composables/useRiskPanel.js'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'
import RecommendationList from './RecommendationList.vue'
import RiskScoreCard from './RiskScoreCard.vue'
import ScamMatchList from './ScamMatchList.vue'

const props = defineProps({
  riskResult: {
    type: Object,
    default: null,
  },
})

const { hasRisk, risk } = useRiskPanel({
  get value() {
    return props.riskResult
  },
})
</script>
