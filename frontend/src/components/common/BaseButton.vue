<template>
  <button
    :type="type"
    :disabled="disabled"
    class="inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-black transition-all duration-200 focus-visible:ring-4 focus-visible:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
    :class="variantClass"
  >
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: {
    type: String,
    default: 'button',
  },
  variant: {
    type: String,
    default: 'primary',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const variantClass = computed(() => {
  const variants = {
    primary: 'bg-blue-600 text-white shadow-lg shadow-blue-200/80 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-blue-300/80',
    secondary: 'border border-slate-200 bg-white text-slate-700 shadow-sm shadow-slate-200/70 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700',
    ghost: 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900',
    danger: 'border border-red-100 bg-red-50 text-red-700 hover:-translate-y-0.5 hover:bg-red-100',
  }
  return variants[props.variant] || variants.primary
})
</script>
