import { get, patch, post } from './request.js'

function adminOptions(adminToken) {
  return { headers: { 'X-Admin-Token': adminToken }, preserveAuth: true }
}

export function getRuleOverview(adminToken) {
  return get('/admin/rules/overview', adminOptions(adminToken))
}

export function getRuleHistory(adminToken) {
  return get('/admin/rules/history?limit=30', adminOptions(adminToken))
}

export function updateRule(adminToken, ruleset, ruleName, payload) {
  return patch(`/admin/rules/${ruleset}/${encodeURIComponent(ruleName)}`, payload, adminOptions(adminToken))
}

export function createTextRule(adminToken, payload) {
  return post('/admin/rules/text', payload, adminOptions(adminToken))
}

export function rollbackRuleVersion(adminToken, versionId, payload) {
  return post(`/admin/rules/rollback/${versionId}`, payload, adminOptions(adminToken))
}
