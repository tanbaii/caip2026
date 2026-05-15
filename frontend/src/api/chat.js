import { post } from './request.js'

export function sendRiskChat(payload) {
  return post('/chat', payload)
}

export function sendAiChat(payload) {
  return post('/ai/chat', payload)
}
