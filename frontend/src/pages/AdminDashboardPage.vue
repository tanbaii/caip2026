<template>
  <div class="page-shell space-y-6">
    <section class="relative overflow-hidden rounded-[2rem] bg-slate-950 p-6 text-white shadow-2xl shadow-slate-900/25 md:p-8">
      <div class="absolute -left-16 top-10 h-52 w-52 rounded-full bg-blue-500/20 blur-3xl"></div>
      <div class="absolute -right-20 -top-20 h-72 w-72 rounded-full border border-emerald-300/20 bg-emerald-300/10 blur-2xl"></div>
      <div class="relative grid gap-6 xl:grid-cols-[1fr_420px] xl:items-end">
        <div>
          <p class="text-xs font-black uppercase tracking-[0.28em] text-emerald-300">Operations Deck</p>
          <h1 class="mt-3 text-4xl font-black tracking-tight md:text-5xl">后台运营看板</h1>
          <p class="mt-3 max-w-3xl text-sm font-semibold leading-7 text-slate-300">把反诈知识库、举报处理、学习闯关和规则运维汇总到一张指挥台。数据来自 SQLite 聚合和运行时规则快照，举报内容只展示脱敏摘要。</p>
        </div>
        <div class="rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur">
          <label class="text-xs font-black uppercase tracking-widest text-slate-400">管理员令牌</label>
          <div class="mt-2 flex gap-2">
            <input v-model="adminToken" type="password" class="min-w-0 flex-1 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm font-bold text-white placeholder:text-slate-600 focus:border-emerald-300" placeholder="X-Admin-Token" @keyup.enter="loadDashboard" />
            <button class="rounded-2xl bg-emerald-300 px-5 py-3 text-sm font-black text-slate-950 transition hover:bg-emerald-200 disabled:opacity-50" :disabled="loading || !adminToken" @click="loadDashboard">{{ loading ? '加载中' : '连接' }}</button>
          </div>
          <p class="mt-2 text-xs font-semibold text-slate-500">与规则管理页共用会话令牌，不写入数据库。</p>
        </div>
      </div>
    </section>

    <p v-if="message" class="rounded-2xl px-4 py-3 text-sm font-bold ring-1" :class="messageTone === 'error' ? 'bg-red-50 text-red-700 ring-red-100' : 'bg-emerald-50 text-emerald-700 ring-emerald-100'">{{ message }}</p>

    <template v-if="summary">
      <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="注册用户" :value="fmt(summary.users.total)" :detail="`学生 ${roleCount('student')} · 泛用户 ${roleCount('general')}`" tone="blue" />
        <MetricCard label="累计举报" :value="fmt(summary.reports.total)" :detail="`待处理 ${statusCount('pending')} · 高危 ${verdictCount('high_risk')}`" tone="rose" />
        <MetricCard label="高危劝阻" :value="fmt(summary.engagement.high_risk_blocks)" detail="聊天中触发 high/critical 劝阻" tone="amber" />
        <MetricCard label="知识库覆盖" :value="fmt(summary.knowledge.scam_count)" :detail="`${summary.knowledge.sourced_scam_count} 条带权威来源`" tone="emerald" />
      </section>

      <section class="grid gap-6 2xl:grid-cols-[1.2fr_0.8fr]">
        <BaseCard padding-class="p-6" class="space-y-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="section-kicker">Risk Funnel</p>
              <h2 class="mt-1 text-2xl font-black text-slate-950">举报风险态势</h2>
            </div>
            <StatusBadge tone="muted">平均分 {{ summary.reports.avg_score }}</StatusBadge>
          </div>
          <div class="grid gap-4 md:grid-cols-3">
            <DistributionCard label="安全" :value="verdictCount('safe')" :total="summary.reports.total" tone="emerald" />
            <DistributionCard label="可疑" :value="verdictCount('suspicious')" :total="summary.reports.total" tone="amber" />
            <DistributionCard label="高危" :value="verdictCount('high_risk')" :total="summary.reports.total" tone="rose" />
          </div>
          <div>
            <div class="mb-3 flex items-center justify-between">
              <h3 class="text-sm font-black text-slate-900">近 7 日举报趋势</h3>
              <span class="text-xs font-bold text-slate-400">高危 / 总量</span>
            </div>
            <div v-if="summary.reports.trend.length" class="space-y-3">
              <div v-for="item in summary.reports.trend" :key="item.day" class="grid grid-cols-[92px_1fr_64px] items-center gap-3">
                <span class="text-xs font-black text-slate-500">{{ item.day }}</span>
                <div class="h-3 overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-rose-500" :style="{ width: percent(item.total, maxTrendTotal) + '%' }"></div>
                </div>
                <span class="text-right text-xs font-black text-slate-700">{{ item.high_risk }}/{{ item.total }}</span>
              </div>
            </div>
            <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">暂无举报趋势数据。</p>
          </div>
        </BaseCard>

        <BaseCard padding-class="p-6" class="space-y-5">
          <div>
            <p class="section-kicker">Rule Ops</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">规则与知识运营</h2>
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <MiniStat label="文本规则" :value="`${summary.rules.enabled_text_rule_count}/${summary.rules.text_rule_count}`" />
            <MiniStat label="URL 规则" :value="`${summary.rules.enabled_url_rule_count}/${summary.rules.url_rule_count}`" />
            <MiniStat label="文本版本" :value="summary.rules.versions.text" />
            <MiniStat label="URL 版本" :value="summary.rules.versions.url" />
          </div>
          <div class="rounded-3xl bg-slate-950 p-5 text-white">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">Active Revision</p>
            <p class="mt-2 text-3xl font-black">#{{ summary.rules.active_revision.id }}</p>
            <p class="mt-2 text-sm font-semibold leading-6 text-slate-300">{{ summary.rules.active_revision.change_summary }}</p>
          </div>
          <div class="space-y-3">
            <h3 class="text-sm font-black text-slate-900">最近规则变更</h3>
            <article v-for="item in summary.rules.recent_changes.slice(0, 4)" :key="item.id" class="rounded-2xl border border-slate-100 bg-slate-50 p-3">
              <div class="flex items-center justify-between gap-3">
                <strong class="text-sm text-slate-900">#{{ item.id }} · {{ item.action }}</strong>
                <span class="text-xs font-black text-slate-400">{{ item.text_version }} / {{ item.url_version }}</span>
              </div>
              <p class="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">{{ item.change_summary }}</p>
            </article>
          </div>
        </BaseCard>
      </section>

      <section class="grid gap-6 2xl:grid-cols-[0.85fr_1.15fr]">
        <BaseCard padding-class="p-6" class="space-y-6">
          <div>
            <p class="section-kicker">Hot Signals</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">高频线索</h2>
          </div>
          <SignalList title="Top 关键词" :items="summary.reports.top_keywords" label-key="keyword" value-key="count" empty="暂无关键词命中。" />
          <SignalList title="Top 可疑域名" :items="summary.reports.top_hosts" label-key="host" value-key="count" empty="暂无 URL 举报。" />
        </BaseCard>

        <BaseCard padding-class="p-0" class="overflow-hidden">
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-6">
            <div>
              <p class="section-kicker">Review Queue</p>
              <h2 class="mt-1 text-2xl font-black text-slate-950">最近举报处理队列</h2>
            </div>
            <StatusBadge tone="warning">pending {{ statusCount('pending') }}</StatusBadge>
          </div>
          <div v-if="summary.reports.recent.length" class="max-h-[36rem] divide-y divide-slate-100 overflow-y-auto">
            <article v-for="item in summary.reports.recent" :key="item.report_id" class="grid gap-4 p-5 xl:grid-cols-[1fr_130px] xl:items-center">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <code class="text-xs font-black text-slate-500">{{ item.report_id }}</code>
                  <StatusBadge :tone="verdictTone(item.verdict)">{{ verdictLabel(item.verdict) }}</StatusBadge>
                  <StatusBadge :tone="statusTone(item.status)">{{ statusLabel(item.status) }}</StatusBadge>
                  <span class="text-xs font-bold text-slate-400">user #{{ item.user_id }} · {{ item.created_at }}</span>
                </div>
                <p class="mt-2 break-all text-sm font-bold text-slate-700">{{ item.url_host || item.content_summary || '无 URL / 无摘要' }}</p>
                <p v-if="item.reasons?.length" class="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-400">{{ item.reasons.join('；') }}</p>
                <div class="mt-4 rounded-2xl border border-slate-100 bg-slate-50/80 p-3">
                  <div class="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
                    <div class="min-w-0 space-y-3">
                      <div class="flex flex-wrap gap-2">
                        <button
                          v-for="option in reviewVerdictOptions"
                          :key="option.value"
                          type="button"
                          class="rounded-xl px-3 py-2 text-xs font-black transition"
                          :class="draftFor(item).verdict === option.value ? option.activeClass : 'bg-white text-slate-500 ring-1 ring-slate-200 hover:text-slate-900'"
                          @click="setDraftVerdict(item.report_id, option.value)"
                        >
                          {{ option.label }}
                        </button>
                      </div>
                      <textarea
                        :value="draftFor(item).review_note"
                        class="focus-ring min-h-20 w-full resize-none rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold leading-5 text-slate-700"
                        maxlength="500"
                        placeholder="复核备注：例如已电话核实、误报、已建议用户报警..."
                        @input="setDraftNote(item.report_id, $event.target.value)"
                      />
                    </div>
                    <div class="flex flex-wrap gap-2 lg:flex-col">
                      <button
                        type="button"
                        class="rounded-xl bg-blue-600 px-4 py-2 text-xs font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                        :disabled="reviewingReportId === item.report_id"
                        @click="submitReview(item, 'reviewed')"
                      >
                        {{ reviewingReportId === item.report_id ? '提交中' : '复核通过' }}
                      </button>
                      <button
                        type="button"
                        class="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                        :disabled="reviewingReportId === item.report_id"
                        @click="submitReview(item, 'closed')"
                      >
                        关闭归档
                      </button>
                    </div>
                  </div>
                  <p
                    v-if="feedbackFor(item.report_id)"
                    class="mt-3 rounded-xl px-3 py-2 text-xs font-black ring-1"
                    :class="feedbackFor(item.report_id).tone === 'error' ? 'bg-red-50 text-red-700 ring-red-100' : 'bg-emerald-50 text-emerald-700 ring-emerald-100'"
                  >
                    {{ feedbackFor(item.report_id).text }}
                  </p>
                  <div v-if="item.review_note || item.reviewed_at" class="mt-3 rounded-xl bg-white p-3 text-xs font-bold text-slate-600 ring-1 ring-slate-200">
                    <p class="text-[11px] font-black uppercase tracking-widest text-slate-400">{{ savedReviewLabel }}</p>
                    <p v-if="item.review_note" class="mt-1 break-words leading-5 text-slate-700">{{ item.review_note }}</p>
                    <p class="mt-1 break-words text-[11px] font-semibold text-slate-400">{{ reviewMetaText(item) }}</p>
                  </div>
                </div>
              </div>
              <div class="text-left xl:text-right">
                <p class="text-xs font-black uppercase tracking-widest text-slate-400">Risk Score</p>
                <p class="mt-1 text-3xl font-black text-slate-950">{{ item.score }}</p>
              </div>
            </article>
          </div>
          <p v-else class="p-8 text-center text-sm font-bold text-slate-400">暂无举报记录。</p>
        </BaseCard>
      </section>

      <section class="grid gap-6 2xl:grid-cols-2">
        <BaseCard padding-class="p-6" class="space-y-5">
          <div>
            <p class="section-kicker">Learning Loop</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">闯关学习效果</h2>
          </div>
          <div v-if="summary.scenarios.length" class="max-h-96 space-y-3 overflow-y-auto pr-1">
            <article v-for="item in summary.scenarios" :key="item.scenario_id" class="rounded-3xl border border-slate-100 bg-slate-50 p-4">
              <div class="flex items-center justify-between gap-3">
                <strong class="text-sm font-black text-slate-900">{{ item.scenario_id }}</strong>
                <span class="text-xs font-black text-slate-500">{{ item.completions }} 次完成</span>
              </div>
              <div class="mt-3 h-2 overflow-hidden rounded-full bg-white">
                <div class="h-full rounded-full bg-blue-600" :style="{ width: Math.min(100, item.avg_best_percent) + '%' }"></div>
              </div>
              <p class="mt-2 text-xs font-semibold text-slate-500">平均最佳分 {{ item.avg_best_percent }}% · 尝试 {{ item.attempts }} 次</p>
            </article>
          </div>
          <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">暂无闯关数据。</p>
        </BaseCard>

        <BaseCard padding-class="p-6" class="space-y-5">
          <div>
            <p class="section-kicker">Growth</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">用户成长分布</h2>
          </div>
          <SignalList title="等级分布" :items="levelItems" label-key="label" value-key="count" empty="暂无等级数据。" />
          <SignalList title="勋章分布" :items="summary.users.badge_distribution" label-key="badge" value-key="count" empty="暂无勋章数据。" />
          <div class="rounded-3xl bg-emerald-50 p-5">
            <p class="text-xs font-black uppercase tracking-widest text-emerald-700">Sources</p>
            <p class="mt-2 text-sm font-bold leading-6 text-emerald-900">权威来源覆盖 {{ summary.knowledge.source_organizations.length }} 个机构，知识库覆盖 {{ summary.knowledge.coverage.length }} 类场景。</p>
          </div>
        </BaseCard>
      </section>
    </template>

    <section v-else class="soft-card p-10 text-center">
      <Gauge class="mx-auto h-10 w-10 text-slate-300" />
      <h2 class="mt-4 text-xl font-black text-slate-900">连接后台看板</h2>
      <p class="mt-2 text-sm font-semibold text-slate-500">输入管理员令牌后，可查看运营指标、举报队列、规则版本和学习效果。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Gauge } from 'lucide-vue-next'
import { getDashboardSummary, reviewReport } from '../api/dashboard.js'
import { useAdminAuth } from '../composables/useAdminAuth.js'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const admin = useAdminAuth()
const adminToken = admin.adminToken
const loading = ref(false)
const summary = ref(null)
const message = ref('')
const messageTone = ref('success')
const reviewDrafts = ref({})
const reviewFeedbacks = ref({})
const reviewingReportId = ref('')

const reviewVerdictOptions = [
  { value: 'safe', label: '安全', riskLevel: 'low', score: 15, activeClass: 'bg-emerald-600 text-white shadow-sm shadow-emerald-200' },
  { value: 'suspicious', label: '可疑', riskLevel: 'medium', score: 55, activeClass: 'bg-amber-500 text-white shadow-sm shadow-amber-200' },
  { value: 'high_risk', label: '高危', riskLevel: 'high', score: 88, activeClass: 'bg-red-600 text-white shadow-sm shadow-red-200' },
]

const savedReviewLabel = '\u5df2\u4fdd\u5b58\u590d\u6838'
const maxTrendTotal = computed(() => Math.max(1, ...((summary.value?.reports?.trend || []).map((item) => item.total))))
const levelItems = computed(() => (summary.value?.users?.level_distribution || []).map((item) => ({ ...item, label: `Lv.${item.level}` })))

const MetricCard = {
  props: { label: String, value: [String, Number], detail: String, tone: String },
  template: `<article class="soft-card relative overflow-hidden p-5"><div class="absolute -right-6 -top-8 h-24 w-24 rounded-full opacity-20" :class="{ 'bg-blue-500': tone === 'blue', 'bg-rose-500': tone === 'rose', 'bg-amber-400': tone === 'amber', 'bg-emerald-500': tone === 'emerald' }"></div><p class="text-xs font-black uppercase tracking-widest text-slate-400">{{ label }}</p><p class="mt-3 text-4xl font-black text-slate-950">{{ value }}</p><p class="mt-1 text-sm font-bold text-slate-500">{{ detail }}</p></article>`,
}

const MiniStat = {
  props: { label: String, value: [String, Number] },
  template: `<div class="rounded-2xl bg-slate-50 p-4"><p class="text-xs font-black uppercase tracking-widest text-slate-400">{{ label }}</p><p class="mt-2 break-words text-xl font-black text-slate-950">{{ value }}</p></div>`,
}

const DistributionCard = {
  props: { label: String, value: Number, total: Number, tone: String },
  template: `<div class="rounded-3xl border border-slate-100 bg-slate-50 p-4"><div class="flex items-end justify-between gap-3"><p class="text-sm font-black text-slate-700">{{ label }}</p><p class="text-3xl font-black text-slate-950">{{ value }}</p></div><div class="mt-3 h-2 overflow-hidden rounded-full bg-white"><div class="h-full rounded-full" :class="{ 'bg-emerald-500': tone === 'emerald', 'bg-amber-500': tone === 'amber', 'bg-rose-500': tone === 'rose' }" :style="{ width: (total > 0 ? Math.round(value / total * 100) : 0) + '%' }"></div></div></div>`,
}

const SignalList = {
  props: { title: String, items: Array, labelKey: String, valueKey: String, empty: String },
  computed: {
    maxValue() {
      return Math.max(1, ...(this.items || []).map((item) => Number(item[this.valueKey] || 0)))
    },
  },
  template: `<section><div class="mb-3 flex items-center justify-between"><h3 class="text-sm font-black text-slate-900">{{ title }}</h3><span class="text-xs font-bold text-slate-400">Top {{ (items || []).length }}</span></div><div v-if="items?.length" class="max-h-64 space-y-3 overflow-y-auto pr-1"><div v-for="item in items" :key="item[labelKey]" class="grid grid-cols-[minmax(0,1fr)_52px] items-center gap-3"><div class="min-w-0"><p class="truncate text-sm font-black text-slate-700">{{ item[labelKey] }}</p><div class="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full bg-slate-900" :style="{ width: Math.round(Number(item[valueKey] || 0) / maxValue * 100) + '%' }"></div></div></div><span class="text-right text-sm font-black text-slate-900">{{ item[valueKey] }}</span></div></div><p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">{{ empty }}</p></section>`,
}

function notify(text, tone = 'success') {
  message.value = text
  messageTone.value = tone
}

function reviewOption(verdict) {
  return reviewVerdictOptions.find((option) => option.value === verdict) || reviewVerdictOptions[1]
}

function draftFor(item) {
  const reportId = String(item.report_id)
  if (!reviewDrafts.value[reportId]) {
    const option = reviewOption(item.verdict)
    reviewDrafts.value = {
      ...reviewDrafts.value,
      [reportId]: {
        verdict: option.value,
        review_note: item.review_note || '',
        reviewer: item.reviewer || 'admin',
      },
    }
  }
  return reviewDrafts.value[reportId]
}

function updateDraft(reportId, patch) {
  const key = String(reportId)
  const current = reviewDrafts.value[key] || { verdict: 'suspicious', review_note: '', reviewer: 'admin' }
  reviewDrafts.value = {
    ...reviewDrafts.value,
    [key]: { ...current, ...patch },
  }
}

function setDraftVerdict(reportId, verdict) {
  updateDraft(reportId, { verdict })
}

function setDraftNote(reportId, reviewNote) {
  updateDraft(reportId, { review_note: reviewNote })
}

function feedbackFor(reportId) {
  return reviewFeedbacks.value[String(reportId)] || null
}

function setReviewFeedback(reportId, feedback) {
  const key = String(reportId)
  reviewFeedbacks.value = {
    ...reviewFeedbacks.value,
    [key]: feedback,
  }
}

function reviewMetaText(item) {
  return [item.reviewer || 'admin', item.reviewed_at || item.updated_at || item.created_at].filter(Boolean).join(' · ')
}

async function refreshDashboardSilently() {
  summary.value = await getDashboardSummary(adminToken.value)
}

async function submitReview(item, status) {
  if (!adminToken.value) {
    notify('\u8bf7\u5148\u8f93\u5165\u7ba1\u7406\u5458\u4ee4\u724c', 'error')
    return
  }

  const draft = draftFor(item)
  const option = reviewOption(draft.verdict)
  const reportId = String(item.report_id)
  reviewingReportId.value = item.report_id

  try {
    const reviewed = await reviewReport(adminToken.value, item.report_id, {
      status,
      reviewer: draft.reviewer || 'admin',
      review_note: draft.review_note,
      verdict: option.value,
      risk_level: option.riskLevel,
      score: option.score,
    })
    updateDraft(reportId, {
      verdict: reviewed.verdict || option.value,
      review_note: reviewed.review_note || draft.review_note,
      reviewer: reviewed.reviewer || draft.reviewer || 'admin',
    })
    setReviewFeedback(reportId, {
      tone: 'success',
      text: status === 'closed'
        ? '\u5df2\u5173\u95ed\u5f52\u6863\uff0c\u590d\u6838\u5907\u6ce8\u5df2\u4fdd\u5b58'
        : '\u590d\u6838\u901a\u8fc7\uff0c\u590d\u6838\u5907\u6ce8\u5df2\u4fdd\u5b58',
    })
    await refreshDashboardSilently()
    notify(status === 'closed' ? '\u4e3e\u62a5\u5df2\u5173\u95ed\u5f52\u6863' : '\u590d\u6838\u7ed3\u679c\u5df2\u63d0\u4ea4')
  } catch (error) {
    if (error.status === 401) {
      admin.clearAdminAccess()
    }
    setReviewFeedback(reportId, {
      tone: 'error',
      text: error.message || '\u590d\u6838\u63d0\u4ea4\u5931\u8d25',
    })
    notify(error.message || '\u590d\u6838\u63d0\u4ea4\u5931\u8d25', 'error')
  } finally {
    reviewingReportId.value = ''
  }
}

async function loadDashboard() {
  loading.value = true
  admin.setAdminToken(adminToken.value)
  try {
    summary.value = await getDashboardSummary(adminToken.value)
    notify('后台看板已连接，数据来自实时聚合')
  } catch (error) {
    if (error.status === 401) {
      admin.clearAdminAccess()
    }
    summary.value = null
    notify(error.message || '后台看板加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function fmt(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function roleCount(role) {
  return summary.value?.users?.roles?.[role] || 0
}

function verdictCount(verdict) {
  return summary.value?.reports?.verdict_distribution?.[verdict] || 0
}

function statusCount(status) {
  return summary.value?.reports?.status_distribution?.[status] || 0
}

function percent(value, total) {
  return total > 0 ? Math.max(4, Math.round(Number(value || 0) / total * 100)) : 0
}

function verdictTone(verdict) {
  return { safe: 'success', suspicious: 'warning', high_risk: 'danger' }[verdict] || 'muted'
}

function verdictLabel(verdict) {
  return { safe: '安全', suspicious: '可疑', high_risk: '高危' }[verdict] || verdict
}

function statusTone(status) {
  return { pending: 'warning', reviewed: 'info', closed: 'muted' }[status] || 'muted'
}

function statusLabel(status) {
  return { pending: '待处理', reviewed: '已复核', closed: '已关闭' }[status] || status
}
</script>
