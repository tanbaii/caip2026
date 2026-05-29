import { ref } from 'vue'
import { answerScenario, getScenarios, startScenario } from '../api/scenario.js'

export function useScenario(userRef) {
  const scenarios = ref([])
  const activeScenario = ref(null)
  const latestFeedback = ref(null)
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
      return scenarios.value
    } catch (err) {
      error.value = err.message || '关卡加载失败'
      scenarios.value = []
      throw err
    } finally {
      loading.value = false
    }
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
        step_index: data.step_index,
        prompt: data.next_prompt || activeScenario.value.prompt,
        options: Array.isArray(data.next_options) ? data.next_options : [],
        finished: Boolean(data.finished),
        feedback: data.feedback || '',
        points_gained: Number(data.points_gained) || 0,
        total_points: Number(data.total_points) || 0,
        badges: Array.isArray(data.badges) ? data.badges : [],
        case_summary: data.case_summary || activeScenario.value.case_summary || null,
        debrief: Array.isArray(data.debrief) && data.debrief.length ? data.debrief : (activeScenario.value.debrief || []),
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
    loading,
    error,
    loadScenarios,
    beginScenario,
    chooseOption,
    resetScenario,
  }
}
