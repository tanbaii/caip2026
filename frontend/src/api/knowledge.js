import { get } from './request.js'

export function getScams() {
  return get('/knowledge/scams')
}

export function getLaws() {
  return get('/knowledge/laws')
}

export function getPlaybooks() {
  return get('/knowledge/playbooks')
}

export function getFaqs() {
  return get('/knowledge/faqs')
}

export function getKnowledgeQuality() {
  return get('/knowledge/quality')
}
