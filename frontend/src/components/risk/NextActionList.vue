<template>
  <section v-if="items.length" class="space-y-3">
    <h3 class="text-sm font-black text-slate-900">建议处置动作</h3>
    <ol class="space-y-2">
      <li v-for="(item, index) in items" :key="index" class="flex gap-3 rounded-2xl border border-blue-100 bg-blue-50/60 p-3 text-sm font-semibold leading-6 text-slate-700">
        <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">{{ index + 1 }}</span>
        <span class="min-w-0 break-words">{{ item }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>
