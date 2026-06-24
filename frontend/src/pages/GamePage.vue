<template>
  <div class="page-shell relative space-y-6">
    <div v-if="progress" class="grid gap-4 sm:grid-cols-3">
      <BaseCard padding-class="p-5" class="bg-gradient-to-br from-blue-600 to-sky-500 text-white">
        <p class="text-xs font-black uppercase tracking-widest text-blue-100">闯关进度</p>
        <p class="mt-2 text-3xl font-black">{{ progress.scenarios_completed ?? 0 }} / {{ scenarios.length }}</p>
      </BaseCard>
      <BaseCard padding-class="p-5">
        <p class="text-xs font-black uppercase tracking-widest text-slate-400">成长积分</p>
        <p class="mt-2 text-3xl font-black text-blue-600">{{ progress.points ?? 0 }}</p>
      </BaseCard>
      <BaseCard padding-class="p-5">
        <p class="text-xs font-black uppercase tracking-widest text-slate-400">奖励规则</p>
        <p class="mt-2 text-sm font-black leading-6 text-slate-700">首次通关 +15，复玩仅奖励刷新最佳成绩的增量</p>
      </BaseCard>
    </div>

    <div class="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      <BaseCard padding-class="p-6" class="space-y-5">
        <div>
          <p class="section-kicker">Training</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-slate-950">反诈剧情训练</h1>
          <p class="mt-2 text-sm font-medium leading-6 text-slate-500">关卡来自后端 `/scenarios`。</p>
        </div>

        <BaseButton variant="secondary" :disabled="loading" class="w-full" @click="loadScenarios">
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          刷新关卡
        </BaseButton>

        <p v-if="error" class="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700 ring-1 ring-red-100">{{ error }}</p>
        <div v-if="!loading && !scenarios.length" class="rounded-2xl bg-slate-50 p-4 text-sm font-bold text-slate-400">暂无关卡数据。</div>
        <div class="max-h-[62vh] space-y-3 overflow-y-auto pr-1">
          <ScenarioCard
            v-for="scenario in scenarios"
            :key="scenario.id"
            :scenario="scenario"
            :active="activeScenario?.scenario_id === scenario.id"
            @start="beginScenario"
          />
        </div>
      </BaseCard>

      <ScenarioPlayer :scenario="activeScenario" :loading="loading" @answer="chooseOption" @reset="resetScenario" />
    </div>

    <BaseCard padding-class="p-5" class="border border-slate-200 bg-slate-950 text-white shadow-xl shadow-slate-300/30">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="text-xs font-black uppercase tracking-widest text-cyan-200">Arcade Mode</p>
          <h2 class="mt-1 text-2xl font-black tracking-tight">诈骗拦截大作战</h2>
        </div>
        <div class="flex flex-wrap gap-3">
          <BaseButton variant="secondary" @click="showArcade = true">
            <Gamepad2 class="h-4 w-4" />
            进入街机模式
          </BaseButton>
          <a
            class="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/15 px-4 text-sm font-black text-white transition hover:bg-white/10"
            :href="arcadeGameUrl"
            target="_blank"
            rel="noreferrer"
          >
            独立打开
          </a>
        </div>
      </div>
    </BaseCard>

    <div
        v-if="showArcade"
        class="absolute inset-0 z-30 flex items-start justify-center bg-slate-950/72 p-3 backdrop-blur-md sm:p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="arcade-title"
        @click.self="showArcade = false"
      >
        <div class="sticky top-4 flex h-[min(820px,calc(100vh-2rem))] w-full max-w-7xl flex-col overflow-hidden rounded-2xl bg-slate-950 shadow-2xl shadow-black/40 ring-1 ring-white/10">
          <div class="flex items-center justify-between border-b border-white/10 bg-slate-900 px-5 py-4 text-white">
            <div>
              <p class="text-xs font-black uppercase tracking-widest text-cyan-200">Interceptor</p>
              <h2 id="arcade-title" class="mt-1 text-xl font-black tracking-tight">诈骗拦截大作战</h2>
            </div>
            <button
              type="button"
              class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/15 text-white transition hover:bg-white/10"
              aria-label="关闭街机模式"
              @click="showArcade = false"
            >
              <X class="h-5 w-5" />
            </button>
          </div>
          <div class="min-h-0 flex-1 bg-black">
            <iframe
              :src="arcadeGameUrl"
              title="Anti-fraud arcade game"
              class="h-full w-full border-0"
              allow="autoplay; fullscreen"
              loading="lazy"
            />
          </div>
        </div>
      </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Gamepad2, Loader2, X } from 'lucide-vue-next'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import ScenarioCard from '../components/game/ScenarioCard.vue'
import ScenarioPlayer from '../components/game/ScenarioPlayer.vue'
import { useAuth } from '../composables/useAuth.js'
import { useScenario } from '../composables/useScenario.js'

const { currentUser } = useAuth()
const { scenarios, activeScenario, progress, loading, error, loadScenarios, beginScenario, chooseOption, resetScenario } = useScenario(currentUser)
const arcadeGameUrl = '/godot_game/index.html?v=arcade-20260622'
const showArcade = ref(false)

onMounted(loadScenarios)
</script>
