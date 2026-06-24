import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import LoginPage from '../pages/LoginPage.vue'
import OverviewPage from '../pages/OverviewPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import GamePage from '../pages/GamePage.vue'
import KnowledgePage from '../pages/KnowledgePage.vue'
import LeaderboardPage from '../pages/LeaderboardPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import AdminAccessPage from '../pages/AdminAccessPage.vue'
import AdminDashboardPage from '../pages/AdminDashboardPage.vue'
import RuleAdminPage from '../pages/RuleAdminPage.vue'
import { useAuth } from '../composables/useAuth.js'
import { hasAdminAccess } from '../composables/useAdminAuth.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage },
    {
      path: '/',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/overview' },
        { path: 'overview', component: OverviewPage },
        { path: 'chat', component: ChatPage },
        { path: 'report', component: ReportPage },
        { path: 'game', component: GamePage },
        { path: 'knowledge', component: KnowledgePage },
        { path: 'leaderboard', component: LeaderboardPage },
        { path: 'profile', component: ProfilePage },
        { path: 'admin', component: AdminAccessPage },
        { path: 'admin/dashboard', component: AdminDashboardPage, meta: { requiresAdmin: true } },
        { path: 'admin/rules', component: RuleAdminPage, meta: { requiresAdmin: true } },
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

  if (to.meta.requiresAdmin && !hasAdminAccess()) {
    return { path: '/admin', query: { redirect: to.fullPath } }
  }

  if (to.path === '/login' && auth.isAuthenticated.value) {
    return '/overview'
  }

  return true
})

export default router
