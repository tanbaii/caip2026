<template>
  <div class="page-shell flex flex-col gap-6 xl:grid xl:grid-cols-[minmax(0,1fr)_400px] xl:items-start">
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
