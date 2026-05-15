<template>
  <button
    :type="type"
    :disabled="disabled"
    class="inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-black transition-all disabled:cursor-not-allowed disabled:opacity-60"
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
    primary: 'bg-blue-600 text-white shadow-lg shadow-blue-200 hover:bg-blue-700',
    secondary: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    ghost: 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900',
    danger: 'bg-red-50 text-red-700 hover:bg-red-100',
  }
  return variants[props.variant] || variants.primary
})
</script>
