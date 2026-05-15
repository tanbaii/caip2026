<template>
  <div class="flex min-h-screen flex-col gap-6 p-6 xl:flex-row">
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
