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
          <div v-if="summary.reports.recent.length" class="divide-y divide-slate-100">
            <article v-for="item in summary.reports.recent" :key="item.report_id" class="grid gap-4 p-5 xl:grid-cols-[1fr_130px] xl:items-center">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <code class="text-xs font-black text-slate-500">{{ item.report_id }}</code>
                  <StatusBadge :tone="verdictTone(item.verdict)">{{ verdictLabel(item.verdict) }}</StatusBadge>
                  <StatusBadge :tone="statusTone(item.status)">{{ statusLabel(item.status) }}</StatusBadge>
                  <span class="text-xs font-bold text-slate-400">user #{{ item.user_id }} · {{ item.created_at }}</span>
                </div>
                <p class="mt-2 break-words text-sm font-bold text-slate-700">{{ item.url_host || item.content_summary || '无 URL / 无摘要' }}</p>
                <p v-if="item.reasons?.length" class="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-400">{{ item.reasons.join('；') }}</p>
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
          <div v-if="summary.scenarios.length" class="space-y-3">
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
import { getDashboardSummary } from '../api/dashboard.js'
import { useAdminAuth } from '../composables/useAdminAuth.js'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const admin = useAdminAuth()
const adminToken = admin.adminToken
const loading = ref(false)
const summary = ref(null)
const message = ref('')
const messageTone = ref('success')

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
  template: `<section><div class="mb-3 flex items-center justify-between"><h3 class="text-sm font-black text-slate-900">{{ title }}</h3><span class="text-xs font-bold text-slate-400">Top {{ (items || []).length }}</span></div><div v-if="items?.length" class="space-y-3"><div v-for="item in items" :key="item[labelKey]" class="grid grid-cols-[minmax(0,1fr)_52px] items-center gap-3"><div class="min-w-0"><p class="truncate text-sm font-black text-slate-700">{{ item[labelKey] }}</p><div class="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full bg-slate-900" :style="{ width: Math.round(Number(item[valueKey] || 0) / maxValue * 100) + '%' }"></div></div></div><span class="text-right text-sm font-black text-slate-900">{{ item[valueKey] }}</span></div></div><p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">{{ empty }}</p></section>`,
}

function notify(text, tone = 'success') {
  message.value = text
  messageTone.value = tone
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
