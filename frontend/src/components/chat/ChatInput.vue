<template>
  <form class="space-y-4" @submit.prevent="submit">
    <div class="rounded-3xl border border-slate-200 bg-white p-3 shadow-lg shadow-slate-200/70 focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-100">
      <textarea
        v-model="text"
        rows="3"
        :disabled="loading"
        class="block w-full resize-none rounded-2xl border-0 bg-transparent px-3 py-2 text-sm font-medium leading-7 text-slate-700 placeholder:text-slate-400 disabled:opacity-60"
        placeholder="输入可疑聊天、链接、转账要求或对方话术，AI 将进行风险研判..."
      />
      <div class="flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
        <p class="hidden text-xs font-semibold text-slate-400 md:block">不会上传 API Key，所有研判通过后端真实接口完成。</p>
        <BaseButton type="submit" :disabled="loading || !text.trim()">
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          <Send v-else class="h-4 w-4" />
          {{ loading ? '研判中' : '发送研判' }}
        </BaseButton>
      </div>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { Loader2, Send } from 'lucide-vue-next'
import BaseButton from '../common/BaseButton.vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['send'])
const text = ref('')

function submit() {
  const value = text.value.trim()
  if (!value || props.loading) {
    return
  }

  emit('send', value)
  text.value = ''
}

function setText(value) {
  text.value = value
}

defineExpose({ setText })
</script>
