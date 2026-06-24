<template>
  <div class="page-shell">
    <div class="mx-auto grid max-w-[1680px] gap-5 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
      <section class="space-y-4">
        <BaseCard padding-class="p-5" class="border-emerald-100 bg-white/95">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="section-kicker text-emerald-600">Overview</p>
              <h1 class="mt-2 text-3xl font-black tracking-tight text-slate-950">概览</h1>
              <p class="mt-2 text-sm font-semibold text-slate-500">{{ displayName }}，今天也保持警觉。</p>
            </div>
            <button
              type="button"
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-slate-500 transition hover:bg-emerald-50 hover:text-emerald-700"
              title="刷新"
              :disabled="loading"
              @click="loadOverview"
            >
              <RefreshCw class="h-5 w-5" :class="{ 'animate-spin': loading }" />
            </button>
          </div>
        </BaseCard>

        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <BaseCard
            v-for="metric in leftMetrics"
            :key="metric.label"
            padding-class="p-5"
            class="min-h-32 bg-white/95"
          >
            <div class="flex items-center justify-between gap-3">
              <p class="text-sm font-black text-slate-500">{{ metric.label }}</p>
              <component :is="metric.icon" class="h-5 w-5" :class="metric.iconClass" />
            </div>
            <p class="mt-4 text-5xl font-black tracking-tight" :class="metric.valueClass">{{ metric.value }}</p>
            <p class="mt-2 text-xs font-bold text-slate-400">{{ metric.caption }}</p>
          </BaseCard>
        </div>

        <BaseCard padding-class="p-5" class="overflow-hidden bg-gradient-to-br from-rose-50 to-white">
          <p class="text-xs font-black uppercase tracking-[0.2em] text-rose-500">96110</p>
          <div class="mt-3 rounded-2xl bg-rose-600 px-5 py-4 text-center text-3xl font-black text-white shadow-lg shadow-rose-200">
            96110
          </div>
          <p class="mt-3 text-sm font-bold leading-6 text-rose-900">反诈预警劝阻专线来电，请及时接听并核实。</p>
        </BaseCard>
      </section>

      <main class="min-w-0 space-y-5">
        <BaseCard padding-class="p-5 md:p-7" class="relative min-h-[30rem] overflow-hidden bg-[#edf4f8]">
          <div class="absolute left-8 top-8 h-28 w-28 rounded-full border border-emerald-200/70" />
          <div class="absolute right-10 top-12 h-16 w-16 rounded-full border border-blue-200/80" />
          <div class="absolute bottom-8 left-16 h-12 w-12 rounded-full border border-amber-200/80" />

          <div class="relative flex items-start justify-between gap-4">
            <div>
              <p class="section-kicker">Safety Radar</p>
              <h2 class="mt-2 text-2xl font-black text-slate-950">个人防骗雷达</h2>
            </div>
            <StatusBadge :tone="safetyScore >= 80 ? 'success' : safetyScore >= 55 ? 'warning' : 'danger'">
              {{ safetyStatus }}
            </StatusBadge>
          </div>

          <div class="relative mx-auto mt-8 flex min-h-[22rem] max-w-2xl items-center justify-center">
            <div class="absolute h-80 w-80 rounded-full border border-slate-300/60" />
            <div class="absolute h-56 w-56 rounded-full border border-slate-300/70" />
            <div class="absolute h-32 w-32 rounded-full border border-slate-300/80" />
            <div class="absolute h-px w-80 bg-slate-300/70" />
            <div class="absolute h-80 w-px bg-slate-300/70" />
            <div class="absolute h-80 w-px rotate-45 bg-slate-300/60" />
            <div class="absolute h-80 w-px -rotate-45 bg-slate-300/60" />

            <div
              v-for="point in radarPoints"
              :key="point.label"
              class="absolute flex h-3 w-3 items-center justify-center rounded-full shadow"
              :class="point.class"
              :style="{ transform: `translate(${point.x}px, ${point.y}px)` }"
              :title="point.label"
            />

            <div class="relative z-10 flex h-24 w-24 items-center justify-center rounded-full border border-white bg-white/80 shadow-xl shadow-slate-300/60 backdrop-blur">
              <div class="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500 text-white shadow-lg shadow-emerald-200">
                <ShieldCheck class="h-6 w-6" />
              </div>
            </div>
          </div>

          <div class="relative z-10 -mt-8 text-center">
            <p class="text-6xl font-black tracking-tight text-emerald-600">{{ displayScore }}</p>
            <p class="mt-2 text-sm font-black text-slate-600">安全感知指数</p>
            <p class="mx-auto mt-3 max-w-xl text-sm font-semibold leading-6 text-slate-500">{{ scoreHint }}</p>
          </div>
        </BaseCard>

        <BaseCard padding-class="p-5 md:p-6" class="bg-white/95">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p class="section-kicker">Checklist</p>
              <h2 class="mt-1 text-2xl font-black text-slate-950">防骗自查清单</h2>
            </div>
            <p class="text-sm font-black text-emerald-700">{{ checkedCount }}/{{ checklist.length }} 已完成</p>
          </div>

          <div class="mt-5 max-h-80 overflow-y-auto pr-1">
            <label
              v-for="item in checklist"
              :key="item.id"
              class="flex cursor-pointer items-start gap-4 border-b border-slate-100 py-4 last:border-b-0"
            >
              <input
                v-model="checkedMap[item.id]"
                type="checkbox"
                class="mt-1 h-6 w-6 rounded-md border-slate-300 text-emerald-600 focus:ring-emerald-100"
              >
              <span class="text-lg font-bold leading-8 text-slate-700" :class="{ 'text-slate-400 line-through': checkedMap[item.id] }">
                {{ item.text }}
              </span>
            </label>
          </div>
        </BaseCard>
      </main>

      <aside class="space-y-4">
        <BaseCard padding-class="p-5" class="bg-white/95">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="section-kicker text-rose-500">Risk Monitor</p>
              <h2 class="mt-1 text-xl font-black text-slate-950">风险提醒</h2>
            </div>
            <AlertTriangle class="h-5 w-5 text-rose-500" />
          </div>

          <div class="mt-5 space-y-4">
            <div v-for="item in riskAlerts" :key="item.label">
              <div class="mb-2 flex items-center justify-between gap-3 text-sm font-black">
                <span class="truncate text-rose-700">{{ item.label }}</span>
                <span class="text-rose-500">{{ item.value }}</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-rose-100">
                <div class="h-full rounded-full bg-rose-500" :style="{ width: `${item.width}%` }" />
              </div>
            </div>
          </div>
        </BaseCard>

        <BaseCard padding-class="p-5" class="bg-white/95">
          <p class="section-kicker">Quick Access</p>
          <h2 class="mt-1 text-xl font-black text-slate-950">快捷入口</h2>
          <div class="mt-5 grid grid-cols-2 gap-3">
            <RouterLink
              v-for="action in quickActions"
              :key="action.path"
              :to="action.path"
              class="interactive-card rounded-2xl border border-slate-100 bg-slate-50 p-4 text-center"
            >
              <component :is="action.icon" class="mx-auto h-6 w-6" :class="action.iconClass" />
              <p class="mt-2 text-sm font-black text-slate-800">{{ action.label }}</p>
              <p class="mt-1 text-xs font-semibold text-slate-400">{{ action.caption }}</p>
            </RouterLink>
          </div>
        </BaseCard>

        <BaseCard padding-class="p-5" class="bg-white/95">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="section-kicker">Recent</p>
              <h2 class="mt-1 text-xl font-black text-slate-950">最近举报</h2>
            </div>
            <RouterLink to="/report" class="text-sm font-black text-blue-600 hover:text-blue-700">查看</RouterLink>
          </div>

          <div class="mt-4 space-y-3">
            <div
              v-for="report in recentReports"
              :key="report.report_id"
              class="rounded-2xl border border-slate-100 bg-slate-50 p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <p class="min-w-0 truncate text-sm font-black text-slate-900">{{ report.report_id }}</p>
                <StatusBadge :tone="report.verdict === 'high_risk' ? 'danger' : report.verdict === 'suspicious' ? 'warning' : 'success'">
                  {{ report.verdict || '-' }}
                </StatusBadge>
              </div>
              <p class="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">
                {{ report.content_summary || report.url_host || '暂无摘要' }}
              </p>
            </div>
            <p v-if="!recentReports.length" class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">暂无举报记录。</p>
          </div>
        </BaseCard>

        <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  AlertTriangle,
  BookOpen,
  ClipboardCheck,
  Flag,
  Gamepad2,
  Gauge,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Trophy,
  UserCheck,
} from 'lucide-vue-next'
import { getUserProgress } from '../api/leaderboard.js'
import { getUserReports } from '../api/report.js'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import { useAuth } from '../composables/useAuth.js'

const { currentUser } = useAuth()
const progress = ref(null)
const recentReports = ref([])
const loading = ref(false)
const error = ref('')

const checklist = [
  { id: 'unknown_code', text: '陌生来电索要验证码时，已挂断且未透露' },
  { id: 'police_claim', text: '遇「公检法办案」话术，已通过 110/96110 核实' },
  { id: 'investment', text: '网络好友提到投资/炒币，未转账、未跟投' },
  { id: 'refund', text: '看到刷单、垫付、解冻费等话术，已提交核验' },
  { id: 'link', text: '不点击陌生链接，不下载来历不明 App' },
]

const checkedMap = reactive(Object.fromEntries(checklist.map((item) => [item.id, false])))
const checklistStorageKey = computed(() => `anti-fraud-overview-checklist-${currentUser.value?.user_id || 'guest'}`)

const displayName = computed(() => currentUser.value?.nickname || currentUser.value?.username || '同学')
const checkedCount = computed(() => checklist.filter((item) => checkedMap[item.id]).length)
const reportsCount = computed(() => Number(progress.value?.reports_submitted || recentReports.value.length || 0))
const gameCount = computed(() => Number(progress.value?.scenarios_completed || 0))
const points = computed(() => Number(progress.value?.points || 0))
const highRiskBlocks = computed(() => Number(progress.value?.high_risk_blocks || 0))
const safetyScore = computed(() => {
  const checklistScore = (checkedCount.value / checklist.length) * 40
  const gameScore = Math.min(gameCount.value * 5, 25)
  const reportScore = Math.min(reportsCount.value * 4, 20)
  const pointsScore = Math.min(points.value / 20, 15)
  return Math.round(checklistScore + gameScore + reportScore + pointsScore)
})
const displayScore = computed(() => (safetyScore.value / 10).toFixed(1))
const safetyStatus = computed(() => {
  if (safetyScore.value >= 80) return '在线'
  if (safetyScore.value >= 55) return '关注'
  return '待提升'
})
const scoreHint = computed(() => {
  if (safetyScore.value >= 80) return '防骗习惯已经比较稳定，继续保持核验、举报和闯关训练。'
  if (safetyScore.value >= 55) return '基础动作已建立，建议补齐自查清单并完成更多高发骗局关卡。'
  return '建议先完成自查清单，再从 AI 对话和情景闯关开始建立识别习惯。'
})

const leftMetrics = computed(() => [
  {
    label: '防骗状态',
    value: safetyStatus.value,
    caption: '综合自查、举报、闯关和积分',
    icon: ShieldCheck,
    iconClass: 'text-emerald-600',
    valueClass: safetyScore.value >= 80 ? 'text-emerald-600 text-4xl' : safetyScore.value >= 55 ? 'text-amber-600 text-4xl' : 'text-rose-600 text-4xl',
  },
  {
    label: '今日自查',
    value: checkedCount.value,
    caption: `共 ${checklist.length} 项防骗动作`,
    icon: ClipboardCheck,
    iconClass: 'text-rose-500',
    valueClass: 'text-rose-600',
  },
  {
    label: '累计积分',
    value: points.value,
    caption: `Lv.${progress.value?.level || 1} 成长中`,
    icon: Trophy,
    iconClass: 'text-blue-500',
    valueClass: 'text-blue-600',
  },
  {
    label: '完成关卡',
    value: gameCount.value,
    caption: '高发场景训练记录',
    icon: Gamepad2,
    iconClass: 'text-amber-500',
    valueClass: 'text-emerald-600',
  },
])

const radarPoints = computed(() => [
  { label: '自查', x: -118, y: -88, class: checkedCount.value >= 3 ? 'bg-emerald-500' : 'bg-slate-400' },
  { label: '举报', x: 132, y: -74, class: reportsCount.value > 0 ? 'bg-rose-500' : 'bg-slate-400' },
  { label: '闯关', x: -148, y: 70, class: gameCount.value > 0 ? 'bg-amber-500' : 'bg-slate-400' },
  { label: '拦截', x: 108, y: 116, class: highRiskBlocks.value > 0 ? 'bg-blue-500' : 'bg-slate-400' },
])

const riskAlerts = computed(() => [
  { label: '刷单返利话术', value: highRiskBlocks.value ? '已拦截' : '关注', width: highRiskBlocks.value ? 86 : 62 },
  { label: '仿冒客服/退款链接', value: reportsCount.value ? '已核验' : '待核验', width: reportsCount.value ? 78 : 54 },
  { label: '投资理财诱导', value: checkedMap.investment ? '已自查' : '自查', width: checkedMap.investment ? 72 : 48 },
  { label: '验证码套取', value: checkedMap.unknown_code ? '已防护' : '提醒', width: checkedMap.unknown_code ? 88 : 58 },
])

const quickActions = [
  { label: 'AI 咨询', caption: '即时研判', path: '/chat', icon: MessageCircle, iconClass: 'text-blue-600' },
  { label: '举报核验', caption: 'URL/文本', path: '/report', icon: Flag, iconClass: 'text-rose-600' },
  { label: '防骗闯关', caption: '训练积分', path: '/game', icon: Gamepad2, iconClass: 'text-amber-600' },
  { label: '知识库', caption: '骗局资料', path: '/knowledge', icon: BookOpen, iconClass: 'text-emerald-600' },
  { label: '排行榜', caption: '学习排名', path: '/leaderboard', icon: Trophy, iconClass: 'text-purple-600' },
  { label: '我的等级', caption: '成长记录', path: '/profile', icon: UserCheck, iconClass: 'text-slate-700' },
]

function restoreChecklist() {
  try {
    const stored = JSON.parse(localStorage.getItem(checklistStorageKey.value) || '{}')
    checklist.forEach((item) => {
      checkedMap[item.id] = Boolean(stored[item.id])
    })
  } catch {
    checklist.forEach((item) => {
      checkedMap[item.id] = false
    })
  }
}

async function loadOverview() {
  if (!currentUser.value?.user_id) return

  loading.value = true
  error.value = ''

  try {
    const [progressData, reportsData] = await Promise.all([
      getUserProgress(currentUser.value.user_id),
      getUserReports(currentUser.value.user_id, { limit: 3 }),
    ])
    progress.value = progressData
    recentReports.value = Array.isArray(reportsData?.items) ? reportsData.items : []
  } catch (err) {
    error.value = err.message || '概览加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  checklistStorageKey,
  () => {
    restoreChecklist()
  },
  { immediate: true },
)

watch(
  checkedMap,
  () => {
    const value = Object.fromEntries(checklist.map((item) => [item.id, Boolean(checkedMap[item.id])]))
    localStorage.setItem(checklistStorageKey.value, JSON.stringify(value))
  },
  { deep: true },
)

onMounted(loadOverview)
</script>
