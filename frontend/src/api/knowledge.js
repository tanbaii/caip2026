import { get } from './request.js'

export function getScams() {
  return get('/knowledge/scams')
}

export function getLaws() {
  return get('/knowledge/laws')
}
