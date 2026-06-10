import { ref } from 'vue'
import { resetRiskChat, sendRiskChat } from '../api/chat.js'

const welcomeMessage = {
  id: 'welcome',
  role: 'assistant',
  content: '你好，我是护盾实验室 AI 风险研判助手。你可以把可疑聊天、链接或转账要求发给我，我会结合反诈知识库给出风险判断和劝阻建议。',
}

export function useChat(userRef) {
  const messages = ref([welcomeMessage])
  const latestRisk = ref(null)
  const loading = ref(false)
  const error = ref('')

  function buildPayload(message) {
    const user = userRef?.value || {}
    return {
      user_id: Number(user.user_id) || 0,
      message,
      channel: 'web',
      emotion: 'anxious',
      user_profile: {
        role: user.role || 'general',
        risk_tolerance: 'low',
      },
      context: {},
    }
  }

  async function sendMessage(message) {
    const content = message.trim()
    if (!content || loading.value) {
      return null
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
    }

    messages.value = [...messages.value, userMessage]
    loading.value = true
    error.value = ''

    try {
      const data = await sendRiskChat(buildPayload(content))
      latestRisk.value = data
      messages.value = [
        ...messages.value,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.reply || '已完成风险研判，请查看右侧分析面板。',
        },
      ]
      return data
    } catch (err) {
      error.value = err.message || '风险研判失败'
      messages.value = [
        ...messages.value,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `风险研判失败：${error.value}`,
          tone: 'error',
        },
      ]
      throw err
    } finally {
      loading.value = false
    }
  }

  async function resetChat() {
    const userId = Number(userRef?.value?.user_id) || 0
    let resetFailed = false
    if (userId) {
      try {
        await resetRiskChat(userId)
      } catch (err) {
        error.value = err.message || '服务端对话状态重置失败'
        resetFailed = true
      }
    }
    messages.value = [welcomeMessage]
    latestRisk.value = null
    if (!resetFailed) {
      error.value = ''
    }
  }

  return {
    messages,
    latestRisk,
    loading,
    error,
    sendMessage,
    resetChat,
  }
}
