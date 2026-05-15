const TOKEN_KEY = 'anti_fraud_token'
const USER_KEY = 'anti_fraud_user'

function getStorage() {
  if (typeof localStorage === 'undefined') {
    return null
  }
  return localStorage
}

export function getToken() {
  return getStorage()?.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  if (token) {
    getStorage()?.setItem(TOKEN_KEY, token)
  }
}

export function clearToken() {
  getStorage()?.removeItem(TOKEN_KEY)
}

export function getStoredUser() {
  const raw = getStorage()?.getItem(USER_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw)
  } catch (_error) {
    clearStoredUser()
    return null
  }
}

export function setStoredUser(user) {
  if (user) {
    getStorage()?.setItem(USER_KEY, JSON.stringify(user))
  }
}

export function clearStoredUser() {
  getStorage()?.removeItem(USER_KEY)
}

export function clearAuthStorage() {
  clearToken()
  clearStoredUser()
}
