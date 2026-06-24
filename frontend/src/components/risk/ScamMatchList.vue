<template>
  <div class="space-y-3">
    <h3 class="text-sm font-black text-slate-900">疑似骗局类型</h3>
    <div v-if="items.length" class="max-h-40 overflow-y-auto pr-1">
      <div class="flex flex-wrap gap-2">
      <span v-for="item in items" :key="item" class="max-w-full break-words rounded-full bg-red-50 px-3 py-1.5 text-xs font-black text-red-700 shadow-sm shadow-red-100 ring-1 ring-red-100">
        {{ item }}
      </span>
      </div>
    </div>
    <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂未命中明确骗局类型。</p>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>
