<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <Sidebar />
    <main class="min-h-screen pl-20 lg:pl-72">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import Sidebar from './Sidebar.vue'
</script>
