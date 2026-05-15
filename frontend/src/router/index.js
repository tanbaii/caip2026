import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import LoginPage from '../pages/LoginPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import { useAuth } from '../composables/useAuth.js'

const ComingSoon = {
  template: `
    <section class="flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
      <div class="soft-card max-w-xl p-10 text-center">
        <p class="text-xs font-black uppercase tracking-[0.25em] text-blue-600">Coming Soon</p>
        <h1 class="mt-4 text-3xl font-black text-slate-900">功能开发中</h1>
        <p class="mt-3 text-sm font-medium leading-6 text-slate-500">第一轮先完成 AI 对话和风险研判主链路，其他页面将在下一轮接入真实接口。</p>
      </div>
    </section>
  `,
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage },
    {
      path: '/',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/chat' },
        { path: 'chat', component: ChatPage },
        { path: 'detection', component: ComingSoon },
        { path: 'report', component: ComingSoon },
        { path: 'game', component: ComingSoon },
        { path: 'knowledge', component: ComingSoon },
        { path: 'leaderboard', component: ComingSoon },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.initialized.value) {
    await auth.initAuth()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return '/login'
  }

  if (to.path === '/login' && auth.isAuthenticated.value) {
    return '/chat'
  }

  return true
})

export default router
