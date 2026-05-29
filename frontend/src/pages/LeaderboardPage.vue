<template>
  <div class="page-shell space-y-6">
    <BaseCard padding-class="p-6 md:p-8" class="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="section-kicker">Leaderboard</p>
        <h1 class="mt-2 text-4xl font-black tracking-tight text-slate-950">排行榜 / 等级</h1>
        <p class="mt-2 text-sm font-medium text-slate-500">展示真实 `/leaderboard?top=20` 返回的积分排名。</p>
      </div>
      <BaseButton variant="secondary" :disabled="loading" @click="loadLeaderboard">
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        刷新排行
      </BaseButton>
    </BaseCard>

    <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
    <div v-if="!loading && !items.length" class="soft-card p-8 text-center text-sm font-bold text-slate-400">暂无排行榜数据。</div>

    <div v-if="topThree.length" class="grid gap-4 lg:grid-cols-3">
      <BaseCard v-for="item in topThree" :key="`top-${item.rank}-${item.user_id}`" padding-class="p-6" class="interactive-card relative overflow-hidden">
        <div class="absolute right-5 top-5 text-5xl font-black opacity-10">#{{ item.rank }}</div>
        <div class="flex h-16 w-16 items-center justify-center rounded-[1.5rem] text-2xl font-black" :class="rankClass(item.rank)">#{{ item.rank }}</div>
        <h2 class="mt-5 truncate text-2xl font-black text-slate-950">{{ item.nickname || item.username || `用户 ${item.user_id}` }}</h2>
        <p class="mt-1 truncate text-sm font-semibold text-slate-500">{{ item.username || '-' }} · {{ item.role || 'general' }}</p>
        <div class="mt-5 flex flex-wrap gap-2">
          <StatusBadge tone="info">Lv.{{ item.level ?? 1 }}</StatusBadge>
          <StatusBadge tone="success">{{ item.points ?? 0 }} 分</StatusBadge>
        </div>
      </BaseCard>
    </div>

    <div class="grid gap-4">
      <BaseCard v-for="item in remainingItems" :key="`${item.rank}-${item.user_id}`" padding-class="p-5" class="interactive-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="flex min-w-0 items-center gap-4">
          <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-3xl text-xl font-black" :class="rankClass(item.rank)">#{{ item.rank }}</div>
          <div class="min-w-0">
            <h2 class="truncate text-xl font-black text-slate-900">{{ item.nickname || item.username || `用户 ${item.user_id}` }}</h2>
            <p class="mt-1 truncate text-sm font-semibold text-slate-500">{{ item.username || '-' }} · {{ item.role || 'general' }}</p>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <StatusBadge tone="info">Lv.{{ item.level ?? 1 }}</StatusBadge>
          <StatusBadge tone="success">{{ item.points ?? 0 }} 分</StatusBadge>
          <StatusBadge v-for="badge in list(item.badges)" :key="badge" tone="muted">{{ badge }}</StatusBadge>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { getLeaderboard } from '../api/leaderboard.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const items = ref([])
const loading = ref(false)
const error = ref('')
const topThree = computed(() => items.value.slice(0, 3))
const remainingItems = computed(() => items.value.slice(3))

function list(value) {
  return Array.isArray(value) ? value : []
}

function rankClass(rank) {
  if (rank === 1) return 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-100'
  if (rank === 2) return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
  if (rank === 3) return 'bg-orange-50 text-orange-700 ring-1 ring-orange-100'
  return 'bg-blue-50 text-blue-700 ring-1 ring-blue-100'
}

async function loadLeaderboard() {
  loading.value = true
  error.value = ''

  try {
    const data = await getLeaderboard(20)
    items.value = Array.isArray(data?.items) ? data.items : []
  } catch (err) {
    error.value = err.message || '排行榜加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadLeaderboard)
</script>
