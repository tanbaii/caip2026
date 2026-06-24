import { get, post, request } from './request.js'

export function sendRiskChat(payload) {
  return post('/chat', payload)
}

export function createRiskChatConversation(userId) {
  return post(`/users/${encodeURIComponent(userId)}/chat/conversations`)
}

export function getRiskChatConversations(userId, limit = 50) {
  return get(`/users/${encodeURIComponent(userId)}/chat/conversations?limit=${encodeURIComponent(limit)}`)
}

export function getRiskChatConversationMessages(userId, conversationId) {
  return get(
    `/users/${encodeURIComponent(userId)}/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
  )
}

export function deleteRiskChatConversation(userId, conversationId) {
  return request(
    `/users/${encodeURIComponent(userId)}/chat/conversations/${encodeURIComponent(conversationId)}`,
    { method: 'DELETE' },
  )
}

export function getRiskChatHistory(userId, limit = 50) {
  return get(`/users/${encodeURIComponent(userId)}/chat/history?limit=${encodeURIComponent(limit)}`)
}

export function sendAiChat(payload) {
  return post('/ai/chat', payload)
}
