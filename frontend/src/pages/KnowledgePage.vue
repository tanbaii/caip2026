<template>
  <div class="page-shell space-y-6">
    <BaseCard padding-class="p-6 md:p-8" class="space-y-6">
      <div class="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="section-kicker">Knowledge Base</p>
          <h1 class="mt-2 text-4xl font-black tracking-tight text-slate-950">反诈知识库</h1>
          <p class="mt-2 max-w-2xl text-sm font-medium leading-6 text-slate-500">骗局特征、法律依据和防护建议均来自真实后端知识库接口。</p>
        </div>
        <div class="w-full xl:w-96">
          <div class="rounded-3xl border border-slate-200 bg-white p-2 shadow-sm shadow-slate-200/70 focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-100">
            <input v-model.trim="keyword" class="w-full rounded-2xl border-0 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700 placeholder:text-slate-400" placeholder="搜索骗局名称、关键词、案例..." />
          </div>
          <p class="mt-2 text-xs font-semibold text-slate-400">当前匹配 {{ filteredScams.length }} 个骗局、{{ filteredLaws.length }} 条法律知识</p>
        </div>
      </div>

      <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
    </BaseCard>

    <section class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-black text-slate-950">骗局知识</h2>
        <StatusBadge tone="info">{{ filteredScams.length }} 条</StatusBadge>
      </div>
      <div v-if="loading" class="soft-card p-8 text-center text-sm font-bold text-slate-500">正在加载知识库...</div>
      <div v-else-if="!filteredScams.length" class="soft-card p-8 text-center text-sm font-bold text-slate-400">暂无匹配的骗局知识。</div>
      <div v-else class="grid gap-5 xl:grid-cols-2">
        <BaseCard v-for="item in filteredScams" :key="item.id || item.name" padding-class="p-6" class="interactive-card space-y-5">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-xs font-black uppercase tracking-widest text-blue-600">{{ item.type || item.id || 'SCAM' }}</p>
              <h3 class="mt-2 text-2xl font-black text-slate-900">{{ item.name || '未命名骗局' }}</h3>
            </div>
            <StatusBadge tone="danger">风险类型</StatusBadge>
          </div>

          <TagList title="关键词" :items="list(item.keywords)" tone="danger" />
          <InfoList title="常见手法" :items="list(item.tactics)" />
          <InfoList title="风险信号" :items="list(item.red_flags)" />
          <div class="rounded-2xl bg-slate-50 p-4">
            <p class="text-xs font-black uppercase tracking-widest text-slate-400">典型案例</p>
            <p class="mt-2 break-words text-sm font-semibold leading-7 text-slate-600">{{ item.typical_case || '暂无案例。' }}</p>
          </div>
          <InfoList title="防护建议" :items="list(item.prevention)" />
          <TagList title="法律依据" :items="list(item.legal_refs)" tone="info" />
        </BaseCard>
      </div>
    </section>

    <section class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-black text-slate-950">法律知识</h2>
        <StatusBadge tone="muted">{{ filteredLaws.length }} 条</StatusBadge>
      </div>
      <div v-if="!filteredLaws.length" class="soft-card p-8 text-center text-sm font-bold text-slate-400">暂无匹配的法律知识。</div>
      <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <BaseCard v-for="law in filteredLaws" :key="law.id || law.title || law.name" padding-class="p-5" class="space-y-3">
          <h3 class="text-lg font-black text-slate-900">{{ law.title || law.name || law.id || '法律条目' }}</h3>
          <p class="text-sm font-semibold leading-7 text-slate-600">{{ law.content || law.summary || law.description || law.text || '暂无说明。' }}</p>
        </BaseCard>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getLaws, getScams } from '../api/knowledge.js'
import BaseCard from '../components/common/BaseCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const loading = ref(false)
const error = ref('')
const scams = ref([])
const laws = ref([])
const keyword = ref('')

const InfoList = {
  props: { title: String, items: { type: Array, default: () => [] } },
  template: `
    <section class="space-y-2">
      <h4 class="text-sm font-black text-slate-900">{{ title }}</h4>
      <ul v-if="items.length" class="space-y-2">
        <li v-for="(item,index) in items" :key="index" class="break-words rounded-2xl border border-slate-100 bg-slate-50 p-3 text-sm font-semibold leading-6 text-slate-600">{{ item }}</li>
      </ul>
      <p v-else class="rounded-2xl bg-slate-50 p-3 text-sm font-semibold text-slate-400">暂无内容。</p>
    </section>
  `,
}

const TagList = {
  props: { title: String, items: { type: Array, default: () => [] }, tone: { type: String, default: 'info' } },
  template: `
    <section class="space-y-2">
      <h4 class="text-sm font-black text-slate-900">{{ title }}</h4>
      <div v-if="items.length" class="flex flex-wrap gap-2">
        <span v-for="item in items" :key="item" class="max-w-full break-words rounded-full px-3 py-1.5 text-xs font-black shadow-sm ring-1" :class="tone === 'danger' ? 'bg-red-50 text-red-700 shadow-red-100 ring-red-100' : 'bg-blue-50 text-blue-700 shadow-blue-100 ring-blue-100'">{{ item }}</span>
      </div>
      <p v-else class="rounded-2xl bg-slate-50 p-3 text-sm font-semibold text-slate-400">暂无内容。</p>
    </section>
  `,
}

function list(value) {
  return Array.isArray(value) ? value : []
}

function matches(item) {
  const term = keyword.value.toLowerCase()
  if (!term) return true
  return JSON.stringify(item || {}).toLowerCase().includes(term)
}

const filteredScams = computed(() => scams.value.filter(matches))
const filteredLaws = computed(() => laws.value.filter(matches))

async function loadKnowledge() {
  loading.value = true
  error.value = ''

  try {
    const [scamData, lawData] = await Promise.all([getScams(), getLaws()])
    scams.value = Array.isArray(scamData) ? scamData : []
    laws.value = Array.isArray(lawData) ? lawData : []
  } catch (err) {
    error.value = err.message || '知识库加载失败'
    scams.value = []
    laws.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadKnowledge)
</script>
