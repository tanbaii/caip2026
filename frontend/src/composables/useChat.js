import { ref, watch } from 'vue'
import {
  createRiskChatConversation,
  deleteRiskChatConversation,
  getRiskChatConversationMessages,
  getRiskChatConversations,
  sendRiskChat,
} from '../api/chat.js'

const welcomeMessage = {
  id: 'welcome',
  role: 'assistant',
  content: '你好，我是护盾实验室 AI 风险研判助手。你可以把可疑聊天、链接或转账要求发给我，我会结合反诈知识库给出风险判断和劝阻建议。',
}

export function useChat(userRef) {
  const messages = ref([welcomeMessage])
  const latestRisk = ref(null)
  const conversations = ref([])
  const conversationTotal = ref(0)
  const activeConversationId = ref(null)
  const viewingConversation = ref(false)
  const loading = ref(false)
  const historyLoading = ref(false)
  const error = ref('')

  function buildPayload(message) {
    const user = userRef?.value || {}
    return {
      user_id: Number(user.user_id) || 0,
      conversation_id: activeConversationId.value,
      message,
      channel: 'web',
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

    if (!activeConversationId.value) {
      await startNewConversation({ refreshHistory: false })
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
    }

    messages.value = [...messages.value, userMessage]
    viewingConversation.value = false
    loading.value = true
    error.value = ''

    try {
      const data = await sendRiskChat(buildPayload(content))
      activeConversationId.value = data.conversation_id || activeConversationId.value
      latestRisk.value = data
      messages.value = [
        ...messages.value,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.reply || '已完成风险研判，请查看右侧分析面板。',
        },
      ]
      await loadConversations()
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

  async function startNewConversation(options = {}) {
    const { refreshHistory = true } = options
    const userId = Number(userRef?.value?.user_id) || 0
    if (userId) {
      try {
        const data = await createRiskChatConversation(userId)
        activeConversationId.value = data.conversation_id
      } catch (err) {
        error.value = err.message || '新对话初始化失败'
        activeConversationId.value = null
      }
    } else {
      activeConversationId.value = null
    }
    messages.value = [welcomeMessage]
    latestRisk.value = null
    viewingConversation.value = false
    if (activeConversationId.value || !userId) {
      error.value = ''
    }
    if (refreshHistory) {
      await loadConversations()
    }
  }

  function mapHistoryItem(item) {
    return [
      {
        id: `history-user-${item.id}`,
        role: 'user',
        content: item.user_message,
      },
      {
        id: `history-assistant-${item.id}`,
        role: 'assistant',
        content: item.assistant_reply,
      },
    ]
  }

  function riskFromHistoryItem(item) {
    return {
      risk_level: item.risk_level,
      risk_score: item.risk_score,
      intent: item.intent,
      matched_scams: item.matched_scams || [],
      session_stage: item.session_stage,
    }
  }

  async function openConversation(item) {
    const userId = Number(userRef?.value?.user_id) || 0
    const conversationId = item?.conversation_id
    if (!userId || !conversationId) {
      return
    }
    historyLoading.value = true
    error.value = ''
    try {
      const data = await getRiskChatConversationMessages(userId, conversationId)
      const historyMessages = (data.messages || []).flatMap(mapHistoryItem)
      const latest = (data.messages || []).at(-1)
      activeConversationId.value = conversationId
      viewingConversation.value = true
      messages.value = historyMessages.length ? [welcomeMessage, ...historyMessages] : [welcomeMessage]
      latestRisk.value = latest ? riskFromHistoryItem(latest) : null
    } catch (err) {
      error.value = err.message || '对话加载失败'
    } finally {
      historyLoading.value = false
    }
  }

  async function loadConversations() {
    const userId = Number(userRef?.value?.user_id) || 0
    if (!userId || historyLoading.value) {
      return
    }
    historyLoading.value = true
    try {
      const data = await getRiskChatConversations(userId, 50)
      const items = data.items || []
      conversations.value = items
      conversationTotal.value = Number(data.total) || items.length
    } catch (err) {
      error.value = err.message || '对话历史加载失败'
    } finally {
      historyLoading.value = false
    }
  }

  async function deleteConversation(item) {
    const userId = Number(userRef?.value?.user_id) || 0
    const conversationId = item?.conversation_id
    if (!userId || !conversationId) {
      return
    }

    const title = item.title || item.preview || '这条历史对话'
    const confirmed = typeof window === 'undefined'
      ? true
      : window.confirm(`确定删除「${title}」吗？删除后无法恢复。`)
    if (!confirmed) {
      return
    }

    error.value = ''
    try {
      await deleteRiskChatConversation(userId, conversationId)
      if (activeConversationId.value === conversationId) {
        await startNewConversation({ refreshHistory: false })
      }
      await loadConversations()
    } catch (err) {
      error.value = err.message || '删除对话失败'
    } finally {
      historyLoading.value = false
    }
  }

  watch(
    () => userRef?.value?.user_id,
    async () => {
      await startNewConversation()
    },
    { immediate: true },
  )

  return {
    messages,
    latestRisk,
    conversations,
    conversationTotal,
    activeConversationId,
    viewingConversation,
    loading,
    historyLoading,
    error,
    sendMessage,
    startNewConversation,
    openConversation,
    deleteConversation,
    loadConversations,
  }
}
