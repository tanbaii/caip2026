import { get } from './request.js'

function adminOptions(adminToken) {
  return { headers: { 'X-Admin-Token': adminToken }, preserveAuth: true }
}

export function getDashboardSummary(adminToken) {
  return get('/admin/dashboard/summary', adminOptions(adminToken))
}
