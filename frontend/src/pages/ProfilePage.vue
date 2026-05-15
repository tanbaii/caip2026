<template>
  <div class="min-h-screen space-y-6 p-6">
    <BaseCard padding-class="p-6 md:p-8" class="space-y-6">
      <div class="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs font-black uppercase tracking-[0.24em] text-blue-600">Profile</p>
          <h1 class="mt-2 text-4xl font-black text-slate-900">我的等级</h1>
          <p class="mt-2 text-sm font-medium text-slate-500">展示真实 `/users/{user_id}/progress` 返回的成长数据。</p>
        </div>
        <BaseButton variant="secondary" :disabled="loading || !currentUser?.user_id" @click="loadProgress">
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          刷新进度
        </BaseButton>
      </div>

      <p v-if="!currentUser?.user_id" class="rounded-2xl bg-orange-50 px-4 py-3 text-sm font-bold text-orange-700 ring-1 ring-orange-100">请先登录后查看个人等级。</p>
      <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
    </BaseCard>

    <div v-if="progress" class="grid gap-6 xl:grid-cols-[1fr_380px]">
      <BaseCard padding-class="p-8" class="space-y-8">
        <div class="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-3xl font-black text-slate-900">{{ currentUser?.nickname || currentUser?.username || `用户 ${progress.user_id}` }}</h2>
            <p class="mt-2 text-sm font-semibold text-slate-500">用户 ID：{{ progress.user_id }}</p>
          </div>
          <div class="text-left md:text-right">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">当前积分</p>
            <p class="mt-1 text-5xl font-black tracking-tighter text-blue-600">{{ progress.points ?? 0 }}</p>
          </div>
        </div>

        <div class="rounded-3xl bg-blue-50 p-6 ring-1 ring-blue-100">
          <div class="flex items-center justify-between text-sm font-black">
            <span class="text-blue-700">Lv.{{ progress.level ?? 1 }}</span>
            <span class="text-blue-500">成长进度</span>
          </div>
          <div class="mt-4 h-4 overflow-hidden rounded-full bg-white">
            <div class="h-full rounded-full bg-blue-600" :style="{ width: `${progressWidth}%` }" />
          </div>
        </div>

        <section class="space-y-3">
          <h3 class="text-lg font-black text-slate-900">徽章</h3>
          <div class="flex flex-wrap gap-2">
            <StatusBadge v-for="badge in list(progress.badges)" :key="badge" tone="info">{{ badge }}</StatusBadge>
            <StatusBadge v-if="!list(progress.badges).length" tone="muted">暂无徽章</StatusBadge>
          </div>
        </section>
      </BaseCard>

      <div class="grid gap-4">
        <BaseCard padding-class="p-6" class="bg-gradient-to-br from-blue-600 to-sky-500 text-white">
          <p class="text-xs font-black uppercase tracking-widest text-blue-100">举报次数</p>
          <p class="mt-3 text-5xl font-black">{{ progress.reports_submitted ?? 0 }}</p>
        </BaseCard>
        <BaseCard padding-class="p-6" class="bg-white">
          <p class="text-xs font-black uppercase tracking-widest text-slate-400">完成闯关</p>
          <p class="mt-3 text-5xl font-black text-slate-900">{{ progress.scenarios_completed ?? 0 }}</p>
        </BaseCard>
      </div>
    </div>

    <div v-else-if="!loading && currentUser?.user_id" class="soft-card p-8 text-center text-sm font-bold text-slate-400">暂无个人进度数据。</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { getUserProgress } from '../api/leaderboard.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import { useAuth } from '../composables/useAuth.js'

const { currentUser } = useAuth()
const progress = ref(null)
const loading = ref(false)
const error = ref('')

function list(value) {
  return Array.isArray(value) ? value : []
}

const progressWidth = computed(() => Math.min(100, Number(progress.value?.points || 0) % 100))

async function loadProgress() {
  if (!currentUser.value?.user_id) {
    return
  }

  loading.value = true
  error.value = ''

  try {
    progress.value = await getUserProgress(currentUser.value.user_id)
  } catch (err) {
    error.value = err.message || '个人进度加载失败'
    progress.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadProgress)
</script>
