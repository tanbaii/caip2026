<template>
  <main class="flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 p-6">
    <div class="absolute inset-0 -z-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.16),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.14),transparent_32%)]" />

    <section class="relative z-10 grid w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
      <div class="hidden flex-col justify-between rounded-[2rem] bg-blue-600 p-10 text-white shadow-2xl shadow-blue-200 lg:flex">
        <div>
          <div class="flex h-14 w-14 items-center justify-center rounded-3xl bg-white/15 ring-1 ring-white/20">
            <Shield class="h-8 w-8" />
          </div>
          <p class="mt-10 text-sm font-black uppercase tracking-[0.3em] text-blue-100">Shield Lab</p>
          <h1 class="mt-4 text-5xl font-black leading-tight">反诈智能对话系统</h1>
          <p class="mt-5 max-w-xl text-lg font-medium leading-8 text-blue-50">通过真实后端接口进行风险研判、劝阻建议生成与积分成长记录，帮助用户识别刷单、冒充客服、投资诱导等常见骗局。</p>
        </div>
        <div class="grid grid-cols-3 gap-3 text-sm font-black">
          <div class="rounded-2xl bg-white/10 p-4 ring-1 ring-white/15">实时研判</div>
          <div class="rounded-2xl bg-white/10 p-4 ring-1 ring-white/15">风险分级</div>
          <div class="rounded-2xl bg-white/10 p-4 ring-1 ring-white/15">劝阻建议</div>
        </div>
      </div>

      <BaseCard padding-class="p-8 md:p-10" class="relative z-10">
        <div class="mb-8 text-center">
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-600 text-white shadow-lg shadow-blue-200 lg:hidden">
            <Shield class="h-8 w-8" />
          </div>
          <p class="mt-4 text-xs font-black uppercase tracking-[0.25em] text-blue-600">Anti-Fraud Lab</p>
          <h2 class="mt-2 text-3xl font-black text-slate-900">{{ mode === 'login' ? '欢迎回来' : '创建护盾账号' }}</h2>
          <p class="mt-2 text-sm font-medium text-slate-500">{{ mode === 'login' ? '登录后进入 AI 风险研判对话。' : '注册后将自动登录并进入系统。' }}</p>
        </div>

        <div class="mb-6 grid grid-cols-2 rounded-2xl bg-slate-100 p-1">
          <button type="button" class="rounded-xl px-4 py-3 text-sm font-black transition" :class="mode === 'login' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'" @click="switchMode('login')">登录</button>
          <button type="button" class="rounded-xl px-4 py-3 text-sm font-black transition" :class="mode === 'register' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'" @click="switchMode('register')">注册</button>
        </div>

        <form class="space-y-4" @submit.prevent="submit">
          <label class="block space-y-2">
            <span class="text-xs font-black uppercase tracking-widest text-slate-400">用户名</span>
            <input v-model.trim="form.username" required class="focus-ring w-full rounded-2xl border bg-white px-4 py-3 text-sm font-bold text-slate-700" placeholder="请输入用户名" autocomplete="username" />
          </label>

          <label class="block space-y-2">
            <span class="text-xs font-black uppercase tracking-widest text-slate-400">密码</span>
            <input v-model="form.password" required type="password" class="focus-ring w-full rounded-2xl border bg-white px-4 py-3 text-sm font-bold text-slate-700" placeholder="请输入密码" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" />
          </label>

          <template v-if="mode === 'register'">
            <label class="block space-y-2">
              <span class="text-xs font-black uppercase tracking-widest text-slate-400">确认密码</span>
              <input v-model="form.confirmPassword" required type="password" class="focus-ring w-full rounded-2xl border bg-white px-4 py-3 text-sm font-bold text-slate-700" placeholder="请再次输入密码" autocomplete="new-password" />
            </label>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block space-y-2">
                <span class="text-xs font-black uppercase tracking-widest text-slate-400">角色</span>
                <select v-model="form.role" class="focus-ring w-full rounded-2xl border bg-white px-4 py-3 text-sm font-bold text-slate-700">
                  <option value="general">普通用户</option>
                  <option value="student">学生</option>
                </select>
              </label>

              <label class="block space-y-2">
                <span class="text-xs font-black uppercase tracking-widest text-slate-400">昵称</span>
                <input v-model.trim="form.nickname" class="focus-ring w-full rounded-2xl border bg-white px-4 py-3 text-sm font-bold text-slate-700" placeholder="可选" />
              </label>
            </div>
          </template>

          <p v-if="localError || error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ localError || error }}</p>

          <BaseButton type="submit" class="w-full" :disabled="loading">
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            {{ mode === 'login' ? '登录并进入系统' : '注册并进入系统' }}
          </BaseButton>
        </form>
      </BaseCard>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Loader2, Shield } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth.js'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'

const router = useRouter()
const { loading, error, loginWithPassword, registerWithPassword } = useAuth()

const mode = ref('login')
const localError = ref('')
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role: 'general',
  nickname: '',
})

function switchMode(nextMode) {
  mode.value = nextMode
  localError.value = ''
}

async function submit() {
  localError.value = ''

  try {
    if (mode.value === 'login') {
      await loginWithPassword({
        username: form.username,
        password: form.password,
      })
    } else {
      if (form.password !== form.confirmPassword) {
        localError.value = '两次输入的密码不一致'
        return
      }

      await registerWithPassword({
        username: form.username,
        password: form.password,
        role: form.role,
        nickname: form.nickname || null,
      })
    }

    router.push('/chat')
  } catch (_error) {
    // useAuth 已统一写入 error
  }
}
</script>
