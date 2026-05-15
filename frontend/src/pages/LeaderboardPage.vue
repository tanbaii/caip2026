<template>
  <div class="min-h-screen space-y-6 p-6">
    <BaseCard padding-class="p-6 md:p-8" class="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.24em] text-blue-600">Leaderboard</p>
        <h1 class="mt-2 text-4xl font-black text-slate-900">排行榜 / 等级</h1>
        <p class="mt-2 text-sm font-medium text-slate-500">展示真实 `/leaderboard?top=20` 返回的积分排名。</p>
      </div>
      <BaseButton variant="secondary" :disabled="loading" @click="loadLeaderboard">
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        刷新排行
      </BaseButton>
    </BaseCard>

    <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
    <div v-if="!loading && !items.length" class="soft-card p-8 text-center text-sm font-bold text-slate-400">暂无排行榜数据。</div>

    <div class="grid gap-4">
      <BaseCard v-for="item in items" :key="`${item.rank}-${item.user_id}`" padding-class="p-5" class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="flex items-center gap-4">
          <div class="flex h-14 w-14 items-center justify-center rounded-3xl text-xl font-black" :class="rankClass(item.rank)">#{{ item.rank }}</div>
          <div>
            <h2 class="text-xl font-black text-slate-900">{{ item.nickname || item.username || `用户 ${item.user_id}` }}</h2>
            <p class="mt-1 text-sm font-semibold text-slate-500">{{ item.username || '-' }} · {{ item.role || 'general' }}</p>
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
import { onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { getLeaderboard } from '../api/leaderboard.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const items = ref([])
const loading = ref(false)
const error = ref('')

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
