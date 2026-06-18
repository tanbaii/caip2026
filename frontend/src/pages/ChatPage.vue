<template>
  <div class="page-shell chat-workbench mx-auto flex min-h-0 max-w-[1480px] flex-col gap-4 xl:grid xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
    <ChatPanel
      :messages="messages"
      :loading="loading"
      @send="sendMessage"
      @reset="resetChat"
    />
    <RiskPanel :risk-result="latestRisk" />
  </div>
</template>

<script setup>
import ChatPanel from '../components/chat/ChatPanel.vue'
import RiskPanel from '../components/risk/RiskPanel.vue'
import { useAuth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'

const { currentUser } = useAuth()
const { messages, latestRisk, loading, sendMessage, resetChat } = useChat(currentUser)
</script>
