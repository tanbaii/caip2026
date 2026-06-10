<template>
  <aside class="fixed inset-x-3 bottom-3 top-auto z-50 flex h-16 items-center justify-between rounded-3xl border border-white/80 bg-white/95 px-3 shadow-2xl shadow-blue-950/10 backdrop-blur md:left-0 md:right-auto md:top-0 md:h-screen md:w-20 md:flex-col md:items-stretch md:rounded-none md:border-r md:border-slate-200 md:px-3 md:py-5 lg:w-56">
    <RouterLink to="/chat" class="hidden items-center gap-3 rounded-2xl px-3 py-2 hover:bg-slate-50 md:mb-10 md:flex">
      <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-200">
        <Shield class="h-6 w-6" />
      </div>
      <div class="hidden lg:block">
        <h1 class="text-xl font-black leading-none text-slate-900">护盾实验室</h1>
        <p class="mt-1 text-xs font-black uppercase tracking-[0.22em] text-slate-400">Shield Lab</p>
      </div>
    </RouterLink>

    <nav class="flex min-w-0 flex-1 items-center justify-around gap-1 md:flex-col md:items-stretch md:justify-start md:gap-2">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="group flex h-11 w-11 items-center justify-center rounded-2xl transition-all md:h-auto md:w-auto md:justify-start md:gap-4 md:px-4 md:py-3"
        :class="isActive(item.path) ? 'bg-blue-600 text-white shadow-lg shadow-blue-100' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
      >
        <component :is="item.icon" class="h-6 w-6 shrink-0 transition-transform group-hover:scale-110" />
        <span class="hidden text-sm font-black lg:block">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="hidden border-t border-slate-100 pt-5 md:block">
      <RouterLink to="/profile" class="mb-3 flex items-center gap-3 rounded-2xl bg-slate-50 px-3 py-3 text-slate-600 hover:bg-slate-100">
        <User class="h-6 w-6 shrink-0" />
        <div class="hidden min-w-0 lg:block">
          <p class="truncate text-sm font-black text-slate-900">{{ displayName }}</p>
          <p class="text-xs font-semibold text-slate-400">{{ currentUser?.role || 'general' }}</p>
        </div>
      </RouterLink>
      <button class="flex w-full items-center gap-4 rounded-2xl px-4 py-3 text-slate-500 hover:bg-red-50 hover:text-red-700" @click="handleLogout">
        <LogOut class="h-6 w-6 shrink-0" />
        <span class="hidden text-sm font-black lg:block">退出登录</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { BookOpen, Flag, Gamepad2, LogOut, Medal, MessageCircle, Shield, User } from 'lucide-vue-next'
import { useAuth } from '../../composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const { currentUser, logout } = useAuth()

const navItems = [
  { icon: MessageCircle, label: 'AI 对话', path: '/chat' },
  { icon: Flag, label: '举报中心', path: '/report' },
  { icon: Gamepad2, label: '反诈闯关', path: '/game' },
  { icon: BookOpen, label: '知识库', path: '/knowledge' },
  { icon: Medal, label: '排行榜 / 等级', path: '/leaderboard' },
]

const displayName = computed(() => currentUser.value?.nickname || currentUser.value?.username || '未登录用户')

function isActive(path) {
  return route.path === path
}

function handleLogout() {
  logout()
  router.push('/login')
}
</script>
