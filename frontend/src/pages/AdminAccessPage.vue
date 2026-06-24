<template>
  <div class="page-shell flex min-h-[calc(100vh-4rem)] items-center justify-center">
    <section class="relative w-full max-w-3xl overflow-hidden rounded-[2rem] bg-slate-950 p-6 text-white shadow-2xl shadow-slate-900/25 md:p-8">
      <div class="absolute -right-16 -top-20 h-72 w-72 rounded-full border border-emerald-300/20 bg-emerald-300/10 blur-2xl"></div>
      <div class="absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-blue-500/20 blur-3xl"></div>
      <div class="relative">
        <p class="text-xs font-black uppercase tracking-[0.28em] text-emerald-300">Admin Access</p>
        <h1 class="mt-3 text-4xl font-black tracking-tight md:text-5xl">管理端权限校验</h1>
        <p class="mt-3 max-w-2xl text-sm font-semibold leading-7 text-slate-300">后台看板和规则管理仅对持有管理员令牌的人员开放。令牌只保存在当前浏览器会话，刷新后仍有效，退出登录时不会写入业务数据库。</p>

        <form class="mt-8 rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur" @submit.prevent="handleVerify">
          <label class="text-xs font-black uppercase tracking-widest text-slate-400">X-Admin-Token</label>
          <div class="mt-2 flex flex-col gap-3 md:flex-row">
            <input v-model="token" type="password" class="min-w-0 flex-1 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm font-bold text-white placeholder:text-slate-600 focus:border-emerald-300" placeholder="输入管理员令牌" />
            <button class="rounded-2xl bg-emerald-300 px-6 py-3 text-sm font-black text-slate-950 transition hover:bg-emerald-200 disabled:opacity-50" :disabled="loading || !token">{{ loading ? '校验中' : '进入后台' }}</button>
          </div>
          <p v-if="errorMessage" class="mt-3 rounded-2xl bg-red-500/10 px-4 py-3 text-sm font-bold text-red-200 ring-1 ring-red-400/20">{{ errorMessage }}</p>
        </form>

        <div class="mt-6 grid gap-3 md:grid-cols-3">
          <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p class="text-sm font-black text-white">后台看板</p>
            <p class="mt-1 text-xs font-semibold leading-5 text-slate-400">运营指标、举报态势、知识来源覆盖。</p>
          </div>
          <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p class="text-sm font-black text-white">规则管理</p>
            <p class="mt-1 text-xs font-semibold leading-5 text-slate-400">在线启停、调权、热加载、回滚。</p>
          </div>
          <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p class="text-sm font-black text-white">最小暴露</p>
            <p class="mt-1 text-xs font-semibold leading-5 text-slate-400">未校验前普通侧栏不展示管理菜单。</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAdminAuth } from '../composables/useAdminAuth.js'

const route = useRoute()
const router = useRouter()
const admin = useAdminAuth()
const token = ref(admin.adminToken.value)
const errorMessage = ref('')
const loading = computed(() => admin.loading.value)

async function handleVerify() {
  errorMessage.value = ''
  try {
    await admin.verifyAdminToken(token.value)
    router.replace(String(route.query.redirect || '/admin/dashboard'))
  } catch (error) {
    errorMessage.value = error.message || '管理员令牌校验失败'
  }
}
</script>
