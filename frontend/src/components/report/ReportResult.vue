<template>
  <BaseCard padding-class="p-6" class="space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="section-kicker">Analysis Result</p>
        <h2 class="mt-1 text-2xl font-black text-slate-950">举报分析结果</h2>
      </div>
      <StatusBadge v-if="result" :tone="tone">{{ verdictLabel }}</StatusBadge>
    </div>

    <div v-if="!result" class="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-blue-500 shadow-sm shadow-slate-200/70">!</div>
      <p class="mt-4 text-sm font-bold leading-6 text-slate-500">提交举报后，这里会显示风险分、命中关键词、判定原因和处理建议。</p>
    </div>

    <template v-else>
      <div class="rounded-3xl p-5 ring-1 shadow-sm" :class="scoreClass">
        <p class="text-xs font-black uppercase tracking-widest">风险分</p>
        <div class="mt-2 flex items-end gap-2">
          <p class="text-5xl font-black tracking-tighter">{{ normalizedScore }}</p>
          <span class="pb-2 text-sm font-black opacity-60">/ 100</span>
        </div>
        <p class="mt-3 min-w-0 break-words text-sm font-semibold">举报单号：{{ result.report_id || '-' }}</p>
        <p v-if="safeNumber(result.risk_score) > 100" class="mt-2 text-xs font-bold opacity-70">规则累计 {{ safeNumber(result.risk_score) }} 分，展示值已归一化为 100。</p>
      </div>

      <section class="space-y-3">
        <h3 class="text-sm font-black text-slate-900">命中关键词</h3>
        <div v-if="list(result.matched_keywords).length" class="flex flex-wrap gap-2">
          <span v-for="keyword in list(result.matched_keywords)" :key="keyword" class="max-w-full break-words rounded-full bg-red-50 px-3 py-1.5 text-xs font-black text-red-700 shadow-sm shadow-red-100 ring-1 ring-red-100">{{ keyword }}</span>
        </div>
        <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无关键词命中。</p>
      </section>

      <ResultList title="判定原因" :items="list(result.reasons)" />
      <ResultList title="URL 特征" :items="list(result.url_flags)" />

      <section class="space-y-3">
        <h3 class="text-sm font-black text-slate-900">命中规则</h3>
        <div v-if="list(result.matched_rules).length" class="space-y-2">
          <div v-for="(rule, index) in list(result.matched_rules)" :key="index" class="rounded-2xl border border-slate-100 bg-white p-3">
            <div class="flex items-center justify-between gap-2">
              <span class="min-w-0 truncate text-sm font-black text-slate-800">{{ ruleName(rule.rule) }}</span>
              <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-black" :class="weightClass(rule.weight)">+{{ rule.weight }}</span>
            </div>
            <p class="mt-1 text-xs font-semibold leading-5 text-slate-500">{{ rule.reason }}</p>
            <p v-if="rule.rule_version || rule.ruleset_version" class="mt-1 text-[11px] font-black text-slate-400">
              规则 v{{ rule.rule_version || '-' }} · 规则集 v{{ rule.ruleset_version || '-' }}
            </p>
            <div v-if="rule.evidence && rule.evidence.length" class="mt-2 flex flex-wrap gap-1">
              <span v-for="ev in rule.evidence" :key="ev" class="max-w-full break-all rounded-full bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-700 ring-1 ring-blue-100">{{ ev }}</span>
            </div>
            <details v-if="rule.rationale" class="mt-2 text-xs text-slate-500">
              <summary class="cursor-pointer font-black text-blue-600">查看判定依据</summary>
              <p class="mt-1 font-semibold leading-5">{{ rule.rationale }}</p>
            </details>
          </div>
        </div>
        <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂未命中规则。</p>
      </section>

      <RiskBreakdown :breakdown="result.risk_breakdown || {}" />
      <NextActionList :items="list(result.next_actions)" />
      <ResultList title="处理建议" :items="list(result.recommendations)" />
    </template>
  </BaseCard>
</template>

<script setup>
import { computed } from 'vue'
import BaseCard from '../common/BaseCard.vue'
import StatusBadge from '../common/StatusBadge.vue'
import NextActionList from '../risk/NextActionList.vue'
import RiskBreakdown from '../risk/RiskBreakdown.vue'

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
        <li v-for="(item, index) in items" :key="index" class="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 p-3 text-sm font-semibold leading-6 text-slate-600">
          <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">{{ index + 1 }}</span>
          <span class="min-w-0 break-words">{{ item }}</span>
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

const ruleLabels = {
  authority_pressure: '冒充公检法',
  account_takeover: '账户接管',
  transfer_before_service: '先付费后服务',
  high_return: '高收益话术',
  off_platform_trade: '绕开平台交易',
  fake_refund_or_compensation: '冒充客服退款',
  acquaintance_impersonation: '冒充熟人',
  campus_loan: '校园贷',
  ai_deepfake: 'AI 深度伪造',
  ai_investment_scam: 'AI 投资骗局',
  scholarship_fraud: '助学金/奖学金诈骗',
  airline_ticket_refund: '机票退改签诈骗',
  trust_reassurance: '主动消除戒心',
  domain_impersonation_text: '链接引导话术',
  transfer_critical: '转账关键节点',
  scam_match: '知识库匹配',
  student_campus: '学生场景',
  emotion_bonus: '情绪信号',
  keyword_blacklist: '关键词命中',
  urgency_pattern: '催促话术',
  missing_protocol: '协议缺失',
  ip_direct: 'IP 直连',
  at_symbol: '@ 符号',
  punycode: 'Punycode 域名',
  shortener: '短链域名',
  risky_tld: '高风险后缀',
  plain_http: 'HTTP 明文',
  subdomain_disguise: '子域名伪装',
  typosquatting: '相似域名抢注',
  keyword_impersonation: '诱导性域名关键词',
  domain_impersonation: '品牌域名仿冒',
  domain_whitelist: '可信域名白名单',
}

function ruleName(rule) {
  return ruleLabels[rule] || rule
}

function weightClass(weight) {
  if (weight >= 20) return 'bg-red-50 text-red-700 ring-1 ring-red-100'
  if (weight >= 15) return 'bg-orange-50 text-orange-700 ring-1 ring-orange-100'
  return 'bg-slate-50 text-slate-700 ring-1 ring-slate-100'
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

const normalizedScore = computed(() => Math.min(100, Math.max(0, safeNumber(props.result?.risk_score))))
</script>
