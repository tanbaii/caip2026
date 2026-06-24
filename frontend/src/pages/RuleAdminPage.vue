<template>
  <div class="page-shell space-y-6">
    <section class="relative overflow-hidden rounded-[2rem] bg-slate-950 p-6 text-white shadow-2xl shadow-slate-900/20 md:p-8">
      <div class="absolute -right-20 -top-28 h-72 w-72 rounded-full border border-cyan-300/20 bg-cyan-400/10 blur-2xl"></div>
      <div class="relative grid gap-6 xl:grid-cols-[1fr_420px] xl:items-end">
        <div>
          <p class="text-xs font-black uppercase tracking-[0.28em] text-cyan-300">Risk Control Console</p>
          <h1 class="mt-3 text-4xl font-black tracking-tight md:text-5xl">规则热更新控制台</h1>
          <p class="mt-3 max-w-2xl text-sm font-semibold leading-7 text-slate-300">规则发布前自动校验，发布后立即替换运行时快照。每次启停、调权、新增和回滚都会形成不可变审计记录。</p>
        </div>
        <div class="rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur">
          <label class="text-xs font-black uppercase tracking-widest text-slate-400">管理员令牌</label>
          <div class="mt-2 flex gap-2">
            <input v-model="adminToken" type="password" class="min-w-0 flex-1 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm font-bold text-white placeholder:text-slate-600 focus:border-cyan-400" placeholder="X-Admin-Token" @keyup.enter="connect" />
            <button class="rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-black text-slate-950 transition hover:bg-cyan-200 disabled:opacity-50" :disabled="loading || !adminToken" @click="connect">连接</button>
          </div>
          <p class="mt-2 text-xs font-semibold text-slate-500">令牌仅保存在当前浏览器会话，不写入业务数据库。</p>
        </div>
      </div>
    </section>

    <p v-if="message" class="rounded-2xl px-4 py-3 text-sm font-bold ring-1" :class="messageTone === 'error' ? 'bg-red-50 text-red-700 ring-red-100' : 'bg-emerald-50 text-emerald-700 ring-emerald-100'">{{ message }}</p>

    <template v-if="overview">
      <section class="grid gap-4 md:grid-cols-3">
        <MetricCard label="当前修订" :value="`#${overview.active_revision.id}`" :detail="overview.active_revision.action" tone="cyan" />
        <MetricCard label="文本规则集" :value="overview.ruleset_versions.text" :detail="`${overview.text_rules.length} 条规则`" tone="blue" />
        <MetricCard label="URL 规则集" :value="overview.ruleset_versions.url" :detail="`${overview.url_rules.length} 条规则`" tone="amber" />
      </section>

      <section class="grid gap-6 2xl:grid-cols-[1fr_360px]">
        <div class="space-y-5">
          <div class="soft-card overflow-hidden">
            <div class="flex flex-col gap-4 border-b border-slate-100 p-5 md:flex-row md:items-center md:justify-between">
              <div>
                <p class="section-kicker">Live Rules</p>
                <h2 class="mt-1 text-2xl font-black text-slate-950">在线规则</h2>
              </div>
              <div class="flex rounded-2xl bg-slate-100 p-1">
                <button v-for="tab in tabs" :key="tab.value" class="rounded-xl px-4 py-2 text-sm font-black transition" :class="activeTab === tab.value ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'" @click="activeTab = tab.value">{{ tab.label }}</button>
              </div>
            </div>

            <div class="max-h-[calc(100vh-16rem)] divide-y divide-slate-100 overflow-y-auto">
              <article v-for="rule in visibleRules" :key="`${rule.ruleset}-${rule.name}`" class="grid gap-4 p-5 lg:grid-cols-[1fr_150px_110px] lg:items-center">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <code class="break-all text-sm font-black text-slate-900">{{ rule.name }}</code>
                    <span class="rounded-full px-2.5 py-1 text-[11px] font-black" :class="rule.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'">{{ rule.enabled ? '运行中' : '已停用' }}</span>
                    <span class="text-xs font-bold text-slate-400">v{{ rule.version }}</span>
                  </div>
                  <p class="mt-2 break-words text-sm font-bold text-slate-600">{{ rule.reason }}</p>
                  <p class="mt-1 max-h-24 overflow-y-auto break-words text-xs font-semibold leading-5 text-slate-400">{{ rule.rationale || '暂无解释依据' }}</p>
                  <div v-if="rule.triggers?.length" class="mt-3 max-h-24 overflow-y-auto pr-1">
                    <div class="flex flex-wrap gap-1.5">
                      <span v-for="trigger in rule.triggers.slice(0, 8)" :key="trigger" class="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-500">{{ trigger }}</span>
                    </div>
                  </div>
                </div>
                <label class="block">
                  <span class="text-xs font-black uppercase tracking-widest text-slate-400">权重</span>
                  <div class="mt-2 flex items-center gap-2">
                    <input v-model.number="draftWeights[ruleKey(rule)]" type="number" min="0" max="100" class="w-20 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-black text-slate-900 focus:border-blue-400" />
                    <button class="rounded-xl border border-slate-200 px-3 py-2 text-xs font-black text-slate-600 hover:border-blue-300 hover:text-blue-700" @click="saveWeight(rule)">保存</button>
                  </div>
                </label>
                <button class="rounded-2xl px-4 py-3 text-sm font-black transition" :class="rule.enabled ? 'bg-red-50 text-red-700 hover:bg-red-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'" @click="toggleRule(rule)">{{ rule.enabled ? '停用规则' : '启用规则' }}</button>
              </article>
            </div>
          </div>
        </div>

        <aside class="space-y-5">
          <form class="soft-card p-5" @submit.prevent="addRule">
            <p class="section-kicker">Fast Onboarding</p>
            <h2 class="mt-1 text-xl font-black text-slate-950">新增骗局规则</h2>
            <p class="mt-2 text-xs font-semibold leading-5 text-slate-500">发布后立即进入文本研判链路，无需重启服务。</p>
            <div class="mt-5 space-y-3">
              <input v-model.trim="newRule.name" required pattern="[a-z][a-z0-9_]{2,63}" class="focus-ring w-full rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="规则标识，如 fake_delivery" />
              <input v-model.trim="newRule.triggers" required class="focus-ring w-full rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="触发词，使用逗号分隔" />
              <div class="grid grid-cols-[90px_1fr] gap-3">
                <input v-model.number="newRule.weight" required type="number" min="0" max="100" class="focus-ring rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="权重" />
                <input v-model.trim="newRule.reason" required class="focus-ring min-w-0 rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="命中原因" />
              </div>
              <textarea v-model.trim="newRule.rationale" required rows="3" class="focus-ring w-full resize-none rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="规则依据和解释"></textarea>
              <input v-model.trim="newRule.change_note" required class="focus-ring w-full rounded-2xl border bg-slate-50 px-4 py-3 text-sm font-bold" placeholder="本次变更说明" />
            </div>
            <button class="mt-4 w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-black text-white hover:bg-blue-700 disabled:opacity-50" :disabled="saving">校验并热发布</button>
          </form>

          <section class="soft-card p-5">
            <div class="flex items-center justify-between">
              <div>
                <p class="section-kicker">Audit Trail</p>
                <h2 class="mt-1 text-xl font-black text-slate-950">版本记录</h2>
              </div>
              <button class="text-xs font-black text-blue-600" @click="loadAll">刷新</button>
            </div>
            <div class="mt-4 max-h-[520px] space-y-3 overflow-y-auto pr-1">
              <article v-for="item in history" :key="item.id" class="rounded-2xl border p-4" :class="item.is_active ? 'border-cyan-200 bg-cyan-50/60' : 'border-slate-100 bg-slate-50'">
                <div class="flex items-center justify-between gap-3">
                  <strong class="text-sm text-slate-900">修订 #{{ item.id }}</strong>
                  <span class="text-[11px] font-black uppercase tracking-wider" :class="item.is_active ? 'text-cyan-700' : 'text-slate-400'">{{ item.is_active ? 'ACTIVE' : item.action }}</span>
                </div>
                <p class="mt-2 text-xs font-semibold leading-5 text-slate-600">{{ item.change_summary }}</p>
                <p class="mt-2 text-[11px] font-bold text-slate-400">文本 {{ item.text_version }} · URL {{ item.url_version }} · {{ item.created_at }}</p>
                <button v-if="!item.is_active" class="mt-3 text-xs font-black text-amber-700 hover:text-amber-900" @click="rollback(item)">回滚到此版本</button>
              </article>
            </div>
          </section>
        </aside>
      </section>
    </template>

    <section v-else class="soft-card p-10 text-center">
      <Settings2 class="mx-auto h-10 w-10 text-slate-300" />
      <h2 class="mt-4 text-xl font-black text-slate-900">连接管理接口后查看规则</h2>
      <p class="mt-2 text-sm font-semibold text-slate-500">默认开发令牌由后端 `ANTI_FRAUD_ADMIN_TOKEN` 环境变量控制。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Settings2 } from 'lucide-vue-next'
import { createTextRule, getRuleHistory, getRuleOverview, rollbackRuleVersion, updateRule } from '../api/rules.js'
import { useAdminAuth } from '../composables/useAdminAuth.js'

const admin = useAdminAuth()
const adminToken = admin.adminToken
const overview = ref(null)
const history = ref([])
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const messageTone = ref('success')
const activeTab = ref('text')
const draftWeights = reactive({})
const tabs = [{ value: 'text', label: '文本规则' }, { value: 'url', label: 'URL 规则' }]
const newRule = reactive({ name: '', triggers: '', weight: 20, reason: '', rationale: '', change_note: '新增骗局快速接入' })

const visibleRules = computed(() => activeTab.value === 'text' ? overview.value?.text_rules || [] : overview.value?.url_rules || [])

const MetricCard = {
  props: { label: String, value: String, detail: String, tone: String },
  template: `<article class="soft-card relative overflow-hidden p-5"><div class="absolute right-0 top-0 h-20 w-20 rounded-bl-full opacity-20" :class="tone === 'cyan' ? 'bg-cyan-400' : tone === 'amber' ? 'bg-amber-400' : 'bg-blue-500'"></div><p class="text-xs font-black uppercase tracking-widest text-slate-400">{{ label }}</p><p class="mt-3 text-3xl font-black text-slate-950">{{ value }}</p><p class="mt-1 text-sm font-bold text-slate-500">{{ detail }}</p></article>`,
}

function ruleKey(rule) { return `${rule.ruleset}:${rule.name}` }
function syncDrafts() { for (const rule of [...overview.value.text_rules, ...overview.value.url_rules]) draftWeights[ruleKey(rule)] = rule.weight }
function notify(text, tone = 'success') { message.value = text; messageTone.value = tone }

async function loadAll() {
  loading.value = true
  try {
    const [overviewData, historyData] = await Promise.all([getRuleOverview(adminToken.value), getRuleHistory(adminToken.value)])
    overview.value = overviewData
    history.value = historyData
    syncDrafts()
  } catch (error) {
    if (error.status === 401) {
      admin.clearAdminAccess()
    }
    overview.value = null
    notify(error.message || '规则管理接口连接失败', 'error')
  } finally { loading.value = false }
}

async function connect() {
  admin.setAdminToken(adminToken.value)
  await loadAll()
  if (overview.value) notify('管理接口已连接，规则状态为实时数据')
}

async function applyChange(rule, payload, successText) {
  saving.value = true
  try {
    overview.value = await updateRule(adminToken.value, rule.ruleset, rule.name, { ...payload, change_note: successText })
    syncDrafts()
    history.value = await getRuleHistory(adminToken.value)
    notify(`${successText}，已热加载生效`)
  } catch (error) { notify(error.message || '规则更新失败', 'error') } finally { saving.value = false }
}

function toggleRule(rule) { applyChange(rule, { enabled: !rule.enabled }, `${rule.enabled ? '停用' : '启用'}规则 ${rule.name}`) }
function saveWeight(rule) { applyChange(rule, { weight: Number(draftWeights[ruleKey(rule)]) }, `调整规则 ${rule.name} 权重`) }

async function addRule() {
  saving.value = true
  try {
    overview.value = await createTextRule(adminToken.value, {
      name: newRule.name,
      triggers: newRule.triggers.split(/[，,]/).map((item) => item.trim()).filter(Boolean),
      weight: Number(newRule.weight), reason: newRule.reason, rationale: newRule.rationale,
      version: '1.0', enabled: true, change_note: newRule.change_note,
    })
    Object.assign(newRule, { name: '', triggers: '', weight: 20, reason: '', rationale: '', change_note: '新增骗局快速接入' })
    syncDrafts()
    history.value = await getRuleHistory(adminToken.value)
    activeTab.value = 'text'
    notify('新骗局规则已校验并热加载，无需重启')
  } catch (error) { notify(error.message || '新增规则失败', 'error') } finally { saving.value = false }
}

async function rollback(item) {
  if (!window.confirm(`确认回滚到修订 #${item.id}？当前配置会作为新修订保留。`)) return
  saving.value = true
  try {
    overview.value = await rollbackRuleVersion(adminToken.value, item.id, { change_note: `管理端回滚到修订 #${item.id}` })
    syncDrafts()
    history.value = await getRuleHistory(adminToken.value)
    notify(`已回滚到修订 #${item.id}，运行时配置同步完成`)
  } catch (error) { notify(error.message || '回滚失败', 'error') } finally { saving.value = false }
}
</script>
