<template>
  <div class="page-shell chat-workbench mx-auto flex min-h-0 max-w-[1680px] flex-col gap-4 xl:grid xl:grid-cols-[280px_minmax(0,1fr)_360px] xl:items-start">
    <ChatHistoryPanel
      :items="conversations"
      :total="conversationTotal"
      :selected-id="activeConversationId"
      :loading="historyLoading"
      @new-conversation="startNewConversation"
      @select="openConversation"
      @delete="deleteConversation"
    />
    <ChatPanel
      :messages="messages"
      :loading="loading"
      :viewing-history="viewingConversation"
      @send="sendMessage"
    />
    <RiskPanel :risk-result="latestRisk" @request-report="goToReport" />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import ChatHistoryPanel from '../components/chat/ChatHistoryPanel.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import RiskPanel from '../components/risk/RiskPanel.vue'
import { useAuth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'

const { currentUser } = useAuth()
const router = useRouter()
const {
  messages,
  latestRisk,
  conversations,
  conversationTotal,
  activeConversationId,
  viewingConversation,
  loading,
  historyLoading,
  sendMessage,
  startNewConversation,
  openConversation,
  deleteConversation,
} = useChat(currentUser)

function goToReport(prefill) {
  router.push({
    path: '/report',
    query: {
      content: prefill?.content || '',
      url: prefill?.url || '',
      source: 'chat',
    },
  })
}
</script>
