// Points to Render backend in production, proxied locally via vite.config.js
const BASE = import.meta.env.VITE_API_URL || ''

function getToken() {
  return localStorage.getItem('token') || ''
}

async function req(method, path, body, isForm = false) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!isForm && body) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  })

  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || data.detail || `HTTP ${res.status}`)
  return data
}

export const api = {
  // Auth
  login:    (body) => req('POST', '/api/auth/login', body),
  register: (body) => req('POST', '/api/auth/register', body),
  me:       ()     => req('GET',  '/api/me'),

  // Assignments
  assignments: ()   => req('GET', '/api/assignments'),
  assignment:  (id) => req('GET', `/api/assignment/${id}`),

  // Submit
  submit: (formData) => req('POST', '/api/submit', formData, true),

  // Evaluation
  evaluation: (id) => req('GET', `/api/evaluation/${id}`),
  report:     (id) => req('GET', `/api/report/${id}`),

  // Leaderboard
  leaderboard: (id) => req('GET', `/api/leaderboard/${id}`),

  // Health
  health: () => req('GET', '/api/health'),
}
