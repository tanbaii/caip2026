<template>
  <section class="flex min-h-[calc(100vh-3rem)] flex-1 flex-col overflow-hidden rounded-[2rem] border border-slate-200 bg-slate-50 shadow-sm">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white/90 px-6 py-4 backdrop-blur">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-black text-slate-900">AI 风险研判对话</h2>
          <StatusBadge tone="danger">Active Monitoring</StatusBadge>
        </div>
        <p class="mt-1 text-sm font-medium text-slate-500">把可疑话术发来，系统会同步输出风险等级和劝阻建议。</p>
      </div>
      <button type="button" class="rounded-2xl bg-white p-3 text-slate-400 hover:bg-slate-100 hover:text-slate-700" @click="$emit('reset')">
        <RotateCcw class="h-5 w-5" />
      </button>
    </header>

    <div class="flex-1 space-y-7 overflow-y-auto p-6">
      <MessageBubble v-for="message in messages" :key="message.id" :message="message" />
      <div v-if="loading" class="flex gap-4">
        <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm shadow-blue-100">
          <Bot class="h-5 w-5" />
        </div>
        <div class="rounded-3xl border border-blue-100 bg-blue-50 px-5 py-4 text-sm font-black text-blue-700">
          正在研判风险...
        </div>
      </div>
    </div>

    <footer class="space-y-4 border-t border-slate-200 bg-white p-5">
      <QuickPrompts @select="handlePromptSelect" />
      <ChatInput ref="inputRef" :loading="loading" @send="$emit('send', $event)" />
    </footer>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Bot, RotateCcw } from 'lucide-vue-next'
import ChatInput from './ChatInput.vue'
import MessageBubble from './MessageBubble.vue'
import QuickPrompts from './QuickPrompts.vue'
import StatusBadge from '../common/StatusBadge.vue'

defineProps({
  messages: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['send', 'reset'])

const inputRef = ref(null)

function handlePromptSelect(prompt) {
  inputRef.value?.setText(prompt)
}
</script>
