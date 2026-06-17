import { clearAuthStorage, getToken } from '../utils/storage.js'

const defaultBaseUrl = ''

function getBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || defaultBaseUrl
}

function buildUrl(path) {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  const baseUrl = getBaseUrl().replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${baseUrl}${normalizedPath}`
}

async function parseResponse(response) {
  const contentType = response.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

function getErrorMessage(body) {
  if (typeof body === 'string') {
    return body || '请求失败'
  }

  if (body?.detail) {
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg || JSON.stringify(item)).join('；')
    }
    return String(body.detail)
  }

  if (body?.message) {
    return String(body.message)
  }

  return '请求失败'
}

export async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    Accept: 'application/json',
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
  })

  const body = await parseResponse(response)

  if (!response.ok) {
    if (response.status === 401 && !options.preserveAuth) {
      clearAuthStorage()
    }

    const error = new Error(`${response.status} ${getErrorMessage(body)}`)
    error.status = response.status
    error.body = body
    throw error
  }

  return body
}

export function get(path, options = {}) {
  return request(path, {
    ...options,
    method: 'GET',
  })
}

export function post(path, body, options = {}) {
  return request(path, {
    ...options,
    method: 'POST',
    body: JSON.stringify(body || {}),
  })
}

export function patch(path, body, options = {}) {
  return request(path, {
    ...options,
    method: 'PATCH',
    body: JSON.stringify(body || {}),
  })
}
