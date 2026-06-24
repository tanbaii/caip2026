<template>
  <div class="space-y-3">
    <h3 class="text-sm font-black text-slate-900">{{ title }}</h3>
    <ol v-if="items.length" class="max-h-56 space-y-2 overflow-y-auto pr-1">
      <li v-for="(item, index) in items" :key="`${index}-${item}`" class="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 p-3 text-sm font-semibold leading-6 text-slate-600">
        <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">{{ index + 1 }}</span>
        <span class="min-w-0 break-words">{{ item }}</span>
      </li>
    </ol>
    <p v-else class="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-400">暂无内容。</p>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    default: () => [],
  },
})
</script>
