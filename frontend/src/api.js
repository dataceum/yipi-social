/**
 * Thin fetch wrapper around the FastAPI backend (see backend/app/api/v1).
 *
 * Base URL: '/api/v1' by default, proxied to the backend by Vite's dev
 * server (see vite.config.js) so requests stay same-origin in the browser.
 *
 * Auth: the backend issues a JWT access token (short-lived) plus a refresh
 * token on /auth/login. There is currently no /auth/refresh endpoint in the
 * backend, so once the access token expires the user is signed out and
 * asked to log back in — apiFetch() does this automatically on a 401.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const ACCESS_TOKEN_KEY = 'yipi.access_token'
const REFRESH_TOKEN_KEY = 'yipi.refresh_token'

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },
  set(access, refresh) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

/** Raised for any non-2xx response; carries the parsed error detail + status. */
export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : 'Request failed')
    this.status = status
    this.detail = detail
  }
}

let onUnauthorized = null
/** Registered once by AuthContext so a 401 anywhere logs the user out. */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function apiFetch(path, { method = 'GET', body, params, skipAuth = false } = {}) {
  let url = `${BASE_URL}${path}`
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (qs) url += `?${qs}`
  }

  const headers = { }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!skipAuth && tokenStore.access) headers['Authorization'] = `Bearer ${tokenStore.access}`

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 204) return null

  let payload = null
  const text = await res.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!res.ok) {
    if (res.status === 401 && !skipAuth) {
      tokenStore.clear()
      onUnauthorized?.()
    }
    throw new ApiError(res.status, payload?.detail ?? payload ?? res.statusText)
  }

  return payload
}

/* ------------------------------- Auth ------------------------------- */

export const authApi = {
  signup: (payload) => apiFetch('/auth/signup', { method: 'POST', body: payload, skipAuth: true }),
  login: (payload) => apiFetch('/auth/login', { method: 'POST', body: payload, skipAuth: true }),
  logout: (refresh_token) => apiFetch('/auth/logout', { method: 'POST', body: { refresh_token } }),
}

/* ------------------------------- Users ------------------------------- */

export const usersApi = {
  me: () => apiFetch('/users/me'),
  // query is required for standard users; reviewers (admin/moderator) may
  // instead/also pass profileStatus to list by Profile.status with no
  // search term (the moderation approval queue) — see users.py get_users.
  search: ({ query, profileStatus, page = 1, limit = 20 } = {}) =>
    apiFetch('/users/search', { params: { query, profile_status: profileStatus, page, limit } }),
  get: (userId) => apiFetch(`/users/${userId}`),
  update: (userId, payload) => apiFetch(`/users/${userId}`, { method: 'PATCH', body: payload }),
}

/* ------------------------------- Posts ------------------------------- */

export const postsApi = {
  list: ({ authorId, page = 1, limit = 20 } = {}) =>
    apiFetch('/posts', { params: { author_id: authorId, page, limit } }),
  get: (postId) => apiFetch(`/posts/${postId}`),
  replies: (postId, { page = 1, limit = 20 } = {}) =>
    apiFetch(`/posts/${postId}/replies`, { params: { page, limit } }),
  create: (payload) => apiFetch('/posts', { method: 'POST', body: payload }),
  update: (postId, payload) => apiFetch(`/posts/${postId}`, { method: 'PATCH', body: payload }),
  remove: (postId) => apiFetch(`/posts/${postId}`, { method: 'DELETE' }),
}

/* ------------------------------ Comments ------------------------------ */

export const commentsApi = {
  listForPost: (postId, { page = 1, limit = 20 } = {}) =>
    apiFetch(`/posts/${postId}/comments`, { params: { page, limit } }),
  replies: (commentId, { page = 1, limit = 20 } = {}) =>
    apiFetch(`/comments/${commentId}/replies`, { params: { page, limit } }),
  create: (postId, payload) => apiFetch(`/posts/${postId}/comments`, { method: 'POST', body: payload }),
  update: (commentId, payload) => apiFetch(`/comments/${commentId}`, { method: 'PATCH', body: payload }),
  remove: (commentId) => apiFetch(`/comments/${commentId}`, { method: 'DELETE' }),
}

/* -------------------------------- Likes -------------------------------- */

export const likesApi = {
  likePost: (postId) => apiFetch(`/posts/${postId}/likes`, { method: 'POST', body: {} }),
  unlikePost: (postId) => apiFetch(`/posts/${postId}/likes`, { method: 'DELETE' }),
  likeComment: (commentId) => apiFetch(`/comments/${commentId}/likes`, { method: 'POST', body: {} }),
  unlikeComment: (commentId) => apiFetch(`/comments/${commentId}/likes`, { method: 'DELETE' }),
}

/* -------------------------------- Rooms -------------------------------- */

export const roomsApi = {
  list: ({ roomType, page = 1, limit = 20 } = {}) =>
    apiFetch('/rooms', { params: { room_type: roomType, page, limit } }),
  get: (roomId) => apiFetch(`/rooms/${roomId}`),
  create: (payload) => apiFetch('/rooms', { method: 'POST', body: payload }),
  update: (roomId, payload) => apiFetch(`/rooms/${roomId}`, { method: 'PATCH', body: payload }),
  remove: (roomId) => apiFetch(`/rooms/${roomId}`, { method: 'DELETE' }),
  members: (roomId, { page = 1, limit = 50 } = {}) =>
    apiFetch(`/rooms/${roomId}/members`, { params: { page, limit } }),
  join: (roomId) => apiFetch(`/rooms/${roomId}/members`, { method: 'POST' }),
  leave: (roomId, userId) => apiFetch(`/rooms/${roomId}/members/${userId}`, { method: 'DELETE' }),
  messages: (roomId, { page = 1, limit = 50 } = {}) =>
    apiFetch(`/rooms/${roomId}/messages`, { params: { page, limit } }),
  sendMessage: (roomId, content) =>
    apiFetch(`/rooms/${roomId}/messages`, { method: 'POST', body: { content } }),
}

/* ------------------------------- Reports ------------------------------- */

export const reportsApi = {
  reportPost: (postId, payload) => apiFetch(`/reports/posts/${postId}`, { method: 'POST', body: payload }),
  reportRoom: (roomId, payload) => apiFetch(`/reports/rooms/${roomId}`, { method: 'POST', body: payload }),
  // Admin/Moderator only — the moderation queue.
  list: ({ status, page = 1, limit = 20 } = {}) => apiFetch('/reports', { params: { status, page, limit } }),
  get: (reportId) => apiFetch(`/reports/${reportId}`),
  update: (reportId, payload) => apiFetch(`/reports/${reportId}`, { method: 'PATCH', body: payload }),
}

export { ApiError as default }
