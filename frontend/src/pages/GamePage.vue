<template>
  <div class="page-shell">
    <div class="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      <BaseCard padding-class="p-6" class="space-y-5">
        <div>
          <p class="section-kicker">Training</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-slate-950">反诈闯关</h1>
          <p class="mt-2 text-sm font-medium leading-6 text-slate-500">关卡来自真实后端 `/scenarios`，选择后开始剧情训练。</p>
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
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import BaseButton from '../components/common/BaseButton.vue'
import BaseCard from '../components/common/BaseCard.vue'
import ScenarioCard from '../components/game/ScenarioCard.vue'
import ScenarioPlayer from '../components/game/ScenarioPlayer.vue'
import { useAuth } from '../composables/useAuth.js'
import { useScenario } from '../composables/useScenario.js'

const { currentUser } = useAuth()
const { scenarios, activeScenario, loading, error, loadScenarios, beginScenario, chooseOption, resetScenario } = useScenario(currentUser)

onMounted(loadScenarios)
</script>
