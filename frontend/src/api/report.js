import { get, post } from './request.js'

export function submitReport(payload) {
  return post('/report', payload)
}

export function getUserReports(userId, params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value)
    }
  })
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return get(`/users/${encodeURIComponent(userId)}/reports${suffix}`)
}
