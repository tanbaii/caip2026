<template>
  <section class="space-y-3">
    <h3 class="text-sm font-black text-slate-900">命中规则</h3>
    <div v-if="items.length" class="space-y-2">
      <div v-for="(rule, index) in items" :key="index" class="rounded-2xl border border-slate-100 bg-white p-3">
        <div class="flex items-center justify-between gap-2">
          <span class="min-w-0 truncate text-sm font-black text-slate-800">{{ ruleName(rule.rule) }}</span>
          <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-black" :class="weightClass(rule.weight)">+{{ rule.weight }}</span>
        </div>
        <p class="mt-1 text-xs font-semibold leading-5 text-slate-500">{{ rule.reason }}</p>
        <div v-if="rule.evidence && rule.evidence.length" class="mt-2 flex flex-wrap gap-1">
          <span v-for="ev in rule.evidence" :key="ev" class="max-w-full break-all rounded-full bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-700 ring-1 ring-blue-100">{{ ev }}</span>
        </div>
      </div>
    </div>
    <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂未命中规则。</p>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

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
}

function ruleName(rule) {
  return ruleLabels[rule] || rule
}

function weightClass(weight) {
  if (weight >= 20) return 'bg-red-50 text-red-700 ring-1 ring-red-100'
  if (weight >= 15) return 'bg-orange-50 text-orange-700 ring-1 ring-orange-100'
  return 'bg-slate-50 text-slate-700 ring-1 ring-slate-100'
}
</script>
