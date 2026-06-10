import { post } from './request.js'

export function sendRiskChat(payload) {
  return post('/chat', payload)
}

export function resetRiskChat(userId) {
  return post('/chat/reset', { user_id: Number(userId) })
}

export function sendAiChat(payload) {
  return post('/ai/chat', payload)
}
