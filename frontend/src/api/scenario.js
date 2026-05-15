import { get, post } from './request.js'

export function getScenarios() {
  return get('/scenarios')
}

export function startScenario(payload) {
  return post('/scenarios/start', payload)
}

export function answerScenario(payload) {
  return post('/scenarios/answer', payload)
}
