<template>
  <div class="soft-card" :class="paddingClass">
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
