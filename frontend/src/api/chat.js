import { get, post } from './request.js'

export function sendRiskChat(payload) {
  return post('/chat', payload)
}

export function resetRiskChat(userId) {
  return post('/chat/reset', { user_id: Number(userId) })
}

export function getRiskChatHistory(userId, limit = 50) {
  return get(`/users/${encodeURIComponent(userId)}/chat/history?limit=${encodeURIComponent(limit)}`)
}

export function sendAiChat(payload) {
  return post('/ai/chat', payload)
}
