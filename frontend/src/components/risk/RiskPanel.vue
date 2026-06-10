<template>
  <aside class="w-full min-w-0 xl:w-[360px]">
    <BaseCard
      padding-class="p-0"
      class="flex min-h-0 flex-col overflow-hidden xl:sticky xl:top-5 xl:max-h-[calc(100vh-2.5rem)]"
      :class="hasRisk && isHighRisk ? 'ring-2 ring-red-100 shadow-red-100/80' : ''"
    >
      <div class="flex shrink-0 items-center justify-between gap-4 border-b border-slate-100 bg-white/95 px-5 py-5 backdrop-blur">
        <div>
          <p class="section-kicker" :class="hasRisk && isHighRisk ? 'text-red-500' : ''">Risk Console</p>
          <h2 class="mt-1 text-2xl font-black text-slate-950">风险分析面板</h2>
        </div>
        <div class="flex h-12 w-12 items-center justify-center rounded-3xl" :class="hasRisk && isHighRisk ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'">
          <ShieldAlert class="h-7 w-7" />
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div v-if="!hasRisk" class="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-slate-400 shadow-sm">
            <Radar class="h-7 w-7" />
          </div>
          <h3 class="mt-5 text-lg font-black text-slate-900">等待首次研判</h3>
          <p class="mt-2 text-sm font-medium leading-6 text-slate-500">发送可疑对话后，这里会展示风险等级、命中规则、劝阻建议和下一步动作。</p>
        </div>

        <div v-else class="space-y-6">
          <section v-if="isHighRisk" class="rounded-3xl border border-red-100 bg-red-50 p-4 text-red-700 shadow-sm shadow-red-100/80">
            <p class="text-sm font-black">高风险拦截提示</p>
            <p class="mt-2 text-sm font-semibold leading-6">立即停止转账，不要共享屏幕或验证码，并通过官方渠道核验对方身份。</p>
          </section>

          <section class="risk-section">
            <RiskScoreCard :risk="risk" />
            <RiskBreakdown :breakdown="risk.riskBreakdown" />
          </section>

          <section v-if="risk.turnCount > 0" class="risk-section">
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-black text-slate-500">会话状态</span>
              <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="stageBadgeClass">{{ stageLabel }}</span>
            </div>
            <p class="text-xs font-semibold leading-5 text-slate-500">{{ risk.conversationSummary }}</p>
            <div v-if="Object.keys(risk.knownFacts).length" class="flex flex-wrap gap-1.5">
              <span v-for="(val, key) in risk.knownFacts" :key="key" class="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-slate-600 ring-1 ring-slate-200">{{ factLabel(key) }}</span>
            </div>
            <div v-if="risk.pendingQuestions.length" class="space-y-1">
              <p class="text-xs font-black text-amber-700">待确认</p>
              <p v-for="(q, i) in risk.pendingQuestions" :key="i" class="text-xs font-semibold leading-5 text-amber-600">{{ q }}</p>
            </div>
          </section>

          <section class="risk-section">
            <ScamMatchList :items="risk.matchedScams" />
          </section>

          <section class="risk-section">
            <MatchedRuleList :items="risk.matchedRules" />
          </section>

          <section class="risk-section">
            <RecommendationList title="劝阻话术" :items="risk.interventionScript" />
            <NextActionList :items="risk.nextActions" />
            <RecommendationList title="防护建议" :items="risk.recommendations" />
          </section>

          <section class="grid grid-cols-2 gap-3">
            <div class="rounded-2xl bg-blue-50 p-4 text-blue-700 ring-1 ring-blue-100">
              <p class="text-xs font-black uppercase tracking-widest">本次积分</p>
              <p class="mt-1 text-2xl font-black">+{{ risk.pointsGained }}</p>
            </div>
            <div class="rounded-2xl bg-slate-50 p-4 text-slate-700 ring-1 ring-slate-100">
              <p class="text-xs font-black uppercase tracking-widest">总积分</p>
              <p class="mt-1 text-2xl font-black">{{ risk.totalPoints }}</p>
            </div>
          </section>

          <section class="risk-section">
            <h3 class="text-sm font-black text-slate-900">勋章与性能</h3>
            <div class="flex flex-wrap gap-2">
              <StatusBadge v-for="badge in risk.badges" :key="badge" tone="info">{{ badge }}</StatusBadge>
              <StatusBadge v-if="!risk.badges.length" tone="muted">暂无新勋章</StatusBadge>
              <StatusBadge tone="muted">{{ risk.latencyMs.toFixed(1) }} ms</StatusBadge>
            </div>
          </section>
        </div>
      </div>
    </BaseCard>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { Radar, ShieldAlert } from 'lucide-vue-next'
import { useRiskPanel } from '../../composables/useRiskPanel.js'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'
import MatchedRuleList from './MatchedRuleList.vue'
import NextActionList from './NextActionList.vue'
import RecommendationList from './RecommendationList.vue'
import RiskBreakdown from './RiskBreakdown.vue'
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

const isHighRisk = computed(() => ['high', 'critical'].includes(risk.value.level))

const stageLabels = {
  collecting: '信息收集',
  assessing: '风险评估',
  warning: '紧急预警',
  debriefing: '复盘总结',
}
const stageLabel = computed(() => stageLabels[risk.value.sessionStage] || risk.value.sessionStage)
const stageBadgeClass = computed(() => {
  if (risk.value.sessionStage === 'warning') return 'bg-red-50 text-red-700 ring-1 ring-red-100'
  if (risk.value.sessionStage === 'assessing') return 'bg-orange-50 text-orange-700 ring-1 ring-orange-100'
  return 'bg-blue-50 text-blue-700 ring-1 ring-blue-100'
})

const factLabels = {
  has_transfer_request: '转账要求',
  has_verification_code_request: '索要验证码',
  has_url: '含链接',
  has_remote_control: '远程控制',
  has_secrecy_pressure: '保密施压',
  has_time_pressure: '限时催促',
  already_paid: '已付款',
  mentions_authority: '冒充公检法',
  mentions_investment: '投资理财',
  mentions_reward_or_subsidy: '奖金补贴',
  mentions_ai_deepfake: 'AI伪造',
}
function factLabel(key) {
  return factLabels[key] || key
}
</script>
