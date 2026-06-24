import { get, patch } from './request.js'

function adminOptions(adminToken) {
  return { headers: { 'X-Admin-Token': adminToken }, preserveAuth: true }
}

export function getDashboardSummary(adminToken) {
  return get('/admin/dashboard/summary', adminOptions(adminToken))
}

export function reviewReport(adminToken, reportId, payload) {
  return patch(`/admin/reports/${encodeURIComponent(reportId)}/review`, payload, adminOptions(adminToken))
}
