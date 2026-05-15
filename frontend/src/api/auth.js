import { get, post } from './request.js'

export function login(payload) {
  return post('/auth/login', payload)
}

export function register(payload) {
  return post('/auth/register', payload)
}

export function getCurrentUser() {
  return get('/auth/me')
}
