<template>
  <aside class="fixed left-0 top-0 z-50 flex h-screen w-20 flex-col border-r border-slate-200 bg-white px-3 py-6 lg:w-72">
    <RouterLink to="/chat" class="mb-10 flex items-center gap-3 rounded-2xl px-3 py-2 hover:bg-slate-50">
      <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-200">
        <Shield class="h-6 w-6" />
      </div>
      <div class="hidden lg:block">
        <h1 class="text-xl font-black leading-none text-slate-900">护盾实验室</h1>
        <p class="mt-1 text-xs font-black uppercase tracking-[0.22em] text-slate-400">Shield Lab</p>
      </div>
    </RouterLink>

    <nav class="flex flex-1 flex-col gap-2">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="group flex items-center gap-4 rounded-2xl px-4 py-3 transition-all"
        :class="isActive(item.path) ? 'bg-blue-600 text-white shadow-lg shadow-blue-100' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
      >
        <component :is="item.icon" class="h-6 w-6 shrink-0 transition-transform group-hover:scale-110" />
        <span class="hidden text-sm font-black lg:block">{{ item.label }}</span>
        <span v-if="item.disabled" class="ml-auto hidden rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-black text-slate-400 lg:block">开发中</span>
      </RouterLink>
    </nav>

    <div class="border-t border-slate-100 pt-5">
      <RouterLink to="/leaderboard" class="mb-3 flex items-center gap-3 rounded-2xl bg-slate-50 px-3 py-3 text-slate-600 hover:bg-slate-100">
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
import { BookOpen, Flag, Gamepad2, LogOut, Medal, MessageCircle, SearchCheck, Shield, ShieldAlert, User } from 'lucide-vue-next'
import { useAuth } from '../../composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const { currentUser, logout } = useAuth()

const navItems = [
  { icon: MessageCircle, label: 'AI 对话', path: '/chat' },
  { icon: ShieldAlert, label: '风险检测', path: '/detection', disabled: true },
  { icon: Flag, label: '举报中心', path: '/report', disabled: true },
  { icon: Gamepad2, label: '反诈闯关', path: '/game', disabled: true },
  { icon: BookOpen, label: '知识库', path: '/knowledge', disabled: true },
  { icon: Medal, label: '排行榜 / 等级', path: '/leaderboard', disabled: true },
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
