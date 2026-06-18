import { computed } from 'vue'

const riskMeta = {
  low: {
    label: '低风险',
    tone: 'success',
    bar: 'bg-emerald-500',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50',
    border: 'border-emerald-100',
  },
  medium: {
    label: '中风险',
    tone: 'warning',
    bar: 'bg-orange-500',
    text: 'text-orange-700',
    bg: 'bg-orange-50',
    border: 'border-orange-100',
  },
  high: {
    label: '高风险',
    tone: 'danger',
    bar: 'bg-red-500',
    text: 'text-red-700',
    bg: 'bg-red-50',
    border: 'border-red-100',
  },
  critical: {
    label: '高风险',
    tone: 'danger',
    bar: 'bg-red-600',
    text: 'text-red-700',
    bg: 'bg-red-50',
    border: 'border-red-100',
  },
}

function asList(value) {
  return Array.isArray(value) ? value : []
}

export function useRiskPanel(riskRef) {
  const hasRisk = computed(() => Boolean(riskRef.value))

  const risk = computed(() => {
    const data = riskRef.value || {}
    const level = data.risk_level || 'low'
    const meta = riskMeta[level] || riskMeta.low

    return {
      level,
      label: meta.label,
      tone: meta.tone,
      score: Number(data.risk_score) || 0,
      intent: data.intent || '暂无意图识别',
      matchedScams: asList(data.matched_scams),
      interventionScript: asList(data.intervention_script),
      recommendations: asList(data.recommendations),
      matchedRules: asList(data.matched_rules),
      riskBreakdown: data.risk_breakdown || {},
      nextActions: asList(data.next_actions),
      sessionStage: data.session_stage || 'collecting',
      knownFacts: data.known_facts || {},
      pendingQuestions: asList(data.pending_questions),
      conversationSummary: data.conversation_summary || '',
      turnCount: Number(data.turn_count) || 0,
      pointsGained: Number(data.points_gained) || 0,
      totalPoints: Number(data.total_points) || 0,
      badges: asList(data.badges),
      latencyMs: Number(data.latency_ms) || 0,
      rulesetVersions: data.ruleset_versions || {},
      meta,
    }
  })

  return {
    hasRisk,
    risk,
  }
}
