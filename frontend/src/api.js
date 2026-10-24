import { reactive } from 'vue'
import { isZh } from './i18n.js'

// 可选访问令牌（服务端设置 VIDHARBOR_TOKEN）：浏览器用令牌换取 HttpOnly 会话 Cookie，
// 之后 fetch / SSE / <video> 等同源请求自动携带；任何请求收到 401 时界面弹出令牌输入
export const access = reactive({ denied: false })

async function req(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 401) access.denied = true
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  get: (path) => req(path),
  post: (path, data) => req(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  put: (path, data) => req(path, { method: 'PUT', body: JSON.stringify(data ?? {}) }),
  del: (path) => req(path, { method: 'DELETE' }),

  // 访问令牌会话
  sessionStatus: () => api.get('/api/auth/session'),
  createSession: (token) => api.post('/api/auth/session', { token }),

  // tasks
  createTasks: (urls, options = null) => api.post('/api/tasks', { urls, options }),
  listTasks: (scheduleId = 0) => api.get(`/api/tasks${scheduleId ? `?schedule_id=${scheduleId}` : ''}`),
  cancelTask: (id) => api.del(`/api/tasks/${id}`),
  retryTask: (id) => api.post(`/api/tasks/${id}/retry`),

  // charts（category + period 时间段）
  getCharts: (platform, category, period = '', refresh = false) =>
    api.get(`/api/charts/${platform}?category=${encodeURIComponent(category)}&period=${encodeURIComponent(period)}${refresh ? '&refresh=true' : ''}`),
  chartsMeta: (platform) => api.get(`/api/charts/${platform}?meta=true`),

  // stats & videos & tags
  stats: () => api.get('/api/stats'),
  videos: (params) => api.get('/api/videos?' + new URLSearchParams(params).toString()),
  video: (id) => api.get(`/api/videos/${id}`),
  deleteVideo: (id) => api.del(`/api/videos/${id}?delete_files=true`),
  tags: (params = {}) => api.get('/api/tags?' + new URLSearchParams(params).toString()),

  // settings
  getSettings: () => api.get('/api/settings'),
  putSettings: (patch) => api.put('/api/settings', patch),

  // auth / cookies
  cookiesStatus: () => api.get('/api/auth/cookies'),
  createBiliQR: () => api.post('/api/auth/bilibili/qr'),
  pollBiliQR: (key) => api.get(`/api/auth/bilibili/qr/${key}`),
  uploadCookies: (platform, file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`/api/auth/cookies/${platform}/upload`, { method: 'POST', body: form })
      .then(async (res) => {
        if (res.status === 401) access.denied = true
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || (isZh.value ? '上传失败' : 'Upload failed'))
        return res.json()
      })
  },
  importCookies: (platform, browser, profile = '') =>
    api.post(`/api/auth/cookies/${platform}/import`, { browser, profile }),
  deleteCookies: (platform) => api.del(`/api/auth/cookies/${platform}`),

  // schedules（定时任务）
  listSchedules: () => api.get('/api/schedules'),
  createSchedule: (data) => api.post('/api/schedules', data),
  updateSchedule: (id, data) => api.put(`/api/schedules/${id}`, data),
  deleteSchedule: (id) => api.del(`/api/schedules/${id}`),
  toggleSchedule: (id) => api.post(`/api/schedules/${id}/toggle`),
  runSchedule: (id) => api.post(`/api/schedules/${id}/run`),
}
