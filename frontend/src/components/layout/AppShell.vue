<template>
  <div class="min-h-screen overflow-x-hidden text-slate-900">
    <Sidebar />
    <main class="min-h-screen min-w-0 overflow-x-hidden md:pl-20 lg:pl-56">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import Sidebar from './Sidebar.vue'
</script>
