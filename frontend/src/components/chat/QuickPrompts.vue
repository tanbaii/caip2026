<template>
  <div class="flex flex-wrap gap-2">
    <button
      v-for="prompt in prompts"
      :key="prompt"
      type="button"
      class="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-black text-slate-500 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
      @click="$emit('select', prompt)"
    >
      {{ prompt }}
    </button>
  </div>
</template>

<script setup>
defineEmits(['select'])

const prompts = [
  '有人让我先垫付刷单，说完成后返利',
  '陌生客服说我的快递丢了要理赔',
  '对方让我下载会议软件并开启屏幕共享',
  '投资群老师保证高收益低风险',
]
</script>
