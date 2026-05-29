<template>
  <section class="glass-card flex min-h-[calc(100vh-7rem)] min-w-0 flex-1 flex-col overflow-hidden xl:min-h-[calc(100vh-4rem)]">
    <header class="flex flex-col gap-4 border-b border-slate-200/80 bg-white/95 px-5 py-5 backdrop-blur sm:flex-row sm:items-center sm:justify-between md:px-7">
      <div class="min-w-0">
        <p class="section-kicker">AI Shield Dialogue</p>
        <div class="mt-2 flex flex-wrap items-center gap-3">
          <h2 class="text-2xl font-black tracking-tight text-slate-950">AI 风险研判对话</h2>
          <StatusBadge tone="danger">实时监测</StatusBadge>
        </div>
        <p class="mt-2 max-w-2xl text-sm font-medium leading-6 text-slate-500">把可疑话术发来，系统会同步输出风险等级、命中骗局和劝阻建议。</p>
      </div>
      <button type="button" class="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-black text-slate-500 shadow-sm shadow-slate-200/70 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700" @click="$emit('reset')">
        <RotateCcw class="h-4 w-4" />
        <span class="hidden sm:inline">重置对话</span>
      </button>
    </header>

    <div class="min-h-0 flex-1 space-y-6 overflow-y-auto bg-slate-50/70 p-4 sm:p-6 md:p-7">
      <MessageBubble v-for="message in messages" :key="message.id" :message="message" />
      <div v-if="loading" class="flex gap-4">
        <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-200">
          <Bot class="h-5 w-5" />
        </div>
        <div class="rounded-3xl border border-blue-100 bg-white px-5 py-4 text-sm font-black text-blue-700 shadow-sm shadow-blue-100/70">
          <div class="flex items-center gap-3">
            <span>正在识别风险信号</span>
            <span class="flex gap-1">
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-500" />
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-500 [animation-delay:120ms]" />
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-500 [animation-delay:240ms]" />
            </span>
          </div>
        </div>
      </div>
    </div>

    <footer class="space-y-4 border-t border-slate-200/80 bg-white/95 p-4 backdrop-blur sm:p-5 md:p-6">
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
