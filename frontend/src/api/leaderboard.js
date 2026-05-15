import { get } from './request.js'

export function getLeaderboard(top = 20) {
  return get(`/leaderboard?top=${encodeURIComponent(top)}`)
}

export function getUserProgress(userId) {
  return get(`/users/${encodeURIComponent(userId)}/progress`)
}
