<template>
  <div class="page-shell space-y-6">
    <div class="grid min-h-0 gap-6 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-start">
      <ReportForm :loading="loading" :error="error" :initial-values="prefillValues" @submit="handleSubmit" />
      <ReportResult :result="result" />
    </div>

    <BaseCard padding-class="p-6" class="space-y-4">
      <div class="flex items-center justify-between gap-4">
        <div>
          <p class="section-kicker">History</p>
          <h2 class="mt-1 text-2xl font-black text-slate-950">最近举报记录</h2>
        </div>
        <BaseButton variant="secondary" :disabled="historyLoading || !currentUser?.user_id" @click="loadHistory">
          <Loader2 v-if="historyLoading" class="h-4 w-4 animate-spin" />
          刷新记录
        </BaseButton>
      </div>

      <p v-if="historyError" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ historyError }}</p>
      <p v-if="!currentUser?.user_id" class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-500">请先登录后查看举报记录。</p>
      <div v-else-if="!historyLoading && !history.length" class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">暂无举报记录。</div>
      <div v-else class="grid max-h-[38rem] gap-3 overflow-y-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
        <button
          v-for="item in history"
          :key="item.report_id"
          type="button"
          class="interactive-card min-w-0 rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm shadow-slate-200/70"
          @click="openDetail(item.report_id)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate font-black text-slate-900">{{ item.report_id }}</p>
              <p class="mt-1 text-xs font-semibold text-slate-400">{{ item.created_at || '-' }}</p>
            </div>
            <StatusBadge :tone="item.verdict === 'high_risk' ? 'danger' : item.verdict === 'suspicious' ? 'warning' : 'success'">{{ item.verdict || '-' }}</StatusBadge>
          </div>
          <div class="mt-4 rounded-2xl bg-slate-50 p-3">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">风险分</p>
            <p class="mt-1 text-2xl font-black text-slate-900">{{ item.score ?? '-' }}</p>
          </div>
          <p v-if="item.url_host" class="mt-3 break-all text-xs font-bold text-slate-500">域名：{{ item.url_host }}</p>
          <p v-if="item.content_summary" class="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">{{ item.content_summary }}</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <StatusBadge tone="muted">{{ statusLabel(item.status) }}</StatusBadge>
            <StatusBadge v-for="keyword in list(item.matched_keywords).slice(0, 3)" :key="keyword" tone="warning">{{ keyword }}</StatusBadge>
          </div>
          <div v-if="item.review_note || item.reviewed_at" class="mt-3 rounded-2xl bg-emerald-50 p-3 text-xs font-bold text-emerald-900 ring-1 ring-emerald-100">
            <p class="text-[11px] font-black uppercase tracking-widest text-emerald-700">{{ reviewFeedbackTitle }}</p>
            <p v-if="item.review_note" class="mt-1 line-clamp-2 break-words leading-5">{{ item.review_note }}</p>
            <p class="mt-1 text-[11px] font-semibold text-emerald-700/80">{{ reviewMetaText(item) }}</p>
          </div>
        </button>
      </div>
    </BaseCard>

    <div v-if="selectedDetail" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
      <div class="flex max-h-[90vh] w-full max-w-3xl min-h-0 flex-col overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-100 bg-white p-6">
          <div>
            <p class="section-kicker">Report Detail</p>
            <h2 class="mt-1 break-all text-2xl font-black text-slate-950">{{ selectedDetail.report_id }}</h2>
            <p class="mt-1 text-sm font-semibold text-slate-400">{{ selectedDetail.created_at }} / {{ selectedDetail.updated_at }}</p>
          </div>
          <BaseButton variant="secondary" @click="selectedDetail = null">关闭</BaseButton>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-6">
        <div class="grid gap-3 md:grid-cols-4">
          <div class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">等级</p>
            <p class="mt-1 text-lg font-black text-slate-900">{{ selectedDetail.risk_level }}</p>
          </div>
          <div class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">判定</p>
            <p class="mt-1 text-lg font-black text-slate-900">{{ selectedDetail.verdict }}</p>
          </div>
          <div class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">分数</p>
            <p class="mt-1 text-lg font-black text-slate-900">{{ selectedDetail.score }}</p>
          </div>
          <div class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">渠道</p>
            <p class="mt-1 text-lg font-black text-slate-900">{{ selectedDetail.channel }}</p>
          </div>
        </div>

        <div class="mt-5 space-y-4">
          <section v-if="selectedDetail.url" class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">URL</p>
            <p class="mt-2 break-all text-sm font-semibold text-slate-700">{{ selectedDetail.url }}</p>
          </section>
          <section v-if="selectedDetail.content" class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">内容</p>
            <p class="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-sm font-semibold leading-6 text-slate-700">{{ selectedDetail.content }}</p>
          </section>
          <section v-if="selectedDetail.review_note || selectedDetail.reviewed_at" class="rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-100">
            <p class="text-xs font-black uppercase tracking-widest text-emerald-700">{{ reviewFeedbackTitle }}</p>
            <p v-if="selectedDetail.review_note" class="mt-2 whitespace-pre-wrap break-words text-sm font-semibold leading-6 text-emerald-950">{{ selectedDetail.review_note }}</p>
            <p class="mt-2 text-xs font-bold text-emerald-700/80">{{ reviewMetaText(selectedDetail) }}</p>
          </section>
          <section class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">分数拆解</p>
            <pre class="mt-2 max-h-64 overflow-auto text-xs font-semibold text-slate-600">{{ JSON.stringify(selectedDetail.score_breakdown || {}, null, 2) }}</pre>
          </section>
          <section class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">命中规则</p>
            <div class="mt-2 max-h-56 overflow-y-auto pr-1">
              <div class="flex flex-wrap gap-2">
              <StatusBadge v-for="rule in list(selectedDetail.matched_rules)" :key="`${rule.rule}-${rule.weight}`" tone="warning">{{ rule.rule }}</StatusBadge>
              </div>
            </div>
          </section>
          <section class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">原因</p>
            <ul class="mt-2 max-h-56 space-y-1 overflow-y-auto pr-1 text-sm font-semibold text-slate-600">
              <li v-for="(reason, index) in list(selectedDetail.reasons)" :key="index" class="break-words">{{ reason }}</li>
            </ul>
          </section>
        </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { getReportDetail, getUserReports, submitReport } from '../api/report.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import ReportForm from '../components/report/ReportForm.vue'
import ReportResult from '../components/report/ReportResult.vue'
import { useAuth } from '../composables/useAuth.js'

const { currentUser } = useAuth()
const route = useRoute()
const loading = ref(false)
const error = ref('')
const result = ref(null)
const history = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const selectedDetail = ref(null)
const reviewFeedbackTitle = '\u590d\u6838\u53cd\u9988'

const prefillValues = computed(() => ({
  url: typeof route.query.url === 'string' ? route.query.url : '',
  content: typeof route.query.content === 'string' ? route.query.content : '',
}))

function list(value) {
  return Array.isArray(value) ? value : []
}

function statusLabel(status) {
  return {
    pending: '待复核',
    reviewed: '已复核',
    closed: '已关闭',
  }[status] || '待复核'
}

function reviewMetaText(item) {
  return [item.reviewer || 'admin', item.reviewed_at || item.updated_at || item.created_at].filter(Boolean).join(' · ')
}

async function handleSubmit(payload) {
  if (!currentUser.value?.user_id) {
    error.value = '请先登录后再提交举报'
    return
  }

  loading.value = true
  error.value = ''

  try {
    result.value = await submitReport({
      user_id: Number(currentUser.value.user_id),
      url: payload.url,
      content: payload.content,
      channel: 'web',
    })
    await loadHistory()
  } catch (err) {
    error.value = err.message || '举报分析失败'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  if (!currentUser.value?.user_id) {
    return
  }

  historyLoading.value = true
  historyError.value = ''

  try {
    const data = await getUserReports(currentUser.value.user_id, { limit: 12 })
    history.value = Array.isArray(data?.items) ? data.items : []
  } catch (err) {
    historyError.value = err.message || '举报记录加载失败'
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

async function openDetail(reportId) {
  historyError.value = ''
  try {
    selectedDetail.value = await getReportDetail(reportId)
  } catch (err) {
    historyError.value = err.message || '举报详情加载失败'
  }
}

onMounted(loadHistory)
</script>
