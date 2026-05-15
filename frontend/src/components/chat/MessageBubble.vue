<template>
  <div class="flex gap-4" :class="message.role === 'user' ? 'flex-row-reverse' : ''">
    <div
      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl shadow-sm"
      :class="message.role === 'user' ? 'bg-slate-100 text-slate-500' : 'bg-blue-600 text-white shadow-blue-100'"
    >
      <User v-if="message.role === 'user'" class="h-5 w-5" />
      <Bot v-else class="h-5 w-5" />
    </div>
    <div class="max-w-[78%] space-y-2" :class="message.role === 'user' ? 'items-end text-right' : ''">
      <div
        class="rounded-3xl px-5 py-4 text-sm font-medium leading-7 shadow-sm"
        :class="bubbleClass"
      >
        {{ message.content }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bot, User } from 'lucide-vue-next'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const bubbleClass = computed(() => {
  if (props.message.role === 'user') {
    return 'bg-blue-600 text-white shadow-blue-100'
  }

  if (props.message.tone === 'error') {
    return 'border border-red-100 bg-red-50 text-red-700'
  }

  return 'border border-slate-200 bg-white text-slate-700'
})
</script>
