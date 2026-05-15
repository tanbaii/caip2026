import { computed, ref } from 'vue'
import { getCurrentUser, login, register } from '../api/auth.js'
import { clearAuthStorage, getStoredUser, getToken, setStoredUser, setToken } from '../utils/storage.js'

const currentUser = ref(getStoredUser())
const loading = ref(false)
const error = ref('')
const initialized = ref(false)

function normalizeAuthUser(data) {
  return {
    user_id: data.user_id || data.id,
    username: data.username,
    role: data.role,
    nickname: data.nickname || '',
    token: data.access_token || getToken(),
  }
}

export function useAuth() {
  const isAuthenticated = computed(() => Boolean(getToken() && currentUser.value?.user_id))

  async function initAuth() {
    if (initialized.value) {
      return currentUser.value
    }

    const token = getToken()
    if (!token) {
      initialized.value = true
      currentUser.value = null
      return null
    }

    loading.value = true
    error.value = ''

    try {
      const user = await getCurrentUser()
      currentUser.value = normalizeAuthUser(user)
      setStoredUser(currentUser.value)
      return currentUser.value
    } catch (err) {
      if (err.status === 401) {
        clearAuthStorage()
        currentUser.value = null
        error.value = err.message || '登录状态已失效'
        return null
      }

      const storedUser = getStoredUser()
      if (storedUser?.user_id) {
        currentUser.value = storedUser
        error.value = err.message || '当前用户校验暂时失败，已使用本地登录态'
        return currentUser.value
      }

      currentUser.value = null
      error.value = err.message || '登录状态校验失败'
      return null
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function loginWithPassword(payload) {
    loading.value = true
    error.value = ''

    try {
      const data = await login(payload)
      setToken(data.access_token)
      currentUser.value = normalizeAuthUser(data)
      setStoredUser(currentUser.value)
      initialized.value = true
      return currentUser.value
    } catch (err) {
      error.value = err.message || '登录失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function registerWithPassword(payload) {
    loading.value = true
    error.value = ''

    try {
      const data = await register(payload)
      setToken(data.access_token)
      currentUser.value = normalizeAuthUser(data)
      setStoredUser(currentUser.value)
      initialized.value = true
      return currentUser.value
    } catch (err) {
      error.value = err.message || '注册失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearAuthStorage()
    currentUser.value = null
    initialized.value = true
  }

  return {
    currentUser,
    loading,
    error,
    initialized,
    isAuthenticated,
    initAuth,
    loginWithPassword,
    registerWithPassword,
    logout,
  }
}
