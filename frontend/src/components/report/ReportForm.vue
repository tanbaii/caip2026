<template>
  <BaseCard padding-class="p-6 md:p-8" class="space-y-6">
    <div class="rounded-3xl bg-gradient-to-br from-blue-50 to-white p-5 ring-1 ring-blue-100/70">
      <p class="section-kicker">Report Center</p>
      <h2 class="mt-2 text-3xl font-black tracking-tight text-slate-950">举报中心</h2>
      <p class="mt-2 text-sm font-medium leading-6 text-slate-500">提交可疑链接或聊天内容，系统会调用真实接口完成风险初判并生成报告。</p>
    </div>

    <form class="space-y-5" @submit.prevent="submit">
      <label class="block space-y-2">
        <span class="text-xs font-black uppercase tracking-widest text-slate-400">可疑链接</span>
        <input v-model.trim="form.url" class="focus-ring w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 shadow-sm shadow-slate-200/60 placeholder:text-slate-400" placeholder="例如：http://example.top/login" />
      </label>

      <label class="block space-y-2">
        <span class="text-xs font-black uppercase tracking-widest text-slate-400">可疑内容</span>
        <textarea v-model.trim="form.content" rows="8" class="focus-ring w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold leading-7 text-slate-700 shadow-sm shadow-slate-200/60 placeholder:text-slate-400" placeholder="粘贴对方话术、短信、聊天记录或转账要求" />
      </label>

      <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>

      <div class="muted-panel p-4 text-xs font-semibold leading-6 text-slate-500">
        支持同时提交链接和文字内容；至少填写一项即可生成风险报告。
      </div>

      <BaseButton type="submit" :disabled="loading || !canSubmit" class="w-full md:w-auto">
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        <Flag v-else class="h-4 w-4" />
        {{ loading ? '分析中' : '提交举报并分析' }}
      </BaseButton>
    </form>
  </BaseCard>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { Flag, Loader2 } from 'lucide-vue-next'
import BaseButton from '../common/BaseButton.vue'
import BaseCard from '../common/BaseCard.vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['submit'])

const form = reactive({
  url: '',
  content: '',
})

const canSubmit = computed(() => Boolean(form.url || form.content))

function submit() {
  if (!canSubmit.value || props.loading) {
    return
  }
  emit('submit', {
    url: form.url || null,
    content: form.content || null,
  })
}
</script>
