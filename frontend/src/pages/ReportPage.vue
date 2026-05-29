<template>
  <div class="page-shell space-y-6">
    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
      <ReportForm :loading="loading" :error="error" @submit="handleSubmit" />
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
      <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="item in history" :key="item.report_id" class="interactive-card rounded-3xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/70">
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
        </div>
      </div>
    </BaseCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { getUserReports, submitReport } from '../api/report.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import ReportForm from '../components/report/ReportForm.vue'
import ReportResult from '../components/report/ReportResult.vue'
import { useAuth } from '../composables/useAuth.js'

const { currentUser } = useAuth()
const loading = ref(false)
const error = ref('')
const result = ref(null)
const history = ref([])
const historyLoading = ref(false)
const historyError = ref('')

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

onMounted(loadHistory)
</script>
