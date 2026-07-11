export function saveAuth(data) {
  localStorage.setItem('token', data.token || '')
  localStorage.setItem('user', JSON.stringify({
    username: data.username,
    role: data.role,
    id: data.id,
  }))
}

export function getUser() {
  try { return JSON.parse(localStorage.getItem('user') || 'null') }
  catch { return null }
}

export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function isLoggedIn() {
  return !!localStorage.getItem('token')
}
