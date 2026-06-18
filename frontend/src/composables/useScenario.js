import { ref } from 'vue'
import { answerScenario, getScenarios, startScenario } from '../api/scenario.js'
import { getUserProgress } from '../api/leaderboard.js'

export function useScenario(userRef) {
  const scenarios = ref([])
  const activeScenario = ref(null)
  const latestFeedback = ref(null)
  const progress = ref(null)
  const loading = ref(false)
  const error = ref('')

  function getUserId() {
    return Number(userRef?.value?.user_id) || 0
  }

  async function loadScenarios() {
    loading.value = true
    error.value = ''

    try {
      const data = await getScenarios()
      scenarios.value = Array.isArray(data) ? data : []
      await loadProgress()
      return scenarios.value
    } catch (err) {
      error.value = err.message || '关卡加载失败'
      scenarios.value = []
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadProgress() {
    const userId = getUserId()
    if (!userId) {
      progress.value = null
      return null
    }

    progress.value = await getUserProgress(userId)
    const records = new Map(
      (Array.isArray(progress.value?.scenario_progress) ? progress.value.scenario_progress : [])
        .map(item => [item.scenario_id, item]),
    )
    scenarios.value = scenarios.value.map(item => ({
      ...item,
      progress: records.get(item.id) || null,
    }))
    return progress.value
  }

  async function beginScenario(scenarioId) {
    const userId = getUserId()
    if (!userId) {
      error.value = '请先登录后再开始闯关'
      return null
    }

    loading.value = true
    error.value = ''
    latestFeedback.value = null

    try {
      const data = await startScenario({ user_id: userId, scenario_id: scenarioId })
      activeScenario.value = {
        ...data,
        finished: false,
        feedback: '',
        points_gained: 0,
        total_points: 0,
        badges: [],
        new_badges: [],
        run_score: 0,
      }
      return activeScenario.value
    } catch (err) {
      error.value = err.message || '开始关卡失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function chooseOption(optionIndex) {
    const userId = getUserId()
    if (!userId || !activeScenario.value) {
      error.value = '请先选择并开始一个关卡'
      return null
    }

    loading.value = true
    error.value = ''

    try {
      const data = await answerScenario({ user_id: userId, option_index: optionIndex })
      latestFeedback.value = data
      activeScenario.value = {
        ...activeScenario.value,
        scenario_id: data.scenario_id,
        step_index: data.finished ? data.step_index : data.step_index + 1,
        total_steps: Number(data.total_steps) || activeScenario.value.total_steps || 1,
        prompt: data.next_prompt || activeScenario.value.prompt,
        options: Array.isArray(data.next_options) ? data.next_options : [],
        finished: Boolean(data.finished),
        feedback: data.feedback || '',
        points_gained: Number(data.points_gained) || 0,
        total_points: Number(data.total_points) || 0,
        badges: Array.isArray(data.badges) ? data.badges : [],
        new_badges: Array.isArray(data.new_badges) ? data.new_badges : [],
        run_score: Number(data.run_score) || 0,
        max_score: Number(data.max_score) || activeScenario.value.max_score || 0,
        score_percent: Number(data.score_percent) || 0,
        best_score: Number(data.best_score) || 0,
        first_clear: Boolean(data.first_clear),
        score_improvement: Number(data.score_improvement) || 0,
        attempts: Number(data.attempts) || activeScenario.value.attempts || 0,
        completions: Number(data.completions) || 0,
        case_summary: data.case_summary || activeScenario.value.case_summary || null,
        debrief: Array.isArray(data.debrief) && data.debrief.length ? data.debrief : (activeScenario.value.debrief || []),
      }
      if (data.finished) {
        await loadProgress()
      }
      return activeScenario.value
    } catch (err) {
      error.value = err.message || '提交答案失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  function resetScenario() {
    activeScenario.value = null
    latestFeedback.value = null
    error.value = ''
  }

  return {
    scenarios,
    activeScenario,
    latestFeedback,
    progress,
    loading,
    error,
    loadScenarios,
    loadProgress,
    beginScenario,
    chooseOption,
    resetScenario,
  }
}
