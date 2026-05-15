<template>
  <div class="rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/70" :class="paddingClass">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  paddingClass: {
    type: String,
    default: 'p-6',
  },
})
</script>
