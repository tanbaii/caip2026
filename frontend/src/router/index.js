import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import LoginPage from '../pages/LoginPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import GamePage from '../pages/GamePage.vue'
import KnowledgePage from '../pages/KnowledgePage.vue'
import LeaderboardPage from '../pages/LeaderboardPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import RuleAdminPage from '../pages/RuleAdminPage.vue'
import { useAuth } from '../composables/useAuth.js'

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
        { path: 'report', component: ReportPage },
        { path: 'game', component: GamePage },
        { path: 'knowledge', component: KnowledgePage },
        { path: 'leaderboard', component: LeaderboardPage },
        { path: 'profile', component: ProfilePage },
        { path: 'admin/rules', component: RuleAdminPage },
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
