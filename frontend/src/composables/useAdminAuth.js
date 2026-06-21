import { computed, ref } from 'vue'
import { getDashboardSummary } from '../api/dashboard.js'

const TOKEN_KEY = 'anti_fraud_admin_token'
const VERIFIED_KEY = 'anti_fraud_admin_verified'

function session() {
  return typeof sessionStorage === 'undefined' ? null : sessionStorage
}

const adminToken = ref(session()?.getItem(TOKEN_KEY) || '')
const adminVerified = ref(Boolean(adminToken.value && session()?.getItem(VERIFIED_KEY) === '1'))
const loading = ref(false)
const error = ref('')

export function hasAdminAccess() {
  return Boolean(adminToken.value && adminVerified.value)
}

export function useAdminAuth() {
  const isAdminVerified = computed(hasAdminAccess)

  async function verifyAdminToken(token) {
    const normalized = String(token || '').trim()
    if (!normalized) {
      throw new Error('请输入管理员令牌')
    }

    loading.value = true
    error.value = ''
    try {
      await getDashboardSummary(normalized)
      adminToken.value = normalized
      adminVerified.value = true
      session()?.setItem(TOKEN_KEY, normalized)
      session()?.setItem(VERIFIED_KEY, '1')
      return true
    } catch (err) {
      clearAdminAccess()
      error.value = err.message || '管理员令牌校验失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  function clearAdminAccess() {
    adminToken.value = ''
    adminVerified.value = false
    session()?.removeItem(TOKEN_KEY)
    session()?.removeItem(VERIFIED_KEY)
  }

  function setAdminToken(token) {
    adminToken.value = String(token || '').trim()
    if (adminToken.value) {
      session()?.setItem(TOKEN_KEY, adminToken.value)
    }
  }

  return {
    adminToken,
    loading,
    error,
    isAdminVerified,
    verifyAdminToken,
    clearAdminAccess,
    setAdminToken,
  }
}
