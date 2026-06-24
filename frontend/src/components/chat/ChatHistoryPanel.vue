<template>
  <aside class="glass-card flex h-[min(34rem,calc(100vh-2rem))] min-h-0 flex-col overflow-hidden xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)]">
    <header class="shrink-0 border-b border-slate-200/80 bg-white/95 p-5 backdrop-blur">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="section-kicker">History</p>
          <h2 class="mt-2 text-xl font-black tracking-tight text-slate-950">历史对话</h2>
        </div>
        <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{{ total }}</span>
      </div>

      <button
        type="button"
        class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-3 text-sm font-black text-white shadow-lg shadow-blue-200/80 transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-blue-300/80 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="loading"
        @click="$emit('new-conversation')"
      >
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        <MessageSquarePlus v-else class="h-4 w-4" />
        新对话
      </button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto bg-slate-50/70 p-3">
      <div v-if="loading && !items.length" class="space-y-3">
        <div v-for="index in 4" :key="index" class="h-24 animate-pulse rounded-2xl bg-white shadow-sm shadow-slate-200/70" />
      </div>

      <div v-else-if="!items.length" class="rounded-2xl border border-dashed border-slate-200 bg-white p-4 text-sm font-bold leading-6 text-slate-400">
        暂无历史对话。
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="item in items"
          :key="item.conversation_id"
          class="group rounded-2xl border bg-white p-3 shadow-sm shadow-slate-200/60 transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-blue-950/5"
          :class="selectedId === item.conversation_id ? 'border-blue-300 ring-4 ring-blue-100' : 'border-slate-200'"
        >
          <div class="flex items-start gap-2">
            <button type="button" class="min-w-0 flex-1 text-left" @click="$emit('select', item)">
              <div class="flex items-start justify-between gap-3">
                <p class="line-clamp-2 min-w-0 text-sm font-black leading-5 text-slate-800">{{ item.title || item.preview || '未命名对话' }}</p>
                <span class="shrink-0 rounded-full px-2 py-1 text-[11px] font-black" :class="riskClass(item.risk_level)">
                  {{ riskLabel(item.risk_level) }}
                </span>
              </div>
              <p class="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">{{ item.preview || '暂无消息预览' }}</p>
            </button>
            <button
              type="button"
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-slate-300 transition hover:bg-red-50 hover:text-red-600"
              title="删除对话"
              aria-label="删除对话"
              @click.stop="$emit('delete', item)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
          <div class="mt-3 flex items-center justify-between gap-3 text-[11px] font-black text-slate-400">
            <span>{{ formatTime(item.updated_at) }}</span>
            <span>{{ item.message_count }} 轮 · {{ item.risk_score }} 分</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { Loader2, MessageSquarePlus, Trash2 } from 'lucide-vue-next'

defineProps({
  items: {
    type: Array,
    required: true,
  },
  total: {
    type: Number,
    default: 0,
  },
  selectedId: {
    type: Number,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['new-conversation', 'select', 'delete'])

const labels = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '紧急',
}

function riskLabel(level) {
  return labels[level] || '待研判'
}

function riskClass(level) {
  const classes = {
    low: 'bg-emerald-50 text-emerald-700',
    medium: 'bg-orange-50 text-orange-700',
    high: 'bg-red-50 text-red-700',
    critical: 'bg-rose-100 text-rose-700',
  }
  return classes[level] || 'bg-slate-100 text-slate-500'
}

function formatTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value || ''
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
</script>
